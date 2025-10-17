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
# CONFIGURACIÓN
# -------------------------------------------------
load_dotenv()
st.set_page_config(page_title="Planificador de Rutas", page_icon="🗺️", layout="wide")

def get_key(name: str):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)

GOOGLE_PLACES_API_KEY = get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY = get_key("SERPAPI_API_KEY") or get_key("SERPAPI_KEY")
REQUEST_TIMEOUT = 10

# Estado para cachear sugerencias por componente
if "suggest_maps" not in st.session_state:
    st.session_state.suggest_maps = {}

# -------------------------------------------------
# PROVEEDORES
# -------------------------------------------------
def provider_google_autocomplete(query: str, max_results: int = 8):
    if not GOOGLE_PLACES_API_KEY:
        return []
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            f"?input={quote_plus(query)}&types=geocode&language=es&key={GOOGLE_PLACES_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        preds = data.get("predictions", [])
        out = [
            (p.get("description"), {"provider": "google", "place_id": p.get("place_id")})
            for p in preds if p.get("description") and p.get("place_id")
        ]
        return out[:max_results]
    except Exception as e:
        print("❌ Google autocomplete error:", e)
        return []

def provider_serpapi_maps(query: str, max_results: int = 8):
    if not SERPAPI_API_KEY:
        return []
    try:
        url = (
            "https://serpapi.com/search.json?"
            f"engine=google_maps&q={quote_plus(query)}&hl=es&api_key={SERPAPI_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        js = r.json()
        res = js.get("local_results") or []
        out = []
        for it in res[:max_results]:
            title = it.get("title") or ""
            addr = it.get("address") or ""
            desc = (f"{title} – {addr}").strip(" –")
            gps = it.get("gps_coordinates") or {}
            lat, lng = gps.get("latitude"), gps.get("longitude")
            if desc and lat and lng:
                out.append((desc, {
                    "provider": "serpapi",
                    "lat": lat, "lng": lng,
                    "desc": desc
                }))
        return out
    except Exception as e:
        print("❌ SerpAPI error:", e)
        return []

def provider_nominatim(query: str, max_results: int = 8):
    try:
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
    except Exception as e:
        print("❌ Nominatim error:", e)
        return []

def get_place_coords_from_google(place_id: str):
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/details/json"
            f"?place_id={quote_plus(place_id)}&fields=geometry,opening_hours,formatted_address,name"
            f"&language=es&key={GOOGLE_PLACES_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        d = r.json().get("result", {})
        loc = d.get("geometry", {}).get("location", {})
        return {
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "open_now": d.get("opening_hours", {}).get("open_now"),
            "address": d.get("formatted_address") or d.get("name")
        }
    except Exception as e:
        print("❌ Google details error:", e)
        return {}

# -------------------------------------------------
# AUTOCOMPLETADO UNIFICADO
# -------------------------------------------------
def suggest_addresses(query: str, key_bucket: str):
    """Devuelve SIEMPRE una lista de cadenas (labels)."""
    if not query or len(query.strip()) < 2:
        return []

    results = []
    try:
        results = provider_google_autocomplete(query) or []
        if not results:
            results = provider_serpapi_maps(query) or []
        if not results:
            results = provider_nominatim(query) or []
    except Exception as e:
        print("❌ Error global en suggest_addresses:", e)
        results = []

    if not isinstance(results, list):
        results = []

    clean = []
    for r in results:
        if isinstance(r, (tuple, list)) and r and isinstance(r[0], str):
            clean.append(r)

    if not clean:
        # No rompemos el componente, simplemente no mostramos opciones
        return []

    bucket = st.session_state.suggest_maps.setdefault(key_bucket, {})
    labels = []
    for label, meta in clean:
        bucket[label] = meta
        labels.append(label)
    return labels

def resolve_selection(label: str, key_bucket: str):
    meta = st.session_state.suggest_maps.get(key_bucket, {}).get(label)
    if not meta:
        return {"address": label, "lat": None, "lng": None, "open_now": None}

    if meta.get("provider") == "google" and meta.get("place_id"):
        det = get_place_coords_from_google(meta["place_id"])
        return {
            "address": det.get("address") or label,
            "lat": det.get("lat"), "lng": det.get("lng"),
            "open_now": det.get("open_now")
        }

    return {
        "address": meta.get("desc") or label,
        "lat": meta.get("lat"), "lng": meta.get("lng"),
        "open_now": meta.get("open_now")
    }

# -------------------------------------------------
# UI HELPERS
# -------------------------------------------------
def address_input(label: str, key: str):
    """Busca con autocompletado; si falla, usa text_input básico."""
    try:
        return st_searchbox(
            search_function=lambda q: suggest_addresses(q, key_bucket=key),
            label=label,
            key=key,
            default=None   # (no usamos max_results_to_show para compatibilidad)
        )
    except Exception as e:
        st.warning("Autocompletado desactivado; usando campo de texto.")
        print("st_searchbox runtime error:", e)
        return st.text_input(label, key=f"text_{key}", placeholder="Escribe la dirección completa…")

def build_gmaps_url(origin, dest, stops=None):
    base = "https://www.google.com/maps/dir/?api=1"
    params = [
        f"origin={quote_plus(origin)}",
        f"destination={quote_plus(dest)}",
        "travelmode=driving"
    ]
    if stops:
        params.append(f"waypoints={quote_plus('|'.join(stops))}")
        params.append("optimize=true")
    return base + "&" + "&".join(params)

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
# INTERFAZ PRINCIPAL
# -------------------------------------------------
st.markdown("# 🗺️ Planificador de Rutas")
st.caption("Crea rutas con paradas usando direcciones completas. La última parada puede ser el destino final.")
tabs = st.tabs(["🧰 Profesional", "🧳 Viajero", "🏖️ Turístico"])

# ---- PROFESIONAL ----
with tabs[0]:
    st.subheader("Ruta de trabajo")
    st.caption("Planifica visitas a clientes, obras o inspecciones.")

    col1, col2 = st.columns([1, 1])
    with col1:
        origin_label = address_input("Dirección completa (origen)", "prof_origin_search")
    with col2:
        dest_label = address_input("Dirección completa (destino final)", "prof_dest_search")

    stops_text = st.text_area("Paradas intermedias (una por línea)", height=120)
    stops = [s.strip() for s in stops_text.splitlines() if s.strip()]

    if st.button("Generar ruta"):
        if not origin_label or not dest_label:
            st.error("Indica al menos **origen** y **destino**.")
        else:
            o = resolve_selection(origin_label, "prof_origin_search")
            d = resolve_selection(dest_label, "prof_dest_search")
            url = build_gmaps_url(o["address"], d["address"], stops if stops else None)
            st.success("Ruta generada")
            st.write(url)
            st.image(make_qr(url), caption="Escanea para abrir la ruta en el móvil")

# ---- VIAJERO ----
with tabs[1]:
    st.subheader("Plan rápido (viajero)")
    o = address_input("Origen", "trav_origin")
    d = address_input("Destino", "trav_dest")
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

# ---- TURÍSTICO ----
with tabs[2]:
    st.subheader("Ruta turística con varias paradas")
    o = address_input("Punto de inicio", "tour_origin")
    d = address_input("Punto final", "tour_dest")
    spots = st.text_area("Lugares a visitar (uno por línea)", height=120)
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
# PIE
# -------------------------------------------------
st.divider()
st.caption("Autocompletado: Google Places / SerpAPI / Nominatim (OSM). "
           "Añade tus claves en .env o st.secrets (`GOOGLE_PLACES_API_KEY`, `SERPAPI_API_KEY`).")