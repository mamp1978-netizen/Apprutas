import streamlit as st

# siempre set_page_config lo primero
st.set_page_config(page_title="Planificador de Rutas", layout="wide", initial_sidebar_state="expanded")

# Import robusto de la UI (usa __init__.py del paquete)
from tab_profesional import mostrar_profesional

def main():
    st.title("Planificador de Rutas")
    st.write("Crea rutas con paradas usando direcciones completas.")

    # (si luego añades más pestañas, aquí)
    mostrar_profesional()

if __name__ == "__main__":
    main()
