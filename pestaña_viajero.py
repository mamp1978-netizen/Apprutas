import streamlit as st
from aplicación_utils import resolve_selection, build_gmaps_url, make_qr

def mostrar_viajero():
    st.subheader("Plan rápido (viajero)")
    st.caption("Indica inicio y final. (Puedes añadir una parada opcional).")

    o = st.text_input("Origen", key="trav_origin")
    d = st.text_input("Destino", key="trav_dest")
    p = st.text_input("Parada intermedia (opcional)", key="trav_mid")

    if st.button("Crear ruta (viajero)"):
        if not o or not d:
            st.error("Falta origen o destino.")
            return
        o_res = resolve_selection(o, "trav_origin")
        d_res = resolve_selection(d, "trav_dest")
        wps = []
        if p:
            wps.append(resolve_selection(p, "trav_mid")["address"])
        url = build_gmaps_url(o_res["address"], d_res["address"], wps if wps else None)
        st.success("Ruta generada")
        st.write(url)
        st.image(make_qr(url), caption="QR de la ruta")