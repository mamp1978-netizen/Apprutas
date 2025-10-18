# app_utils.py
import os
import json
import requests
import qrcode
import streamlit as st
from io import BytesIO
from urllib.parse import quote_plus
from dotenv import load_dotenv

# ---------- CARGA .env ----------
load_dotenv()

# ---------- CLAVES ----------
def _get_key(name: str):
    """Intenta obtener la clave desde .env o desde st.secrets"""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, "")

GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY = _get_key("SERPAPI_API_KEY")

REQUEST_TIMEOUT = 12

# ---------- DEPÓSITO DE RESULTADOS ----------
def _bucket_for(key: str):
    """Crea o recupera un diccionario temporal donde guardar datos asociados a un widget."""
    key_full = f"_bucket_{key}"
    if key_full not in st.session_state:
        st.session_state[key_full] = {}
    return st.session_state[key_full]

# ---------- PROVEEDORES ----------

def provider_google_autocomplete(query: str, max_results: int = 8):
    """Usa Google Places Autocomplete API"""
    if not GOOGLE_PLACES_API_KEY or not query:
        return [], "no-key-or-empty"
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            f"?input={quote_plus(query)}"
            "&types=address"
            "&language=es"
            f"&key={GOOGLE_PLACES_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "OK":
            return [], f"google:{data.get('status')}:{data.get('error_message')}"
        preds = data.get("predictions", [])
        out = []
        for p in preds[:max_results]:
            d, pid = p.get("description"), p.get("place_id")
            if d and pid:
                out.append((d, {"provider": "google", "place_id": pid, "desc": d}))
        return out, ""
    except Exception as e:
        return [], f"google-ex:{e}"


def provider_serpapi_maps(query: str, max_results: int = 8):
    """Alternativa: SerpAPI Google Maps"""
    if not SERPAPI_API_KEY or not query:
        return [], "no-key-or-empty"
    try:
        url = (
            f"https://serpapi.com/search.json?engine=google_maps&q={quote_plus(query)}&hl=es"
            f"&api_key={SERPAPI_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        res = r.json().get("local_results") or []
        out = []
        for it in res[:max_results]:
            title = it.get("title") or ""
            addr = it.get("address") or ""
            desc = (f"{title} – {addr}").strip(" –")
            gps = it.get("gps_coordinates") or {}
            lat, lng = gps.get("latitude"), gps.get("longitude")
            if desc:
                meta = {"provider": "serpapi", "lat": lat, "lng": lng, "desc": desc}
                out.append((desc, meta))
        return out, ""
    except Exception as e:
        return [], f"serp-ex:{e}"


def provider_nominatim(query: str, max_results: int = 8):
    """Respaldo: Nominatim (OpenStreetMap)"""
    if not query:
        return [], "empty"
    try:
        url = (
            f"https://nominatim.openstreetmap.org/search?q={quote_plus(query)}"
            "&format=json&limit={}".format(max_results)
        )
        headers = {"User-Agent": "PlanificadorRutas/1.0 (streamlit)"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        arr = r.json()
        out = []
        for it in arr[:max_results]:
            desc = it.get("display_name")
            lat, lng = it.get("lat"), it.get("lon")
            if desc:
                out.append((desc, {"provider": "nominatim", "lat": lat, "lng": lng, "desc": desc}))
        return out, ""
    except Exception as e:
        return [], f"nom-ex:{e}"

# ---------- FUNCIÓN PRINCIPAL ----------

def suggest_addresses(query: str, key_bucket: str):
    """Obtiene sugerencias desde los proveedores disponibles."""
    q = (query or "").strip()
    if len(q) < 2:
        st.session_state["_suggest_diag"] = {"q": q, "g": 0, "s": 0, "n": 0, "err": "short"}
        return []

    g, gerr = provider_google_autocomplete(q)
    s, serr = provider_serpapi_maps(q) if not g else ([], "")
    n, nerr = provider_nominatim(q) if (not g and not s) else ([], "")

    diag = {"q": q, "g": len(g), "s": len(s), "n": len(n), "err": ";".join([x for x in (gerr, serr, nerr) if x])}
    st.session_state["_suggest_diag"] = diag

    results = g or s or n or []
    if results:
        bucket = _bucket_for(key_bucket)
        labels = []
        for label, meta in results:
            bucket[label] = meta
            labels.append(label)
        return labels
    return []

# ---------- RESOLVE + GMAPS + QR ----------

def resolve_selection(label: str, key_bucket: str):
    """Devuelve metadatos guardados o estructura mínima"""
    bucket = _bucket_for(key_bucket)
    data = bucket.get(label)
    if data:
        return data
    return {"provider": "manual", "address": label, "open_now": None}


def build_gmaps_url(origin: str, destination: str, waypoints=None, mode="driving", avoid=None, optimize=False):
    """Construye una URL de Google Maps Directions"""
    base = "https://www.google.com/maps/dir/?api=1"
    params = [
        f"origin={quote_plus(origin)}",
        f"destination={quote_plus(destination)}",
        f"travelmode={mode}"
    ]
    if waypoints:
        waypoints_str = "|".join(waypoints)
        if optimize:
            waypoints_str = "optimize:true|" + waypoints_str
        params.append(f"waypoints={quote_plus(waypoints_str)}")
    if avoid:
        params.append(f"avoid={'|'.join(avoid)}")
    return base + "&" + "&".join(params)


def make_qr(url: str) -> BytesIO:
    """Crea un código QR con la URL dada"""
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf