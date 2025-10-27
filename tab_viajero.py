import streamlit as st
from app_utils_core import build_gmaps_url

def mostrar_viajero():
    st.header("🌍 Planificador de Viajes")

    o = st.text_input("Origen", "")
    d = st.text_input("Destino", "")
    wps = st.text_area("Paradas (una por línea)")

    if st.button("Generar ruta viajero"):
        if not o or not d:
            st.warning("Indica al menos origen y destino.")
            return

        wps = wps.splitlines()
        # --- SANEAR WAYPOINTS ---
        if isinstance(wps, str):
            wps = [w.strip() for w in wps.split("|") if w.strip() and not w.lower().startswith("optimize")]
        wps = [w.strip() for w in wps if w.strip() and not w.lower().startswith("optimize")]
        # --- FIN SANEO ---

        url = build_gmaps_url({"address": o}, {"address": d}, wps if wps else None)
        st.success("Ruta generada correctamente ✅")
        st.markdown(f"[🌍 Abrir en Google Maps]({url})")
