import streamlit as st
from tab_profesional import mostrar_profesional
from tab_viajero import mostrar_viajero
from tab_turistico import mostrar_turistico

st.set_page_config(page_title="Planificador de Rutas", page_icon="🗺️", layout="wide")

st.markdown("# 🗺️ Planificador de Rutas")
st.caption("Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final.")

tabs = st.tabs(["🧰 Profesional", "🧳 Viajero", "🏖️ Turístico"])

with tabs[0]:
    mostrar_profesional()

with tabs[1]:
    mostrar_viajero()

with tabs[2]:
    mostrar_turistico()

st.divider()
st.caption("Autocompletado: Google Places / SerpAPI / Nominatim (OSM). "
           "Añade tus claves en .env o st.secrets (`GOOGLE_PLACES_API_KEY`, `SERPAPI_API_KEY`).")