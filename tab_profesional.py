# tab_profesional.py — buscador con autocompletado en vivo (tipo Google)

import streamlit as st
import requests

from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
    set_location_bias,
)

# Intenta usar el componente nativo de autocompletado
try:
    from streamlit_searchbox import st_searchbox
    HAS_SEARCHBOX = True
except Exception:
    HAS_SEARCHBOX = False


# ====== Utilidades ubicación (IP → addr + lat/lon) ======
def _ip_location_guess():
    """Devuelve (address_str, lat, lng) usando ipapi.co."""
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        city = ip.get("city") or ""
        region = ip.get("region") or ""
        country = ip.get("country_name") or ""
        lat = ip.get("latitude")
        lng = ip.get("longitude")
        addr = ", ".join([x for x in (city, region, country) if x])
        return (addr or None, lat, lng)
    except Exception as e:
        print("ip->address error:", e)
        return (None, None, None)


# ====== Helpers lista ======
def _remove_point(idx: int, t: dict):
    if 0 <= idx < len(st.session_state.prof_points):
        removed = st.session_state.prof_points.pop(idx)
        st.info(t["removed"].format(x=removed))


def _move_point(idx: int, direction: str):
    pts = st.session_state.prof_points
    if direction == "up" and idx > 0:
        pts[idx - 1], pts[idx] = pts[idx], pts[idx - 1]
    elif direction == "down" and idx < len(pts) - 1:
        pts[idx + 1], pts[idx] = pts[idx], pts[idx + 1]


def _add_point(value: str | None, t: dict):
    value = (value or "").strip()
    if not value:
        st.warning(t["type_or_select"])
        return
    st.session_state.prof_points.append(value)
    st.success(t["added"].format(x=value))


def _add_point_from_location(t: dict, also_bias=True):
    addr, lat, lng = _ip_location_guess()
    if addr:
        st.session_state.prof_last_location_guess = addr
        st.session_state.prof_points.append(addr)
        st.success(t["loc_added"].format(x=addr))
    else:
        st.warning(t["loc_failed"])
    if also_bias and lat is not None and lng is not None:
        set_location_bias(lat, lng, 30000)
        st.info(t.get("bias_set", "Sesgo de ubicación aplicado para mejorar sugerencias."))


# ====== Estado ======
def _init_state():
    if "prof_points" not in st.session_state:
        st.session_state.prof_points = []
    if "prof_last_route_url" not in st.session_state:
        st.session_state.prof_last_route_url = None
    if "prof_open_check" not in st.session_state:
        st.session_state.prof_open_check = False
    if "prof_last_location_guess" not in st.session_state:
        st.session_state.prof_last_location_guess = ""
    if "prof_route_type" not in st.session_state:
        st.session_state.prof_route_type = None


# ====== Callback para el autocompletado en vivo ======
def _live_suggestions(query: str):
    """
    Devuelve una lista de etiquetas (strings) de direcciones
    mientras el usuario escribe (sin pulsar ENTER).
    """
    if not query or len(query.strip()) < 2:
        return []
    # clave de bucket común para la barra superior
    return suggest_addresses(query, "prof_top")


# ====== Buscador ======
def search_and_add_top(t: dict):
    st.caption(t["search_label"])

    selected = None

    if HAS_SEARCHBOX:
        # Autocompletado tipo Google: despliega y filtra en vivo
        selected = st_searchbox(
            search_function=_live_suggestions,
            placeholder="Calle, número, ciudad… / Street, number, city…",
            key="prof_top_searchbox",
            default=None,           # no preselecciona nada
            clear_on_submit=False,  # mantiene lo escrito
        )
    else:
        # Fallback (si no está el componente) con text_input + radio
        q = st.text_input(
            label="",
            key="prof_top_q",
            placeholder="Calle, número, ciudad… / Street, number, city…",
        )
        suggestions = _live_suggestions(q) if q else []
        if suggestions:
            selected = st.radio(
                t["choose_one"],
                options=suggestions,
                index=None,
                key="prof_top_choice",
            )
        else:
            st.caption(t.get("no_suggestions", "Sin sugerencias todavía"))

    c1, c2, c3 = st.columns([0.45, 0.3, 0.25])
    with c1:
        if st.button(t["add_enter"], key="btn_add_prof"):
            if selected:
                _add_point(selected, t)
            else:
                # Si no hubo selección, intenta añadir el texto actual del searchbox
                if HAS_SEARCHBOX:
                    raw = st.session_state.get("prof_top_searchbox") or ""
                else:
                    raw = st.session_state.get("prof_top_q") or ""
                _add_point(raw, t)
    with c2:
        if st.button(t["use_my_location"]):
            _add_point_from_location(t, also_bias=True)
    with c3:
        if st.button(t.get("apply_bias", "Mejorar sugerencias aquí")):
            _, lat, lng = _ip_location_guess()
            if lat is not None and lng is not None:
                set_location_bias(lat, lng, 30000)
                st.success(t.get("bias_set", "Sesgo de ubicación aplicado."))
            else:
                st.warning(t["loc_failed"])


