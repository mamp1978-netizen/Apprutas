# app_utils.py
from urllib.parse import quote_plus
from io import BytesIO
import os
import re
import requests
import streamlit as st
import qrcode
from dotenv import load_dotenv

# -------- Carga .env / claves --------
load_dotenv()

def _get_key(name: str):
    """Lee primero de st.secrets, si no existe usa os.environ."""
    try:
        if name in st.secrets:  # type: ignore[attr-defined]
            return st.secrets[name]  # type: ignore[index]
    except Exception:
        pass
    return os.getenv(name)

GOOGLE_PLACES_API_KEY = _get_key("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY       = _get_key("SERPAPI_API_KEY") or _get_key("SERPAPI_KEY")
NOMINATIM_EMAIL       = _get_key("NOMINATIM_EMAIL")  # opcional, recomendado por OSM
REQUEST_TIMEOUT = 8

# Google Maps (URL Directions) suele admitir hasta ~23 waypoints intermedios.
MAX_WAYPOINTS = 23

# ---- helper seguro para el bucket de sugerencias ----
def _bucket_for(key_bucket: str) -> dict:
    """Devuelve el sub-bucket para key_bucket, creando lo necesario en session_state."""
    if "suggest_maps" not in st.session_state:
        st.session_state["suggest_maps"] = {}
    sm = st.session_state["suggest_maps"]
    if key_bucket not in sm:
        sm[key_bucket] = {}
    return sm[key_bucket]

def _norm_text(x: str | None) -> str:
    x = (x or "").strip()
    # quita múltiple espacio y separadores raros
    x = re.sub(r"\s+", " ", x)
    return x

# -------- Proveedores (con cache) --------
@st.cache_data(ttl=600, show_spinner=False)
def provider_google_autocomplete(query: str, max_results: int = 8, *, lang: str = "es"):
    if not GOOGLE_PLACES_API_KEY or not query:
        return []
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            f"?input={quote_plus(query)}&types=geocode&language={quote_plus(lang)}&key={GOOGLE_PLACES_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        preds = r.json().get("predictions", []) or []
        out = []
        for p in preds[:max_results]:
            d = _norm_text(p.get("description"))
            pid = p.get("place_id")
            if d and pid:
                out.append((d, {"provider": "google", "place_id": pid, "desc": d}))
        return out
    except Exception as e:
        print("Google autocomplete error:", e)
        return []

@st.cache_data(ttl=600, show_spinner=False)
def provider_serpapi_maps(query: str, max_results: int = 8, *, lang: str = "es"):
    if not SERPAPI_API_KEY or not query:
        return []
    try:
        url = (
            f"https://serpapi.com/search.json?engine=google_maps"
            f"&q={quote_plus(query)}&hl={quote_plus(lang)}&api_key={SERPAPI_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        res = r.json().get("local_results") or []
        out = []
        for it in res[:max_results]:
            title = it.get("title") or ""
            addr  = it.get("address") or ""
            desc  = _norm_text((f"{title} – {addr}").strip(" –"))
            gps   = it.get("gps_coordinates") or {}
            lat, lng = gps.get("latitude"), gps.get("longitude")
            if desc:
                meta = {"provider": "serpapi", "lat": lat, "lng": lng, "desc": desc}
                out.append((desc, meta))
        return out
    except Exception as e:
        print("SerpAPI error:", e)
        return []

@st.cache_data(ttl=600, show_spinner=False)
def provider_nominatim(query: str, max_results: int = 8):
    if not query:
        return []
    try:
        url = (
            f"https://nominatim.openstreetmap.org/search"
            f"?q={quote_plus(query)}&format=json&limit={max_results}"
        )
        headers = {
            "User-Agent": "PlanificadorRutas/1.0 (streamlit)",
        }
        # OSM recomienda incluir email de contacto si es posible
        if NOMINATIM_EMAIL:
            headers["From"] = NOMINATIM_EMAIL

        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        arr = r.json() or []
        out = []
        for it in arr[:max_results]:
            desc = _norm_text(it.get("display_name"))
            lat, lng = it.get("lat"), it.get("lon")
            if desc:
                out.append((desc, {"provider":"nominatim","lat":lat,"lng":lng,"desc":desc}))
        return out
    except Exception as e:
        print("Nominatim error:", e)
        return []

@st.cache_data(ttl=600, show_spinner=False)
def get_place_coords_from_google(place_id: str, *, lang: str = "es"):
    if not GOOGLE_PLACES_API_KEY:
        return {}
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/details/json"
            f"?place_id={quote_plus(place_id)}"
            f"&fields=geometry,opening_hours,formatted_address,name"
            f"&language={quote_plus(lang)}&key={GOOGLE_PLACES_API_KEY}"
        )
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        d = r.json().get("result", {}) or {}
        loc = d.get("geometry", {}).get("location", {}) or {}
        return {
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "open_now": d.get("opening_hours", {}).get("open_now"),
            "address": _norm_text(d.get("formatted_address") or d.get("name")),
        }
    except Exception as e:
        print("Google details error:", e)
        return {}

# -------- Autocompletado unificado --------
def suggest_addresses(query: str, key_bucket: str, *, lang: str = "es"):
    """Devuelve lista de labels. Guarda metadata por label en session_state.suggest_maps[bucket]."""
    q = _norm_text(query)
    if len(q) < 2:
        return []
    results = (
        provider_google_autocomplete(q, lang=lang)
        or provider_serpapi_maps(q, lang=lang)
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

def resolve_selection(label: str, key_bucket: str, *, lang: str = "es"):
    """Devuelve siempre address (texto). Si hay meta de Google, añade open_now/coords."""
    label = _norm_text(label)
    if not label:
        return {"address": "", "lat": None, "lng": None, "open_now": None}
    meta = st.session_state.get("suggest_maps", {}).get(key_bucket, {}).get(label)
    if not meta:
        return {"address": label, "lat": None, "lng": None, "open_now": None}
    if meta.get("provider") == "google" and meta.get("place_id"):
        det = get_place_coords_from_google(meta["place_id"], lang=lang)
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
        "open_now": meta.get("open_now"),
    }

# -------- URL Google Maps + QR --------
def _clamp_waypoints(waypoints: list[str] | None) -> list[str] | None:
    """Asegura que no superamos el máximo recomendado de paradas intermedias."""
    if not waypoints:
        return None
    # Limpia duplicados triviales y vacíos
    clean = [w for w in map(_norm_text, waypoints) if w]
    # Google Maps suele tolerar hasta ~23 waypoints (intermedios). Ajustamos por seguridad.
    if len(clean) > MAX_WAYPOINTS:
        clean = clean[:MAX_WAYPOINTS]
    return clean

def build_gmaps_url(
    origin: str,
    destination: str,
    waypoints: list[str] | None = None,
    *,
    mode: str = "driving",
    avoid: list[str] | None = None,
    optimize: bool = True
) -> str:
    """
    Construye URL para Google Maps Directions (UI) con api=1.
    - origin/destination: textos completos
    - waypoints: lista de paradas intermedias (se hace clamp por si excede límites)
    - mode: driving|walking|bicycling|transit
    - avoid: p.ej. ["tolls","highways","ferries"]
    - optimize: si True y hay >1 waypoint, añade optimize:true (permite a Maps optimizar orden)
    """
    origin = _norm_text(origin)
    destination = _norm_text(destination)
    wp = _clamp_waypoints(waypoints)

    base = "https://www.google.com/maps/dir/?api=1"
    parts = [
        f"origin={quote_plus(origin)}",
        f"destination={quote_plus(destination)}",
        f"travelmode={quote_plus(mode)}",
    ]
    if avoid:
        parts.append(f"avoid={quote_plus(','.join(avoid))}")

    if wp:
        wp_str = "|".join(wp)
        if optimize and len(wp) > 1:
            wp_str = f"optimize:true|{wp_str}"
        parts.append(f"waypoints={quote_plus(wp_str)}")

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