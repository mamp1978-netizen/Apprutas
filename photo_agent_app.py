import streamlit as st
# import warnings # No es necesario si no lo usas

# --- 1. IMPORTACIONES ---
# Importa la función de la pestaña profesional
from tab_profesional import mostrar_profesional 
# from tab_viajero import mostrar_viajero   # Descomentar cuando estas pestañas estén listas
# from tab_turistico import mostrar_turistico # Descomentar cuando estas pestañas estén listas


# --- 2. CONFIGURACIÓN DE PÁGINA Y BARRA LATERAL ---
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

# ⭐️ IMPLEMENTACIÓN DEL CÓDIGO QR ⭐️

# 1. Muestra la imagen del QR para escanear
# Asegúrate de que 'qrcode.png' está en el directorio de tu aplicación
st.sidebar.image("qrcode.png", caption="Escanea para donar vía PayPal", use_column_width=True)

# 2. Opcionalmente, puedes mantener el botón/enlace directo de respaldo:
DONATION_URL = https://www.paypal.com/donate/?business=73LFHKS2WCQ9U&no_recurring=0&item_name=Ayuda+para+desarrolladores&currency_code=EUR # Sustituye por el enlace directo de PayPal.

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

st.sidebar.markdown("---") # Separador para limpiar la barra lateral

# ... (El resto del código de la función main() continúa abajo)

# --- 3. FUNCIÓN PRINCIPAL DE LA APLICACIÓN ---
def main():
    """Función principal que maneja la navegación por pestañas."""
    
    st.title("Planificador de Rutas")
    st.write(
        "Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final."
    )

    # Define las pestañas principales
    tab_prof, tab_viajero, tab_turistico = st.tabs(["Profesional", "Viajero", "Turístico"])

    # Muestra el contenido de cada pestaña
    with tab_prof:
        mostrar_profesional()
        
    with tab_viajero:
        st.info("Pestaña Viajero en construcción. ¡Vuelve pronto!")
        # mostrar_viajero() 
        
    with tab_turistico:
        st.info("Pestaña Turístico en construcción. ¡Vuelve pronto!")
        # mostrar_turistico()


# --- 4. EJECUCIÓN DEL PROGRAMA ---
if __name__ == "__main__":
    main()