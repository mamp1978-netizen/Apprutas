# photo_agent_app.py  — PRUEBAS (rama desarrollo)
import streamlit as st

st.set_page_config(
    page_title="Planificador de Rutas",
    layout="wide",
    initial_sidebar_state="expanded",
)

DONATION_URL = "https://www.paypal.com/donate/?business=73LFHKS2WCQ9U&no_recurring=0&item_name=Ayuda+para+desarrolladores&currency_code=EUR"
st.sidebar.markdown("---")
st.sidebar.subheader("Apoya el desarrollo 🧑‍💻")
st.sidebar.info(
    "¿Te ha sido útil este planificador de rutas? "
    "Considera una pequeña donación para ayudarme a mantener y mejorar la aplicación."
)
st.sidebar.markdown(
    f"""
    <a href="{DONATION_URL}" target="_blank">
        <button style="background-color:#0070BA;color:#fff;padding:10px 20px;border:none;border-radius:5px;cursor:pointer;width:100%;">
            Ir al enlace de donación
        </button>
    </a>
    """,
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")


def _import_ui():
    """
    Importa la UI de forma robusta:
    1) from tab_profesional import mostrar_profesional
    2) importlib.import_module("tab_profesional.ui")
    """
    try:
        from tab_profesional import mostrar_profesional  # ✅ import estable (via __init__.py)
        return mostrar_profesional
    except Exception:
        import importlib
        mod = importlib.import_module("tab_profesional.ui")
        return getattr(mod, "mostrar_profesional")


mostrar_profesional = _import_ui()


def main():
    st.title("Planificador de Rutas")
    st.caption("La UI se carga desde `tab_profesional` (import robusto) ✅")
    mostrar_profesional()


if __name__ == "__main__":
    main()