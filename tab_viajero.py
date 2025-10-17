import streamlit as st
from utils import address_input, resolve_selection, build_gmaps_url, make_qr

def mostrar_viajero():
    st.subheader("Plan rápido (viajero)")
    o = address_input("Origen", "viajero_origen")
    d = address_input("Destino", "viajero_destino")

    if st.button("Crear ruta (viajero)"):
        if not o or not d:
            st.error("Falta origen o destino.")
        else:
            o_res = resolve_selection(o, "viajero_origen")
            d_res = resolve_selection(d, "viajero_destino")
            url = build_gmaps_url(o_res["address"], d_res["address"])
            st.success("Ruta generada")
            st.write(url)
            st.image(make_qr(url), caption="QR de la ruta")
            