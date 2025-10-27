import streamlit as st
from app_utils_core import build_gmaps_url

def mostrar_turistico():
    st.header("🗺️ Planificador Turístico")

    o = st.text_input("Origen", "")
    d = st.text_input("Destino", "")
    stops = st.text_area("Puntos intermedios (uno por línea)")

    if st.button("Generar ruta turística"):
        if not o or not d:
            st.warning("Indica al menos origen y destino.")
            return

        stops = stops.splitlines()
        # --- SANEAR WAYPOINTS ---
        if isinstance(stops, str):
            stops = [w.strip() for w in stops.split("|") if w.strip() and not w.lower().startswith("optimize")]
        stops = [w.strip() for w in stops if w.strip() and not w.lower().startswith("optimize")]
        # --- FIN SANEO ---

        url = build_gmaps_url({"address": o}, {"address": d}, stops if stops else None)
        st.success("Ruta generada correctamente ✅")
        st.markdown(f"[🌍 Abrir en Google Maps]({url})")
