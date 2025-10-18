# tab_profesional.py
import streamlit as st
import requests
from app_utils import suggest_addresses, resolve_selection, build_gmaps_url, make_qr

# ------------------------------
# Utilidades
# ------------------------------

def _ip_location_city() -> str | None:
    """Devuelve una ciudad aproximada por IP (solo para sesgo humano en UI)."""
    try:
        r = requests.get("https://ipapi.co/json/", timeout=6)
        r.raise_for_status()
        j = r.json()
        parts = [j.get("city") or "", j.get("region") or "", j.get("country_name") or ""]
        city = ", ".join([p for p in parts if p])
        return city or None
    except Exception:
        return None


def _remove_point(idx: int, t: dict):
    if 0 <= idx < len(st.session_state.prof_points):
        removed = st.session_state.prof_points.pop(idx)
        st.info(t.get("removed", "Eliminado: {x}").format(x=removed))


def _move_point(idx: int, direction: str):
    pts = st.session_state.prof_points
    if direction == "up" and idx > 0:
        pts[idx - 1], pts[idx] = pts[idx], pts[idx - 1]
    elif direction == "down" and idx < len(pts) - 1:
        pts[idx + 1], pts[idx] = pts[idx], pts[idx + 1]


def _add_point(value: str | None, t: dict):
    value = (value or "").strip()
    if not value:
        st.warning(t.get("type_or_select", "Escribe o elige una sugerencia."))
        return
    st.session_state.prof_points.append(value)
    st.success(t.get("added", "Añadido: {x}").format(x=value))


def _add_point_from_location(t: dict):
    guess = _ip_location_city()
    if guess:
        st.session_state.prof_last_location_guess = guess
        st.session_state.prof_points.append(guess)
        st.success(t.get("loc_added", "Añadido (aprox. por IP): {x}").format(x=guess))
    else:
        st.warning(t.get("loc_failed", "No se pudo estimar tu ubicación."))


def _init_state():
    ss = st.session_state
    ss.setdefault("prof_points", [])
    ss.setdefault("prof_last_route_url", None)
    ss.setdefault("prof_open_check", False)
    ss.setdefault("prof_last_location_guess", "")
    ss.setdefault("prof_route_type", None)
    # Estado del buscador en vivo
    ss.setdefault("prof_top_q", "")
    ss.setdefault("prof_suggestions", [])
    ss.setdefault("prof_selected_label", "")
    ss.setdefault("prof_needs_clear", False)
    # Sesgo de ubicación (texto informativo)
    ss.setdefault("prof_location_bias", _ip_location_city() or "")


# ------------------------------
# Autocompletado en vivo
# ------------------------------

def _refresh_suggestions(t: dict):
    """
    Regenera la lista de sugerencias en función del texto que el usuario va escribiendo.
    """
    q = (st.session_state.get("prof_top_q") or "").strip()
    if len(q) < 3:
        st.session_state.prof_suggestions = []
        return

    # Llamamos a nuestro proveedor unificado (Google/SerpAPI/Nominatim).
    # app_utils.suggest_addresses guarda la meta en el bucket 'prof_top'
    try:
        labels = suggest_addresses(q, "prof_top")
    except Exception:
        labels = []

    # Si no hay nada, vaciamos
    st.session_state.prof_suggestions = labels or []


def _enter_add_handler(t: dict):
    """
    Callback al pulsar ENTER en el input o al hacer clic en 'Añadir'.
    IMPORTANTE: no modificar el propio text_input aquí (para evitar la StreamlitAPIException).
    """
    sel = st.session_state.get("prof_selected_label", "") or ""
    sugs = st.session_state.get("prof_suggestions", []) or []
    q = (st.session_state.get("prof_top_q") or "").strip()

    if not (sel or sugs or q):
        st.warning(t.get("type_or_select", "Escribe o elige una sugerencia."))
        return

    # 1) prioridad a una sugerencia seleccionada
    # 2) luego la primera sugerencia
    # 3) finalmente el texto literal
    candidate = sel or (sugs[0] if sugs else q)
    _add_point(candidate, t)

    # Marcamos limpieza diferida (se hará al próximo render)
    st.session_state.prof_needs_clear = True


def search_and_add_top(t: dict):
    # Limpiamos tras un alta anterior (sin tocar el input dentro del callback)
    if st.session_state.get("prof_needs_clear", False):
        st.session_state.prof_top_q = ""
        st.session_state.prof_suggestions = []
        st.session_state.prof_selected_label = ""
        st.session_state.prof_needs_clear = False

    # Input principal (re-renderiza en cada cambio)
    st.text_input(
        label=t.get("search_label", "Buscar dirección… (pulsa ENTER para añadir)"),
        key="prof_top_q",
        placeholder="Calle, número, ciudad… / Street, number, city…",
        on_change=_enter_add_handler,  # ENTER en el input
        args=(t,),
    )

    # Refrescamos sugerencias cada render
    _refresh_suggestions(t)

    sugs = st.session_state.get("prof_suggestions", []) or []
    if sugs:
        st.caption(t.get("suggestions", "Sugerencias:"))
        st.radio(
            label=t.get("select_suggestion", "Elige una sugerencia"),
            options=sugs,
            key="prof_selected_label",
        )
    else:
        st.caption(t.get("no_suggestions", "Sin sugerencias todavía"))

    c1, c2 = st.columns([0.5, 0.5])
    with c1:
        if st.button(t.get("add_enter", "Añadir (ENTER)")):
            _enter_add_handler(t)
    with c2:
        if st.button(t.get("use_my_location", "📍 Usar mi ubicación")):
            _add_point_from_location(t)


