import streamlit as st
import googlemaps
import os
from qrcode import make as make_qr_code 
from io import BytesIO
from urllib.parse import quote

# Inicialización del cliente de Google Maps
API_KEY = st.secrets.get("GOOGLE_PLACES_API_KEY") or os.environ.get("GOOGLE_PLACES_API_KEY") 
gmaps = googlemaps.Client(key=API_KEY) if API_KEY else None

# Bucket de metadatos (para almacenar place_id/lat/lng asociados a las sugerencias)
if "_metadata" not in st.session_state:
    st.session_state["_metadata"] = {}

# -------------------------------
# FUNCIONES DE GOOGLE MAPS/PLACES
# -------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def suggest_addresses(address_term: str, key_bucket: str, min_len: int = 3) -> list:
    """Busca sugerencias de direcciones usando la API de Places Autocomplete."""
    if not gmaps or not address_term or len(address_term) < min_len:
        return []

    try:
        predictions = gmaps.places_autocomplete(
            input_text=address_term,
            language='es'
        )
        
        suggestions = []
        resolved_meta = {}
        
        for p in predictions:
            description = p.get("description")
            place_id = p.get("place_id")
            
            if description and place_id:
                suggestions.append(description)
                resolved_meta[description] = {"place_id": place_id}

        st.session_state["_metadata"][key_bucket] = resolved_meta
        return suggestions
        
    except Exception as e:
        return []

@st.cache_data(show_spinner=False, ttl=3600)
def _gmaps_place_details(place_id: str) -> dict:
    """Obtiene los detalles completos de un Place ID (Dirección y Geometría)."""
    if not gmaps:
        return None
    try:
        details = gmaps.place(
            place_id=place_id,
            fields=['formatted_address', 'geometry'],
            language='es'
        )
        result = details.get('result', {})
        if not result:
             return None
             
        address = result.get('formatted_address', place_id)
        location = result.get('geometry', {}).get('location', {})
        lat = location.get('lat')
        lng = location.get('lng')

        return {
            "address": address,
            "lat": lat,
            "lng": lng
        }
    except Exception as e:
        return None
        

def resolve_selection(selection_text: str, key_bucket: str) -> dict:
    """Resuelve la selección de una dirección a sus metadatos (Place ID, dirección formateada)."""
    
    resolved_meta = st.session_state.get("_metadata", {}).get(key_bucket, {})
    place_meta = resolved_meta.get(selection_text, {})
    place_id = place_meta.get("place_id")
    
    if place_id:
        details = _gmaps_place_details(place_id)
        if details:
            return details
        
    return {"address": selection_text, "lat": None, "lng": None}


def set_location_bias(lat: float, lng: float):
    """Establece el sesgo de ubicación para la búsqueda de direcciones."""
    st.session_state["_loc_bias"] = {"lat": lat, "lng": lng}

def _use_ip_bias():
    """Simula la obtención de la IP para sesgar la búsqueda (solo un placeholder)."""
    # Ejemplo: Madrid, España
    set_location_bias(40.4168, -3.7038)


# -------------------------------
# CONSTRUCCIÓN DE ENLACES Y QR
# -------------------------------

def build_gmaps_url(origin: str, destination: str, waypoints: list = None, mode: str = "driving", avoid: str = None, optimize: bool = True) -> str:
    """
    Construye una URL de Google Maps para direcciones que incluye origen, destino y waypoints.
    """
    # CORRECCIÓN: Usando la URL base de Google Maps
    base_url = "https://www.google.com/maps/dir/"
    
    all_points = [origin]
    if waypoints:
        all_points.extend(waypoints)
    all_points.append(destination)
    
    encoded_path = "/".join([quote(p) for p in all_points])
    
    params = []
    if mode and mode != "driving":
        params.append(f"travelmode={mode}")
    if avoid in ["tolls", "ferries"]:
        params.append(f"avoid={avoid}")
        
    query_string = f"?{'&'.join(params)}" if params else ""
    
    return f"{base_url}{encoded_path}{query_string}"

def build_waze_url(origin: str, destination: str, waypoints: list = None) -> str:
    """
    Construye una URL de Waze. Solo enlaza al destino, ya que Waze no soporta waypoints complejos en URL.
    """
    encoded_dest = quote(destination)
    return f"https://waze.com/ul?q={encoded_dest}&navigate=yes"


def build_apple_maps_url(origin: str, destination: str, waypoints: list = None) -> str:
    """
    Construye una URL de Apple Maps. Solo enlaza al origen y destino.
    """
    encoded_origin = quote(origin)
    
    # Apple Maps puede manejar el destino y las paradas de forma concatenada
    destination_path = destination
    if waypoints:
        for wp in waypoints:
            destination_path += f"&to={wp}" 
            
    encoded_destination_path = quote(destination_path)
    
    return f"http://maps.apple.com/?saddr={encoded_origin}&daddr={encoded_destination_path}"


def make_qr(url: str) -> BytesIO:
    """Genera un código QR para la URL dada."""
    qr_img = make_qr_code(url)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    return buffer.getvalue()