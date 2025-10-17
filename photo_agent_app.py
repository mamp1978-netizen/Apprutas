import streamlit as st
from app_utils import build_gmaps_url, make_qr, suggest_addresses, resolve_selection

st.set_page_config(page_title="Planificador de Rutas", page_icon="🗺️", layout="wide")
st.set_option("client.showErrorDetails", True)

st.markdown("# 🗺️ Planificador de Rutas")
st.caption("Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final.")

def _safe_import(modname, funcname):
    try:
        mod = __import__(modname, fromlist=[funcname])
        return getattr(mod, funcname)
    except Exception as e:
        st.error(f"Error cargando `{modname}.{funcname}`")
        st.exception(e)
        return lambda: st.stop()

mostrar_profesional = _safe_import("tab_profesional", "mostrar_profesional")
mostrar_viajero = _safe_import("tab_viajero", "mostrar_viajero")
mostrar_turistico = _safe_import("tab_turistico", "mostrar_turistico")

tabs = st.tabs(["💼 Profesional", "🧳 Viajero", "🌴 Turístico"])

with tabs[0]:
    mostrar_profesional()

with tabs[1]:
    mostrar_viajero()

with tabs[2]:
    mostrar_turistico()

st.divider()
st.caption("Autocompletado: Google Places / SerpAPI / Nominatim (OSM).")
st.caption("Añade tus claves en .env o en st.secrets (`GOOGLE_PLACES_API_KEY`, `SERPAPI_API_KEY`).")
