# tab_profesional.py
import streamlit as st
import requests

from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
    set_location_bias,  # sesgo geográfico para Google Autocomplete
)

# ---------------------------
# Utilidades de esta pestaña
# ---------------------------
def _ip_location_to_latlng() -> tuple[float | None, float | None, str]:
    """
    Devuelve (lat, lng, location_str) a partir de la IP (servicio ipapi.co).
    Si falla, devuelve (None, None, "").
    """
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        lat = ip.get("latitude")
        lng = ip.get("longitude")
        city = ip.get("city") or ""
        region = ip.get("region") or ""
        country = ip.get("country_name") or ""
        s = ", ".join([x for x in (city, region, country) if x])
        return lat, lng, s
    except Exception:
        return None, None, ""

def _remove_point(idx: int, t: dict):
    if 0 <= idx < len(st.session_state.prof_points):
        removed = st.session_state.prof_points.pop(idx)
        st.info(t.get("removed", "Eliminado: {x}").format(x=removed))

def _move_point(idx: int, direction: str):
    pts = st.session_state.prof_points
    if direction == "up" and idx > 0:
        pts[idx-1], pts[idx] = pts[idx], pts[idx-1]
    elif direction == "down" and idx < len(pts) - 1:
        pts[idx+1], pts[idx] = pts[idx], pts[idx+1]

def _init_state():
    st.session_state.setdefault("prof_points", [])
    st.session_state.setdefault("prof_last_route_url", None)
    st.session_state.setdefault("prof_open_check", False)
    st.session_state.setdefault("prof_last_location_guess", "")
    st.session_state.setdefault("prof_route_type", None)
    st.session_state.setdefault("prof_top_bucket", "prof_top")
    st.session_state.setdefault("prof_selected_sug", "")
    st.session_state.setdefault("prof_top_q", "")  # valor inicial del input

# ---------------------------
# Acciones (botones)
# ---------------------------
def _enter_add_handler(t: dict):
    """Añadir a la lista usando la sugerencia elegida o el texto crudo (ya guardados en session_state)."""
    q = (st.session_state.get("prof_top_q", "") or "").strip()
    sel = (st.session_state.get("prof_selected_sug", "") or "").strip()

    if not q and not sel:
        st.warning(t.get("type_or_select", "Escribe o selecciona una dirección antes de añadir."))
        return

    value = sel or q
    st.session_state.prof_points.append(value)
    st.success(t.get("added", "Añadido: {x}").format(x=value))

def _use_my_location_handler(t: dict):
    """
    1) Obtiene (lat,lng) por IP para fijar un 'location bias' (Google Places Autocomplete).
    2) Añade un punto aproximado con la ciudad/región/país (opcional).
    """
    lat, lng, loc_str = _ip_location_to_latlng()
    if lat is not None and lng is not None:
        # Sesgo 30 km para priorizar sugerencias cercanas
        set_location_bias(lat, lng, radius_m=30000)
        st.info(t.get("bias_set_ok", "Sesgo de ubicación aplicado para sugerencias cercanas."))
    else:
        st.warning(t.get("loc_failed", "No se pudo detectar tu ubicación."))

    if loc_str:
        st.session_state.prof_last_location_guess = loc_str
        st.session_state.prof_points.append(loc_str)
        st.success(t.get("loc_added", "Añadido (aprox.): {x}").format(x=loc_str))

def _clear_input_and_suggestions():
    """Limpia el input y las sugerencias (seguro)."""
    st.session_state["prof_top_q"] = ""
    st.session_state["prof_selected_sug"] = ""
    st.session_state.get("suggest_maps", {}).pop(st.session_state["prof_top_bucket"], None)
    st.rerun()

# ---------------------------
# UI: buscador y sugerencias
# ---------------------------
def search_and_add_top(t: dict):
    st.markdown("### " + t.get("workbench", "Ruta de trabajo"))

    # Campo de texto (NO reasignamos session_state aquí)
    q_ph = t.get("search_label", "Buscar dirección… (pulsa ENTER para añadir)")
    q = st.text_input(
        q_ph,
        key="prof_top_q",
        placeholder=t.get("search_ph", "Calle, número, ciudad… / Street, number, city…"),
    )

    # Sugerencias dinámicas con el texto actual
    labels = []
    if (q or "").strip():
        labels = suggest_addresses(q, st.session_state["prof_top_bucket"])

    if labels:
        st.caption(t.get("suggestions", "Sugerencias:"))
        st.radio(
            t.get("choose_suggestion", "Elige una sugerencia"),
            labels,
            index=0,
            key="prof_selected_sug",
        )
    else:
        st.caption(t.get("no_suggestions", "Sin sugerencias todavía"))

    # Acciones
    c1, c2, c3 = st.columns([0.26, 0.26, 0.48])
    with c1:
        if st.button(t.get("add_enter", "Añadir (ENTER)"), type="primary", key="btn_add"):
            _enter_add_handler(t)
    with c2:
        if st.button(t.get("clear_input", "Limpiar"), key="btn_clear"):
            _clear_input_and_suggestions()
    with c3:
        if st.button(t.get("use_my_location", "Usar mi ubicación"), key="btn_loc"):
            _use_my_location_handler(t)

