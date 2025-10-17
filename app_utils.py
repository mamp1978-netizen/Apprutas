from urllib.parse import quote_plus
from io import BytesIO
import os
import requests
import streamlit as st
import qrcode
from dotenv import load_dotenv

# ----------------- Config -----------------
load_dotenv()

def _get_key(name: str):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)

GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY = _get_key("SERPAPI_API_KEY") or _get_key("SERPAPI_KEY")
REQUEST_TIMEOUT = 8

if "suggest_maps" not in st.session_state:
    st.session_state.suggest_maps = {}

# ----------------- Proveedores -----------------
def _google_autocomplete(query: str, max_results: int = 8):
    if not GOOGLE_PLACES_API_KEY:
        return []
    try:
        url = ("https://maps.googleapis.com/maps/api/place/autocomplete/json"
               f"?input={quote_plus(query)}&types=geocode&language=es&key={GOOGLE_PLACES_API_KEY}")
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        preds = data.get("predictions", [])
        out = []
        for p in preds[:max_results]:
            d, pid = p.get("description"), p.get("place_id")
            if d and pid:
                out.append((d, {"provider":"google","place_id":pid,"desc":d}))
        return out
    except Exception as e:
        print("Google autocomplete error:", e)
        return []

def _serpapi_maps(query: str, max_results: int = 8):
    if not SERPAPI_API_KEY:
        return []
    try:
        url = (f"https://serpapi.com/search.json?engine=google_maps&q={quote_plus(query)}&hl=es"
               f"&api_key={SERPAPI_API_KEY}")
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        js = r.json()
        res = js.get("local_results") or []
        out = []
        for it in res[:max_results]:
            title = it.get("title") or ""
            addr  = it.get("address") or ""
            desc  = (f"{title} – {addr}").strip(" –")
            gps   = it.get("gps_coordinates") or {}
            lat, lng = gps.get("latitude"), gps.get("longitude")
            if desc and lat and lng:
                out.append((desc, {"provider":"serpapi","lat":lat,"lng":lng,"desc":desc}))
        return out
    except Exception as e:
        print("SerpAPI error:", e)
        return []

def _nominatim(query: str, max_results: int = 8):
    try:
        url = (f"https://nominatim.openstreetmap.org/search?q={quote_plus(query)}"
               "&format=json&addressdetails=0&limit={}".format(max_results))
        headers = {"User-Agent":"PlanificadorRutas/1.0 (streamlit)"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        arr = r.json()
        out = []
        for it in arr[:max_results]:
            desc = it.get("display_name")
            lat, lng = it.get("lat"), it.get("lon")
            if desc and lat and lng:
                out.append((desc, {"provider":"nominatim","lat":float(lat),"lng":float(lng),"desc":desc}))
        return out
    except Exception as e:
        print("Nominatim error:", e)
        return []

def _google_details(place_id: str):
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

# ----------------- Autocompletado unificado -----------------
def _suggest_addresses(query: str, bucket_key: str):
    q = (query or "").strip()
    if len(q) < 2:
        return []

    results = _google_autocomplete(q) or _serpapi_maps(q) or _nominatim(q) or []
    clean = []
    for item in results:
        if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
            clean.append(item)
    if not clean:
        return []

    bucket = st.session_state.suggest_maps.setdefault(bucket_key, {})
    labels = []
    for label, meta in clean:
        bucket[label] = meta
        labels.append(label)
    return labels

# ----------------- API pública para pestañas -----------------
def address_input(label: str, key: str):
    """Autocompletar con fallback a text_input si el componente falla/no existe."""
    try:
        from streamlit_searchbox import st_searchbox  # import local para evitar fallos globales
        return st_searchbox(
            search_function=lambda q: _suggest_addresses(q, bucket_key=key),
            label=label,
            key=key,
            default=None
        )
    except Exception as e:
        st.warning("Autocompletado no disponible; usando campo de texto.")
        print("st_searchbox error:", e)
        return st.text_input(label, key=f"text_{key}", placeholder="Escribe la dirección completa…")

def resolve_selection(label: str, bucket_key: str):
    meta = st.session_state.suggest_maps.get(bucket_key, {}).get(label)
    if not meta:
        return {"address": label, "lat": None, "lng": None, "open_now": None}

    if meta.get("provider") == "google" and meta.get("place_id"):
        det = _google_details(meta["place_id"])
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

def build_gmaps_url(origin: str, destination: str, waypoints=None):
    base = "https://www.google.com/maps/dir/?api=1"
    parts = [
        f"origin={quote_plus(origin)}",
        f"destination={quote_plus(destination)}",
        "travelmode=driving"
    ]
    if waypoints:
        parts.append(f"waypoints={quote_plus('|'.join(waypoints))}")
        parts.append("optimize=true")
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