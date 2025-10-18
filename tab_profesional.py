import streamlit as st
from app_utils import (
    suggest_addresses,
    resolve_selection, 
    build_gmaps_url,
    make_qr,
    set_location_bias,
    _use_ip_bias 
)
from io import BytesIO

# -------------------------------
# INICIALIZACIÓN DEL ESTADO DE SESIÓN (CRUCIAL)
# -------------------------------
# Aseguramos que todas las claves existan al inicio
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

if "prof_use_loc" not in st.session_state:
    st.session_state["prof_use_loc"] = False

if "_loc_bias" not in st.session_state:
    st.session_state["_loc_bias"] = None
    
# Inicialización de las opciones de ruta (si no existen)
if "prof_mode" not in st.session_state:
    st.session_state["prof_mode"] = "Más rápido"
if "prof_avoid" not in st.session_state:
    st.session_state["prof_avoid"] = "Ninguno"


# -------------------------------
# FUNCIONES DE MANEJO DE ESTADO Y LÓGICA
# -------------------------------

def _add_point_from_ui():
    """Añade la dirección seleccionada/escrita a la lista y limpia la barra."""
    
    # 1. DETERMINAR EL VALOR A AÑADIR (prioriza la selección)
    if st.session_state.get("prof_top_suggestions"):
        value = st.session_state.get("prof_selection")
    else:
        value = st.session_state.get("prof_text_input")
        
    value = (value or "").strip()

    if not value:
        st.warning("Escribe o selecciona una dirección válida.")
        return

    # 2. Añadir a la lista
    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")
    
    # 3. Limpieza de estado
    st.session_state["prof_text_input"] = ""
    st.session_state["prof_top_suggestions"] = []
    st.session_state["prof_selection"] = ""
    
    # IMPORTANTE: No usar st.rerun() aquí. Esto evita el error 'removeChild' en móvil.

def _clear_points():
    """Limpia la lista de puntos y el estado de la ruta."""
    st.session_state["prof_points"] = []
    st.session_state["prof_last_route_url"] = None
    
    # Limpieza del sistema de búsqueda
    st.session_state["prof_text_input"] = ""
    st.session_state["prof_top_suggestions"] = []
    st.session_state["prof_selection"] = ""

    st.rerun()

def _run_search():
    """Ejecuta la búsqueda de sugerencias manualmente."""
    term = st.session_state.get("prof_text_input", "").strip()
    
    if len(term) < 3:
        st.warning("Escribe al menos 3 caracteres para que la búsqueda sea efectiva.")
        st.session_state["prof_top_suggestions"] = []
        return
        
    # Llama a la función de la API de Google
    suggestions = suggest_addresses(term, key_bucket="prof_top", min_len=3) 
    
    # Guarda las sugerencias para el selectbox
    st.session_state["prof_top_suggestions"] = suggestions
    
    if not suggestions:
        st.warning(f"No se encontraron sugerencias para '{term}'.")
        st.session_state["prof_selection"] = ""
    else:
        # Si hay sugerencias, selecciona la primera por defecto
        st.session_state["prof_selection"] = suggestions[0]


# -------------------------------
# Componente de búsqueda y lógica de ubicación
# -------------------------------

