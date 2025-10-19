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
        # Aquí cre