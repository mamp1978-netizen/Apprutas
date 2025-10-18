# Contenido COMPLETO y CORREGIDO FINAL de tab_profesional.py

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

# --- Estado de Sesión ---
if "prof_points" not in st.session_state:
    st.session_state["prof_points"] = []
if "prof_q" not in st.session_state:
    st.session_state["prof_q"] = ""
if "prof_last_route_url" not in st.session_state:
    st.session_state["prof_last_route_url"] = None

# -------------------------------
# Componente de búsqueda
# -------------------------------
# --- EN /workspaces/Apprutas/tab_profesional.py (función _search_box) ---
def _search_box():
    st.markdown("---")
    
    # CRUCIAL: 'key_bucket' y 'min_len' deben pasarse como keyword arguments
    # para que suggest_addresses los extraiga de **kwargs.
    func_kwargs={
        "key_bucket": "prof_top", # <-- ESTO HACE QUE VUELVA A FUNCIONAR
        "min_len": 1
    }
    
    # La barra de búsqueda
    selected_value = st_searchbox(
        search_function=suggest_addresses,
        placeholder="Buscar dirección... (presione ENTER para agregar)",
        # 'key' del widget: CRUCIAL para poder resetearlo
        key="prof_q_searchbox",
        # 'default_value' del widget: Toma el valor de sesión
        default_value=st.session_state.get("prof_q", ""),
        # argumentos pasados a suggest_addresses
        func_kwargs=func_kwargs, # <-- Se pasa el diccionario de argumentos
        label="Ruta de trabajo",
        label_visibility="collapsed"
    )

    # Actualiza la variable de sesión
    st.session_state["prof_q"] = selected_value

    # Botones de acción
    col_add, col_clear, col_loc = st.columns([1.5, 1, 3])

    with col_add:
        st.button("Añadir (ENTER)", on_click=_add_point_from_ui, type="primary")

    with col_clear:
        st.button("Limpiar", on_click=_clear_points)

    with col_loc:
        st.checkbox("Usar mi ubicación", key="prof_use_loc", value=False)
        # Opcional: Llama a la función de sesgo de ubicación si se activa
        if st.session_state["prof_use_loc"] and not st.session_state.get("_loc_bias"):
            _use_ip_bias() # Esto es un intento de geolocalización, puede fallar

    st.markdown("---")

# -------------------------------
# Añadir punto según lo visible
# -------------------------------
def _add_point_from_ui():
    """Añade la dirección seleccionada/escrita a la lista y limpia la barra."""
    # Intentamos resolver el valor de la barra de búsqueda (selected_value)
    value = (st.session_state.get("prof_q") or "").strip()

    if not value or value.lower() in ["", "buscar dirección… (presione enter para agregar)"]:
        st.warning("Escribe o selecciona una dirección.")
        return

    # Añadir a la lista
    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")
    
    # LIMPIEZA DE LA BARRA DE BÚSQUEDA
    # 1. Limpiamos la variable de estado principal.
    st.session_state["prof_q"] = ""
    # 2. Limpiamos el valor del widget st_searchbox usando su clave única.
    st.session_state["prof_q_searchbox"] = "" 
    
    st.rerun() # Recarga el script para reflejar el punto añadido y la barra limpia

def _clear_points():
    st.session_state["prof_points"] = []
    st.session_state["prof_last_route_url"] = None

# -------------------------------
# Lógica de la ruta
# -------------------------------
def mostrar_profesional():
    st.header("Ruta de trabajo")
    
    # 1. Opciones de ruta (Tipo y Evitar)
    col_mode, col_avoid = st.columns([1, 1])
    with col_mode:
        st.selectbox("Tipo de ruta", ["Más rápido", "Más corto"], key="prof_mode", label_visibility="collapsed")
    with col_avoid:
        # Aquí puedes añadir un selectbox o multiselect para evitar cosas
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
            # Solo permite mover arriba si no es el Origen (i > 0)
            if i > 0: 
                if st.button("⬆️", key=f"up_{i}", help="Mover arriba", use_container_width=True):
                    pts.insert(i-1, pts.pop(i)) # Mueve el elemento actual a la posición anterior
                    st.rerun()
        with col2:
            # Solo permite mover abajo si no es el Destino (i < len(pts) - 1)
            if i < len(pts) - 1: 
                if st.button("⬇️", key=f"down_{i}", help="Mover abajo", use_container_width=True):
                    pts.insert(i+1, pts.pop(i)) # Mueve el elemento actual a la posición siguiente
                    st.rerun()

        # --- Etiqueta (col4) ---
        with col4:
            prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}:")
            # Usamos markdown para darle un estilo claro a la lista
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
        # El primer punto es el Origen, el último es el Destino
        origen_label = pts[0]
        destino_label = pts[-1]
        
        # Paradas intermedias (Waypoints)
        waypoints_labels = pts[1:-1]
        
        # Resolvemos las etiquetas a coordenadas/direcciones completas
        origen_meta = resolve_selection(origen_label, "prof_top")
        destino_meta = resolve_selection(destino_label, "prof_top")
        
        waypoints_resolved = [
            resolve_selection(label, "prof_top")["address"]
            for label in waypoints_labels
        ]
        
        # --- 4.2 Generación de URL ---
        # El modo 'Más rápido' o 'Más corto' no afecta directamente a la URL de Google Maps,
        # pero la optimización de los waypoints sí.
        
        # Mapeo del 'Evitar'
        avoid_map = {
            "Peajes": "tolls",
            "Ferries": "ferries",
            "Ninguno": None
        }
        
        route_url = build_gmaps_url(
            origin=origen_meta["address"],
            destination=destino_meta["address"],
            waypoints=waypoints_resolved,
            mode="driving", # Se usa 'driving' por defecto
            avoid=avoid_map.get(st.session_state["prof_avoid"]),
            optimize=True # Asumimos que un profesional siempre quiere la ruta optimizada
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