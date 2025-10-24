cd ~/proyectos/apprutas
git switch desarrollo

cat > photo_agent_app.py <<'PY'
import importlib
import streamlit as st

# Siempre primero:
st.set_page_config(page_title="Planificador de Rutas", layout="wide", initial_sidebar_state="expanded")

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
        # fallback
        mod = importlib.import_module("tab_profesional.ui")
        return getattr(mod, "mostrar_profesional")

mostrar_profesional = _import_ui()

def main():
    st.title("Planificador de Rutas (PRUEBAS)")
    st.caption("🧪 Rama desarrollo")
    mostrar_profesional()

if __name__ == "__main__":
    main()
PY