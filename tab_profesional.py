# tab_profesional.py (COMPLETO)
import streamlit as st
import requests
from app_utils import suggest_addresses, resolve_selection, build_gmaps_url, make_qr

# -------- util ip → texto para "usar mi ubicación" --------
def _ip_location_to_address() -> str | None:
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        city = ip.get("city") or ""
        region = ip.get("region") or ""
        country = ip.get("country_name") or ""
        s = ", ".join([x for x in (city, region, country) if x])
        return s or None
    except Exception as e:
        print("ip->address error:", e)
        return None

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

def _add_point(value: str | None, t: dict):
    value = (value or "").strip()
    if not value:
        st.warning(t["type_or_select"])
        return
    st.session_state.prof_points.append(value)
    st.success(t["added"].format(x=value))

def _add_point_from_location(t: dict):
    guess = _ip_location_to_address()
    if guess:
        st.session_state.prof_last_location_guess = guess
        st.session_state.prof_points.append(guess)
        st.success(t["loc_added"].format(x=guess))
    else:
        st.warning(t["loc_failed"])

def _init_state():
    st.session_state.setdefault("prof_points", [])
    st.session_state.setdefault("prof_last_route_url", None)
    st.session_state.setdefault("prof_open_check", False)
    st.session_state.setdefault("prof_last_location_guess", "")
    st.session_state.setdefault("prof_route_type", None)
    st.session_state.setdefault("prof_top_q", "")
    st.session_state.setdefault("prof_top_suggestions", [])
    st.session_state.setdefault("prof_top_selected", "")

# -------- entrada reactiva con sugerencias en vivo --------
def _on_query_change():
    q = st.session_state.get("prof_top_q", "")
    if len((q or "").strip()) >= 2:
        st.session_state["prof_top_suggestions"] = suggest_addresses(q, "prof_top") or []
        # si cambian las sugerencias, limpia selección previa
        st.session_state["prof_top_selected"] = ""
    else:
        st.session_state["prof_top_suggestions"] = []
        st.session_state["prof_top_selected"] = ""

def search_and_add_top(t: dict):
    st.text_input(
        t["search_label"],
        key="prof_top_q",
        placeholder="Calle, número, ciudad… / Street, number, city…",
        on_change=_on_query_change
    )

    sugg = st.session_state.get("prof_top_suggestions", [])
    if sugg:
        st.caption(t["suggestions"])
        st.session_state["prof_top_selected"] = st.radio(
            t["choose_suggestion"],
            options=sugg,
            key="prof_top_radio",
            label_visibility="collapsed"
        )
    else:
        st.caption(t["no_suggestions"])

    c1, c2, c3 = st.columns([0.4, 0.3, 0.3])
    with c1:
        if st.button(t["add_enter"], key="btn_add_selected"):
            sel = st.session_state.get("prof_top_selected")
            if sel:
                _add_point(sel, t)
            else:
                # Si no eligió nada, añadimos el texto libre
                _add_point(st.session_state.get("prof_top_q", ""), t)
            # reset Query y sugerencias
            st.session_state["prof_top_q"] = ""
            st.session_state["prof_top_suggestions"] = []
            st.session_state["prof_top_selected"] = ""
    with c2:
        if st.button(t["use_my_location"], key="btn_use_loc"):
            _add_point_from_location(t)
    with c3:
        if st.button(t["clear_input"], key="btn_clear"):
            st.session_state["prof_top_q"] = ""
            st.session_state["prof_top_suggestions"] = []
            st.session_state["prof_top_selected"] = ""

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
            o["address"], d["address"],
            wp_resolved if wp_resolved else None,
            mode=mode, avoid=avoid, optimize=True
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