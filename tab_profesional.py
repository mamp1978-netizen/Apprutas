# tab_profesional.py
import os
import requests
import streamlit as st
from urllib.parse import quote_plus
from app_utils import resolve_selection, build_gmaps_url, make_qr

# --------------------- Claves ---------------------
GOOGLE_KEY  = os.getenv("GOOGLE_PLACES_API_KEY") or (st.secrets.get("GOOGLE_PLACES_API_KEY") if hasattr(st, "secrets") else None)
SERP_KEY    = os.getenv("SERPAPI_API_KEY")        or (st.secrets.get("SERPAPI_API_KEY")        if hasattr(st, "secrets") else None)
TIMEOUT = 6

# --------------------- Estado ---------------------
def _init_state():
    if "prof_stops_count" not in st.session_state:
        st.session_state.prof_stops_count = 0
    if "prof_last_route_url" not in st.session_state:
        st.session_state.prof_last_route_url = None
    if "prof_origin_loc" not in st.session_state:
        st.session_state.prof_origin_loc = ""  # origen fijado por botón ubicación
    if "prof_open_check" not in st.session_state:
        st.session_state.prof_open_check = False

def _add_stop():
    st.session_state.prof_stops_count += 1

def _remove_stop():
    if st.session_state.prof_stops_count > 0:
        i = st.session_state.prof_stops_count - 1
        for k in (f"prof_stop_{i}", f"prof_stop_{i}_manual", f"prof_stop_choice_{i}"):
            st.session_state.pop(k, None)
        st.session_state.prof_stops_count -= 1

# --------------------- Proveedores de sugerencias ---------------------
def _google_autocomplete(q: str, n=6) -> list[str]:
    if not GOOGLE_KEY or not q:
        return []
    try:
        url = ("https://maps.googleapis.com/maps/api/place/autocomplete/json"
               f"?input={quote_plus(q)}&types=geocode&language=es&key={GOOGLE_KEY}")
        r = requests.get(url, timeout=TIMEOUT)
        preds = r.json().get("predictions", [])
        return [p.get("description") for p in preds[:n] if p.get("description")]
    except Exception as e:
        print("Google autocomplete error:", e)
        return []

def _serpapi_suggest(q: str, n=6) -> list[str]:
    if not SERP_KEY or not q:
        return []
    try:
        url = ("https://serpapi.com/search.json"
               f"?engine=google_maps&q={quote_plus(q)}&hl=es&api_key={SERP_KEY}")
        r = requests.get(url, timeout=TIMEOUT)
        res = r.json().get("local_results") or []
        out = []
        for it in res[:n]:
            title = it.get("title") or ""
            addr  = it.get("address") or ""
            s = (f"{title} – {addr}").strip(" –")
            if s:
                out.append(s)
        return out
    except Exception as e:
        print("SerpAPI suggest error:", e)
        return []

def _suggest_list(q: str) -> list[str]:
    # Google primero; si no, SerpAPI.
    s = _google_autocomplete(q)
    if not s:
        s = _serpapi_suggest(q)
    return s or []

# --------------------- Ubicación por IP (aprox.) ---------------------
def _ip_location_to_address() -> str | None:
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=TIMEOUT).json()
        # Evitamos reverse a coords desde servidor; usamos string ciudad, región, país
        city = ip.get("city") or ""
        region = ip.get("region") or ""
        country = ip.get("country_name") or ""
        guess = ", ".join([x for x in (city, region, country) if x])
        return guess or None
    except Exception as e:
        print("ip->address error:", e)
        return None

