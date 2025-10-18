# tab_profesional.py
import streamlit as st
import requests
from streamlit_searchbox import st_searchbox

from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
    set_location_bias,          # sesgo para Google
    provider_google_autocomplete # lo usamos para el autocompletado vivo
)

# ---------------- utilidades ----------------

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
    # 1) intenta fijar el bias con la localización aproximada de IP
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        lat = ip.get("latitude")
        lng = ip.get("longitude")
        if lat and lng:
            # bias de 30km y país ES (ajústalo si quieres)
            set_location_bias(float(lat), float(lng), 30000, components="country:es")
    except Exception:
        pass

    # 2) añade un texto aproximado para empezar
    guess = _ip_location_to_address()
    if guess:
        st.session_state.prof_last_location_guess = guess
        st.session_state.prof_points.append(guess)
        st.success(t["loc_added"].format(x=guess))
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
        st.session_state.prof_route_type = None
    if "prof_last_selected" not in st.session_state:
        st.session_state.prof_last_selected = ""

# ---------------- autocompletado vivo ----------------
# Usaremos streamlit-searchbox, que llama a esta función en cada pulsación.
# Debe devolver una lista de strings (las etiquetas a mostrar).
def _live_search_places(query: str) -> list[str]:
    if not query or len(query.strip()) < 2:
        return []
    # Google con types=address + locationbias + components (definido en app_utils)
    results = provider_google_autocomplete(query.strip(), max_results=8)
    labels = [label for (label, _meta) in results]
    # Guardamos las metas en el bucket "prof_top" para que luego resolve_selection funcione
    bucket = st.session_state.setdefault("suggest_maps", {}).setdefault("prof_top", {})
    for (label, meta) in results:
        bucket[label] = meta
    return labels

def search_and_add_top(t: dict):
    # Caja de búsqueda con dropdown estilo Google (en vivo)
    selected = st_searchbox(
        search_function=_live_search_places,
        key="prof_searchbox",
        default="",
        placeholder="Calle, número, ciudad… / Street, number, city…",
        clear_on_submit=False,          # conservamos texto tras seleccionar
    )

    c1, c2 = st.columns([0.25, 0.25])
    with c1:
        if st.button(t["add_enter"], key="btn_add"):
            # Si el usuario eligió un ítem del dropdown, úsalo; si no, usa el texto actual
            value = selected or st.session_state.get("prof_searchbox", "")
            _add_point(value, t)
    with c2:
        if st.button(t["use_my_location"]):
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

    # 🔎 Autocompletado vivo con Google
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

        # Resolver selecciones (usa bucket para place_id de Google)
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