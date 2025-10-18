# tab_profesional.py
import requests
import streamlit as st
from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
)

# -------------------------------
# Utilidades internas (ligeras)
# -------------------------------

def _ip_location_to_address() -> str | None:
    """
    Intenta aproximar la ciudad/región/país desde la IP del usuario
    para usarla como punto o como pista de ubicación.
    """
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


def _init_state():
    """
    Inicializa las claves de estado usadas por la pestaña profesional.
    """
    ss = st.session_state
    ss.setdefault("prof_points", [])             # lista de puntos (labels de usuario o sugerencias)
    ss.setdefault("prof_last_route_url", None)   # última URL generada
    ss.setdefault("prof_open_check", False)      # checkbox de abrir ahora (si hay datos)
    ss.setdefault("prof_last_location_guess", "")# última ciudad aproximada por IP
    ss.setdefault("prof_route_type", None)       # preferencia de ruta seleccionada
    # Para el buscador superior:
    ss.setdefault("prof_top_selected", None)     # índice seleccionado en el select de sugerencias
    # Nota: el valor del cuadro de texto lo gestiona streamlit con la key "prof_top_q"


# -------------------------------
# Acciones sobre la lista de puntos
# -------------------------------

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


def _add_point(value: str | None, t: dict):
    value = (value or "").strip()
    if not value:
        st.warning(t.get("type_or_select", "Escribe o selecciona una dirección."))
        return
    st.session_state.prof_points.append(value)
    st.success(t.get("added", "Añadido: {x}").format(x=value))


def _add_point_from_location(t: dict):
    guess = _ip_location_to_address()
    if guess:
        st.session_state.prof_last_location_guess = guess
        st.session_state.prof_points.append(guess)
        st.success(t.get("loc_added", "Añadido desde tu ubicación: {x}").format(x=guess))
    else:
        st.warning(t.get("loc_failed", "No se pudo detectar tu ubicación."))


# -------------------------------
# Buscador superior con sugerencias “vivas”
# -------------------------------

def _clear_search():
    """
    Limpia el input y la selección. Usado por el botón 'Limpiar'.
    OJO: usamos pop para evitar el error de Streamlit de reescritura
    de session_state tras instanciar el widget.
    """
    st.session_state.pop("prof_top_q", None)
    st.session_state["prof_top_selected"] = None
    # En apps recientes, st.rerun() mejora la UX al limpiar
    try:
        st.rerun()
    except Exception:
        pass


def search_and_add_top(t: dict):
    st.markdown("### " + t.get("work_header", "Ruta de trabajo"))

    # 1) Cuadro de texto: al teclear, la app se reejecuta y pedimos sugerencias
    q = st.text_input(
        t.get("search_label", "Buscar dirección… (pulsa ENTER para añadir)"),
        key="prof_top_q",
        placeholder=t.get("placeholder", "Calle, número, ciudad… / Street, number, city…"),
    )

    # 2) Sugerencias dinámicas (Google / SerpAPI / Nominatim via app_utils.suggest_addresses)
    labels = suggest_addresses(q, "prof_top") if q and len(q.strip()) >= 2 else []

    # Guardamos las sugerencias en memoria para esta sección,
    # de forma que la selección por índice sea estable durante este render.
    st.session_state["_prof_top_last_labels"] = labels

    # Render de la lista de sugerencias (si hay)
    if labels:
        st.caption(t.get("suggestions", "Sugerencias:"))
        # índice seleccionado (None => nada elegido)
        idx_selected = st.session_state.get("prof_top_selected", None)

        # Mostramos un selectbox con las opciones
        idx = st.selectbox(
            t.get("select_suggestion", "Elige una sugerencia"),
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            index=idx_selected if idx_selected is not None and 0 <= idx_selected < len(labels) else 0,
            key="prof_top_selectbox",
        )
        st.session_state["prof_top_selected"] = idx
    else:
        st.caption(t.get("no_suggestions", "Sin sugerencias todavía"))

    # Botones de acción
    c_add, c_clear, c_loc = st.columns([0.25, 0.2, 0.55])
    with c_add:
        add_clicked = st.button(t.get("add_enter", "Añadir (ENTER)"), type="primary")
    with c_clear:
        st.button(t.get("clear_input", "Limpiar"), on_click=_clear_search)
    with c_loc:
        loc_clicked = st.button("📍 " + t.get("use_my_location", "Usar mi ubicación"))

    # Lógica de añadir
    if add_clicked:
        # Si hay una sugerencia elegida, usamos esa; si no, el texto tal cual
        labels_now = st.session_state.get("_prof_top_last_labels") or []
        sel = st.session_state.get("prof_top_selected", None)
        if labels_now and sel is not None and 0 <= sel < len(labels_now):
            _add_point(labels_now[sel], t)
        else:
            _add_point(q, t)

    if loc_clicked:
        _add_point_from_location(t)


# -------------------------------
# Pantalla principal de la pestaña
# -------------------------------

def mostrar_profesional(t: dict):
    _init_state()

    # Título y guía
    st.subheader(t.get("prof_header", "Ruta de trabajo"))
    st.caption(t.get("prof_caption", "Añade puntos con la barra de arriba. El primero es origen, el último es destino; los demás son paradas intermedias."))

    # Tipos de ruta traducidos
    route_types = t.get("route_types", ["Más rápido", "Más corto", "Evitar autopistas", "Evitar peajes", "Ruta panorámica"])
    # índice por defecto
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
                      else t.get("stop_num", "Parada #{i}:").format(i=i))
            )
            c_lbl, c_up, c_down, c_del = st.columns([0.76, 0.08, 0.08, 0.08])
            with c_lbl:
                st.write(f"**{prefix}:** {p}")
            with c_up:
                st.button(t.get("btn_up", "↑"), key=f"up_{i}_{len(pts)}", on_click=_move_point, args=(i, "up"),
                          disabled=(i == 0), use_container_width=True)
            with c_down:
                st.button(t.get("btn_down", "↓"), key=f"down_{i}_{len(pts)}", on_click=_move_point, args=(i, "down"),
                          disabled=(i == len(pts)-1), use_container_width=True)
            with c_del:
                st.button(t.get("btn_del", "🗑"), key=f"del_{i}_{len(pts)}", on_click=_remove_point, args=(i, t),
                          use_container_width=True)

    st.divider()

    # Comprobación de apertura (si hay datos de Google Details en resolve_selection)
    st.session_state.prof_open_check = st.checkbox(
        t.get("open_now_check", "Comprobar si los lugares están abiertos ahora (si hay datos de Google)"),
        value=st.session_state.prof_open_check
    )

    # Generar ruta
    if st.button(t.get("generate_prof", "Generar ruta profesional"), type="primary", key="btn_generar_prof"):
        if len(pts) < 2:
            st.error(t.get("need_two_points", "Necesitas al menos origen y destino."))
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
                open_report.append((t.get("stop_num", "Parada #{i}:").format(i=i), det.get("address"), det.get("open_now")))

        # Preferencias de ruta → travelmode/avoid
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
        st.success(t.get("route_generated", "Ruta generada ({pref})").format(pref=pref))
        st.write(url)
        st.image(make_qr(url), caption=t.get("scan_qr", "Escanea el QR para abrir la ruta"))

        # Informe "abierto ahora" si procede
        if st.session_state.prof_open_check:
            st.markdown("### " + t.get("open_status_now", "Estado ahora"))
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

    # Expander con la última ruta
    if st.session_state.prof_last_route_url:
        with st.expander(t.get("last_route", "Última ruta"), expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption=t.get("scan_qr", "Escanea el QR para abrir la ruta"))