import streamlit as st
from app_utils import address_input, resolve_selection, build_gmaps_url, make_qr

def mostrar_viajero():
    st.subheader("Plan rápido (viajero)")
    st.caption("Indica inicio y final. (Puedes añadir una parada opcional).")

    o = address_input("Origen", "trav_origin")
    d = address_input("Destino", "trav_dest")
    p = address_input("Parada intermedia (opcional)", "trav_mid")

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