# tab_viajero.py
import streamlit as st
from app_utils import resolve_selection, build_gmaps_url, make_qr

def _current_lang() -> str:
    try:
        return (st.session_state.get("lang") or "es").lower()
    except Exception:
        return "es"

def _norm(x: str | None) -> str:
    return (x or "").strip()

def mostrar_viajero(t: dict):
    st.subheader(t["trav_header"])
    st.caption(t["trav_caption"])

    o = st.text_input(t["input_origin"], key="trav_origin", placeholder="C/ Ejemplo 1, Ciudad")
    d = st.text_input(t["input_dest"],   key="trav_dest",   placeholder="C/ Ejemplo 2, Ciudad")
    p = st.text_input(t["input_mid"],    key="trav_mid",    placeholder="(Opcional)")

    if st.button(t["generate_trav"]):
        lang = _current_lang()

        o, d, p = _norm(o), _norm(d), _norm(p)
        if not o or not d:
            st.error(t["missing_o_d"])
            return

        # Resolver origen/destino
        o_res = resolve_selection(o, "trav_origin", lang=lang)
        d_res = resolve_selection(d, "trav_dest",   lang=lang)

        # Parada intermedia opcional
        waypoints = []
        if p:
            waypoints.append(resolve_selection(p, "trav_mid", lang=lang)["address"])

        # Construir URL y QR
        url = build_gmaps_url(o_res["address"], d_res["address"], waypoints if waypoints else None)
        st.success(t["route_ready"])
        st.write(url)
        st.image(make_qr(url), caption=t["qr_route"])