# tab_turistico.py
import streamlit as st
from app_utils import resolve_selection, build_gmaps_url, make_qr

def _current_lang() -> str:
    try:
        return (st.session_state.get("lang") or "es").lower()
    except Exception:
        return "es"

def _norm(x: str | None) -> str:
    return (x or "").strip()

def mostrar_turistico(t: dict):
    st.subheader(t["tour_header"])
    st.caption(t["tour_caption"])

    o = st.text_input(t["tour_start"], key="tour_origin", placeholder="Sagrada Familia, Barcelona")
    d = st.text_input(t["tour_end"],   key="tour_dest",   placeholder="Parc Güell, Barcelona")

    st.markdown(f"**{t['tour_spots']}**")
    spots = st.text_area(
        "",
        height=140,
        placeholder="Sagrada Familia, Barcelona\nParc Güell, Barcelona\nCasa Batlló, Barcelona…"
    )

    # Limpiar y normalizar paradas
    raw_stops = [s.strip() for s in (spots or "").splitlines() if s.strip()]

    if st.button(t["generate_tour"]):
        lang = _current_lang()

        o, d = _norm(o), _norm(d)
        if not o or not d:
            st.error(t["need_start_end"])
            return

        # Resolver inicio y final
        o_res = resolve_selection(o, "tour_origin", lang=lang)
        d_res = resolve_selection(d, "tour_dest",   lang=lang)

        # Resolver cada parada intermedia con su bucket e idioma
        resolved_stops = []
        for i, s in enumerate(raw_stops):
            det = resolve_selection(s, f"tour_stop_{i}", lang=lang)
            if det.get("address"):
                resolved_stops.append(det["address"])

        # Construir ruta y QR
        url = build_gmaps_url(o_res["address"], d_res["address"], resolved_stops if resolved_stops else None)
        st.success(t["tour_ready"])
        st.write(url)
        st.image(make_qr(url), caption=t["tour_qr"])