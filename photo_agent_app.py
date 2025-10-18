# --- EN photo_agent_app.py ---

import streamlit as st
import warnings

# Importa las funciones de cada pestaña.
from tab_profesional import mostrar_profesional # <- ESTA ES LA LÍNEA 5
# from tab_viajero import mostrar_viajero
# from tab_turistico import mostrar_turistico

# ... (resto del código) ...

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Planificador de Rutas",
    page_icon="🗺️",
    layout="wide"
)

# Suprimir advertencias de Streamlit (opcional, pero útil para limpiar la UI)
warnings.filterwarnings('ignore')

# --- TÍTULO Y DESCRIPCIÓN ---
st.title("🗺️ Planificador de Rutas")
st.markdown("Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final.")

# --- NAVEGACIÓN POR PESTAÑAS ---
# Si no has creado los otros archivos (tab_viajero.py y tab_turistico.py),
# debes comentar las líneas 8, 9 y 40-41 para evitar errores.
tab_profesional, tab_viajero, tab_turistico = st.tabs(["Profesional", "Viajero", "Turístico"])

with tab_profesional:
    mostrar_profesional()

# with tab_viajero:
#     # Si usas esta línea, asegúrate de que tab_viajero.py exista
#     # y que la función mostrar_viajero no requiera argumentos
#     # mostrar_viajero() 
#     st.info("La pestaña 'Viajero' aún no está implementada.")

# with tab_turistico:
#     # Si usas esta línea, asegúrate de que tab_turistico.py exista
#     # y que la función mostrar_turistico no requiera argumentos
#     # mostrar_turistico()
#     st.info("La pestaña 'Turístico' aún no está implementada.")