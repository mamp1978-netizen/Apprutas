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

def initialize_session_state():
    """Asegura que todas las claves necesarias existan en st.session_state."""
    if "prof_points" not in st.session_state:
        st.session_state["prof_points"] = []
    
    # Nuevo estado para la selección en la lista y el modo de edición.
    if "selected_point_index" not in st.session_state:
        st.session_state["selected_point_index"] = 0 # El índice seleccionado para operar
    if "is_editing_point" not in st.session_state:
        st.session_state["is_editing_point"] = False # Bandera para mostrar/ocultar el input de edición
    if "edit_input_value" not in st.session_state:
        st.session_state["edit_input_value"] = "" # Valor del input de edición
    
    # ... (Resto de inicializaciones de input, suggestions, etc.)
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
        

# -------------------------------
# FUNCIONES DE MANEJO DE ESTADO Y LÓGICA
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


def _add_point_from_ui():
    """Añade la dirección seleccionada/escrita a la lista y limpia la barra."""
    # ... (lógica de añadir punto) ...
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
    
    # Selecciona el nuevo punto y reinicia el modo edición
    st.session_state["selected_point_index"] = len(st.session_state["prof_points"]) - 1
    _reset_point_selection() # Force rerun is inside this function
    

def _clear_points():
    """Limpia la lista de puntos y el estado de la ruta."""
    st.session_state["prof_points"] = []
    st.session_state["prof_last_route_url"] = None
    st.session_state["prof_text_input"] = ""
    st.session_state["prof_top_suggestions"] = []
    st.session_state["prof_selection"] = ""
    st.session_state["selected_point_index"] = 0
    st.session_state["is_editing_point"] = False
    st.session_state["edit_input_value"] = ""

    _force_rerun_with_clear() 

# --- FUNCIONES DE MANEJO DE LA BARRA DE HERRAMIENTAS ---

def _move_point(direction: str):
    """Mueve el punto seleccionado arriba o abajo."""
    i = st.session_state["selected_point_index"]
    pts = st.session_state["prof_points"]
    
    if direction == "up" and i > 0:
        pts.insert(i-1, pts.pop(i))
        st.session_state["selected_point_index"] = i - 1
    elif direction == "down" and i < len(pts) - 1:
        pts.insert(i+1, pts.pop(i))
        st.session_state["selected_point_index"] = i + 1
        
    _reset_point_selection() # Force rerun is inside this function

def _delete_point():
    """Elimina el punto seleccionado."""
    i = st.session_state["selected_point_index"]
    if 0 <= i < len(st.session_state["prof_points"]):
        st.session_state["prof_points"].pop(i)
    _reset_point_selection()

def _enter_edit_mode():
    """Entra en modo edición, cargando el valor del punto seleccionado."""
    i = st.session_state["selected_point_index"]
    if 0 <= i < len(st.session_state["prof_points"]):
        st.session_state["is_editing_point"] = True
        st.session_state["edit_input_value"] = st.session_state["prof_points"][i]
    _force_rerun_with_clear()
    
def _save_point_from_toolbar():
    """Guarda el valor editado."""
    i = st.session_state["selected_point_index"]
    new_value = st.session_state["edit_input_value"].strip()
    
    if new_value and len(new_value) >= 3:
        st.session_state["prof_points"][i] = new_value
        st.success(f"Punto actualizado a: {new_value}")
        _reset_point_selection()
    else:
        st.warning("La dirección no puede estar vacía y debe tener al menos 3 letras.")


def _run_search():
    """Ejecuta la búsqueda de sugerencias (se llama on_change en el input)."""
    # ... (lógica de búsqueda de sugerencias) ...
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


# -------------------------------
# Componente de búsqueda y lógica de ubicación (Sin cambios)
# -------------------------------

def _search_box():
    # ... (código de _search_box sin cambios) ...
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

    # 3. Lista de puntos y herramientas (Layout compacto)
    pts = st.session_state["prof_points"] 
    st.subheader("Puntos de la ruta (orden de viaje)")
    
    if not pts:
        st.info("Agregue al menos dos puntos (origen y destino) para generar la ruta.")
        return # Salir si no hay puntos

    # 3.1. SELECCIÓN DE PUNTO CON FORMATO CORREGIDO
    options_formatted = []
    for i, p in enumerate(pts):
        prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}:")
        # Aquí creamos la cadena completa que queremos que se vea
        options_formatted.append(f"{i}. {prefix} {p}")
        
    # --- CORRECCIÓN CLAVE: Pasamos las opciones formateadas y usamos el índice como valor ---
    # Ya no necesitamos el format_func, ya que options_formatted ya contiene el texto que queremos.
    selected_option_index = st.selectbox(
        "Selecciona el punto a modificar:",
        options=options_formatted, # Pasamos la lista de strings completos
        index=st.session_state["selected_point_index"],
        key="selected_point_index_ui", # Usamos una clave de UI diferente para evitar conflictos de estado
        label_visibility="visible"
    )
    
    # Después del selectbox, actualizamos el índice de estado de sesión para el resto de la lógica
    # El valor devuelto por el selectbox (selected_option_index) es el índice de la opción seleccionada.
    st.session_state["selected_point_index"] = selected_option_index
    
    current_index = st.session_state["selected_point_index"]
    is_editing = st.session_state["is_editing_point"]
    
    # 3.2. BARRA DE HERRAMIENTAS COMPACTA
    col_up, col_down, col_edit, col_del, _ = st.columns([1, 1, 1, 1, 3])
    
    with col_up:
        if current_index > 0 and not is_editing:
            st.button("⬆️ Mover Arriba", on_click=_move_point, args=("up",), use_container_width=True)
        else:
            st.button(" ", use_container_width=True, disabled=True) # Placeholder
            
    with col_down:
        if current_index < len(pts) - 1 and not is_editing:
            st.button("⬇️ Mover Abajo", on_click=_move_point, args=("down",), use_container_width=True)
        else:
            st.button(" ", use_container_width=True, disabled=True) # Placeholder
            
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
            "Modificar la dirección seleccionada:",
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