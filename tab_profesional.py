# Contenido COMPLETO, FINAL y CORREGIDO de tab_profesional.py

import streamlit as st
from streamlit_searchbox import st_searchbox 
from app_utils import (
    suggest_addresses,
    resolve_selection, 
    build_gmaps_url,
    make_qr,
    set_location_bias,
    _get_key,
    _use_ip_bias 
)
from io import BytesIO

# -------------------------------
# INICIALIZACIÓN DEL ESTADO DE SESIÓN (CRUCIAL para evitar KeyErrors)
# -------------------------------
if "prof_points" not in st.session_state:
    st.session_state["prof_points"] = []
if "prof_q" not in st.session_state:
    st.session_state["prof_q"] = ""
if "prof_last_route_url" not in st.session_state:
    st.session_state["prof_last_route_url"] = None
# La clave '_loc_bias' se gestiona aquí y en app_utils.py

# -------------------------------
# Componente de búsqueda y lógica de ubicación
# -------------------------------
def _search_box():
    st.markdown("---")
    
    # Parámetros para la función suggest_addresses
    func_kwargs={
        "key_bucket": "prof_top",
        "min_len": 1 
    }
    
    # La barra de búsqueda (st_searchbox)
    selected_value = st_searchbox(
        search_function=suggest_addresses,
        placeholder="Buscar dirección... (presione ENTER para agregar)",
        # 'key' del widget: CRUCIAL para poder resetearlo
        key="prof_q_searchbox",
        # 'default_value' del widget:
        default_value=st.session_state.get("prof_q", ""),
        # argumentos pasados a suggest_addresses
        func_kwargs=func_kwargs,
        label="Ruta de trabajo",
        label_visibility="collapsed"
    )

    st.session_state["prof_q"] = selected_value

    # Botones de acción
    col_add, col_clear, col_loc = st.columns([1.5, 1, 3])

    with col_add:
        st.button("Añadir (ENTER)", on_click=_add_point_from_ui, type="primary")

    with col_clear:
        st.button("Limpiar", on_click=_clear_points)

    # --- LÓGICA DE ACTIVACIÓN DE UBICACIÓN (MODIFICACIÓN) ---
    with col_loc:
        # Checkbox que activa/desactiva el sesgo
        is_loc_active = st.checkbox("Usar mi ubicación", key="prof_use_loc", value=st.session_state.get("_loc_bias") is not None)
        
        if is_loc_active:
             # Si se activa el checkbox y NO HAY sesgo, lo creamos.
             if st.session_state.get("_loc_bias") is None:
                 _use_ip_bias() # Establece el sesgo en st.session_state["_loc_bias"]
                 st.rerun() # Recarga para que suggest_addresses lea el nuevo sesgo
        else:
             # Si se desactiva el checkbox y SÍ HAY sesgo, lo eliminamos.
             if st.session_state.get("_loc_bias") is not None:
                 del st.session_state["_loc_bias"]
                 st.rerun() # Recarga para que suggest_addresses deje de usar el sesgo
                 
    st.markdown("---")

# -------------------------------
# Añadir punto y limpiar UI
# -------------------------------
def _add_point_from_ui():
    """Añade la dirección seleccionada/escrita a la lista y limpia la barra."""
    value = (st.session_state.get("prof_q") or "").strip()

    if not value or value.lower() in ["", "buscar dirección… (presione enter para agregar)"]:
        st.warning("Escribe o selecciona una dirección.")
        return

    # Añadir a la lista
    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")
    
    # Limpiar el estado del widget y del cache de opciones del searchbox (CORRECCIÓN)
    st.session_state["prof_q"] = ""
    st.session_state["prof_q_searchbox"] = ""
    
    # Soluciona: TypeError: list indices must be integers, not str
    if 'prof_q_searchboxoptions_ts' in st.session_state:
        del st.session_state['prof_q_searchboxoptions_ts'] 
        
    st.rerun()

def _clear_points():
    st.session_state["prof_points"] = []
    st.session_state["prof_last_route_url"] = None
    if 'prof_q_searchboxoptions_ts' in st.session_state:
        del st.session_state['prof_q_searchboxoptions_ts']
    st.rerun()


