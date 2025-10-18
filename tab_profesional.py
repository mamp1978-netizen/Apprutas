# tab_profesional.py
import requests
import streamlit as st
from app_utils import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    make_qr,
    _get_key
)

# -------------------------------
# Inicialización del estado
# -------------------------------
def _init_state():
    ss = st.session_state
    ss.setdefault("prof_points", [])
    ss.setdefault("prof_last_route_url", None)
    ss.setdefault("prof_route_type", "Más rápido")
    ss.setdefault("prof_top_selected", None)
    ss.setdefault("prof_top_q", "")


# -------------------------------
# Limpieza del buscador
# -------------------------------
def _clear_search():
    st.session_state.pop("prof_top_q", None)
    st.session_state["prof_top_selected"] = None
    st.rerun()


# -------------------------------
# Añadir punto a la ruta
# -------------------------------
def _add_point(value, t):
    if not value:
        st.warning("Escribe o selecciona una dirección.")
        return
    st.session_state.prof_points.append(value)
    st.success(f"Añadido: {value}")


# -------------------------------
# Sección del buscador con autocompletado
# -------------------------------
def search_and_add_top(t):
    q = st.text_input("Buscar dirección… (presione ENTER para agregar)", key="prof_top_q")

    labels = suggest_addresses(q, "prof_top") if q and len(q) >= 2 else []
    st.session_state["_prof_top_last_labels"] = labels

    if labels:
        st.caption("Sugerencias:")
        idx = st.selectbox(
            "Elige una sugerencia",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            key="prof_top_selectbox"
        )
        st.session_state["prof_top_selected"] = idx
    else:
        st.caption("Sin sugerencias todavía")

    col1, col2, col3 = st.columns([0.25, 0.2, 0.55])
    with col1:
        if st.button("Añadir (ENTER)", type="primary"):
            labels_now = st.session_state.get("_prof_top_last_labels") or []
            sel = st.session_state.get("prof_top_selected", None)
            if labels_now and sel is not None and 0 <= sel < len(labels_now):
                _add_point(labels_now[sel], t)
            else:
                _add_point(q, t)
    with col2:
        st.button("Limpiar", on_click=_clear_search)
    with col3:
        if st.button("📍 Usar mi ubicación"):
            _add_point("Mi ubicación aproximada", t)


# -------------------------------
# Generar ruta
# -------------------------------
def mostrar_profesional(t: dict):
    _init_state()
    st.subheader("Ruta de trabajo")

    # Diagnóstico de API key y sugerencias
    GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
    st.sidebar.markdown("**🔑 Tecla Google OK (últimos 6):**")
    if GOOGLE_PLACES_API_KEY:
        st.sidebar.code(str(GOOGLE_PLACES_API_KEY)[-6:], language=None)
    else:
        st.sidebar.error("Falta GOOGLE_PLACES_API_KEY")

    diag = st.session_state.get("_suggest_diag", {})
    if diag:
        st.sidebar.caption(
            f'Q="{diag.get("q","")}" | Google:{diag.get("g",0)} '
            f'Serp:{diag.get("s",0)} OSM:{diag.get("n",0)}'
        )
        if diag.get("err"):
            st.sidebar.warning(diag["err"])

    # Tipo de ruta
    route_types = ["Más rápido", "Más corto", "Evitar autopistas", "Evitar peajes"]
    st.session_state.prof_route_type = st.selectbox(
        "Tipo de ruta", route_types, index=route_types.index(st.session_state.prof_route_type)
    )

    st.divider()
    search_and_add_top(t)
    st.divider()

    # Lista de puntos
    st.markdown("### Puntos de la ruta (orden de viaje)")
    pts = st.session_state.prof_points
    if not pts:
        st.info("Agregue al menos dos puntos (origen y destino) para generar la ruta.")
        return

    for i, p in enumerate(pts):
        prefix = (
            "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}:")
        )
        c1, c2 = st.columns([0.9, 0.1])
        with c1:
            st.write(f"**{prefix}**: {p}")
        with c2:
            if st.button("🗑", key=f"del_{i}"):
                pts.pop(i)
                st.rerun()

    if st.button("Generar ruta profesional", type="primary"):
        if len(pts) < 2:
            st.warning("Debes tener origen y destino.")
            return

        o = resolve_selection(pts[0], "prof_point_0")
        d = resolve_selection(pts[-1], f"prof_point_{len(pts)-1}")
        wp = [resolve_selection(p, f"prof_point_{i}")["address"] for i, p in enumerate(pts[1:-1], 1)]

        url = build_gmaps_url(o["address"], d["address"], wp)
        st.session_state.prof_last_route_url = url

        st.success("Ruta generada correctamente ✅")
        st.write(url)
        st.image(make_qr(url), caption="Escanea el QR para abrir la ruta")

    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada"):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url))