# app_utils.py
from urllib.parse import quote_plus
from io import BytesIO
import os
import requests
import qrcode
import streamlit as st
from dotenv import load_dotenv

# ---------- .env ----------
load_dotenv()

# ---------- claves ----------
def _get_key(name: str):
    """Intenta obtener primero de st.secrets y luego de variables de entorno."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)

GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY       = _get_key("SERPAPI_API_KEY") or _get_key("SERPAPI_KEY")

REQUEST_TIMEOUT = 8

# ---------- bias de ubicación (para centrar sugerencias) ----------
def set_location_bias(lat: float | None, lng: float | None, radius_m: int = 50000):
    """
    Guarda en session_state un bias para autocompletar: locationbias=circle:radius@lat,lng
    radius_m por defecto 50 km.
    """
    if lat is None or lng is None:
        st.session_state["__loc_bias"] = None
        return
    st.session_state["__loc_bias"] = {"lat": lat, "lng": lng, "r": int(radius_m)}

def _locationbias_qs() -> str:
    b = st.session_state.get("__loc_bias")
    if not b:
        return ""
    return f"&locationbias=circle:{b['r']}@{b['lat']},{b['lng']}"

# ---------- bucket en memoria para labels -> meta ----------
def _bucket_for(key_bucket: str) -> dict:
    if "suggest_maps" not in st.session_state:
        st.session_state["suggest_maps"] = {}
    sm = st.session_state["suggest_maps"]
    if key_bucket not in sm:
        sm[key_bucket] = {}
    return sm[key_bucket]

# ---------- Proveedores ----------
def provider_google_autocomplete(query: str, max_results: int = 8):
    out = []
    if not GOOGLE_PLACES_API_KEY or not query:
        return out
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            f"?input={quote_plus(query)}&types=geocode&language=es"
            f"{_locationbias_qs()}&key={GOOGLE_PLACES_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        preds = data.get("predictions", [])
        for p in preds[:max_results]:
            d, pid = p.get("description"), p.get("place_id")
            if d and pid:
                out.append((d, {"provider": "google", "place_id": pid, "desc": d}))
        # diagnóstico
        st.session_state["_suggest_diag"] = {
            "q": query,
            "g": len(out),
            "s": st.session_state.get("_suggest_diag", {}).get("s", 0),
            "n": st.session_state.get("_suggest_diag", {}).get("n", 0),
            "status": data.get("status")
        }
    except Exception as e:
        st.session_state["_suggest_diag"] = {"q": query, "g": 0, "s": 0, "n": 0, "err": str(e)}
    return out

def provider_serpapi_maps(query: str, max_results: int = 8):
    out = []
    if not SERPAPI_API_KEY or not query:
        return out
    try:
        url = f"https://serpapi.com/search.json?engine=google_maps&q={quote_plus(query)}&hl=es&api_key={SERPAPI_API_KEY}"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        res = r.json().get("local_results") or []
        for it in res[:max_results]:
            title = it.get("title") or ""
            addr  = it.get("address") or ""
            desc  = (f"{title} – {addr}").strip(" –")
            gps   = it.get("gps_coordinates") or {}
            lat, lng = gps.get("latitude"), gps.get("longitude")
            if desc:
                out.append((desc, {"provider": "serpapi", "lat": lat, "lng": lng, "desc": desc}))
        d = st.session_state.get("_suggest_diag", {}) ; d["s"] = len(out) ; st.session_state["_suggest_diag"] = d
    except Exception as e:
        d = st.session_state.get("_suggest_diag", {}) ; d["err"] = str(e) ; st.session_state["_suggest_diag"] = d
    return out

def provider_nominatim(query: str, max_results: int = 8):
    out = []
    if not query:
        return out
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={quote_plus(query)}&format=json&limit={max_results}"
        headers = {"User-Agent": "PlanificadorRutas/1.0 (streamlit)"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        arr = r.json()
        for it in arr[:max_results]:
            desc = it.get("display_name")
            lat, lng = it.get("lat"), it.get("lon")
            if desc:
                out.append((desc, {"provider":"nominatim","lat":lat,"lng":lng,"desc":desc}))
        d = st.session_state.get("_suggest_diag", {}) ; d["n"] = len(out) ; st.session_state["_suggest_diag"] = d
    except Exception as e:
        d = st.session_state.get("_suggest_diag", {}) ; d["err"] = str(e) ; st.session_state["_suggest_diag"] = d
    return out

def get_place_coords_from_google(place_id: str):
    if not GOOGLE_PLACES_API_KEY or not place_id:
        return {}
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
    except Exception:
        return {}

# ---------- Autocompletado unificado ----------
def suggest_addresses(query: str, key_bucket: str):
    q = (query or "").strip()
    if len(q) < 2:
        return []
    # Google primero, si falla usa SerpAPI y luego Nominatim
    results = provider_google_autocomplete(q) or provider_serpapi_maps(q) or provider_nominatim(q) or []
    # limpia tuplas
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
    # limita a 6 para el desplegable
    return labels[:6]

def resolve_selection(label: str, key_bucket: str):
    """
    Devuelve dict con: address, lat, lng, open_now.
    Busca en el bucket; si hay place_id usa detalles de Google.
    """
    if not label:
        return {"address": "", "lat": None, "lng": None, "open_now": None}

    # 1) Busca en el bucket del propio input
    meta = st.session_state.get("suggest_maps", {}).get(key_bucket, {}).get(label)

    # 2) Si no está, busca en todos los buckets (por si se copió de otra caja)
    if not meta:
        for bname, bdict in st.session_state.get("suggest_maps", {}).items():
            if isinstance(bdict, dict) and label in bdict:
                meta = bdict[label]
                break

    # 3) Si sigue sin meta, devolver address plano
    if not meta:
        return {"address": label, "lat": None, "lng": None, "open_now": None}

    if meta.get("provider") == "google" and meta.get("place_id"):
        det = get_place_coords_from_google(meta["place_id"])
        return {
            "address": det.get("address") or label,
            "lat": det.get("lat"),
            "lng": det.get("lng"),
            "open_now": det.get("open_now"),
        }
    # para serpapi/nominatim
    return {
        "address": meta.get("desc") or label,
        "lat": meta.get("lat"),
        "lng": meta.get("lng"),
        "open_now": meta.get("open_now"),
    }

# ---------- URL Google Maps + QR ----------
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