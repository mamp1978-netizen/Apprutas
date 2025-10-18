# photo_agent_app.py
import os
import streamlit as st
from i18n import get_texts
# imports diferidos para capturar errores dentro de las pestañas
def _safe_import(modname, funcname):
    try:
        mod = __import__(modname, fromlist=[funcname])
        return getattr(mod, funcname)
    except Exception as e:
        st.error(f"Error cargando `{modname}.{funcname}`")
        st.exception(e)
        return lambda *_args, **_kw: st.stop()

mostrar_profesional = _safe_import("tab_profesional", "mostrar_profesional")
mostrar_viajero     = _safe_import("tab_viajero", "mostrar_viajero")
mostrar_turistico   = _safe_import("tab_turistico", "mostrar_turistico")

st.set_page_config(page_title="Planificador de Rutas", page_icon="🗺️", layout="wide")
st.set_option("client.showErrorDetails", True)

# --- Detección de idioma (query param > session > default es)
def _get_query_lang():
    try:
        # Streamlit recientes
        qp = st.query_params
        if "lang" in qp:
            return qp.get("lang")
    except Exception:
        pass
    try:
        # Compatibilidad antigua
        qp = st.experimental_get_query_params()
        if "lang" in qp and qp["lang"]:
            return qp["lang"][0]
    except Exception:
        pass
    return None

if "lang" not in st.session_state:
    st.session_state["lang"] = _get_query_lang() or "es"

# Sidebar selector
langs_ui = {"es": ("es", "Español / Spanish"), "en": ("en", "Inglés / English")}
sel = st.sidebar.selectbox(
    label=get_texts(st.session_state["lang"])["lang_label"],
    options=list(langs_ui.keys()),
    format_func=lambda k: langs_ui[k][1],
    index=0 if st.session_state["lang"] == "es" else 1
)
st.session_state["lang"] = sel
t = get_texts(sel)

# Encabezado
st.markdown(f"# 🗺️ {t['app_title']}")
st.caption(t["app_subtitle"])

# Tabs con textos traducidos
tab_labels = t["tabs"]
tabs = st.tabs(tab_labels)

with tabs[0]:
    mostrar_profesional(t)

with tabs[1]:
    mostrar_viajero(t)

with tabs[2]:
    mostrar_turistico(t)

st.divider()
st.caption(t["footer_a"])
st.caption(t["footer_b"])