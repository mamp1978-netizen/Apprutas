# tab_profesional_ui.py — UI sin import circular
import streamlit as st
from app_utils_core import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    build_waze_url,
    build_apple_maps_url,
)

def mostrar_profesional():
    st.header("Generar tu ruta (PRUEBAS)")

    col1, col2 = st.columns(2)
    with col1:
        origen_txt = st.text_input("Origen", placeholder="Calle / ciudad")
    with col2:
        destino_txt = st.text_input("Destino", placeholder="Calle / ciudad")

    if st.button("Generar ruta"):
        if not origen_txt or not destino_txt:
            st.warning("Introduce origen y destino.")
            return

        # Resolución simple (sin place_id)
        origen_meta = resolve_selection(origen_txt, None)
        destino_meta = resolve_selection(destino_txt, None)

        gmaps_url = build_gmaps_url(origen_meta, destino_meta, waypoints=None, mode="driving")
        waze_url  = build_waze_url(origen_meta, destino_meta)
        apple_url = build_apple_maps_url(origen_meta, destino_meta)

        if gmaps_url:
            st.link_button("Abrir en Google Maps", gmaps_url)
        if waze_url:
            st.link_button("Abrir en Waze", waze_url)
        if apple_url:
            st.link_button("Abrir en Apple Maps", apple_url)

        if not (gmaps_url or waze_url or apple_url):
            st.error("No se pudo generar ninguna URL. Revisa que los textos sean direcciones válidas.")
