import importlib
import streamlit as st

st.set_page_config(page_title="Planificador de Rutas (PRUEBAS)", layout="wide", initial_sidebar_state="expanded")

def _import_ui():
    # 1) paquete con __init__.py
    try:
        mod = importlib.import_module("tab_profesional")
        return getattr(mod, "mostrar_profesional")
    except Exception:
        # 2) fallback al módulo ui
        mod = importlib.import_module("tab_profesional.ui")
        return getattr(mod, "mostrar_profesional")

mostrar_profesional = _import_ui()

def main():
    st.title("Planificador de Rutas 🧪 PRUEBAS")
    mostrar_profesional()

if __name__ == "__main__":
    main()