def _search_box():
    st.markdown("---")
    
    # 1. ENTRADA DE TEXTO
    col_input, col_search = st.columns([4, 1])
    
    with col_input:
        st.text_input(
            "Buscar dirección...",
            key="prof_text_input",
            label_visibility="collapsed",
            placeholder="Escribe la dirección (mín. 3 letras) y pulsa 'Buscar'"
        )
    
    # 2. BOTÓN DE BÚSQUEDA MANUAL
    with col_search:
        st.button("🔎 Buscar", on_click=_run_search, use_container_width=True)


    # 3. SELECTBOX CON SUGERENCIAS
    suggestions = st.session_state.get("prof_top_suggestions", [])
    
    if suggestions:
        st.selectbox(
            "Selecciona la sugerencia más precisa:",
            options=suggestions,
            key="prof_selection",
            label_visibility="visible"
        )
    
    # 4. Botones de acción y ubicación
    col_add, col_clear, col_loc = st.columns([1.5, 1, 3])

    with col_add:
        st.button("Añadir", on_click=_add_point_from_ui, type="primary")

    with col_clear:
        st.button("Limpiar", on_click=_clear_points)

    # Lógica de ubicación
    with col_loc:
        is_loc_active = st.checkbox(
            "Usar mi ubicación", 
            key="prof_use_loc", 
            # Inicializamos el estado del checkbox con el estado de _loc_bias
            value=st.session_state.get("_loc_bias") is not None,
            help="Si está activado, la búsqueda se sesga a tu ubicación IP (solo en Streamlit Cloud)."
        )
        
        # Lógica para activar/desactivar el sesgo de ubicación
        if is_loc_active:
             if st.session_state.get("_loc_bias") is None:
                 _use_ip_bias()
                 st.rerun() 
        else:
             if st.session_state.get("_loc_bias") is not None:
                 del st.session_state["_loc_bias"]
                 st.rerun() 
                 
    st.markdown("---")


# -------------------------------
# Función principal de la pestaña
# -------------------------------
def mostrar_profesional():
    st.header("Ruta de trabajo")
    
# En tab_profesional.py, dentro de la función mostrar_profesional(), 
# en el bucle 'for i, p in enumerate(pts):'

# 1. Función para forzar el re-dibujado
def _force_rerun_with_clear():
    # El clear_memo_cache es el equivalente a forzar una limpieza del frontend
    st.experimental_memo.clear() 
    # El rerun forzado debe ser lo último
    st.rerun()

# 2. Modificación de los botones

# --- Botones de Movimiento (col1 y col2) ---
with col1:
    if i > 0: 
        if st.button("⬆️", key=f"up_{i}", help="Mover arriba", use_container_width=True):
            pts.insert(i-1, pts.pop(i))
            _force_rerun_with_clear() # <-- Llamamos a la nueva función aquí
with col2:
    if i < len(pts) - 1: 
        if st.button("⬇️", key=f"down_{i}", help="Mover abajo", use_container_width=True):
            pts.insert(i+1, pts.pop(i))
            _force_rerun_with_clear() # <-- Llamamos a la nueva función aquí

# --- Botón Eliminar (col5) ---
with col5:
    if st.button("🗑️", key=f"del_{i}", help="Eliminar punto", use_container_width=True):
        pts.pop(i)
        _force_rerun_with_clear() # <-- Llamamos a la nueva función aquí
        
    # 3. Lista de puntos (Origen, Destino, Paradas)
    pts = st.session_state["prof_points"] 
    
    st.subheader("Puntos de la ruta (orden de viaje)")
    
    if not pts:
        st.info("Agregue al menos dos puntos (origen y destino) para generar la ruta.")
    
    # USAMOS st.container() PARA AISLAR EL WIDGET PROBLEMÁTICO Y MEJORAR LA ESTABILIDAD EN MÓVILES
    point_list_container = st.container() 

    with point_list_container:
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
            return # <-- Indentación Correcta: Esto resuelve el error de Pylance
        
        # --- 4.1 Resolución de Puntos ---
        origen_label = pts[0]
        destino_label = pts[-1]
        waypoints_labels = pts[1:-1]
        
        # Resolvemos el origen y destino
        origen_meta = resolve_selection(origen_label, "prof_top")
        destino_meta = resolve_selection(destino_label, "prof_top")
        
        # Resolvemos los waypoints (solo necesitamos la dirección formateada)
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
                st.image(qr_bytes, caption="Escanea para abrir la ruta", use_container_width=True)
                        
            with col_info:
                st.info("Escanee el código QR con su teléfono para abrir la ruta en la aplicación de Google Maps de forma inmediata.")

        except Exception as e:
            st.error(f"Error al generar el QR: {e}")