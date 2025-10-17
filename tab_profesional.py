import streamlit as st
import requests
import os
from urllib.parse import quote_plus
from app_utils import resolve_selection, build_gmaps_url, make_qr

# --------------------- Carga clave API ---------------------
GOOGLE_KEY = os.getenv("GOOGLE_PLACES_API_KEY") or st.secrets.get("GOOGLE_PLACES_API_KEY")

# --------------------- Estado ---------------------
def _init_state():
    if "prof_stops_count" not in st.session_state:
        st.session_state.prof_stops_count = 0
    if "prof_last_route_url" not in st.session_state:
        st.session_state.prof_last_route_url = None
    if "prof_origin_manual" not in st.session_state:
        st.session_state.prof_origin_manual = ""
    if "prof_open_check" not in st.session_state:
        st.session_state.prof_open_check = False

def _add_stop():
    st.session_state.prof_stops_count += 1

def _remove_stop():
    if st.session_state.prof_stops_count > 0:
        idx = st.session_state.prof_stops_count - 1
        st.session_state.pop(f"prof_stop_{idx}", None)
        st.session_state.pop(f"prof_stop_{idx}_manual", None)
        st.session_state.prof_stops_count -= 1

# --------------------- Autocompletado Google ---------------------
def google_autocomplete(query: str, max_results: int = 5):
    """Devuelve sugerencias de direcciones desde Google Places API"""
    if not GOOGLE_KEY or not query:
        return []
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            f"?input={quote_plus(query)}&types=geocode&language=es&key={GOOGLE_KEY}"
        )
        r = requests.get(url, timeout=6)
        data = r.json()
        preds = data.get("predictions", [])
        return [p.get("description") for p in preds if p.get("description")]
    except Exception as e:
        print("Google autocomplete error:", e)
        return []

# --------------------- IP -> dirección aproximada ---------------------
def _ip_location_to_address() -> str | None:
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        city = ip.get("city") or ""
        region = ip.get("region") or ""
        country = ip.get("country_name") or ""
        return ", ".join([x for x in [city, region, country] if x])
    except Exception as e:
        print("ip->address error:", e)
        return None

# --------------------- UI principal ---------------------
def mostrar_profesional():
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption("Planifica visitas a clientes, obras o inspecciones. La **última parada** será el **destino final**.")

    # -------- ORIGEN
    st.markdown("**Origen**")
    origin = st.text_input("Dirección completa (autocompletar)", key="prof_origin")
    # Sugerencias Google
    if origin and GOOGLE_KEY:
        suggestions = google_autocomplete(origin)
        if suggestions:
            chosen = st.selectbox("Sugerencias", suggestions, key="prof_origin_choice")
            if chosen:
                origin = chosen

    colb1, colb2 = st.columns([0.55, 0.45])
    with colb1:
        if st.button("📍 Usar mi ubicación (aprox.)", use_container_width=True):
            addr = _ip_location_to_address()
            if addr:
                st.session_state.prof_origin_manual = addr
                st.success(f"Origen fijado: {addr}")
            else:
                st.warning("No pude obtener tu ubicación. Escribe tu dirección manualmente.")
    with colb2:
        if st.session_state.prof_origin_manual:
            st.info(f"Origen actual: {st.session_state.prof_origin_manual}")

    if not GOOGLE_KEY:
        st.warning("⚠️ No hay clave de Google Places configurada. El autocompletado puede no funcionar en móvil.")

    # -------- PARADAS
    st.markdown("### Paradas intermedias (la última será el destino)")
    c1, c2, _ = st.columns([0.25, 0.25, 0.5])
    with c1:
        st.button("+ Añadir parada", on_click=_add_stop, use_container_width=True)
    with c2:
        st.button("Eliminar última", on_click=_remove_stop, use_container_width=True)

    stops_labels: list[str] = []
    for i in range(st.session_state.prof_stops_count):
        st.markdown(f"**Parada #{i+1}**")
        stop = st.text_input(f"Buscar parada #{i+1}", key=f"prof_stop_{i}")
        # Autocompletado en paradas
        sug = google_autocomplete(stop) if stop and GOOGLE_KEY else []
        if sug:
            choice = st.selectbox("Sugerencias", sug, key=f"prof_stop_choice_{i}")
            if choice:
                stop = choice
        manual = st.text_input("o escribir manualmente", key=f"prof_stop_{i}_manual")
        final_label = stop or manual
        if final_label:
            stops_labels.append(final_label)

    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

    # -------- GENERAR RUTA --------
    if st.button("Generar ruta profesional", type="primary"):
        chosen_origin = origin or st.session_state.prof_origin_manual
        if not chosen_origin:
            st.error("Indica el **origen** (o usa el botón de ubicación).")
            return
        if len(stops_labels) == 0:
            st.error("Añade al menos **una parada** (será el destino final).")
            return

        # Origen y destino
        o = resolve_selection(chosen_origin, "prof_origin")
        destination_label = stops_labels[-1]
        waypoints_labels = stops_labels[:-1]

        d_det = resolve_selection(destination_label, f"prof_stop_{len(stops_labels)-1}")

        # Waypoints
        wp_resolved = [resolve_selection(w, f"prof_stop_{i}")["address"] for i, w in enumerate(waypoints_labels)]

        url = build_gmaps_url(o["address"], d_det["address"], wp_resolved if wp_resolved else None)
        st.session_state.prof_last_route_url = url

        st.success("✅ Ruta generada correctamente")
        st.write(url)
        st.image(make_qr(url), caption="Escanea para abrir la ruta en el móvil")

    # -------- ÚLTIMA RUTA
    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada (esta sesión)", expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption="QR de la última ruta")