# ====== Vista principal ======
def mostrar_profesional(t: dict):
    _init_state()

    st.subheader(t["prof_header"])
    st.caption(t["prof_caption"])

    # Tipos de ruta traducidos
    route_types = t["route_types"]
    default_idx = 0
    if st.session_state.prof_route_type and st.session_state.prof_route_type in route_types:
        default_idx = route_types.index(st.session_state.prof_route_type)
    st.session_state.prof_route_type = st.selectbox(
        t["route_type_label"], route_types, index=default_idx
    )

    st.divider()
    search_and_add_top(t)

    st.markdown(f"### {t['list_title']}")
    pts = st.session_state.prof_points
    if not pts:
        st.info(t["add_at_least_two"])
    else:
        for i, p in enumerate(pts):
            prefix = (
                t["origin"]
                if i == 0
                else (t["destination"] if i == len(pts) - 1 else t["stop_num"].format(i=i))
            )
            c_lbl, c_up, c_down, c_del = st.columns([0.76, 0.08, 0.08, 0.08])
            with c_lbl:
                st.write(f"**{prefix}:** {p}")
            with c_up:
                st.button(
                    t["btn_up"],
                    key=f"up_{i}_{len(pts)}",
                    on_click=_move_point,
                    args=(i, "up"),
                    disabled=(i == 0),
                    use_container_width=True,
                )
            with c_down:
                st.button(
                    t["btn_down"],
                    key=f"down_{i}_{len(pts)}",
                    on_click=_move_point,
                    args=(i, "down"),
                    disabled=(i == len(pts) - 1),
                    use_container_width=True,
                )
            with c_del:
                st.button(
                    t["btn_del"],
                    key=f"del_{i}_{len(pts)}",
                    on_click=_remove_point,
                    args=(i, t),
                    use_container_width=True,
                )

    st.divider()
    st.session_state.prof_open_check = st.checkbox(
        t["open_now_check"], value=st.session_state.prof_open_check
    )

    if st.button(t["generate_prof"], type="primary", key="btn_generar_prof"):
        if len(pts) < 2:
            st.error(t["need_two_points"])
            return

        o_raw = pts[0]
        d_raw = pts[-1]
        wp_raw = pts[1:-1]

        o = resolve_selection(o_raw, "prof_point_0")
        d = resolve_selection(d_raw, f"prof_point_{len(pts)-1}")
        wp_resolved, open_report = [], []

        for i, label in enumerate(wp_raw, start=1):
            det = resolve_selection(label, f"prof_point_{i}")
            wp_resolved.append(det["address"])
            if st.session_state.prof_open_check:
                open_report.append((t["stop_num"].format(i=i), det.get("address"), det.get("open_now")))

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
            optimize=True,
        )

        st.session_state.prof_last_route_url = url
        st.success(t["route_generated"].format(pref=pref))
        st.write(url)
        st.image(make_qr(url), caption=t["scan_qr"])

        if st.session_state.prof_open_check:
            st.markdown(f"### {t['open_status_now']}")
            def _flagline(prefix, det):
                if det.get("open_now") is True:
                    st.markdown(f"**{prefix}:** {t['open']} – {det['address']}")
                elif det.get("open_now") is False:
                    st.markdown(f"**{prefix}:** {t['closed']} – {det['address']}")
                else:
                    st.markdown(f"**{prefix}:** {t['nodata']} – {det['address']}")
            _flagline(t["origin"], o)
            for title, addr, flag in open_report:
                if flag is True:
                    st.markdown(f"**{title}:** {t['open']} – {addr}")
                elif flag is False:
                    st.markdown(f"**{title}:** {t['closed']} – {addr}")
                else:
                    st.markdown(f"**{title}:** {t['nodata']} – {addr}")
            _flagline(t["destination"], d)

    if st.session_state.prof_last_route_url:
        with st.expander(t["last_route"], expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption=t["scan_qr"])