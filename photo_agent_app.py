import streamlit as st
import warnings

# Importa las funciones de cada pestaña.
from tab_profesional import mostrar_profesional
# from tab_viajero import mostrar_viajero # Descomentar cuando estén listas
# from tab_turistico import mostrar_turistico # Descomentar cuando estén listas

# --- Configuración de la página ---
st.set_page_config(
    page_title="Planificador de Rutas",
    page_icon="🗺️",
    layout="wide"
)

# Suprimir un warning específico de Google Maps que Streamlit no maneja bien
warnings.filterwarnings("ignore", category=UserWarning, module="googlemaps")

# --- Lógica principal de la aplicación ---
def main():
    """
    Función principal que renderiza la interfaz.
    """
    
    # Título principal y descripción
    st.title("🗺️ Planificador de Rutas")
    st.markdown("Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final.")
    
    # Creación de pestañas (tabs)
    tabs = ["Profesional", "Viajero", "Turístico"]
    
    # Usamos st.tabs para organizar el contenido
    tab_profesional, tab_viajero, tab_turistico = st.tabs(tabs)
    
    with tab_profesional:
        mostrar_profesional()
        
    # with tab_viajero:
    #     st.info("Funcionalidad en desarrollo.")
    #     # mostrar_viajero() 
        
    # with tab_turistico:
    #     st.info("Funcionalidad en desarrollo.")
    #     # mostrar_turistico()

if __name__ == "__main__":
    main()