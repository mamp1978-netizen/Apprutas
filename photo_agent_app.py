import importlib
import streamlit as st

# Configuración inicial de página
st.set_page_config(
    page_title="Planificador de Rutas (PRUEBAS)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Importación robusta de la UI ---
def _import_ui():
    """
    Intenta importar la UI de forma robusta:
    1) from tab_profesional import mostrar_profesional
    2) from tab_profesional.ui import mostrar_profesional
    """
    try:
        mod = importlib.import_module("tab_profesional")
        return getattr(mod, "mostrar_profesional")
    except Exception:
        mod = importlib.import_module("tab_profesional.ui")
        return getattr(mod, "mostrar_profesional")

mostrar_profesional = _import_ui()

# --- Función principal ---
def main():
    st.title("Planificador de Rutas 🧪 PRUEBAS")
    st.caption("Rama desarrollo")
    mostrar_profesional()

if __name__ == "__main__":
    main()