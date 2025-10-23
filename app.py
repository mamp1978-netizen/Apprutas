import streamlit as st

# --- Config básica de la página ---
st.set_page_config(
    page_title="Planificador de Rutas",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Barra lateral (opcional, igual que prod) ---
st.sidebar.markdown("---")
st.sidebar.subheader("Apoya el desarrollo 🧑‍💻")
st.sidebar.info(
    "¿Te ha sido útil este planificador de rutas? "
    "Considera una pequeña donación para ayudarme a mantener y mejorar la aplicación."
)

# --- UI principal ---
from tab_profesional import mostrar_profesional

def main():
    st.title("Planificador de Rutas")
    mostrar_profesional()

if __name__ == "__main__":
    main()
