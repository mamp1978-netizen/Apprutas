# app_utils.py
from urllib.parse import quote_plus
from io import BytesIO
import os
import requests
import streamlit as st
import qrcode
from dotenv import load_dotenv

# -------- Carga .env (local) --------
load_dotenv()

# -------- Helpers para claves --------
def _get_key(name: str):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)

GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY       = _get_key("SERPAPI_API_KEY") or _get_key("SERPAPI_KEY")
REQUEST_TIMEOUT = 8

# Session token para mejorar resultados de Autocomplete
if "_g_session" not in st.session_state:
    st.session_state["_g_session"] = os.urandom(12).hex()

# -----------------------------------
#  Bias de ubicación para mejorar sugerencias
# -----------------------------------
def set_location_bias(lat: float, lng: float, radius_m: int = 50000):
    """Fija un sesgo de ubicación (círculo lat/lng/radio en metros) para el Autocomplete."""
    st.session_state["_loc_bias"] = {"lat": lat, "lng": lng, "radius_m": int(radius_m)}

def _get_locationbias_param() -> str:
    b = st.session_state.get("_loc_bias")
    if b and all(k in b for k in ("lat", "lng", "radius_m")):
        return f"circle:{b['radius_m']}@{b['lat']},{b['lng']}"
    # si no hay bias, usa ipbias (dejamos que Google centre por IP)
    return "ipbias"

# -----------------------------------
# Proveedores de sugerencias
# -----------------------------------
def provider_google_autocomplete(query: str, max_results: int = 8):
    """Google Places Autocomplete (tira de números de portal y se siente más 'Google')."""
    if not GOOGLE_PLACES_API_KEY or not query:
        return []

    try:
        params = {
            "input": query,
            "key": GOOGLE_PLACES_API_KEY,
            "language": "es",
            # address prioriza direcciones con números de portal frente a negocios
            "types": "address",
            # si quieres limitar país, descomenta -> "components": "country:es",
            "locationbias": _get_locationbias_param(),
            "sessiontoken": st.session_state["_g_session"],
        }
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        preds = data.get("predictions", [])
        out = []
        for p in preds[:max_results]:
            desc = p.get("description")
            pid  = p.get("place_id")
            if desc and pid:
                out.append((desc, {"provider":"google","place_id":pid,"desc":desc}))
        # diagnóstico
        _diag = st.session_state.get("_suggest_diag", {})
        _diag.update({"q":query, "g":len(out)})
        st.session_state["_suggest_diag"] = _diag
        return out
    except Exception as e:
        st.session_state["_suggest_diag"] = {"q": query, "g": 0, "err": str(e)}
        return []

def provider_serpapi_maps(query: str, max_results: int = 8):
    if not SERPAPI_API_KEY or not query:
        return []
    try:
        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_maps",
            "q": query,
            "hl": "es",
            "api_key": SERPAPI_API_KEY
        }
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
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
                out.append((desc, {"provider":"serpapi","lat":lat,"lng":lng,"desc":desc}))
        # diag
        _diag = st.session_state.get("_suggest_diag", {})
        _diag["s"] = len(out)
        st.session_state["_suggest_diag"] = _diag
        return out
    except Exception:
        return []

def provider_nominatim(query: str, max_results: int = 8):
    if not query:
        return []
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": max_results}
        headers = {"User-Agent": "PlanificadorRutas/1.0 (streamlit)"}
        r = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        arr = r.json()
        out = []
        for it in arr[:max_results]:
            desc = it.get("display_name")
            lat, lng = it.get("lat"), it.get("lon")
            if desc:
                out.append((desc, {"provider":"nominatim","lat":lat,"lng":lng,"desc":desc}))
        # diag
        _diag = st.session_state.get("_suggest_diag", {})
        _diag["n"] = len(out)
        st.session_state["_suggest_diag"] = _diag
        return out
    except Exception:
        return []

def get_place_coords_from_google(place_id: str):
    if not GOOGLE_PLACES_API_KEY:
        return {}
    try:
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "geometry,opening_hours,formatted_address,name",
            "language": "es",
            "key": GOOGLE_PLACES_API_KEY,
            "sessiontoken": st.session_state["_g_session"]
        }
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        d = r.json().get("result", {})
        loc = d.get("geometry", {}).get("location", {})
        return {
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "open_now": d.get("opening_hours", {}).get("open_now"),
            "address": d.get("formatted_address") or d.get("name")
        }
    except Exception:
        return {}

# -----------------------------------
# Autocompletado unificado + resolución
# -----------------------------------
def suggest_addresses(query: str, key_bucket: str, min_len: int = 1):
    q = (query or "").strip()
    if len(q) < min_len:
        return []

    # Google primero. Si no responde, caemos a SerpAPI y luego OSM.
    results = provider_google_autocomplete(q) \
              or provider_serpapi_maps(q) \
              or provider_nominatim(q) \
              or []

    # sanea
    clean = []
    for item in results:
        if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
            clean.append(item)
    if not clean:
        return []

    # bucket por campo (para poder resolver place_id luego)
    if "suggest_maps" not in st.session_state:
        st.session_state["suggest_maps"] = {}
    bucket = st.session_state["suggest_maps"].setdefault(key_bucket, {})

    labels = []
    for label, meta in clean:
        bucket[label] = meta
        labels.append(label)
    return labels

def resolve_selection(label: str, key_bucket: str):
    """Devuelve address/coords siempre; si hay place_id, detalla con Google."""
    if not label:
        return {"address": "", "lat": None, "lng": None, "open_now": None}

    meta = st.session_state.get("suggest_maps", {}).get(key_bucket, {}).get(label)
    if not meta:
        # sin meta: usamos el texto tal cual
        return {"address": label, "lat": None, "lng": None, "open_now": None}

    if meta.get("provider") == "google" and meta.get("place_id"):
        det = get_place_coords_from_google(meta["place_id"])
        return {
            "address": det.get("address") or label,
            "lat": det.get("lat"),
            "lng": det.get("lng"),
            "open_now": det.get("open_now"),
        }

    return {
        "address": meta.get("desc") or label,
        "lat": meta.get("lat"),
        "lng": meta.get("lng"),
        "open_now": meta.get("open_now")
    }

# -----------------------------------
# Google Maps URL + QR
# -----------------------------------
def build_gmaps_url(origin: str, destination: str, waypoints=None, *, mode="driving", avoid=None, optimize=True):
    base = "https://www.google.com/maps/dir/?api=1"
    parts = [
        f"origin={quote_plus(origin)}",
        f"destination={quote_plus(destination)}",
        f"travelmode={mode}"
    ]
    if avoid:
        parts.append(f"avoid={quote_plus(','.join(avoid))}")
    if waypoints:
        wp = "|".join(waypoints)
        if optimize and len(waypoints) > 1:
            wp = f"optimize:true|{wp}"
        parts.append(f"waypoints={quote_plus(wp)}")
    return base + "&" + "&".join(parts)

def make_qr(url: str) -> BytesIO:
    qr = qrcode.QRCode(border=1, box_size=6)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf