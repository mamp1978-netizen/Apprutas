# app_utils_core.py
import os
import urllib.parse
import streamlit as st
from dotenv import load_dotenv
import googlemaps

# ---------------------------------------------------------
# Cargar variables de entorno
# ---------------------------------------------------------
load_dotenv()
GMAPS_API_KEY = os.getenv("GOOGLE_API_KEY")

@st.cache_resource
def get_gmaps_client():
    """
    Devuelve el cliente de Google Maps si hay API KEY.
    Si no hay clave o la API falla, retorna None (modo simulado).
    """
    key_to_use = GMAPS_API_KEY
    if not key_to_use:
        st.warning(
            "ERROR: La clave GOOGLE_API_KEY no está configurada. "
            "La geocodificación será SIMULADA."
        )
        return None
    try:
        client = googlemaps.Client(key=key_to_use)
        # Sondeo rápido para validar credenciales
        client.geocode("Barcelona")
        return client
    except Exception:
        return None

GMAPS_CLIENT = get_gmaps_client()

# ---------------------------------------------------------
# Geocodificación
# ---------------------------------------------------------
def geocode_address(query: str):
    """Geocodifica una dirección. Devuelve dict con address/lat/lon o None."""
    if not GMAPS_CLIENT:
        return None
    try:
        results = GMAPS_CLIENT.geocode(query)
        if results:
            loc = results[0]["geometry"]["location"]
            return {
                "address": results[0]["formatted_address"],
                "lat": loc["lat"],
                "lon": loc["lng"],
            }
    except Exception:
        return None
    return None


def suggest_addresses(query: str, min_len: int = 3, max_results: int = 8):
    """Stub sencillo para sugerencias (puedes reemplazar por Places si quieres)."""
    if not query or len(query.strip()) < min_len:
        return []
    return [{"description": query.strip()}]


def resolve_selection(label: str, meta=None):
    """
    Convierte texto a metadatos con address/coords si hay API;
    si no, deja el texto tal cual como fallback.
    """
    geo = geocode_address(label)
    if geo:
        coords = f"{geo['lat']},{geo['lon']}"
        return {"address": geo["address"], "coords": coords}
    txt = (label or "").strip()
    return {"address": txt, "coords": txt}

# ---------------------------------------------------------
# Utilidades
# ---------------------------------------------------------
def _encode(s: str) -> str:
    """URL-encode con quote_plus (espacios como '+')."""
    return urllib.parse.quote_plus(s or "")


def _clean_waypoints(raw):
    """
    Normaliza y limpia cualquier rastro de 'optimize:true' para que NUNCA
    entre como waypoint. Acepta lista de strings o de dicts {address/coords}.
    Devuelve lista de strings (cada uno ya limpio).
    """
    cleaned = []
    for w in (raw or []):
        # extraer string base
        if isinstance(w, dict):
            s = w.get("coords") or w.get("address") or ""
        else:
            s = str(w or "")

        s = s.strip()
        if not s:
            continue

        # deshacer codificaciones que podrían camuflar 'optimize:true'
        s = s.replace("%7C", "|")
        s = urllib.parse.unquote_plus(s)
        low = s.lower()

        # descartar 'optimize:true' suelto
        if low == "optimize:true" or low.startswith("optimize:true "):
            continue

        # si alguien pegó 'optimize:true|Punto'
        if low.startswith("optimize:true|"):
            s = s.split("|", 1)[1].strip()
            if not s:
                continue

        cleaned.append(s)
    return cleaned

# ---------------------------------------------------------
# Construcción de URLs Google / Waze / Apple
# ---------------------------------------------------------
def build_gmaps_url(
    origin_meta,
    destination_meta,
    waypoints_meta=None,
    mode: str = "driving",
    avoid: str | None = None,
):
    """
    Construye la URL de Google Maps usando 'optimize:true' correctamente dentro
    del parámetro 'waypoints', evitando que Google lo trate como una parada más.
    """
    # Origen/Destino: prioriza coords si existen
    origin = origin_meta.get("coords", origin_meta.get("address"))
    destination = destination_meta.get("coords", destination_meta.get("address"))

    # Limpieza fuerte de waypoints (acepta dicts/strings)
    waypoints_list = _clean_waypoints(waypoints_meta)

    params = [
        "api=1",
        f"origin={_encode(origin)}",
        f"destination={_encode(destination)}",
        f"travelmode={_encode(mode)}",
    ]

    if waypoints_list:
        encoded_waypoints = [_encode(w) for w in waypoints_list]

        # Cambia esta bandera si NO quieres que Google reordene las paradas
        optimize_flag = False

        if optimize_flag:
            # Google espera exactamente: optimize:true|wp1|wp2|...
            waypoints_param = "optimize:False|" + "%7C".join(encoded_waypoints)
        else:
            waypoints_param = "%7C".join(encoded_waypoints)

        params.append(f"waypoints={waypoints_param}")

    if avoid:
        params.append(f"avoid={_encode(avoid)}")

    return "https://www.google.com/maps/dir/?" + "&".join(params)


def build_waze_url(origin_meta, destination_meta):
    """Waze: usa address; si hay lat/lon de destino, mejor con ?ll=""."""
    origin = origin_meta.get("address")
    destination = destination_meta.get("address")

    if destination_meta.get("lat") and destination_meta.get("lon"):
        ll = f"{destination_meta['lat']},{destination_meta['lon']}"
        return (
            "https://waze.com/ul"
            f"?ll={_encode(ll)}&navigate=yes&from_name={_encode(origin)}"
        )

    return (
        "https://waze.com/ul"
        f"?q={_encode(destination)}&navigate=yes&from_name={_encode(origin)}"
    )


def build_apple_maps_url(origin_meta, destination_meta, waypoints=None):
    """Apple Maps usa address para saddr/daddr."""
    origin = origin_meta.get("address")
    destination = destination_meta.get("address")
    return (
        "https://maps.apple.com/"
        f"?saddr={_encode(origin)}&daddr={_encode(destination)}&dirflg=d"
    )

# Bandera de “API disponible”
gmaps = bool(GMAPS_CLIENT)