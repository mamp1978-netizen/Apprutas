# tab_profesional.py
import streamlit as st
import requests
from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
)

# --- Parámetros de seguridad/UX ---
MAX_POINTS = 30  # límite suave para evitar URLs enormes; puedes subirlo si quieres

def _current_lang() -> str:
    try:
        return (st.session_state.get("lang") or "es").lower()
    except Exception:
        return "es"

def _ip_location_to_address() -> str | None:
    """Intenta inferir ubicación aproximada por IP pública (no requiere permisos del navegador)."""
    try:
        r = requests.get("https://ipapi.co/json/", timeout=6)
        r.raise_for_status()
        ip = r.json()
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
        pts[idx - 1], pts[idx] = pts[idx], pts[idx - 1]
    elif direction == "down" and idx < len(pts) - 1:
        pts[idx + 1], pts[idx] = pts[idx], pts[idx + 1]

def _add_point(value: str | None, t: dict):
    value = (value or "").strip()
    if not value:
        st.warning(t["type_or_select"])
        return

    # 1) Añadimos el texto a la lista visible
    st.session_state.prof_points.append(value)
    st.success(t["added"].format(x=value))

    # 2) Si existe meta en el bucket 'prof_top', la copiamos al bucket del punto recién creado
    #    para que luego resolve_selection encuentre el place_id correcto.
    try:
        sm = st.session_state.get("suggest_maps", {})
        top_meta = sm.get("prof_top", {}).get(value)
        if top_meta:
            idx = len(st.session_state.prof_points) - 1
            bucket_name = f"prof_point_{idx}"
            if "suggest_maps" not in st.session_state:
                st.session_state["suggest_maps"] = {}
            if bucket_name not in st.session_state["suggest_maps"]:
                st.session_state["suggest_maps"][bucket_name] = {}
            st.session_state["suggest_maps"][bucket_name][value] = top_meta
    except Exception:
        pass

def _add_point_from_location(t: dict):
    guess = _ip_location_to_address()
    if guess:
        st.session_state.prof_last_location_guess = guess
        _add_point(guess, t)
    else:
        st.warning(t["loc_failed"])

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
        st.session_state.prof_route_type = None  # lo ponemos al crear el select

def search_and_add_top(t: dict):
    lang = _current_lang()
    with st.form(key="prof_top_form", clear_on_submit=True):
        q = st.text_input(
            t["search_label"],
            key="prof_top_q",
            placeholder="Calle, número, ciudad… / Street, number, city…",
        )

        # Sugerencias (multi-proveedor via utils) según idioma activo
        suggestions = suggest_addresses(q, "prof_top", lang=lang) if q else []
        if suggestions:
            st.caption(t["suggestions"])
            for s in suggestions[:6]:
                st.write(f"• {s}")

        c1, c2 = st.columns([0.7, 0.3])
        with c1:
            submitted = st.form_submit_button(t["add_enter"])
        with c2:
            loc = st.form_submit_button(t["use_my_location"])

        if submitted:
            if suggestions:
                # Selecciona la primera sugerencia (ENTER rápido)
                _add_point(suggestions[0], t)
            else:
                _add_point(q, t)

        if loc:
            _add_point_from_location(t)

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

        lang = _current_lang()

        o_raw = pts[0]
        d_raw = pts[-1]
        wp_raw = pts[1:-1]

        # Resolver cada label usando el bucket correspondiente y el idioma
        o = resolve_selection(o_raw, "prof_point_0", lang=lang)
        d = resolve_selection(d_raw, f"prof_point_{len(pts)-1}", lang=lang)

        wp_resolved = []
        open_report = []
        for i, label in enumerate(wp_raw, start=1):
            det = resolve_selection(label, f"prof_point_{i}", lang=lang)
            wp_resolved.append(det["address"])
            if st.session_state.prof_open_check:
                open_report.append((t["stop_num"].format(i=i), det.get("address"), det.get("open_now")))

        # Preferencias de ruta → parámetros URL
        mode = "driving"
        avoid: list[str] = []
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
            def _flagline(prefix: str, det: dict):
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