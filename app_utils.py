import streamlit as st
import googlemaps
import os
from qrcode import make as make_qr_code 
from io import BytesIO
from urllib.parse import quote

# Inicialización del cliente de Google Maps
# Asumimos que la clave está en secrets.toml o env vars
API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY") 
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
        # Usamos Place Autocomplete para obtener sugerencias
        predictions = gmaps.places_autocomplete(
            input_text=address_term,
            language='es'
        )
        
        suggestions = []
        resolved_meta = {}
        
        for p in predictions:
            # Texto a mostrar en el SelectBox
            description = p.get("description")
            # El ID que usaremos para obtener detalles
            place_id = p.get("place_id")
            
            if description and place_id:
                suggestions.append(description)
                # Almacenamos el place_id asociado a la descripción
                resolved_meta[description] = {"place_id": place_id}

        # Almacenamos los metadatos en el estado de sesión bajo la clave específica
        st.session_state["_metadata"][key_bucket] = resolved_meta
        return suggestions
        
    except Exception as e:
        # st.error(f"Error en la búsqueda de sugerencias: {e}") # Comentar para no saturar
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
        # st.error(f"Error al obtener detalles del lugar: {e}") 
        return None # <--- CORRECCIÓN CLAVE: Devuelve None para evitar el AttributeError
        

def resolve_selection(selection_text: str, key_bucket: str) -> dict:
    """
    Resuelve la selección de una dirección a sus metadatos (Place ID, dirección formateada).
    Si la selección no tiene metadatos (es una dirección escrita directamente),
    intenta obtener los detalles del Place ID.
    """
    
    resolved_meta = st.session_state.get("_metadata", {}).get(key_bucket, {})

    # Intentamos obtener el Place ID del diccionario de metadatos guardado
    place_meta = resolved_meta.get(selection_text, {})
    place_id = place_meta.get("place_id")
    
    if place_id:
        # Si tenemos un Place ID, obtenemos los detalles completos
        details = _gmaps_place_details(place_id)
        if details:
            return details
        
    # Si no se encuentra el Place ID o falla la obtención de detalles, 
    # asumimos que el texto de entrada es una dirección válida (fallback)
    return {"address": selection_text, "lat": None, "lng": None}


def set_location_bias(lat: float, lng: float):
    """Establece el sesgo de ubicación para la búsqueda de direcciones."""
    st.session_state["_loc_bias"] = {"lat": lat, "lng": lng}

def _use_ip_bias():
    """Simula la obtención de la IP para sesgar la búsqueda (solo un placeholder)."""
    # En producción, usarías una API para geolocalizar la IP.
    # Aquí establecemos un punto fijo (ejemplo: Madrid, España)
    set_location_bias(40.4168, -3.7038)


# -------------------------------
# CONSTRUCCIÓN DE ENLACES Y QR
# -------------------------------

def build_gmaps_url(origin: str, destination: str, waypoints: list = None, mode: str = "driving", avoid: str = None, optimize: bool = True) -> str:
    """
    Construye una URL de Google Maps de direcciones (daddr) 
    con soporte para múltiples paradas (waypoints).
    """
    
    # Usamos una URL de Directions
    base_url = "https://www.google.com/maps/dir/"
    
    # 1. Lista de todos los puntos a codificar
    all_points = [origin]
    if waypoints:
        all_points.extend(waypoints)
    all_points.append(destination)
    
    # 2. Codificamos y unimos todas las direcciones usando quote()
    # Esta es la parte crucial para asegurar que los espacios y caracteres especiales funcionen.
    encoded_path = "/".join([quote(p) for p in all_points])
    
    # 3. Parámetros adicionales (query string)
    params = []

    # El modo de viaje se suele manejar en el propio /dir/ o en la URL
    if mode and mode != "driving":
        params.append(f"travelmode={mode}")
    
    # Optimizamos la ruta (Google lo hace por defecto con más de 25 paradas)
    # Aquí podríamos forzarlo si fuera un parámetro de la URL de directions, 
    # pero no es estándar para /dir/
        
    if avoid in ["tolls", "ferries"]:
        params.append(f"avoid={avoid}")
        
    query_string = f"?{'&'.join(params)}" if params else ""
    
    # 4. La URL final debe ser: base_url + encoded_path + query_string
    return f"{base_url}{encoded_path}{query_string}"

def make_qr(url: str) -> BytesIO:
    """Genera un código QR para la URL dada."""
    qr_img = make_qr_code(url)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    return buffer.getvalue()