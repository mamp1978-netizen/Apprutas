# tab_profesional.py
import requests
import streamlit as st
from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
    set_location_bias,
)

# =========================
# Estado inicial
# =========================
def _init_state():
    ss = st.session_state
    ss.setdefault("prof_points", [])
    ss.setdefault("prof_last_route_url", None)
    ss.setdefault("prof_route_type", "Más rápido")
    ss.setdefault("prof_q", "")                 # texto actual del buscador
    ss.setdefault("prof_sel_idx", None)         # índice seleccionado en el selectbox
    ss.setdefault("_prof_last_labels", [])      # copia de las últimas etiquetas mostradas

# =========================
# Sesgo de ubicación (IP)
# =========================
def _use_ip_bias():
    """Intenta fijar un sesgo de ubicación basado en IP (≈50 km)."""
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        lat = ip.get("latitude")
        lng = ip.get("longitude")
        if lat and lng:
            set_location_bias(float(lat), float(lng), radius_m=50000)
            return True
    except Exception:
        pass
    return False

# =========================
# UI: Buscador + sugerencias
# =========================
def _search_box():
    # entrada de texto
    q = st.text_input(
        "Buscar dirección… (presione ENTER para agregar)",
        key="prof_q",
        placeholder="Calle, número, ciudad… / Street, number, city…",
    )

    # sugerencias (a partir de 2 letras; puedes bajar a 1 si quieres)
    labels = suggest_addresses(q, "prof_top") if q and len(q) >= 2 else []
    st.session_state["_prof_last_labels"] = labels

    if labels:
        st.caption("Sugerencias:")
        idx = st.selectbox(
            "Elige una sugerencia",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            key="prof_sel_idx",
        )
    else:
        st.caption("Sin sugerencias todavía")

    c1, c2, c3 = st.columns([0.28, 0.28, 0.44])

    with c1:
        if st.button("Añadir (ENTER)", type="primary", key="prof_add_btn"):
            _add_point_from_ui()

    with c2:
        if st.button("Limpiar", key="prof_clear_btn"):
            st.session_state["prof_q"] = ""
            st.session_state["prof_sel_idx"] = None
            st.rerun()

    with c3:
        if st.button("📍 Usar mi ubicación", key="prof_loc_btn"):
            ok = _use_ip_bias()
            if ok:
                st.success("Sesgo de ubicación fijado ✅ (cerca de tu IP).")
            else:
                st.warning("No se pudo obtener tu ubicación aproximada.")

# =========================
# Añadir punto usando texto/selección
# =========================
def _add_point_from_ui():
    labels = st.session_state.get("_prof_last_labels") or []
    sel = st.session_state.get("prof_sel_idx")
    q = (st.session_state.get("prof_q") or "").strip()

    if labels and sel is not None and 0 <= sel < len(labels):
        value = labels[sel]
    else:
        value = q

    if not value:
        st.warning("Escribe o selecciona una dirección.")
        return

    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")

# =========================
# Mover / borrar puntos
# =========================
def _move_point(i: int, direction: str):
    pts = st.session_state["prof_points"]
    if direction == "up" and i > 0:
        pts[i-1], pts[i] = pts[i], pts[i-1]
        st.rerun()
    elif direction == "down" and i < len(pts) - 1:
        pts[i+1], pts[i] = pts[i], pts[i+1]
        st.rerun()

def _delete_point(i: int):
    pts = st.session_state["prof_points"]
    if 0 <= i < len(pts):
        removed = pts.pop(i)
        st.info(f"Eliminado: {removed}")
        st.rerun()

# =========================
# Preferencias de ruta
# =========================
def _route_prefs():
    opts = ["Más rápido", "Más corto", "Evitar autopistas", "Evitar peajes"]
    curr = st.session_state.get("prof_route_type", "Más rápido")
    idx = opts.index(curr) if curr in opts else 0
    choice = st.selectbox("Tipo de ruta", opts, index=idx)
    st.session_state["prof_route_type"] = choice
    mode = "driving"
    avoid = []
    if choice in ("Más corto", "Shortest"):
        avoid = ["tolls", "highways"]
    elif choice in ("Evitar autopistas", "Avoid highways"):
        avoid = ["highways"]
    elif choice in ("Evitar peajes", "Avoid tolls"):
        avoid = ["tolls"]
    elif choice in ("Ruta panorámica", "Scenic route"):
        mode = "bicycling"
    return mode, avoid, choice

# =========================
# Render principal
# =========================
def mostrar_profesional(t: dict):
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption(
        "Añade puntos con la barra de arriba. El **primero** es **origen**, el **último** es **destino**; "
        "los demás son **paradas intermedias**. Puedes reordenar con las flechas y eliminar cualquier punto."
    )

    # Preferencias de ruta
    mode, avoid, pref_name = _route_prefs()

    st.divider()

    # Buscador con autocompletado
    _search_box()

    st.divider()

    # Lista de puntos
    st.markdown("### Puntos de la ruta (orden de viaje)")
    pts = st.session_state["prof_points"]
    if not pts:
        st.info("Agrega al menos dos puntos (origen y destino) para generar la ruta.")
        return

    for i, p in enumerate(pts):
        prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}:")
        c_lbl, c_up, c_down, c_del = st.columns([0.74, 0.09, 0.09, 0.08])
        with c_lbl:
            st.write(f"**{prefix}**: {p}")
        with c_up:
            st.button("↑", key=f"up_{i}", on_click=_move_point, args=(i, "up"), disabled=(i == 0), use_container_width=True)
        with c_down:
            st.button("↓", key=f"down_{i}", on_click=_move_point, args=(i, "down"), disabled=(i == len(pts)-1), use_container_width=True)
        with c_del:
            st.button("🗑", key=f"del_{i}", on_click=_delete_point, args=(i,), use_container_width=True)

    # Botón de generar
    if st.button("Generar ruta profesional", type="primary"):
        if len(pts) < 2:
            st.error("Debes tener **origen** y **destino**.")
            return

        # Resolver texto/labels a direcciones definitivas (mantiene número si Google lo devuelve)
        o = resolve_selection(pts[0], "prof_point_0")
        d = resolve_selection(pts[-1], f"prof_point_{len(pts)-1}")
        waypoints = []
        for i, label in enumerate(pts[1:-1], start=1):
            det = resolve_selection(label, f"prof_point_{i}")
            waypoints.append(det["address"])

        url = build_gmaps_url(
            origin=o["address"],
            destination=d["address"],
            waypoints=waypoints if waypoints else None,
            mode=mode,
            avoid=avoid,
            optimize=True,
        )
        st.session_state["prof_last_route_url"] = url
        st.success(f"Ruta generada ({pref_name}) ✅")
        st.write(url)
        st.image(make_qr(url), caption="Escanea el QR para abrir la ruta")

    # Última ruta
    if st.session_state["prof_last_route_url"]:
        with st.expander("Última ruta generada", expanded=False):
            st.write(st.session_state["prof_last_route_url"])
            st.image(make_qr(st.session_state["prof_last_route_url"]))