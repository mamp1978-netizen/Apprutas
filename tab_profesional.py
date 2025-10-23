import streamlit as st
from uuid import uuid4

# Importamos SOLO el núcleo de utilidades (sin importar la UI)
# Debe existir app_utils_core.py en el repo (con suggest_addresses/build_*_url)
from app_utils_core import (
    suggest_addresses,
    build_gmaps_url,
    build_waze_url,
    build_apple_maps_url,
)

# -------------------------------
# Helpers de estado
# -------------------------------
def _init_state():
    """
    Inicializa claves necesarias en st.session_state para evitar KeyError.
    """
    ss = st.session_state
    ss.setdefault("prof_points", [])           # lista de puntos: [{id, address}, ...]
    ss.setdefault("selected_point_index", 0)   # índice del punto seleccionado
    ss.setdefault("prof_last_route_url", "")   # último URL generado de Google Maps
    ss.setdefault("prof_mode", "Más rápido")   # modo de ruta
    ss.setdefault("prof_avoid", "Ninguno")     # evitar
    ss.setdefault("prof_input", "")            # texto que estás escribiendo

def _add_point(address: str):
    address = (address or "").strip()
    if not address:
        return
    # ID único y estable para el punto (evita claves duplicadas en widgets)
    point = {"id": str(uuid4()), "address": address}
    st.session_state.prof_points.append(point)
    st.session_state.prof_input = ""  # limpia el input

def _remove_point(idx: int):
    if 0 <= idx < len(st.session_state.prof_points):
        del st.session_state.prof_points[idx]
        st.session_state.selected_point_index = max(0, min(st.session_state.selected_point_index, len(st.session_state.prof_points)-1))

def _move_point_up(idx: int):
    if 1 <= idx < len(st.session_state.prof_points):
        pts = st.session_state.prof_points
        pts[idx-1], pts[idx] = pts[idx], pts[idx-1]
        st.session_state.selected_point_index = idx-1

def _move_point_down(idx: int):
    pts = st.session_state.prof_points
    if 0 <= idx < len(pts)-1:
        pts[idx], pts[idx+1] = pts[idx+1], pts[idx]
        st.session_state.selected_point_index = idx+1

# -------------------------------
# Búsqueda con sugerencias simples (opcional)
# -------------------------------
def _search_box():
    col1, col2 = st.columns([4,1])
    with col1:
        val = st.text_input(
            "Escribe la dirección (mín. 3 letras) y pulsa ENTER",
            key="prof_input",  # clave estable
            placeholder="Ej: Passeig de Gràcia 1, Barcelona",
        )
    with col2:
        if st.button("Añadir", use_container_width=True):
            _add_point(val)

    # Sugerencias (no cambia la UI si no hay API)
    term = (st.session_state.get("prof_input") or "").strip()
    if len(term) >= 3:
        try:
            suggestions = suggest_addresses(term, key_bucket="prof_top", min_len=3)
            if suggestions:
                with st.expander("Sugerencias"):
                    for s in suggestions[:5]:
                        if st.button(f"➕ {s}", key=f"sugg_{hash(s)}"):
                            _add_point(s)
        except Exception as e:
            # No rompemos la UI si falla la API
            st.info("No se pudieron obtener sugerencias en este momento.")

# -------------------------------
# Render de la lista de puntos
# -------------------------------
def _render_points():
    st.subheader("Puntos de la ruta (orden de viaje)")
    pts = st.session_state.prof_points

    if not pts:
        st.info("Agregue al menos dos puntos (origen y destino) para generar la ruta.")
        return

    for i, p in enumerate(pts):
        # Cada fila con claves ÚNICAS
        c1, c2, c3, c4 = st.columns([6, 1, 1, 1])
        with c1:
            new_addr = st.text_input(
                label=f"address_{p['id']}",  # etiqueta única por id, no visible
                value=p["address"],
                key=f"addr_input_{p['id']}",
                label_visibility="collapsed",
            )
            if new_addr.strip() != p["address"]:
                p["address"] = new_addr.strip()

            etiqueta = "**Origen**" if i == 0 else ("**Destino**" if i == len(pts)-1 else f"**Parada {i}**")
            st.markdown(etiqueta + f":  {p['address']}")

        with c2:
            if st.button("▲", key=f"up_{p['id']}"):
                _move_point_up(i)
        with c3:
            if st.button("▼", key=f"down_{p['id']}"):
                _move_point_down(i)
        with c4:
            if st.button("🗑️", key=f"del_{p['id']}"):
                _remove_point(i)

# -------------------------------
# Construcción de URLs y botones
# -------------------------------
def _build_and_show_links():
    pts = st.session_state.prof_points
    if len(pts) < 2:
        st.warning("Necesitas al menos **origen** y **destino**.")
        return

    origin = pts[0]["address"]
    destination = pts[-1]["address"]
    waypoints = [p["address"] for p in pts[1:-1]]  # intermedias

    mode = st.session_state.get("prof_mode", "Más rápido")
    avoid = st.session_state.get("prof_avoid", "Ninguno")

    # Google Maps (acepta múltiples paradas)
    try:
        gmaps_url = build_gmaps_url(
            origin=origin,
            destination=destination,
            waypoints=waypoints,
            mode=mode,
            avoid=avoid,
            optimize=True,
        )
        st.session_state.prof_last_route_url = gmaps_url or ""
    except Exception as e:
        gmaps_url = None

    # Waze/Apple no soportan bien las múltiples paradas por URL pública -> solo O/D
    try:
        waze_url = build_waze_url(origin, destination)
    except Exception:
        waze_url = None

    try:
        apple_url = build_apple_maps_url(origin, destination)
    except Exception:
        apple_url = None

    # Enlaces (sin 'key', para evitar error de kwargs no soportado)
    cols = st.columns(3)
    with cols[0]:
        if gmaps_url:
            st.link_button("Abrir en Google Maps", url=gmaps_url, use_container_width=True)
        else:
            st.caption("Google Maps no disponible.")
    with cols[1]:
        if waze_url:
            st.link_button("Abrir en Waze", url=waze_url, use_container_width=True)
        else:
            st.caption("Waze no disponible.")
    with cols[2]:
        if apple_url:
            st.link_button("Abrir en Apple Maps", url=apple_url, use_container_width=True)
        else:
            st.caption("Apple Maps no disponible.")

# -------------------------------
# Panel principal
# -------------------------------
def mostrar_profesional():
    _init_state()

    st.markdown("Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final.")
    st.markdown("---")

    # Controles superiores
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox(
            "Tipo de ruta",
            ["Más rápido", "Corta", "Económica"],
            index=["Más rápido", "Corta", "Económica"].index(st.session_state.prof_mode),
            key="prof_mode"
        )
    with c2:
        st.selectbox(
            "Evitar",
            ["Ninguno", "Peajes", "Autopistas"],
            index=["Ninguno", "Peajes", "Autopistas"].index(st.session_state.prof_avoid),
            key="prof_avoid"
        )

    # Input de búsqueda + añadir
    _search_box()

    # Lista de puntos
    _render_points()

    st.markdown("---")
    if st.button("Generar ruta profesional"):
        _build_and_show_links()

    # Muestra el último enlace de Google Maps si existe (útil tras recargas)
    url = st.session_state.get("prof_last_route_url")
    if url:
        st.markdown(f"[Última ruta en Google Maps]({url})")
