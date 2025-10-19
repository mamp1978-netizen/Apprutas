import streamlit as st
from app_utils import (
    suggest_addresses,
    resolve_selection, 
    build_gmaps_url,
    build_waze_url,  # <-- NUEVA FUNCIÓN
    build_apple_maps_url, # <-- NUEVA FUNCIÓN
    make_qr,
    set_location_bias,
    _use_ip_bias 
)
from io import BytesIO

# -------------------------------
# INICIALIZACIÓN DEL ESTADO DE SESIÓN (CRUCIAL)
# -------------------------------

def initialize_session_state():
    """Asegura que todas las claves necesarias existan en st.session_state."""
    if "prof_points" not in st.session_state:
        st.session_state["prof_points"] = []
        
    if "prof_text_input" not in st.session_state:
        st.session_state["prof_text_input"] = ""
    if "prof_top_suggestions" not in st.session_state:
        st.session_state["prof_top_suggestions"] = []
    if "prof_selection" not in st.session_state:
        st.session_state["prof_selection"] = ""
        
    if "prof_last_route_url" not in st.session_state:
        st.session_state["prof_last_route_url"] = None

    if "prof_use_loc_cb" not in st.session_state:
        st.session_state["prof_use_loc_cb"] = False

    if "_loc_bias" not in st.session_state:
        st.session_state["_loc_bias"] = None
        
    if "prof_mode" not in st.session_state:
        st.session_state["prof_mode"] = "Más rápido"
    if "prof_avoid" not in st.session_state:
        st.session_state["prof_avoid"] = "Ninguno"
        
    if "edit_index" not in st.session_state: # <-- NUEVA CLAVE DE ESTADO
        st.session_state["edit_index"] = None


# -------------------------------
# FUNCIONES DE MANEJO DE ESTADO Y LÓGICA
# -------------------------------

def _force_rerun_with_clear():
    """Fuerza el re-renderizado."""
    st.rerun()


def _add_point_from_ui():
    """Añade la dirección seleccionada/escrita a la lista y limpia la barra."""
    
    value = ""
    if st.session_state.get("prof_top_suggestions"):
        value = st.session_state.get("prof_selection")
    else:
        value = st.session_state.get("prof_text_input")
        
    value = (value or "").strip()

    if not value:
        st.warning("Escribe o selecciona una dirección válida.")
        return

    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")
    
    st.session_state["prof_text_input"] = ""
    st.session_state["prof_top_suggestions"] = []
    st.session_state["prof_selection"] = ""
    
    _force_rerun_with_clear()
    

def _clear_points():
    """Limpia la lista de puntos y el estado de la ruta."""
    st.session_state["prof_points"] = []
    st.session_state["prof_last_route_url"] = None
    st.session_state["edit_index"] = None # Limpiar estado de edición

    st.session_state["prof_text_input"] = ""
    st.session_state["prof_top_suggestions"] = []
    st.session_state["prof_selection"] = ""

    _force_rerun_with_clear() 

def _run_search():
    """Ejecuta la búsqueda de sugerencias (se llama on_change en el input)."""
    term = st.session_state.get("prof_text_input", "").strip()
    
    if len(term) >= 3:
        suggestions = suggest_addresses(term, key_bucket="prof_top", min_len=3) 
        st.session_state["prof_top_suggestions"] = suggestions
        
        if not suggestions:
            st.warning(f"No se encontraron sugerencias para '{term}'.")
            st.session_state["prof_selection"] = ""
        else:
            st.session_state["prof_selection"] = suggestions[0]
    else:
        st.session_state["prof_top_suggestions"] = []
        st.session_state["prof_selection"] = ""


# --- FUNCIONES PARA LA EDICIÓN DE PUNTOS ---
def _set_edit_mode(index):
    """Establece el índice a editar y carga el valor actual."""
    st.session_state["edit_index"] = index
    # Cargamos el valor actual del punto en la key del input temporal
    st.session_state[f"edit_text_input_{index}"] = st.session_state["prof_points"][index]
    st.rerun()

def _save_point(index):
    """Guarda la nueva dirección del punto editado y sale del modo de edición."""
    # Obtenemos el valor del input temporal creado en el bucle
    new_value = st.session_state.get(f"edit_text_input_{index}", "").strip()
    
    if new_value and len(new_value) >= 3:
        # 1. Actualiza el punto
        st.session_state["prof_points"][index] = new_value
        # 2. Sale del modo de edición
        st.session_state["edit_index"] = None
        st.success(f"Punto actualizado a: {new_value}")
        
        # Eliminamos el input temporal y forzamos re-run
        if f"edit_text_input_{index}" in st.session_state:
            del st.session_state[f"edit_text_input_{index}"]
        _force_rerun_with_clear()
    else:
        st.warning("La dirección no puede estar vacía y debe tener al menos 3 letras.")
        # No salimos del modo de edición para que el usuario pueda corregir


# -------------------------------
# Componente de búsqueda y lógica de ubicación
# -------------------------------

