import streamlit as st
from i18n import get_texts
import os

# --- Clave API Google ---
# NOTA: En un entorno de producción como Streamlit Cloud, usar st.secrets es mejor.
# Aquí mantenemos os.getenv para desarrollo local con .env
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

if GOOGLE_PLACES_API_KEY:
    st.sidebar.caption(
        "🔑 Google key OK (últimos 6): **" +
        str(GOOGLE_PLACES_API_KEY)[-6:] + "**"
    )
else:
    st.sidebar.error("❌ Falta GOOGLE_PLACES_API_KEY")

# --- Import diferido para aislar errores de pestañas ---
def _safe_import(modname, funcname):
    try:
        mod = __import__(modname, fromlist=[funcname])
        return getattr(mod, funcname)
    except Exception as e:
        st.error(f"Error cargando `{modname}.{funcname}`")
        st.exception(e)
        # Devuelve una función que no hace nada para evitar que el script se detenga
        # y para que reciba 0 argumentos (el error que vimos)
        return lambda: st.stop() # <-- Retorna lambda sin argumentos

# Importación de las funciones de las pestañas
# Si hay error, devuelve la función que detiene el script sin argumentos.
mostrar_profesional = _safe_import("tab_profesional", "mostrar_profesional")
mostrar_viajero     = _safe_import("tab_viajero", "mostrar_viajero")
mostrar_turistico   = _safe_import("tab_turistico", "mostrar_turistico")

st.set_page_config(page_title="Planificador de Rutas", page_icon="🗺️", layout="wide")
st.set_option("client.showErrorDetails", True)

# --- Detección de idioma (query param > session > default es) ---
def _get_query_lang():
    # Streamlit >= 1.31: st.query_params
    try:
        qp = st.query_params  # type: ignore[attr-defined]
        if "lang" in qp:
            val = qp.get("lang")
            if isinstance(val, (list, tuple)):
                return val[0]
            return val
    except Exception:
        pass
    # Compatibilidad versiones anteriores
    try:
        qp = st.experimental_get_query_params()
        if "lang" in qp and qp["lang"]:
            return qp["lang"][0]
    except Exception:
        pass
    return None

if "lang" not in st.session_state:
    st.session_state["lang"] = _get_query_lang() or "es"

# --- Selector de idioma en la sidebar ---
langs_ui = {"es": ("es", "Español / Spanish"), "en": ("en", "Inglés / English")}
current_lang = st.session_state["lang"]
sel = st.sidebar.selectbox(
    label=get_texts(current_lang)["lang_label"],
    options=list(langs_ui.keys()),
    format_func=lambda k: langs_ui[k][1],
    index=0 if current_lang == "es" else 1
)

# Si el idioma cambia, lo persistimos en URL y rerun para refrescar toda la UI
if sel != current_lang:
    st.session_state["lang"] = sel
    # Persistir ?lang=<sel> en la URL (compatibilidad antigua y nueva)
    try:
        st.experimental_set_query_params(lang=sel)
    except Exception:
        pass
    st.rerun()

# Diccionario de textos activo
t = get_texts(st.session_state["lang"])

# --- Encabezado ---
st.markdown(f"# 🗺️ {t['app_title']}")
st.caption(t["app_subtitle"])

# --- Tabs con textos traducidos ---
tab_labels = t["tabs"]
tabs = st.tabs(tab_labels)

# CORRECCIÓN: Llamamos a las funciones sin el argumento 't'
# La función mostrar_profesional ya usa el estado de sesión para el idioma
with tabs[0]:
    mostrar_profesional() 

with tabs[1]:
    mostrar_viajero()

with tabs[2]:
    mostrar_turistico()

st.divider()
st.caption(t["footer_a"])
st.caption(t["footer_b"])