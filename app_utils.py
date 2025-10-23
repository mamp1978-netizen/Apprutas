# app_utils.py — utilidades puras (NO importa la UI)
import os
import typing as t
from urllib.parse import quote_plus

import streamlit as st

try:
    import googlemaps
except Exception:  # si no está instalada en local, no rompas
    googlemaps = None  # type: ignore

# --- Clave para Google Places (secrets primero, luego env) ---
API_KEY = (
    st.secrets.get("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_PLACES_API_KEY")
    or st.secrets.get("GOOGLE_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
)

gmaps = None
if googlemaps and API_KEY:
    try:
        gmaps = googlemaps.Client(key=API_KEY)
    except Exception:
        gmaps = None


# ------------------ Helpers internos ------------------ #
def _addr_from_any(x) -> t.Optional[str]:
    """Convierte str/dict a 'address' o 'lat,lng' en texto. None si no hay datos."""
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        return s or None
    if isinstance(x, dict):
        addr = x.get("address") or x.get("formatted_address")
        if isinstance(addr, str) and addr.strip():
            return addr.strip()
        lat = x.get("lat")
        lng = x.get("lng")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            return f"{lat},{lng}"
        latlng = (
            x.get("latlng")
            or x.get("location")
            or x.get("geometry", {}).get("location")
        )
        if isinstance(latlng, dict):
            lat = latlng.get("lat")
            lng = latlng.get("lng")
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                return f"{lat},{lng}"
    return None


# ------------------ Autocompletado / Places ------------------ #
def suggest_addresses(term: str, min_len: int = 3, max_results: int = 8) -> list[dict]:
    """Devuelve sugerencias de Google Places. Si no hay API/cliente, devuelve []."""
    if not term or len(term.strip()) < min_len:
        return []
    if gmaps is None:
        return []
    try:
        resp = gmaps.places_autocomplete(input_text=term, types="geocode") or []
        out: list[dict] = []
        for r in resp[:max_results]:
            out.append(
                {
                    "description": r.get("description", ""),
                    "place_id": r.get("place_id", ""),
                    "types": r.get("types", []),
                }
            )
        return out
    except Exception:
        return []


def resolve_selection(term: str, place_id: str | None = None) -> dict:
    """Devuelve address/lat/lng de un place_id. Si falla, vuelve con address=term."""
    base = {"query": term, "place_id": place_id, "address": term, "lat": None, "lng": None}
    if gmaps is None or not place_id:
        return base
    try:
        detail = gmaps.place(place_id=place_id) or {}
        result = detail.get("result", {}) if isinstance(detail, dict) else {}
        addr = result.get("formatted_address") or result.get("name") or term
        lat = None
        lng = None
        loc = result.get("geometry", {}).get("location", {})
        if isinstance(loc, dict):
            lat = loc.get("lat")
            lng = loc.get("lng")
        base.update({"address": addr, "lat": lat, "lng": lng})
        return base
    except Exception:
        return base


# ------------------ Construcción de URLs de rutas ------------------ #
def build_gmaps_url(
    origin,
    destination,
    waypoints=None,
    mode: str = "driving",
    avoid=None,
    optimize: bool = True,
):
    """URL de Google Maps. Acepta str o dicts en origin/destination/waypoints."""
    o = _addr_from_any(origin)
    d = _addr_from_any(destination)
    if not o or not d:
        return None

    parts = [
        "https://www.google.com/maps/dir/?api=1",
        f"origin={quote_plus(o)}",
        f"destination={quote_plus(d)}",
        f"travelmode={quote_plus((mode or 'driving').lower())}",
    ]

    if avoid:
        if isinstance(avoid, str):
            avoid_vals = [a.strip().lower() for a in avoid.split(",") if a.strip()]
        else:
            avoid_vals = [str(a).strip().lower() for a in (avoid or []) if str(a).strip()]
        allowed = {"tolls", "highways", "ferries", "indoor"}
        avoid_vals = [a for a in avoid_vals if a in allowed]
        if avoid_vals:
            parts.append(f"avoid={quote_plus(','.join(avoid_vals))}")

    if waypoints:
        if not isinstance(waypoints, (list, tuple)):
            waypoints = [waypoints]
        wp = []
        for w in waypoints:
            s = _addr_from_any(w)
            if s:
                wp.append(quote_plus(s))
        if wp:
            wp_str = ("optimize:true|" if optimize else "") + "|".join(wp)
            parts.append(f"waypoints={wp_str}")

    return "&".join(parts)


def build_waze_url(origin=None, destination=None):
    """URL de Waze. No soporta múltiples paradas; solo origen/destino."""
    d = _addr_from_any(destination)
    if not d:
        return None
    o = _addr_from_any(origin)
    if o:
        return f"https://waze.com/ul?from={quote_plus(o)}&to={quote_plus(d)}&navigate=yes"
    return f"https://waze.com/ul?to={quote_plus(d)}&navigate=yes"


def build_apple_maps_url(origin=None, destination=None):
    """URL de Apple Maps. Soporta origen+destino (sin paradas)."""
    o = _addr_from_any(origin)
    d = _addr_from_any(destination)
    if not d:
        return None
    parts = ["http://maps.apple.com/?dirflg=d"]
    if o:
        parts.append(f"saddr={quote_plus(o)}")
    parts.append(f"daddr={quote_plus(d)}")
    return "&".join(parts)


# ------------------ Bias opcional (no imprescindible) ------------------ #
def set_location_bias(location=None, radius_km=50):
    if not location:
        return None
    try:
        lat, lng = map(float, location)
        return {"locationBias": f"circle:{int(radius_km*1000)}@{lat},{lng}"}
    except Exception:
        return None


def _use_ip_bias(ip_address=None) -> bool:
    # Puedes implementar lógica real si quieres usar bias por IP
    return False