def _search_box():
    st.markdown("---")
    
    # 1. ENTRADA DE TEXTO
    st.text_input(
        "Buscar dirección...",
        key="prof_text_input",
        label_visibility="collapsed",
        placeholder="Escribe la dirección (mín. 3 letras) y pulsa ENTER",
        on_change=_run_search 
    )
    
    # 2. SELECTBOX CON SUGERENCIAS
    suggestions = st.session_state.get("prof_top_suggestions", [])
    
    if suggestions:
        st.selectbox(
            "Selecciona la sugerencia más precisa:",
            options=suggestions,
            key="prof_selection",
            label_visibility="visible"
        )
    
    # 3. Botones de acción y ubicación (claves únicas para evitar DuplicateElement)
    col_add, col_clear, col_loc = st.columns([1.5, 1, 3])

    with col_add:
        st.button(
            "Añadir", 
            on_click=_add_point_from_ui, 
            type="primary",
            key="prof_add_btn" 
        )

    with col_clear:
        st.button("Limpiar", on_click=_clear_points, key="prof_clear_btn")

    # Lógica de ubicación
    with col_loc:
        is_loc_active = st.checkbox(
            "Usar mi ubicación", 
            key="prof_use_loc_cb", 
            value=st.session_state.get("_loc_bias") is not None,
            help="Si está activado, la búsqueda se sesga a tu ubicación IP."
        )
        
        if is_loc_active:
             if st.session_state.get("_loc_bias") is None:
                 _use_ip_bias()
                 _force_rerun_with_clear()
        else:
             if st.session_state.get("_loc_bias") is not None:
                 del st.session_state["_loc_bias"]
                 _force_rerun_with_clear()
                 
    st.markdown("---")


# -------------------------------
# Función principal de la pestaña
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

    # 3. Lista de puntos (Origen, Destino, Paradas)
    pts = st.session_state["prof_points"] 
    
    st.subheader("Puntos de la ruta (orden de viaje)")
    
    if not pts:
        st.info("Agregue al menos dos puntos (origen y destino) para generar la ruta.")
    
    point_list_container = st.container() 

    with point_list_container:
        edit_index = st.session_state.get("edit_index") # Obtener el índice que se está editando
        
        for i, p in enumerate(pts):
            # Aumentamos las columnas para el botón de edición
            col1, col2, col3, col4, col5 = st.columns([0.08, 0.08, 0.1, 0.64, 0.1])
            
            # --- Botones de Movimiento ---
            with col1:
                if i > 0: 
                    if st.button("⬆️", key=f"up_{i}", help="Mover arriba", use_container_width=True):
                        pts.insert(i-1, pts.pop(i))
                        _force_rerun_with_clear() 
            with col2:
                if i < len(pts) - 1: 
                    if st.button("⬇️", key=f"down_{i}", help="Mover abajo", use_container_width=True):
                        pts.insert(i+1, pts.pop(i))
                        _force_rerun_with_clear()

            # --- Columna de Edición ---
            with col3:
                if edit_index == i:
                    # Si estamos editando, mostramos el botón GUARDAR
                    st.button("💾", key=f"save_{i}", help="Guardar cambios", on_click=_save_point, args=(i,), use_container_width=True, type="primary")
                else:
                    # Si NO estamos editando, mostramos el botón EDITAR
                    st.button("✏️", key=f"edit_{i}", help="Editar punto", on_click=_set_edit_mode, args=(i,), use_container_width=True)


            # --- Columna de Texto/Input ---
            with col4:
                prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}:")
                
                if edit_index == i:
                    # Mostramos el input de texto editable
                    # Usamos el key creado en _set_edit_mode para el valor
                    st.text_input(
                        prefix, 
                        key=f"edit_text_input_{i}", 
                        label_visibility="visible"
                    )
                else:
                    # Mostramos la etiqueta estática
                    st.markdown(f"**{prefix}**: {p}")
            
            # --- Botón Eliminar ---
            with col5:
                if st.button("🗑️", key=f"del_{i}", help="Eliminar punto", use_container_width=True):
                    # Si eliminamos un punto, salimos del modo de edición
                    st.session_state["edit_index"] = None
                    pts.pop(i)
                    _force_rerun_with_clear()
                
    # 4. Botón Generar Ruta
    st.markdown("---")
    
    if st.button("Generar ruta profesional", type="primary", key="prof_generate_btn"):
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
        
        # Google Maps (la más completa y que se usa para QR)
        gmaps_url = build_gmaps_url(
            origin=origen_meta["address"],
            destination=destino_meta["address"],
            waypoints=waypoints_resolved,
            mode="driving", 
            avoid=avoid_map.get(st.session_state["prof_avoid"]),
            optimize=True 
        )
        
        # Waze
        waze_url = build_waze_url(origen_meta["address"], destino_meta["address"], waypoints_resolved)
        
        # Apple Maps
        apple_url = build_apple_maps_url(origen_meta["address"], destino_meta["address"], waypoints_resolved)
        
        # --- 4.3 Mostrar Resultados ---
        st.session_state.prof_last_route_url = gmaps_url # Usamos Google para el QR
        
        st.success("¡Ruta generada correctamente! 👇")
        
        # Mostrar enlaces de navegación en columnas
        col_gmaps, col_waze, col_apple = st.columns([1, 1, 1])
        
        with col_gmaps:
            st.write(f"[🗺️ Google Maps]({gmaps_url})")
        with col_waze:
            st.write(f"[🚗 Waze]({waze_url})")
        with col_apple:
            st.write(f"[🍎 Apple Maps]({apple_url})")


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
                st.info("Escanee el código QR con su teléfono para abrir la ruta en la aplicación de Google Maps de forma inmediata.")

        except Exception as e:
            st.error(f"Error al generar el QR: {e}")