# -------------------------------
# Función principal de la pestaña
# -------------------------------
def mostrar_profesional():
    st.header("Ruta de trabajo")
    
    # 1. Opciones de ruta (Tipo y Evitar)
    col_mode, col_avoid = st.columns([1, 1])
    with col_mode:
        st.selectbox("Tipo de ruta", ["Más rápido", "Más corto"], key="prof_mode", label_visibility="collapsed")
    with col_avoid:
        st.selectbox("Evitar", ["Ninguno", "Peajes", "Ferries"], key="prof_avoid", label_visibility="collapsed")


    # 2. Barra de búsqueda
    _search_box()

    # 3. Lista de puntos (Origen, Destino, Paradas)
    pts = st.session_state["prof_points"] 
    
    st.subheader("Puntos de la ruta (orden de viaje)")
    
    if not pts:
        st.info("Agregue al menos dos puntos (origen y destino) para generar la ruta.")
    
    # render lista con funcionalidad de reordenación
    for i, p in enumerate(pts):
        # Usamos columnas para alinear la dirección y los botones de control
        col1, col2, col3, col4, col5 = st.columns([0.08, 0.08, 0.08, 0.68, 0.08])
        
        # --- Botones de Movimiento (col1 y col2) ---
        with col1:
            if i > 0: 
                if st.button("⬆️", key=f"up_{i}", help="Mover arriba", use_container_width=True):
                    pts.insert(i-1, pts.pop(i))
                    st.rerun()
        with col2:
            if i < len(pts) - 1: 
                if st.button("⬇️", key=f"down_{i}", help="Mover abajo", use_container_width=True):
                    pts.insert(i+1, pts.pop(i))
                    st.rerun()

        # --- Etiqueta (col4) ---
        with col4:
            prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}:")
            st.markdown(f"**{prefix}**: {p}")
        
        # --- Botón Eliminar (col5) ---
        with col5:
            if st.button("🗑️", key=f"del_{i}", help="Eliminar punto", use_container_width=True):
                pts.pop(i)
                st.rerun()
                
    # 4. Botón Generar Ruta
    st.markdown("---")
    
    if st.button("Generar ruta profesional", type="primary"):
        if len(pts) < 2:
            st.warning("Deben haber dos o más puntos (origen y destino).")
            return
        
        # --- 4.1 Resolución de Puntos ---
        origen_label = pts[0]
        destino_label = pts[-1]
        waypoints_labels = pts[1:-1]
        
        origen_meta = resolve_selection(origen_label, "prof_top")
        destino_meta = resolve_selection(destino_label, "prof_top")
        
        waypoints_resolved = [
            resolve_selection(label, "prof_top")["address"]
            for label in waypoints_labels
        ]
        
        # --- 4.2 Generación de URL ---
        avoid_map = {
            "Peajes": "tolls",
            "Ferries": "ferries",
            "Ninguno": None
        }
        
        route_url = build_gmaps_url(
            origin=origen_meta["address"],
            destination=destino_meta["address"],
            waypoints=waypoints_resolved,
            mode="driving", 
            avoid=avoid_map.get(st.session_state["prof_avoid"]),
            optimize=True 
        )
        
        # --- 4.3 Mostrar Resultados ---
        st.session_state.prof_last_route_url = route_url
        st.success("¡Ruta generada correctamente! 👇")
        st.write(f"[Abrir en Google Maps (URL)]({route_url})")

    # 5. Visualización del QR (si hay ruta generada)
    if st.session_state.prof_last_route_url:
        st.markdown("---")
        st.subheader("Última ruta generada (QR)")
        
        # Generar QR
        try:
            qr_bytes = make_qr(st.session_state.prof_last_route_url)
            
            col_qr, col_info = st.columns([1, 3])
            
            with col_qr:
                st.image(qr_bytes, caption="Escanea para abrir la ruta", use_column_width=True)
            
            with col_info:
                st.info("Escanee el código QR con su teléfono para abrir la ruta en la aplicación de Google Maps de forma inmediata.")

        except Exception as e:
            st.error(f"Error al generar el QR: {e}")