# ---------------------------
# UI principal
# ---------------------------
def mostrar_profesional(t: dict):
    _init_state()

    st.subheader(t.get("prof_header", "Ruta de trabajo"))
    st.caption(t.get(
        "prof_caption",
        "Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final."
    ))

    # Tipos de ruta (opciones traducidas)
    route_types = t.get("route_types", ["Más rápido", "Más corto", "Evitar autopistas", "Evitar peajes", "Ruta panorámica"])
    default_idx = 0
    if st.session_state.prof_route_type and st.session_state.prof_route_type in route_types:
        default_idx = route_types.index(st.session_state.prof_route_type)

    st.session_state.prof_route_type = st.selectbox(
        t.get("route_type_label", "Tipo de ruta"),
        route_types,
        index=default_idx
    )

    st.divider()
    # Buscador + sugerencias + acciones
    search_and_add_top(t)

    # Lista de puntos
    st.markdown("### " + t.get("list_title", "Puntos de la ruta (orden de viaje)"))
    pts = st.session_state.prof_points
    if not pts:
        st.info(t.get("add_at_least_two", "Añade al menos dos puntos (origen y destino) para generar la ruta."))
    else:
        for i, p in enumerate(pts):
            prefix = (
                t.get("origin", "Origen") if i == 0
                else (t.get("destination", "Destino") if i == len(pts) - 1
                      else t.get("stop_num", "Parada {i}").format(i=i))
            )
            c_lbl, c_up, c_down, c_del = st.columns([0.76, 0.08, 0.08, 0.08])
            with c_lbl:
                st.write(f"**{prefix}:** {p}")
            with c_up:
                st.button(
                    t.get("btn_up", "↑"),
                    key=f"up_{i}_{len(pts)}",
                    on_click=_move_point,
                    args=(i, "up"),
                    disabled=(i == 0),
                    use_container_width=True
                )
            with c_down:
                st.button(
                    t.get("btn_down", "↓"),
                    key=f"down_{i}_{len(pts)}",
                    on_click=_move_point,
                    args=(i, "down"),
                    disabled=(i == len(pts) - 1),
                    use_container_width=True
                )
            with c_del:
                st.button(
                    t.get("btn_del", "🗑️"),
                    key=f"del_{i}_{len(pts)}",
                    on_click=_remove_point,
                    args=(i, t),
                    use_container_width=True
                )

    st.divider()

    # Comprobación de abierto ahora (si hay datos de Google)
    st.session_state.prof_open_check = st.checkbox(
        t.get("open_now_check", "Comprobar si los lugares están abiertos ahora (si hay datos de Google)"),
        value=st.session_state.prof_open_check
    )

    # Generar ruta
    if st.button(t.get("generate_prof", "Generar ruta"), type="primary", key="btn_generar_prof"):
        if len(pts) < 2:
            st.error(t.get("need_two_points", "Necesitas al menos origen y destino."))
            return

        o_raw, d_raw = pts[0], pts[-1]
        wp_raw = pts[1:-1]

        o = resolve_selection(o_raw, "prof_point_0")
        d = resolve_selection(d_raw, f"prof_point_{len(pts)-1}")
        wp_resolved = []
        open_report = []

        for i, label in enumerate(wp_raw, start=1):
            det = resolve_selection(label, f"prof_point_{i}")
            wp_resolved.append(det["address"])
            if st.session_state.prof_open_check:
                open_report.append((t.get("stop_num", "Parada {i}").format(i=i), det.get("address"), det.get("open_now")))

        # Preferencias de ruta
        mode = "driving"
        avoid = []
        pref = st.session_state.prof_route_type
        if pref in ("Más corto", "Shortest"):
            avoid = ["tolls", "highways"]
        elif pref in ("Evitar autopistas", "Avoid highways"):
            avoid = ["highways"]
        elif pref in ("Evitar peajes", "Avoid tolls"):
            avoid = ["tolls"]
        elif pref in ("Ruta panorámica", "Scenic route"):
            mode = "bicycling"

        url = build_gmaps_url(
            o["address"],
            d["address"],
            wp_resolved if wp_resolved else None,
            mode=mode,
            avoid=avoid,
            optimize=True
        )
        st.session_state.prof_last_route_url = url
        st.success(t.get("route_generated", "Ruta generada ({pref}).").format(pref=pref))
        st.write(url)
        st.image(make_qr(url), caption=t.get("scan_qr", "Escanea el QR"))

        if st.session_state.prof_open_check:
            st.markdown("### " + t.get("open_status_now", "Estado de apertura (ahora)"))
            def _flagline(prefix, det):
                if det.get("open_now") is True:
                    st.markdown(f"**{prefix}:** {t.get('open','Abierto')} – {det['address']}")
                elif det.get("open_now") is False:
                    st.markdown(f"**{prefix}:** {t.get('closed','Cerrado')} – {det['address']}")
                else:
                    st.markdown(f"**{prefix}:** {t.get('nodata','Sin datos')} – {det['address']}")
            _flagline(t.get("origin","Origen"), o)
            for title, addr, flag in open_report:
                if flag is True:
                    st.markdown(f"**{title}:** {t.get('open','Abierto')} – {addr}")
                elif flag is False:
                    st.markdown(f"**{title}:** {t.get('closed','Cerrado')} – {addr}")
                else:
                    st.markdown(f"**{title}:** {t.get('nodata','Sin datos')} – {addr}")
            _flagline(t.get("destination","Destino"), d)

    # Última ruta
    if st.session_state.prof_last_route_url:
        with st.expander(t.get("last_route", "Última ruta"), expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption=t.get("scan_qr", "Escanea el QR"))