# Contenido Completo de /workspaces/Apprutas/tab_profesional.py

import requests
import streamlit as st
from streamlit_searchbox import st_searchbox 
from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
    set_location_bias,
    _get_key,
    _use_ip_bias # Ya añadida a app_utils.py en el paso anterior
)

# -------------------------------
# Estado
# -------------------------------
def _init_state():
    ss = st.session_state
    ss.setdefault("prof_points", [])
    ss.setdefault("prof_last_route_url", None)
    ss.setdefault("prof_route_type", "Más rápido")
    ss.setdefault("prof_q", "") 

# -------------------------------
# Añadir punto según lo visible
# -------------------------------
def _add_point_from_ui():
    # El valor seleccionado (o escrito) por el usuario está en st.session_state["prof_q"]
    value = (st.session_state.get("prof_q") or "").strip()

    if not value or value.lower() in ["", "buscar dirección… (presione enter para agregar)"]:
        st.warning("Escribe o selecciona una dirección.")
        return

    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")
    
    # Limpiar la barra de búsqueda después de añadir
    st.session_state["prof_q"] = ""
    st.rerun()

# -------------------------------
# Buscador con comportamiento Google-like
# -------------------------------
def _search_box():
    # USAMOS st_searchbox
    selected_value = st_searchbox(
        search_function=suggest_addresses,
        label="Buscar dirección… (presione ENTER para agregar)",
        placeholder="Calle, número, ciudad… / Street, number, city…",
        key="prof_q_searchbox",
        default_value=st.session_state.get("prof_q", ""),
        # Parámetros para tu función suggest_addresses
        # CRUCIAL: Añadimos 'key_bucket' aquí para que se pase como **kwargs a suggest_addresses
        func_kwargs={
            "key_bucket": "prof_top", # <--- ESTE ES EL CAMBIO CLAVE
            "min_len": 1
        }
    )
    
    # El valor seleccionado/escrito se guarda en el estado para el botón "Añadir".
    st.session_state["prof_q"] = selected_value

    # --- Botones ---
    col1, col2, col3 = st.columns([0.28, 0.28, 0.44])
    with col1:
        submitted = st.button("Añadir (ENTER)", type="primary", key="add_btn")
    with col2:
        clear = st.button("Limpiar", key="clear_btn")
    with col3:
        geobias = st.button("📍 Usar mi ubicación", key="geo_btn")

    if submitted:
        _add_point_from_ui()
    if clear:
        st.session_state["prof_q"] = ""
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

        avoid_list = []
        if st.session_state.prof_route_type == "Evitar autopistas":
            avoid_list.append("highways")
        if st.session_state.prof_route_type == "Evitar peajes":
            avoid_list.append("tolls")
            
        url = build_gmaps_url(o["address"], d["address"], wp, avoid=avoid_list)
        st.session_state.prof_last_route_url = url
        st.success("Ruta generada correctamente ✅")
        st.write(url)
        st.image(make_qr(url), caption="Escanea el QR para abrir la ruta")

    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada"):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url))