import streamlit as st
from app_utils import (
    suggest_addresses,
    resolve_selection, 
    build_gmaps_url,
    build_waze_url, 
    build_apple_maps_url, 
    make_qr,
    set_location_bias,
    _use_ip_bias 
)
from io import BytesIO

# -------------------------------
# INICIALIZACIÓN DEL ESTADO DE SESIÓN (CRUCIAL)
# -------------------------------

# (Las funciones initialize_session_state, _force_rerun_with_clear, 
# _reset_point_selection, _add_point_from_ui, _clear_points, 
# _move_point, _delete_point, _enter_edit_mode, _save_point_from_toolbar, 
# _run_search, y _search_box NO NECESITAN CAMBIOS.)

# -------------------------------
# FUNCIONES DE MANEJO DE ESTADO Y LÓGICA (Mantenidas del código anterior)
# -------------------------------

def _force_rerun_with_clear():
    """Fuerza el re-renderizado."""
    st.rerun()

def _reset_point_selection():
    """Reinicia el estado de selección/edición al añadir/limpiar/eliminar un punto."""
    st.session_state["is_editing_point"] = False
    st.session_state["edit_input_value"] = ""
    # Intentamos mantener el selected_point_index en un valor válido
    if st.session_state["prof_points"]:
        st.session_state["selected_point_index"] = max(0, min(st.session_state["selected_point_index"], len(st.session_state["prof_points"]) - 1))
    else:
        st.session_state["selected_point_index"] = 0
    _force_rerun_with_clear()

# ... (El resto de _add_point_from_ui, _clear_points, _move_point, 
#      _delete_point, _enter_edit_mode, _save_point_from_toolbar, 
#      _run_search, _search_box se mantienen IGUAL) ...