# ------------------------------
# Pantalla principal
# ------------------------------

def mostrar_profesional(t: dict):
    _init_state()

    st.subheader(t.get("prof_header", "Ruta de trabajo"))
    st.caption(
        t.get(
            "prof_caption",
            "Añade puntos con la barra de arriba. El primero es origen, el último es destino; "
            "los demás son paradas intermedias. Puedes reordenar con las flechas y eliminar cualquier punto.",
        )
    )

    # Tipos de ruta
    route_types = t.get("route_types", ["Más rápido", "Más corto", "Evitar autopistas", "Evitar peajes", "Ruta panorámica"])
    default_idx = 0
    if st.session_state.prof_route_type in route_types:
        default_idx = route_types.index(st.session_state.prof_route_type)
    st.session_state.prof_route_type = st.selectbox(
        t.get("route_type_label", "Tipo de ruta"),
        route_types,
        index=default_idx,
    )

    st.divider()

    # Buscador en vivo + sugerencias
    search_and_add_top(t)

    # Lista de puntos
    st.markdown(f"### {t.get('list_title', 'Puntos de la ruta (orden de viaje)')}")
    pts = st.session_state.prof_points
    if not pts:
        st.info(t.get("add_at_least_two", "Añade al menos dos puntos (origen y destino) para generar la ruta."))
    else:
        for i, p in enumerate(pts):
            prefix = (
                t.get("origin", "Origen")
                if i == 0
                else (t.get("destination", "Destino") if i == len(pts) - 1 else t.get("stop_num", "Parada {i}").format(i=i))
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
                    use_container_width=True,
                )
            with c_down:
                st.button(
                    t.get("btn_down", "↓"),
                    key=f"down_{i}_{len(pts)}",
                    on_click=_move_point,
                    args=(i, "down"),
                    disabled=(i == len(pts) - 1),
                    use_container_width=True,
                )
            with c_del:
                st.button(
                    t.get("btn_del", "🗑️"),
                    key=f"del_{i}_{len(pts)}",
                    on_click=_remove_point,
                    args=(i, t),
                    use_container_width=True,
                )

    st.divider()

    # Checkbox aperturas
    st.session_state.prof_open_check = st.checkbox(
        t.get("open_now_check", "Comprobar si los lugares están abiertos ahora (si hay datos de Google)"),
        value=st.session_state.prof_open_check,
    )

    # Botón generar
    if st.button(t.get("generate_prof", "Generar ruta profesional"), type="primary", key="btn_generar_prof"):
        if len(pts) < 2:
            st.error(t.get("need_two_points", "Añade al menos origen y destino."))
            return

        o_raw = pts[0]
        d_raw = pts[-1]
        wp_raw = pts[1:-1]

        o = resolve_selection(o_raw, "prof_point_0")
        d = resolve_selection(d_raw, f"prof_point_{len(pts) - 1}")
        wp_resolved = []
        open_report = []

        for i, label in enumerate(wp_raw, start=1):
            det = resolve_selection(label, f"prof_point_{i}")
            wp_resolved.append(det["address"])
            if st.session_state.prof_open_check:
                open_report.append((t.get("stop_num", "Parada {i}").format(i=i), det.get("address"), det.get("open_now")))

        # Preferencias
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
        st.success(t.get("route_generated", "Ruta generada ({pref}).").format(pref=pref))
        st.write(url)
        st.image(make_qr(url), caption=t.get("scan_qr", "Escanea el QR para abrir la ruta"))

        if st.session_state.prof_open_check:
            st.markdown(f"### {t.get('open_status_now', 'Estado de apertura (ahora)')}")
            def _flagline(prefix, det):
                if det.get("open_now") is True:
                    st.markdown(f"**{prefix}:** {t.get('open','Abierto')} – {det['address']}")
                elif det.get("open_now") is False:
                    st.markdown(f"**{prefix}:** {t.get('closed','Cerrado')} – {det['address']}")
                else:
                    st.markdown(f"**{prefix}:** {t.get('nodata','Sin datos')} – {det['address']}")
            _flagline(t.get("origin", "Origen"), o)
            for title, addr, flag in open_report:
                if flag is True:
                    st.markdown(f"**{title}:** {t.get('open','Abierto')} – {addr}")
                elif flag is False:
                    st.markdown(f"**{title}:** {t.get('closed','Cerrado')} – {addr}")
                else:
                    st.markdown(f"**{title}:** {t.get('nodata','Sin datos')} – {addr}")
            _flagline(t.get("destination", "Destino"), d)

    # Última ruta
    if st.session_state.prof_last_route_url:
        with st.expander(t.get("last_route", "Última ruta generada"), expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption=t.get("scan_qr", "Escanea el QR"))