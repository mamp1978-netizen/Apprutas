# photo_agent_app.py  (PRUEBAS)
import importlib, sys
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="Planificador de Rutas (PRUEBAS)",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _import_ui():
    """
    Importa la UI de forma robusta:
    1) intenta importar el paquete tab_profesional (que reexporta mostrar_profesional)
    2) si falla, añade el directorio del archivo al sys.path e importa tab_profesional.ui
    """
    try:
        mod = importlib.import_module("tab_profesional")
        return getattr(mod, "mostrar_profesional")
    except Exception:
        here = Path(__file__).resolve().parent
        if str(here) not in sys.path:
            sys.path.insert(0, str(here))
        mod = importlib.import_module("tab_profesional.ui")
        return getattr(mod, "mostrar_profesional")

mostrar_profesional = _import_ui()

def main():
    st.title("Planificador de Rutas 🧪 PRUEBAS")
    st.caption("UI cargada desde paquete tab_profesional")
    mostrar_profesional()

if __name__ == "__main__":
    main()