# -------------------------------
# Función principal de la pestaña (MODIFICADA EN SECCIÓN 3)
# -------------------------------
def mostrar_profesional():
    
    initialize_session_state() 

    st.header("Ruta de trabajo")
    
    # 1. Opciones de ruta (Tipo y Evitar)
    col_mode, col_avoid = st.columns([1, 1])
    with col_mode:
        st.selectbox("Tipo de ruta", ["Más rápido", "Más corto"], key="prof_mode", label_visibility="visible")
    with col_avoid:
        st.selectbox("Evitar", ["Ninguno", "Peajes", "Ferries"], key="prof_avoid", label_visibility="visible")


    # 2. Barra de búsqueda
    _search_box()

    # 3. Lista de puntos y herramientas (Layout de LISTA COMPACTA)
    pts = st.session_state["prof_points"] 
    st.subheader("Puntos de la ruta (orden de viaje)")
    
    if not pts:
        st.info("Agregue al menos dos puntos (origen y destino) para generar la ruta.")
        return # Salir si no hay puntos

    current_index = st.session_state["selected_point_index"]
    is_editing = st.session_state["is_editing_point"]

    # 3.1. LISTADO DE PUNTOS CON SELECCIÓN VISUAL
    
    # Prepara las opciones formateadas
    options_formatted = []
    for i, p in enumerate(pts):
        prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}:")
        options_formatted.append(f"**{prefix}** {p}")
    
    # Usamos un radio button invisible para gestionar la selección del índice, 
    # pero mostraremos la lista completa de puntos.
    
    # Contenedor para el radio button y la lista
    container = st.container()
    
    with container:
        
        # El st.radio gestiona la selección del índice (0, 1, 2, ...)
        # Lo ponemos al final y lo hacemos invisible con CSS (si usas un custom CSS) 
        # o lo mantenemos visible si queremos que la UX sea simple.
        # Por simplicidad en Streamlit nativo, lo hacemos visible pero conciso:
        
        st.session_state["selected_point_index"] = st.radio(
            "Selecciona el punto a operar:",
            options=range(len(pts)),
            format_func=lambda x: f"Punto #{x}", # Etiqueta concisa
            index=current_index,
            key="selected_point_index_radio",
            horizontal=True,
            label_visibility="collapsed" # Ocultamos la etiqueta grande del radio
        )
        current_index = st.session_state["selected_point_index"]
        
        # Mostramos la lista de puntos
        for i, text in enumerate(options_formatted):
            
            # El punto seleccionado actualmente se resalta
            bg_color = "#E6F7FF" if i == current_index else "transparent"
            
            st.markdown(
                f"""
                <div style='background-color: {bg_color}; padding: 10px; border-radius: 5px; margin-bottom: 5px;'>
                    {text}
                </div>
                """,
                unsafe_allow_html=True
            )
            
        st.markdown("---")


    # 3.2. BARRA DE HERRAMIENTAS COMPACTA (Basada en el índice seleccionado)
    
    # Creamos la barra de herramientas fuera del bucle, ya que opera sobre el 'current_index'
    col_up, col_down, col_edit, col_del, _ = st.columns([1, 1, 1, 1, 3])
    
    with col_up:
        if current_index > 0 and not is_editing:
            st.button("⬆️ Mover Arriba", on_click=_move_point, args=("up",), use_container_width=True)
        else:
            st.button(" ", use_container_width=True, disabled=True, key="up_dis") # Placeholder
            
    with col_down:
        if current_index < len(pts) - 1 and not is_editing:
            st.button("⬇️ Mover Abajo", on_click=_move_point, args=("down",), use_container_width=True)
        else:
            st.button(" ", use_container_width=True, disabled=True, key="down_dis") # Placeholder
            
    with col_edit:
        if is_editing:
            st.button("💾 Guardar", on_click=_save_point_from_toolbar, use_container_width=True, type="primary")
        else:
            st.button("✏️ Editar", on_click=_enter_edit_mode, use_container_width=True)
            
    with col_del:
        if not is_editing:
            st.button("🗑️ Borrar", on_click=_delete_point, use_container_width=True)
        else:
            # Si estamos editando, mostramos un botón para cancelar
            st.button("❌ Cancelar", on_click=_reset_point_selection, use_container_width=True)


    # 3.3. CAMPO DE EDICIÓN
    if is_editing:
        st.text_input(
            f"Modificar punto seleccionado (Índice {current_index}):",
            value=st.session_state["edit_input_value"],
            key="edit_input_value",
            label_visibility="visible",
            on_change=_save_point_from_toolbar # Guardar al presionar ENTER
        )
        st.markdown("---") # Separador para el modo edición


    # 4. Botón Generar Ruta
    st.markdown("---")
    
    if st.button("Generar ruta profesional", type="primary", key="prof_generate_btn"):
        # ... (lógica de generación de URL) ...
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
        
        # --- 4.2 Generación de URLs ---
        avoid_map = {
            "Peajes": "tolls",
            "Ferries": "ferries",
            "Ninguno": None
        }
        
        gmaps_url = build_gmaps_url(
            origin=origen_meta["address"],
            destination=destino_meta["address"],
            waypoints=waypoints_resolved,
            mode="driving", 
            avoid=avoid_map.get(st.session_state["prof_avoid"]),
            optimize=True 
        )
        
        waze_url = build_waze_url(origen_meta["address"], destino_meta["address"], waypoints_resolved)
        apple_url = build_apple_maps_url(origen_meta["address"], destino_meta["address"], waypoints_resolved)
        
        # --- 4.3 Mostrar Resultados ---
        st.session_state.prof_last_route_url = gmaps_url # Usamos Google para el QR
        
        st.success("¡Ruta generada correctamente! 👇")
        
        col_gmaps, col_waze, col_apple = st.columns([1, 1, 1])
        
        with col_gmaps:
            st.markdown(f"**[🗺️ Google Maps]({gmaps_url})**")
        with col_waze:
            st.markdown(f"**[🚗 Waze]({waze_url})**")
        with col_apple:
            st.markdown(f"**[🍎 Apple Maps]({apple_url})**")


    # 5. Visualización del QR (si hay ruta generada)
    if st.session_state.prof_last_route_url:
        st.markdown("---")
        st.subheader("Última ruta generada (QR)")
        
        try:
            qr_bytes = make_qr(st.session_state.prof_last_route_url)
            
            col_qr, col_info = st.columns([1, 3])
            
            with col_qr:
                st.image(qr_bytes, caption="Escanea para abrir la ruta", use_container_width=True) 
            
            with col_info:
                st.info("Escanee el código QR con su teléfono para abrir la ruta en la aplicación de Google Maps de forma inmediata. Se han generado enlaces alternativos para Waze y Apple Maps.")

        except Exception as e:
            st.error(f"Error al generar el QR: {e}")