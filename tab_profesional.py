# tab_profesional.py
import requests
import streamlit as st
from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
    set_location_bias,
    _get_key,
)

# -------------------------------
# Estado
# -------------------------------
def _init_state():
    ss = st.session_state
    ss.setdefault("prof_points", [])
    ss.setdefault("prof_last_route_url", None)
    ss.setdefault("prof_route_type", "Más rápido")
    ss.setdefault("prof_sel_idx", None)
    ss.setdefault("prof_q", "")

# -------------------------------
# IP -> lat/lng (sesgo ubicación)
# -------------------------------
def _use_ip_bias() -> bool:
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        lat, lng = ip.get("latitude"), ip.get("longitude")
        if lat and lng:
            set_location_bias(float(lat), float(lng), 50000)  # ~50 km
            return True
    except Exception:
        pass
    return False

# -------------------------------
# Añadir punto según lo visible
# -------------------------------
def _add_point_from_ui():
    labels = st.session_state.get("_prof_last_labels") or []
    sel    = st.session_state.get("prof_sel_idx")
    q      = (st.session_state.get("prof_q") or "").strip()

    if labels:
        value = labels[sel] if (sel is not None and 0 <= sel < len(labels)) else labels[0]
    else:
        value = q

    if not value:
        st.warning("Escribe o selecciona una dirección.")
        return

    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")

# -------------------------------
# Buscador con comportamiento Google-like
# -------------------------------
def _search_box():
    with st.form(key="prof_form", clear_on_submit=False):
        q = st.text_input(
            "Buscar dirección… (presione ENTER para agregar)",
            key="prof_q",
            placeholder="Calle, número, ciudad… / Street, number, city…",
        )

        # Sugerencias (desde 1 letra)
        labels = suggest_addresses(q, "prof_top", min_len=1) if q else []
        st.session_state["_prof_last_labels"] = labels

        if labels:
            st.caption("Sugerencias:")
            sel_key = f"prof_sel_{hash(q) % 10_000_000}"
            idx = st.selectbox(
                "Elige una sugerencia",
                options=list(range(len(labels))),
                format_func=lambda i: labels[i],
                key=sel_key,
                index=0,  # auto-selecciona la primera
            )
            st.session_state["prof_sel_idx"] = idx
        else:
            st.caption("Sin sugerencias todavía")
            st.session_state["prof_sel_idx"] = None

        col1, col2, col3 = st.columns([0.28, 0.28, 0.44])
        with col1:
            submitted = st.form_submit_button("Añadir (ENTER)", type="primary")
        with col2:
            clear = st.form_submit_button("Limpiar")
        with col3:
            geobias = st.form_submit_button("📍 Usar mi ubicación")

    # fuera del form para no recrear widgets
    if submitted:
        _add_point_from_ui()
    if clear:
        st.session_state["prof_q"] = ""
        st.session_state["prof_sel_idx"] = None
        st.rerun()
    if geobias:
        ok = _use_ip_bias()
        st.success("Sesgo de ubicación fijado ✅ (≈50 km).") if ok else st.warning("No se pudo obtener tu ubicación.")

# -------------------------------
# Pantalla principal
# -------------------------------
def mostrar_profesional(t: dict):
    _init_state()
    st.subheader("Ruta de trabajo")

    # Diagnóstico simple de clave
    GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
    st.sidebar.markdown("**Tecla Google OK (últimos 6):**")
    st.sidebar.code((str(GOOGLE_PLACES_API_KEY)[-6:] + "") if GOOGLE_PLACES_API_KEY else "—")

    # Tipo de ruta
    route_types = ["Más rápido", "Más corto", "Evitar autopistas", "Evitar peajes"]
    st.session_state.prof_route_type = st.selectbox(
        "Tipo de ruta", route_types, index=route_types.index(st.session_state.prof_route_type)
    )

    st.divider()
    _search_box()
    st.divider()

    # Lista de puntos
    st.markdown("### Puntos de la ruta (orden de viaje)")
    pts = st.session_state.prof_points
    if not pts:
        st.info("Agregue al menos dos puntos (origen y destino) para generar la ruta.")
        return

    # render lista
    for i, p in enumerate(pts):
        prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}:")
        c1, c2 = st.columns([0.9, 0.1])
        with c1:
            st.write(f"**{prefix}**: {p}")
        with c2:
            if st.button("🗑", key=f"del_{i}"):
                pts.pop(i)
                st.rerun()

    # Generar ruta
    if st.button("Generar ruta profesional", type="primary"):
        if len(pts) < 2:
            st.warning("Debes tener origen y destino.")
            return
        o = resolve_selection(pts[0], "prof_point_0")
        d = resolve_selection(pts[-1], f"prof_point_{len(pts)-1}")
        wp = [resolve_selection(p, f"prof_point_{i}")["address"] for i, p in enumerate(pts[1:-1], 1)]

        url = build_gmaps_url(o["address"], d["address"], wp)
        st.session_state.prof_last_route_url = url
        st.success("Ruta generada correctamente ✅")
        st.write(url)
        st.image(make_qr(url), caption="Escanea el QR para abrir la ruta")

    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada"):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url))