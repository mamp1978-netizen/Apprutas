# photo_agent_app.py
import streamlit as st
from tab_profesional import mostrar_profesional   # <— import simple

def main():
    st.set_page_config(page_title="Planificador de Rutas", layout="wide")
    mostrar_profesional()

if __name__ == "__main__":
    main()

# --- 2. CONFIGURACIÓN DE PÁGINA Y BARRA LATERAL (DONACIONES) ---
st.set_page_config(
    page_title="Planificador de Rutas",
    layout="wide", 
    initial_sidebar_state="expanded" 
)

# Sección de Donaciones en la Barra Lateral
st.sidebar.markdown("---")
st.sidebar.subheader("Apoya el desarrollo 🧑‍💻")
st.sidebar.info(
    "¿Te ha sido útil este planificador de rutas? "
    "Considera una pequeña donación para ayudarme a mantener y mejorar la aplicación."
)

# CORRECCIÓN DE SINTAXIS: La URL está correctamente encapsulada.
DONATION_URL = "https://www.paypal.com/donate/?business=73LFHKS2WCQ9U&no_recurring=0&item_name=Ayuda+para+desarrolladores&currency_code=EUR" 

# Muestra el botón de enlace directo
st.sidebar.markdown(
    f"""
    <a href="{DONATION_URL}" target="_blank">
        <button style="background-color: #0070BA; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; width: 100%;">
            Ir al enlace de donación
        </button>
    </a>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("---") 


# --- 3. FUNCIÓN PRINCIPAL DE LA APLICACIÓN ---
def main():
    
    st.title("Planificador de Rutas")
    st.write(
        "Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final."
    )

    tab_prof, tab_viajero, tab_turistico = st.tabs(["Profesional", "Viajero", "Turístico"])

    with tab_prof:
        mostrar_profesional()
        
    with tab_viajero:
        st.info("Pestaña Viajero en construcción. ¡Vuelve pronto!")
        
    with tab_turistico:
        st.info("Pestaña Turístico en construcción. ¡Vuelve pronto!")


# --- 4. EJECUCIÓN DEL PROGRAMA ---
if __name__ == "__main__":
    main()