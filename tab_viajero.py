# tab_viajero.py
import streamlit as st
from app_utils import resolve_selection, build_gmaps_url, make_qr

def mostrar_viajero(t: dict):
    st.subheader(t["trav_header"])
    st.caption(t["trav_caption"])

    o = st.text_input(t["input_origin"], key="trav_origin")
    d = st.text_input(t["input_dest"], key="trav_dest")
    p = st.text_input(t["input_mid"], key="trav_mid")

    if st.button(t["generate_trav"]):
        if not o or not d:
            st.error(t["missing_o_d"])
            return
        o_res = resolve_selection(o, "trav_origin")
        d_res = resolve_selection(d, "trav_dest")
        wps = []
        if p:
            wps.append(resolve_selection(p, "trav_mid")["address"])
        url = build_gmaps_url(o_res["address"], d_res["address"], wps if wps else None)
        st.success(t["route_ready"])
        st.write(url)
        st.image(make_qr(url), caption=t["qr_route"])