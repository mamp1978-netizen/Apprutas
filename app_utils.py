# --- pega/actualiza en app_utils.py ---

from urllib.parse import quote_plus
from io import BytesIO
import os, uuid, requests
import streamlit as st
import qrcode
from dotenv import load_dotenv
load_dotenv()

# (… el resto de tu app_utils.py arriba/abajo debe quedarse igual …)

REQUEST_TIMEOUT = 8

def _get_key(name: str):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)

GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY       = _get_key("SERPAPI_API_KEY") or _get_key("SERPAPI_KEY")


# --- Localización aproximada por IP para sesgo de resultados (cache en session) ---
def _ensure_ip_bias():
    """Obtiene lat/lng aproximados por IP y los guarda en session_state una sola vez."""
    if "ip_bias" in st.session_state:
        return
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=5).json()
        lat = ip.get("latitude")
        lng = ip.get("longitude")
        if lat and lng:
            st.session_state["ip_bias"] = (float(lat), float(lng))
        else:
            st.session_state["ip_bias"] = None
    except Exception:
        st.session_state["ip_bias"] = None


# -------- Proveedor Google (con sessiontoken + locationbias “point:lat,lng|radius”) --------
def provider_google_autocomplete(query: str, max_results: int = 8):
    if not GOOGLE_PLACES_API_KEY or not query:
        return []

    _ensure_ip_bias()

    try:
        # Session token estable durante la edición del campo
        tok_key = "places_session_token"
        if tok_key not in st.session_state:
            st.session_state[tok_key] = uuid.uuid4().hex
        sessiontoken = st.session_state[tok_key]

        # Sesgo de ubicación (si tenemos lat/lng por IP)
        bias_param = ""
        if st.session_state.get("ip_bias"):
            lat, lng = st.session_state["ip_bias"]
            # radio 50km
            bias_param = f"&locationbias=point:{lat},{lng}|radius:50000"

        # Si sabes que casi todo es España, puedes acotar:
        # components=country:es  (coméntalo si quieres resultados globales)
        url = (
            "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            f"?input={quote_plus(query)}"
            f"&types=geocode"
            f"&language=es"
            f"&components=country:es"
            f"&key={GOOGLE_PLACES_API_KEY}"
            f"&sessiontoken={sessiontoken}"
            f"{bias_param}"
        )

        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        preds = r.json().get("predictions", [])

        out = []
        for p in preds[:max_results]:
            d = p.get("description")
            pid = p.get("place_id")
            if d and pid:
                out.append((d, {"provider": "google", "place_id": pid, "desc": d}))
        return out

    except Exception as e:
        print("Google autocomplete error:", e)
        return []


# -------- Otros proveedores como respaldo (se quedan tal cual o como ya tenías) --------
def provider_serpapi_maps(query: str, max_results: int = 8):
    if not SERPAPI_API_KEY or not query:
        return []
    try:
        url = (f"https://serpapi.com/search.json?engine=google_maps&q={quote_plus(query)}&hl=es"
               f"&api_key={SERPAPI_API_KEY}")
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        res = r.json().get("local_results") or []
        out = []
        for it in res[:max_results]:
            title = it.get("title") or ""
            addr  = it.get("address") or ""
            desc  = (f"{title} – {addr}").strip(" –")
            gps   = it.get("gps_coordinates") or {}
            lat, lng = gps.get("latitude"), gps.get("longitude")
            if desc:
                meta = {"provider": "serpapi", "lat": lat, "lng": lng, "desc": desc}
                out.append((desc, meta))
        return out
    except Exception as e:
        print("SerpAPI error:", e)
        return []


def provider_nominatim(query: str, max_results: int = 8):
    if not query:
        return []
    try:
        url = (f"https://nominatim.openstreetmap.org/search?q={quote_plus(query)}"
               "&format=json&limit={}".format(max_results))
        headers = {"User-Agent": "PlanificadorRutas/1.0 (streamlit)"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        arr = r.json()
        out = []
        for it in arr[:max_results]:
            desc = it.get("display_name")
            lat, lng = it.get("lat"), it.get("lon")
            if desc:
                out.append((desc, {"provider":"nominatim","lat":lat,"lng":lng,"desc":desc}))
        return out
    except Exception as e:
        print("Nominatim error:", e)
        return []


# -------- Autocompletado unificado (usa Google y cae a SERPAPI/OSM si hace falta) --------
def suggest_addresses(query: str, key_bucket: str):
    q = (query or "").strip()
    if len(q) < 2:
        return []
    results = (provider_google_autocomplete(q) 
               or provider_serpapi_maps(q) 
               or provider_nominatim(q) 
               or [])
    clean = []
    for item in results:
        if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
            clean.append(item)
    if not clean:
        return []
    bucket = _bucket_for(key_bucket)
    labels = []
    for label, meta in clean:
        bucket[label] = meta
        labels.append(label)
    return labels


def get_place_coords_from_google(place_id: str):
    if not GOOGLE_PLACES_API_KEY:
        return {}
    try:
        url = ("https://maps.googleapis.com/maps/api/place/details/json"
               f"?place_id={quote_plus(place_id)}&fields=geometry,opening_hours,formatted_address,name"
               f"&language=es&key={GOOGLE_PLACES_API_KEY}")
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
        print("Google details error:", e)
        return {}