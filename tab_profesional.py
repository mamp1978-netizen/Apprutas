import streamlit as st
# Ya no importamos streamlit_searchbox
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
# INICIALIZACIÓN DEL ESTADO DE SESIÓN (CRUCIAL para evitar KeyErrors)
# -------------------------------
if "prof_points" not in st.session_state:
    st.session_state["prof_points"] = []
    
# Claves para el nuevo sistema de búsqueda
if "prof_text_input" not in st.session_state:
    st.session_state["prof_text_input"] = ""
if "prof_top_suggestions" not in st.session_state:
    st.session_state["prof_top_suggestions"] = []
if "prof_selection" not in st.session_state:
    st.session_state["prof_selection"] = ""
    
# Clave para el estado de la ruta
if "prof_last_route_url" not in st.session_state:
    st.session_state["prof_last_route_url"] = None


# -------------------------------
# FUNCIONES DE MANEJO DE ESTADO Y LÓGICA
# -------------------------------
def _add_point_from_ui():
    """Añade la dirección seleccionada/escrita a la lista y limpia la barra."""
    
    # ... (El código de obtención de 'value' se mantiene igual) ...
        
    value = (value or "").strip()

    if not value:
        st.warning("Escribe una dirección y pulsa 'Buscar', o añade la dirección manualmente si ya está completa.")
        return

    # 1. Añadir a la lista
    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")
    
    # 2. Limpieza de estado
    st.session_state["prof_text_input"] = ""
    st.session_state["prof_top_suggestions"] = []
    st.session_state["prof_selection"] = ""
        
    # 3. NO FORZAMOS EL RE-RENDERIZADO AQUÍ. 
    # La adición de un punto causará un rerun "suave" automático.
    # Eliminamos: st.rerun() 
    
    # PERO, si estamos en Streamlit Cloud y la app no se refresca,
    # podemos usar este truco si la lista no se actualiza
    # (En la mayoría de los casos, un simple return debería bastar)
    pass # Dejamos que Streamlit maneje el rerun.

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
    
    # La API de Google es más eficiente con 3 o más caracteres
    if len(term) < 3:
        st.warning("Escribe al menos 3 caracteres para que la búsqueda sea efectiva.")
        st.session_state["prof_top_suggestions"] = [] # Asegura que no haya sugerencias viejas
        return
        
    # Llama a la función de la API de Google (AHORA SÓLO AQUÍ)
    suggestions = suggest_addresses(term, key_bucket="prof_top", min_len=3) 
    
    # Guarda las sugerencias para el selectbox
    st.session_state["prof_top_suggestions"] = suggestions
    
    if not suggestions:
        st.warning(f"No se encontraron sugerencias para '{term}'. Intenta añadirlo directamente.")
    else:
        # Si hay sugerencias, selecciona la primera por defecto
        st.session_state["prof_selection"] = suggestions[0]


# -------------------------------
# Componente de búsqueda y lógica de ubicación (REESCRITO)
# -------------------------------

def _search_box():
    st.markdown("---")
    
    # 1. ENTRADA DE TEXTO (ya no hace un rerun con cada letra)
    col_input, col_search = st.columns([4, 1])
    
    with col_input:
        st.text_input(
            "Buscar dirección...",
            key="prof_text_input",
            label_visibility="collapsed",
            placeholder="Escribe la dirección (mín. 3 letras) y pulsa 'Buscar'"
        )
    
    # 2. BOTÓN DE BÚSQUEDA MANUAL (fuerza la llamada a la API)
    with col_search:
        # El botón llama a la función de búsqueda
        st.button("🔎 Buscar", on_click=_run_search, use_container_width=True)


    # 3. SELECTBOX CON SUGERENCIAS (solo aparece si hay resultados)
    suggestions = st.session_state.get("prof_top_suggestions", [])
    
    if suggestions:
        st.selectbox(
            "Selecciona la sugerencia más precisa:",
            options=suggestions,
            key="prof_selection",
            label_visibility="visible"
        )
    # else: 
        # Ya no mostramos el mensaje de "no sugerencias" aquí, se gestiona en _run_search


    # 4. Botones de acción
    col_add, col_clear, col_loc = st.columns([1.5, 1, 3])

    with col_add:
        # El botón de Añadir ahora utiliza el valor guardado en prof_selection/prof_text_input
        st.button("Añadir", on_click=_add_point_from_ui, type="primary")

    with col_clear:
        st.button("Limpiar", on_click=_clear_points)

    # --- LÓGICA DE ACTIVACIÓN DE UBICACIÓN (se mantiene) ---
    with col_loc:
        is_loc_active = st.checkbox(
            "Usar mi ubicación", 
            key="prof_use_loc", 
            value=st.session_state.get("_loc_bias") is not None
        )
        
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
# Función principal de la pestaña (sin cambios, solo usa _search_box)
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

# USAMOS st.container() PARA AISLAR EL WIDGET PROBLEMÁTICO
point_list_container = st.container() 

with point_list_container:
    # render lista con funcionalidad de reordenación
    for i, p in enumerate(pts):
        # Usamos columnas para alinear la dirección y los botones de control
        col1, col2, col3, col4, col5 = st.columns([0.08, 0.08, 0.08, 0.68, 0.08])
        
        # --- Botones de Movimiento (col1 y col2) ---
        with col1:
            if i > 0: 
                # Asegúrate que los on_click handlers no generen problemas (pero son esenciales)
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
                
# En tab_profesional.py, en la función mostrar_profesional()

# ... (código anterior)

# 4. Botón Generar Ruta
st.markdown("---")

# En tab_profesional.py, en la función mostrar_profesional()

# ...
if st.button("Generar ruta profesional", type="primary"):
    if len(pts) < 2:
        st.warning("Deben haber dos o más puntos (origen y destino).")
        # --- AHORA ESTÁ EN LA INDENTACIÓN CORRECTA ---
        return 
        
    # El resto del código continúa con la indentación de 4 espacios (alineado con el 'if len(pts)')
    # --- 4.1 Resolución de Puntos ---
    origen_label = pts[0]
            
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