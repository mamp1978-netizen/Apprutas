import streamlit as st
from aplicación_utils import resolve_selection, build_gmaps_url, make_qr

def mostrar_turistico():
    st.subheader("Ruta turística con varias paradas")
    st.caption("La última parada se toma como destino final.")

    o = st.text_input("Punto de inicio", key="tour_origin")
    d = st.text_input("Punto final", key="tour_dest")

    st.markdown("**Lugares a visitar (uno por línea)**")
    spots = st.text_area("", height=140, placeholder="Sagrada Familia, Barcelona\nParc Güell, Barcelona\nCasa Batlló, Barcelona…")
    stops = [s.strip() for s in spots.splitlines() if s.strip()]

    if st.button("Crear itinerario turístico"):
        if not o or not d:
            st.error("Indica inicio y final.")
            return
        o_res = resolve_selection(o, "tour_origin")
        d_res = resolve_selection(d, "tour_dest")
        url = build_gmaps_url(o_res["address"], d_res["address"], stops if stops else None)
        st.success("Itinerario listo")
        st.write(url)
        st.image(make_qr(url), caption="QR del itinerario")