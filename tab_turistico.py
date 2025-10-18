# tab_turistico.py
import streamlit as st
from app_utils import resolve_selection, build_gmaps_url, make_qr

def mostrar_turistico(t: dict):
    st.subheader(t["tour_header"])
    st.caption(t["tour_caption"])

    o = st.text_input(t["tour_start"], key="tour_origin")
    d = st.text_input(t["tour_end"], key="tour_dest")

    st.markdown(f"**{t['tour_spots']}**")
    spots = st.text_area("", height=140, placeholder="Sagrada Familia, Barcelona\nParc Güell, Barcelona\nCasa Batlló, Barcelona…")
    stops = [s.strip() for s in spots.splitlines() if s.strip()]

    if st.button(t["generate_tour"]):
        if not o or not d:
            st.error(t["need_start_end"])
            return
        o_res = resolve_selection(o, "tour_origin")
        d_res = resolve_selection(d, "tour_dest")
        url = build_gmaps_url(o_res["address"], d_res["address"], stops if stops else None)
        st.success(t["tour_ready"])
        st.write(url)
        st.image(make_qr(url), caption=t["tour_qr"])