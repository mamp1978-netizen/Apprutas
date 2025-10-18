# app_utils.py
from urllib.parse import quote_plus
from io import BytesIO
from uuid import uuid4
import os
import requests
import streamlit as st
import qrcode
from dotenv import load_dotenv

# -------- Carga .env --------
load_dotenv()

def _get_key(name: str):
    """Obtiene una clave de st.secrets o de variables de entorno."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)

GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY       = _get_key("SERPAPI_API_KEY") or _get_key("SERPAPI_KEY")
REQUEST_TIMEOUT = 8


# ============================
#   SessionState helpers
# ============================

def _bucket_for(key_bucket: str) -> dict:
    """Devuelve (y crea si no existe) el sub-bucket de sugerencias para 'key_bucket'."""
    if "suggest_maps" not in st.session_state:
        st.session_state["suggest_maps"] = {}
    sm = st.session_state["suggest_maps"]
    if key_bucket not in sm:
        sm[key_bucket] = {}
    return sm[key_bucket]

def _get_autocomplete_token(bucket: str) -> str:
    """Token de sesión para Autocomplete (mejora calidad/coste)."""
    key = f"autocomplete_token__{bucket}"
    tok = st.session_state.get(key)
    if not tok:
        tok = uuid4().hex
        st.session_state[key] = tok
    return tok

def reset_autocomplete_token(bucket: str):
    key = f"autocomplete_token__{bucket}"
    if key in st.session_state:
        del st.session_state[key]

def set_user_bias_coords(lat: float, lng: float):
    st.session_state["user_bias_lat"] = lat
    st.session_state["user_bias_lng"] = lng

def get_user_bias_coords():
    return (
        st.session_state.get("user_bias_lat"),
        st.session_state.get("user_bias_lng"),
    )


# ============================
#   Proveedores
# ============================

def provider_google_autocomplete(
    query: str,
    max_results: int = 8,
    *,
    country: str | None = "ES",
    bias_lat: float | None = None,
    bias_lng: float | None = None,
    bucket: str = "prof_top",
):
    """Google Places Autocomplete con types=address, country y sessiontoken."""
    if not GOOGLE_PLACES_API_KEY or not query:
        return []
    try:
        token = _get_autocomplete_token(bucket)

        base = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": query,
            "language": "es",
            "types": "address",             # prioriza direcciones (con número si hay)
            "key": GOOGLE_PLACES_API_KEY,
            "sessiontoken": token,          # agrupa la sesión de tecleo del usuario
        }
        if country:
            params["components"] = f"country:{country}"
        if bias_lat is not None and bias_lng is not None:
            params["locationbias"] = f"point:{bias_lat},{bias_lng}"

        r = requests.get(base, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        preds = r.json().get("predictions", [])

        out = []
        for p in preds[:max_results]:
            desc = p.get("description")
            pid  = p.get("place_id")
            if desc and pid:
                out.append((desc, {"provider": "google", "place_id": pid, "desc": desc}))
        return out
    except Exception as e:
        print("Google autocomplete error:", e)
        return []

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

def get_place_coords_from_google(place_id: str):
    """Place Details: devuelve dirección formateada, lat/lng y estado abierto si existe."""
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


# ============================
#   Autocompletado unificado
# ============================

def suggest_addresses(query: str, key_bucket: str):
    """Devuelve lista de labels y guarda meta en el bucket de session_state."""
    q = (query or "").strip()
    if len(q) < 2:
        return []

    bias_lat = st.session_state.get("user_bias_lat")
    bias_lng = st.session_state.get("user_bias_lng")

    results = (
        provider_google_autocomplete(
            q, max_results=8, country="ES", bias_lat=bias_lat, bias_lng=bias_lng, bucket=key_bucket
        )
        or provider_serpapi_maps(q)
        or provider_nominatim(q)
        or []
    )

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


def resolve_selection(label: str, key_bucket: str):
    """
    Devuelve siempre un dict con:
      {address: str, lat: float|None, lng: float|None, open_now: bool|None}
    Busca primero en el bucket indicado; si no, en todos los buckets (por si se copió la meta).
    """
    if not label:
        return {"address": "", "lat": None, "lng": None, "open_now": None}

    sm = st.session_state.get("suggest_maps", {})
    meta = sm.get(key_bucket, {}).get(label)

    # Búsqueda en todos los buckets si no lo encontramos en el actual
    if not meta:
        for bname, sub in sm.items():
            if isinstance(sub, dict) and label in sub:
                meta = sub[label]
                break

    if not meta:
        # Sin meta: usamos tal cual lo tecleado
        return {"address": label, "lat": None, "lng": None, "open_now": None}

    # Si tiene place_id, tiramos Place Details (recoge número de portal cuando existe)
    if meta.get("provider") == "google" and meta.get("place_id"):
        det = get_place_coords_from_google(meta["place_id"])
        return {
            "address": det.get("address") or meta.get("desc") or label,
            "lat": det.get("lat"),
            "lng": det.get("lng"),
            "open_now": det.get("open_now"),
        }

    # Meta de otros proveedores
    return {
        "address": meta.get("desc") or label,
        "lat": meta.get("lat"),
        "lng": meta.get("lng"),
        "open_now": meta.get("open_now"),
    }


# ============================
#   URL Google Maps + QR
# ============================

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