# --------------------- UI principal ---------------------
def mostrar_profesional():
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption("Planifica visitas a clientes, obras o inspecciones. La **última parada** será el **destino final**.")

    # -------- ORIGEN (buscador + manual + ubicación)
    st.markdown("**Origen**")
    origin_search = st.text_input("Dirección completa (origen)", key="prof_origin_search_text", placeholder="Carrer / Calle, ciudad…")

    origin_suggestions = _suggest_list(origin_search) if origin_search else []
    if origin_suggestions:
        origin_choice = st.selectbox("Sugerencias", origin_suggestions, key="prof_origin_choice", index=0)
    else:
        origin_choice = ""

    origin_manual = st.text_input("o escribir manualmente", key="prof_origin_manual_text")

    colb1, colb2 = st.columns([0.55, 0.45])
    with colb1:
        if st.button("📍 Usar mi ubicación (aprox.)", use_container_width=True):
            addr = _ip_location_to_address()
            if addr:
                st.session_state.prof_origin_loc = addr
                st.success(f"Origen fijado: {addr}")
            else:
                st.warning("No pude obtener tu ubicación. Escribe tu dirección manualmente.")
    with colb2:
        if st.session_state.prof_origin_loc:
            st.info(f"Origen actual: {st.session_state.prof_origin_loc}")

    # Aviso de claves
    if not GOOGLE_KEY and not SERP_KEY:
        st.warning("⚠️ Sin Google Places ni SerpAPI. El autocompletado puede ser limitado; usa los campos manuales.")

    # -------- PARADAS (dinámicas) ------------
    st.markdown("### Paradas intermedias (la última será el destino)")
    c1, c2, _ = st.columns([0.25, 0.25, 0.5])
    with c1:
        st.button("+ Añadir parada", on_click=_add_stop, use_container_width=True)
    with c2:
        st.button("Eliminar última", on_click=_remove_stop, use_container_width=True)

    stops_labels: list[str] = []
    for i in range(st.session_state.prof_stops_count):
        st.markdown(f"**Parada #{i+1}**")
        stop_search = st.text_input(f"Buscar parada #{i+1}", key=f"prof_stop_{i}", placeholder="Dirección…")
        sug = _suggest_list(stop_search) if stop_search else []
        if sug:
            choice = st.selectbox("Sugerencias", sug, key=f"prof_stop_choice_{i}")
        else:
            choice = ""
        manual = st.text_input("o escribir manualmente", key=f"prof_stop_{i}_manual")

        # ✅ Prioridad: buscador > manual
        final_label = (choice or stop_search) or manual
        if final_label:
            stops_labels.append(final_label)

    # -------- 'abierto ahora'
    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

    # -------- GENERAR RUTA ------------
    if st.button("Generar ruta profesional", type="primary"):
        # ✅ Origen: prioridad buscador > manual > ubicación
        chosen_origin = (origin_choice or origin_search) or origin_manual or st.session_state.prof_origin_loc
        if not chosen_origin:
            st.error("Indica el **origen** (o usa el botón de ubicación).")
            return
        if len(stops_labels) == 0:
            st.error("Añade al menos **una parada** (será el destino final).")
            return

        # Resolver a dirección final (resolve_selection acepta texto libre)
        o = resolve_selection(chosen_origin, "prof_origin")  # si no es selección previa, devuelve address=texto
        destination_label = stops_labels[-1]
        waypoints_labels  = stops_labels[:-1]

        d_det = resolve_selection(destination_label, f"prof_stop_{len(stops_labels)-1}")

        # Waypoints: resolvemos cada uno y extraemos la dirección final
        wp_resolved = []
        open_report = []
        for i, lab in enumerate(waypoints_labels):
            det = resolve_selection(lab, f"prof_stop_{i}")
            wp_resolved.append(det["address"])
            if st.session_state.prof_open_check:
                open_report.append((f"Parada #{i+1}", det.get("address"), det.get("open_now")))

        url = build_gmaps_url(o["address"], d_det["address"], wp_resolved if wp_resolved else None)
        st.session_state.prof_last_route_url = url

        st.success("✅ Ruta generada correctamente")
        st.write(url)
        st.image(make_qr(url), caption="Escanea para abrir la ruta en el móvil")

        # Informe “abierto ahora” (si hay datos)
        if st.session_state.prof_open_check:
            st.markdown("### Estado de apertura (ahora)")
            def _flagline(prefix, det):
                if det.get("open_now") is True:
                    st.markdown(f"**{prefix}:** ✅ Abierto – {det['address']}")
                elif det.get("open_now") is False:
                    st.markdown(f"**{prefix}:** ⛔ Cerrado – {det['address']}")
                else:
                    st.markdown(f"**{prefix}:** ℹ️ Sin datos – {det['address']}")
            _flagline("Origen", o)
            for title, addr, flag in open_report:
                if flag is True:
                    st.markdown(f"**{title}:** ✅ Abierto – {addr}")
                elif flag is False:
                    st.markdown(f"**{title}:** ⛔ Cerrado – {addr}")
                else:
                    st.markdown(f"**{title}:** ℹ️ Sin datos – {addr}")
            _flagline("Destino", d_det)

    # -------- ÚLTIMA RUTA
    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada (esta sesión)", expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption="QR de la última ruta")