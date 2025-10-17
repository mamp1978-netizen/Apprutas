import streamlit as st
from app_utils import address_input, resolve_selection, build_gmaps_url, make_qr

def mostrar_turistico():
    st.subheader("Ruta turística con varias paradas")
    o = address_input("Punto de inicio", "turistico_inicio")
    d = address_input("Punto final", "turistico_final")

    spots = st.text_area(
        "Lugares a visitar (uno por línea)",
        height=120,
        placeholder="Sagrada Familia, Barcelona\nParc Güell, Barcelona\nCasa Batlló, Barcelona…"
    )
    stops = [s.strip() for s in spots.splitlines() if s.strip()]

    if st.button("Crear itinerario turístico"):
        if not o or not d:
            st.error("Indica inicio y final.")
            return

        o_res = resolve_selection(o, "turistico_inicio")
        d_res = resolve_selection(d, "turistico_final")

        url = build_gmaps_url(o_res["address"], d_res["address"], stops if stops else None)
        st.success("Itinerario listo")
        st.write(url)
        st.image(make_qr(url), caption="QR del itinerario")