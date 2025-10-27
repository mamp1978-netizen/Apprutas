import urllib.parse
import os
import streamlit as st
from dotenv import load_dotenv
import googlemaps

# Cargar variables de entorno
load_dotenv()
GMAPS_API_KEY = os.getenv("GOOGLE_API_KEY")

@st.cache_resource
def get_gmaps_client():
    key_to_use = GMAPS_API_KEY
    if not key_to_use:
        st.warning("ERROR: La clave GOOGLE_API_KEY no está configurada. La geocodificación será SIMULADA.")
        return None
    try:
        client = googlemaps.Client(key=key_to_use)
        client.geocode("Barcelona")
        return client
    except Exception:
        return None

GMAPS_CLIENT = get_gmaps_client()

# ---------------------------------------------------------
# Geocodificación
# ---------------------------------------------------------
def geocode_address(query):
    if not GMAPS_CLIENT:
        return None
    try:
        results = GMAPS_CLIENT.geocode(query)
        if results:
            loc = results[0]['geometry']['location']
            return {
                "address": results[0]['formatted_address'],
                "lat": loc['lat'],
                "lon": loc['lng']
            }
    except Exception:
        return None
    return None


def suggest_addresses(query, min_len=3, max_results=8):
    if not query or len(query.strip()) < min_len:
        return []
    return [{"description": query.strip()}]


def resolve_selection(label, meta=None):
    geo = geocode_address(label)
    if geo:
        coords = f"{geo['lat']},{geo['lon']}"
        return {"address": geo['address'], "coords": coords}
    return {"address": (label or "").strip(), "coords": (label or "").strip()}


# ---------------------------------------------------------
# Utilidades
# ---------------------------------------------------------
def _encode(s: str) -> str:
    return urllib.parse.quote_plus(s or "")

def _clean_waypoints(raw):
    """
    Normaliza y limpia cualquier rastro de 'optimize:true' para que JAMÁS entre como waypoint.
    Acepta lista de strings o lista de dicts {address/coords}.
    """
    cleaned = []
    for w in (raw or []):
        # extraer string base
        if isinstance(w, dict):
            s = w.get("coords") or w.get("address") or ""
        else:
            s = str(w or "")

        # normalización fuerte
        s = s.strip()
        if not s:
            continue
        # deshacer codificaciones que podrían camuflar 'optimize:true'
        s = s.replace("%7C", "|")
        s = urllib.parse.unquote_plus(s)

        low = s.lower()
        if low.startswith("optimize:true") or low == "optimize:true":
            # descartar completamente
            continue

        # por si alguien pegó 'optimize:true|Punto' entero como waypoint
        if low.startswith("optimize:true|"):
            s = s.split("|", 1)[1].strip()
            if not s:
                continue

        cleaned.append(s)
    return cleaned


# ---------------------------------------------------------
# Construcción de URLs Google / Waze / Apple
# ---------------------------------------------------------
def build_gmaps_url(origin_meta, destination_meta, waypoints_meta=None, mode="driving", avoid=None):
    """
    Construye la URL de Google Maps usando 'optimize:true' correctamente dentro del parámetro waypoints,
    evitando que Google lo trate como un punto adicional.
    """
    origin = origin_meta.get("coords", origin_meta.get("address"))
    destination = destination_meta.get("coords", destination_meta.get("address"))

    # Limpieza fuerte de waypoints (admita dicts o strings)
    waypoints_list = _clean_waypoints(waypoints_meta)

    params = [
        "api=1",
        f"origin={_encode(origin)}",
        f"destination={_encode(destination)}",
        f"travelmode={_encode(mode)}",
    ]
    if waypoints:
        encoded_waypoints = [_encode(w.strip()) for w in waypoints if (w or "").strip()]

       # 🔧 Si quieres evitar que se vea "optimize:true" en el enlace final, cambia optimize_flag=False
       optimize_flag = True

       if optimize_flag:
        waypoints_param = "optimize:true|" + "%7C".join(encoded_waypoints)
       else:
        waypoints_param = "%7C".join(encoded_waypoints)

    params.append(f"waypoints={waypoints_param}")

    if avoid:
        params.append(f"avoid={_encode(avoid)}")

    return "https://www.google.com/maps/dir/?" + "&".join(params)


def build_waze_url(origin_meta, destination_meta):
    origin = origin_meta.get("address")
    destination = destination_meta.get("address")
    if destination_meta.get("lat") and destination_meta.get("lon"):
        ll = f"{destination_meta['lat']},{destination_meta.get('lon')}"
        return f"https://waze.com/ul?ll={_encode(ll)}&navigate=yes&from_name={_encode(origin)}"
    return f"https://waze.com/ul?q={_encode(destination)}&navigate=yes&from_name={_encode(origin)}"


def build_apple_maps_url(origin_meta, destination_meta, waypoints=None):
    origin = origin_meta.get("address")
    destination = destination_meta.get("address")
    return f"https://maps.apple.com/?saddr={_encode(origin)}&daddr={_encode(destination)}&dirflg=d"


gmaps = bool(GMAPS_CLIENT)
