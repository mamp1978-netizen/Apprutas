import streamlit as st
import requests
from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
    ip_geo_bias   # <-- esta es la correcta, antes era set_location_bias
)

# =========================
# Estado inicial / helpers
# =========================
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

    # --- Geolocalización automática al abrir la pestaña ---
    if "geo_bias" not in st.session_state:
        guess = ip_geo_bias()
        if guess:
            # Radio por defecto 30km; si quieres, ajústalo a 50-80km
            guess["radius"] = 30000
            st.session_state["geo_bias"] = guess


def _remove_point(idx: int, t: dict):
    if 0 <= idx < len(st.session_state.prof_points):
        removed = st.session_state.prof_points.pop(idx)
        st.info(t["removed"].format(x=removed))


def _move_point(idx: int, direction: str):
    pts = st.session_state.prof_points
    if direction == "up" and idx > 0:
        pts[idx-1], pts[idx] = pts[idx], pts[idx-1]
    elif direction == "down" and idx < len(pts) - 1:
        pts[idx+1], pts[idx] = pts[idx], pts[idx+1]


def _add_point(value: str | None, t: dict, selected_label: str | None = None, key_bucket: str | None = None):
    """
    Añade a la lista:
    - Si el usuario eligió una sugerencia (selected_label), resolver con ese label y el bucket.
    - Si no, añade el texto literal escrito (para no perder el número).
    """
    value = (value or "").strip()
    if not value:
        st.warning(t["type_or_select"])
        return

    if selected_label and key_bucket:
        det = resolve_selection(selected_label, key_bucket)
        final_text = det.get("address") or selected_label
    else:
        final_text = value

    st.session_state.prof_points.append(final_text)
    st.success(t["added"].format(x=final_text))


def _add_point_from_location(t: dict):
    # Reutilizamos ip_geo_bias() para actualizar el bias actual
    guess = ip_geo_bias()
    if guess:
        guess["radius"] = 30000
        st.session_state["geo_bias"] = guess
        # Lo convertimos a un texto "ciudad, región, país" aproximado
        try:
            ip = requests.get("https://ipapi.co/json/", timeout=6).json()
            city = ip.get("city") or ""
            region = ip.get("region") or ""
            country = ip.get("country_name") or ""
            s = ", ".join([x for x in (city, region, country) if x])
        except Exception:
            s = ""
        if s:
            st.session_state.prof_last_location_guess = s
            st.session_state.prof_points.append(s)
            st.success(t["loc_added"].format(x=s))
        else:
            st.info(t["loc_bias_set"])
    else:
        st.warning(t["loc_failed"])


# =========================
# UI de búsqueda superior
# =========================
def search_and_add_top(t: dict):
    with st.form(key="prof_top_form", clear_on_submit=True):
        q = st.text_input(
            t["search_label"],
            key="prof_top_q",
            placeholder="Calle, número, ciudad… / Street, number, city…"
        )

        suggestions = suggest_addresses(q, "prof_top") if q else []
        selected_label = None

        # Mensaje de “elige una”
        if suggestions:
            st.caption(t["suggestions"])
            # Radio buttons con las opciones (como el dropdown nativo)
            selected_label = st.radio(
                label=t["select_suggestion"],
                options=suggestions,
                key="prof_select_suggestion",
                index=0,
                horizontal=False
            )
        else:
            st.caption(t["no_suggestions"])

        c1, c2 = st.columns([0.7, 0.3])
        with c1:
            submitted = st.form_submit_button(t["add_enter"])
        with c2:
            loc = st.form_submit_button(t["use_my_location"])

        if submitted:
            # Si hay selección en radio -> respetar esa selección y usar bucket "prof_top"
            if selected_label:
                _add_point(q, t, selected_label=selected_label, key_bucket="prof_top")
            else:
                # Sin sugerencias o sin seleccionar -> añade literal
                _add_point(q, t)

        if loc:
            _add_point_from_location(t)


# =========================
# Pantalla principal
# =========================
def mostrar_profesional(t: dict):
    _init_state()

    st.subheader(t["prof_header"])
    st.caption(t["prof_caption"])

    # Tipos de ruta
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
                t["origin"] if i == 0
                else (t["destination"] if i == len(pts) - 1
                      else t["stop_num"].format(i=i))
            )
            c_lbl, c_up, c_down, c_del = st.columns([0.76, 0.08, 0.08, 0.08])
            with c_lbl:
                st.write(f"**{prefix}:** {p}")
            with c_up:
                st.button(t["btn_up"], key=f"up_{i}_{len(pts)}", on_click=_move_point, args=(i, "up"),
                          disabled=(i == 0), use_container_width=True)
            with c_down:
                st.button(t["btn_down"], key=f"down_{i}_{len(pts)}", on_click=_move_point, args=(i, "down"),
                          disabled=(i == len(pts)-1), use_container_width=True)
            with c_del:
                st.button(t["btn_del"], key=f"del_{i}_{len(pts)}", on_click=_remove_point, args=(i, t),
                          use_container_width=True)

    st.divider()
    st.session_state.prof_open_check = st.checkbox(
        t["open_now_check"],
        value=st.session_state.prof_open_check
    )

    if st.button(t["generate_prof"], type="primary", key="btn_generar_prof"):
        if len(pts) < 2:
            st.error(t["need_two_points"])
            return

        o_raw = pts[0]
        d_raw = pts[-1]
        wp_raw = pts[1:-1]

        # Resolución con buckets por índice
        o = resolve_selection(o_raw, "prof_point_0")
        d = resolve_selection(d_raw, f"prof_point_{len(pts)-1}")

        wp_resolved = []
        open_report = []
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
            optimize=True
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