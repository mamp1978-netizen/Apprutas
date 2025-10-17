# photo_agent_app.py
from urllib.parse import quote_plus
from io import BytesIO
import os
import requests
from dotenv import load_dotenv

import streamlit as st
from streamlit_searchbox import st_searchbox
import qrcode

# -------------------------------------------------
# Configuración general
# -------------------------------------------------
load_dotenv()
st.set_page_config(page_title="Planificador de Rutas", page_icon="🗺️", layout="wide")

def get_key(name: str):
    """Prioriza st.secrets y luego variables de entorno."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)

GOOGLE_PLACES_API_KEY = get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY = get_key("SERPAPI_API_KEY") or get_key("SERPAPI_KEY")

# Caché ligera de sugerencias por searchbox
if "suggest_maps" not in st.session_state:
    st.session_state.suggest_maps = {}
if "last_empty_query" not in st.session_state:
    st.session_state.last_empty_query = None

REQUEST_TIMEOUT = 10  # seg

# -------------------------------------------------
# Proveedores de autocompletado / geocodificación
# -------------------------------------------------
def provider_google_autocomplete(query: str, max_results: int = 8):
    if not GOOGLE_PLACES_API_KEY:
        return []
    url = (
        "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        f"?input={quote_plus(query)}&types=geocode&language=es&key={GOOGLE_PLACES_API_KEY}"
    )
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    out = []
    for p in data.get("predictions", [])[:max_results]:
        desc = p.get("description")
        place_id = p.get("place_id")
        if desc and place_id:
            out.append((desc, {"provider": "google", "place_id": place_id, "desc": desc}))
    return out

def provider_serpapi_maps(query: str, max_results: int = 8):
    if not SERPAPI_API_KEY:
        return []
    url = (
        "https://serpapi.com/search.json?"
        f"engine=google_maps&q={quote_plus(query)}&hl=es&api_key={SERPAPI_API_KEY}"
    )
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    js = r.json()
    results = js.get("local_results") or []
    out = []
    for it in results[:max_results]:
        title = it.get("title") or ""
        address = it.get("address") or ""
        desc = f"{title} – {address}".strip(" –")
        gps = it.get("gps_coordinates") or {}
        lat, lng = gps.get("latitude"), gps.get("longitude")
        open_now = None
        status = it.get("opening_status")
        if isinstance(status, str):
            if "Abierto" in status:
                open_now = True
            elif "Cerrado" in status:
                open_now = False
        if desc and lat and lng:
            out.append((desc, {
                "provider": "serpapi",
                "lat": lat, "lng": lng,
                "desc": desc,
                "open_now": open_now
            }))
    return out

def provider_nominatim(query: str, max_results: int = 8):
    url = (
        "https://nominatim.openstreetmap.org/search?"
        f"q={quote_plus(query)}&format=json&addressdetails=0&limit={max_results}"
    )
    headers = {"User-Agent": "PlanificadorRutas/1.0 (streamlit app)"}
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    arr = r.json()
    out = []
    for it in arr[:max_results]:
        desc = it.get("display_name")
        lat, lng = it.get("lat"), it.get("lon")
        if desc and lat and lng:
            out.append((desc, {
                "provider": "nominatim",
                "lat": float(lat), "lng": float(lng),
                "desc": desc
            }))
    return out

def get_place_coords_from_google(place_id: str):
    url = (
        "https://maps.googleapis.com/maps/api/place/details/json"
        f"?place_id={quote_plus(place_id)}&fields=geometry,opening_hours,formatted_address,name"
        f"&language=es&key={GOOGLE_PLACES_API_KEY}"
    )
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json().get("result", {})
    geo = data.get("geometry", {}).get("location", {})
    lat, lng = geo.get("lat"), geo.get("lng")
    open_now = data.get("opening_hours", {}).get("open_now")
    address = data.get("formatted_address") or data.get("name")
    return {"lat": lat, "lng": lng, "open_now": open_now, "desc": address}

# -------------------------------------------------
# Sugeridor unificado (a prueba de errores)
# -------------------------------------------------
def suggest_addresses(query: str, key_bucket: str):
    """
    Devuelve SIEMPRE una lista de labels (strings).
    Guarda metadatos por label en session_state.suggest_maps[key_bucket].
    """
    q = (query or "").strip()
    if len(q) < 2:
        return []

    suggestions = []

    # Google
    try:
        suggestions = provider_google_autocomplete(q) or []
    except Exception as e:
        print("Google autocomplete error:", e)

    # SerpAPI
    if not suggestions:
        try:
            suggestions = provider_serpapi_maps(q) or []
        except Exception as e:
            print("SerpAPI fallback error:", e)

    # Nominatim
    if not suggestions:
        try:
            suggestions = provider_nominatim(q) or []
        except Exception as e:
            print("Nominatim fallback error:", e)

    # Garantiza lista, nunca None
    if not isinstance(suggestions, list):
        suggestions = []

    # Si no hay nada, avisamos en la UI una única vez por consulta
    if len(suggestions) == 0:
        # Evita repetir el mismo aviso mientras el usuario escribe
        if st.session_state.last_empty_query != q:
            st.session_state.last_empty_query = q
            st.info("No se encontraron sugerencias. Prueba con más detalle (p. ej. 'Girona, España' o una calle).")
        return []

    # Guardar metadatos por label
    bucket = st.session_state.suggest_maps.setdefault(key_bucket, {})
    labels = []
    for label, meta in suggestions:
        bucket[label] = meta
        labels.append(label)
    return labels

def resolve_selection(label: str, key_bucket: str):
    """Resuelve una selección del searchbox a dirección + (lat/lng/open_now si procede)."""
    meta = st.session_state.suggest_maps.get(key_bucket, {}).get(label)
    if not meta:
        # El usuario puede teclear/pegar una dirección manual
        return {"address": label, "lat": None, "lng": None, "open_now": None, "provider": None}

    provider = meta.get("provider")
    if provider == "google":
        det = get_place_coords_from_google(meta["place_id"])
        return {"address": det.get("desc") or label, "lat": det["lat"], "lng": det["lng"],
                "open_now": det.get("open_now"), "provider": "google"}
    elif provider in ("serpapi", "nominatim"):
        return {"address": meta.get("desc") or label, "lat": meta.get("lat"), "lng": meta.get("lng"),
                "open_now": meta.get("open_now"), "provider": provider}

    return {"address": label, "lat": None, "lng": None, "open_now": None, "provider": None}

# -------------------------------------------------
# Helpers UI
# -------------------------------------------------
def address_input(label: str, key: str):
    return st_searchbox(
        search_function=lambda q: suggest_addresses(q, key_bucket=key),
        label=label,
        key=key,
        default=None,
        max_results_to_show=8
    )

def build_gmaps_url(origin: str, destination: str, waypoints=None):
    base = "https://www.google.com/maps/dir/?api=1"
    params = [
        f"origin={quote_plus(origin)}",
        f"destination={quote_plus(destination)}",
        "travelmode=driving"
    ]
    if waypoints:
        params.append(f"waypoints={quote_plus('|'.join(waypoints))}")
        params.append("optimize=true")
    return f"{base}&" + "&".join(params)

def make_qr(url: str) -> BytesIO:
    qr = qrcode.QRCode(border=1, box_size=6)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# -------------------------------------------------
# Interfaz
# -------------------------------------------------
st.markdown("# 🗺️ Planificador de Rutas")
st.caption("Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final.")

tabs = st.tabs(["🧰 Profesional", "🧳 Viajero", "🏖️ Turístico"])

# ---- Profesional ----
with tabs[0]:
    st.subheader("Ruta de trabajo")
    st.caption("Planifica visitas a clientes, obras o inspecciones. Usa direcciones completas.")

    col1, col2 = st.columns([1, 1])
    with col1:
        origin_label = address_input("Dirección completa (origen)", key="prof_origin_search")
    with col2:
        dest_label = address_input("Dirección completa (destino final)", key="prof_dest_search")

    stops_txt = st.text_area(
        "Paradas intermedias (una por línea)",
        height=140,
        placeholder="Cliente 1, Barcelona\nCliente 2, Girona\n..."
    )
    stops = [s.strip() for s in stops_txt.splitlines() if s.strip()]

    check_open = st.checkbox("Comprobar si los lugares están abiertos ahora (requiere Google Places)")

    if st.button("Generar ruta"):
        if not origin_label or not dest_label:
            st.error("Indica al menos **origen** y **destino**.")
        else:
            origin = resolve_selection(origin_label, "prof_origin_search")
            dest = resolve_selection(dest_label, "prof_dest_search")
            url = build_gmaps_url(origin["address"], dest["address"], stops if stops else None)
            st.success("Ruta generada")
            st.write(url)
            st.image(make_qr(url), caption="Escanea para abrir la ruta en el móvil")

            if check_open and GOOGLE_PLACES_API_KEY:
                st.subheader("Estado de apertura (ahora)")
                for label, keybucket in [(origin_label, "prof_origin_search"), (dest_label, "prof_dest_search")]:
                    det = resolve_selection(label, keybucket)
                    if det["open_now"] is True:
                        st.markdown(f"✅ **Abierto** – {det['address']}")
                    elif det["open_now"] is False:
                        st.markdown(f"⛔ **Cerrado** – {det['address']}")
                    else:
                        st.markdown(f"ℹ️ **Sin datos** – {det['address']}")

# ---- Viajero ----
with tabs[1]:
    st.subheader("Plan rápido (viajero)")
    o = address_input("Origen", key="trav_origin")
    d = address_input("Destino", key="trav_dest")
    if st.button("Crear ruta (viajero)"):
        if not o or not d:
            st.error("Falta origen o destino.")
        else:
            o_res = resolve_selection(o, "trav_origin")
            d_res = resolve_selection(d, "trav_dest")
            url = build_gmaps_url(o_res["address"], d_res["address"])
            st.success("Ruta generada")
            st.write(url)
            st.image(make_qr(url), caption="QR de la ruta")

# ---- Turístico ----
with tabs[2]:
    st.subheader("Ruta turística con varias paradas")
    o = address_input("Punto de inicio", key="tour_origin")
    d = address_input("Punto final", key="tour_dest")
    spots = st.text_area(
        "Lugares a visitar (uno por línea)",
        height=140,
        placeholder="Sagrada Familia, Barcelona\nParc Güell, Barcelona\nCasa Batlló, Barcelona\n..."
    )
    tour_stops = [s.strip() for s in spots.splitlines() if s.strip()]

    if st.button("Crear itinerario turístico"):
        if not o or not d:
            st.error("Indica inicio y final.")
        else:
            o_res = resolve_selection(o, "tour_origin")
            d_res = resolve_selection(d, "tour_dest")
            url = build_gmaps_url(o_res["address"], d_res["address"], tour_stops if tour_stops else None)
            st.success("Itinerario listo")
            st.write(url)
            st.image(make_qr(url), caption="QR del itinerario")

# -------------------------------------------------
# Pie de página
# -------------------------------------------------
st.divider()
st.caption(
    "Claves opcionales: `GOOGLE_PLACES_API_KEY`, `SERPAPI_API_KEY` en .env o st.secrets. "
    "Si no hay claves, el autocompletado usa Nominatim (OSM)."
)