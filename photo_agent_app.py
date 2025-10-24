# photo_agent_app.py  — PRUEBAS

import streamlit as st

# Config de página
st.set_page_config(page_title="Planificador de Rutas", layout="wide", initial_sidebar_state="expanded")

def _import_ui():
    """
    Carga robusta de la UI:
    1) from tab_profesional import mostrar_profesional
    2) importlib.import_module("tab_profesional.ui").mostrar_profesional
    """
    try:
        # Si el paquete está bien (tab_profesional/__init__.py), esto basta
        from tab_profesional import mostrar_profesional   # noqa
        return mostrar_profesional
    except Exception:
        # Fallback: importación directa del módulo ui.py
        import importlib, pathlib, sys
        here = pathlib.Path(__file__).resolve().parent
        if str(here) not in sys.path:
            sys.path.insert(0, str(here))
        mod = importlib.import_module("tab_profesional.ui")
        return getattr(mod, "mostrar_profesional")

def main():
    mostrar_profesional = _import_ui()
    mostrar_profesional()

if __name__ == "__main__":
    main()