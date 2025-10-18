import streamlit as st
import googlemaps
import os
from qrcode import make as make_qr_code 
from io import BytesIO

# Carga la clave API de Google Maps desde los secretos de Streamlit
# Asegúrate de tener GOOGLE_PLACES_API_KEY en tu archivo .streamlit/secrets.toml
try:
    GMAPS_API_KEY = st.secrets["GOOGLE_PLACES_API_KEY"]
    gmaps = googlemaps.Client(key=GMAPS_API_KEY)
except KeyError:
    st.error("Error: La clave GOOGLE_PLACES_API_KEY no se encontró en 'secrets.toml'.")
    gmaps = None
except Exception:
    gmaps = None

# --- CONSTANTES ---
LOC_BIAS_KEY = "_loc_bias"

# ----------------------------------------------------------------------
# 1. FUNCIONES DE UBICACIÓN Y SESGO (GEOLOCALIZACIÓN POR IP)
# ----------------------------------------------------------------------

def set_location_bias():
    """Busca la ubicación aproximada del usuario por IP si está disponible en Streamlit Cloud."""
    try:
        session = st.runtime.get_instance().get_script_run_ctx()
        if session and hasattr(session, 'location'):
            loc = session.location
            if loc:
                lat = loc.latitude
                lng = loc.longitude
                st.session_state[LOC_BIAS_KEY] = f"{lat},{lng}"
                return
    except Exception:
        pass
        
    st.session_state[LOC_BIAS_KEY] = None


def _use_ip_bias():
    """Activa el sesgo de ubicación y lo almacena."""
    if st.session_state.get(LOC_BIAS_KEY) is None:
        with st.spinner("Buscando tu ubicación aproximada..."):
            set_location_bias()
            if st.session_state.get(LOC_BIAS_KEY):
                st.info("Búsqueda sesgada a tu ubicación IP.")
            else:
                st.warning("No se pudo obtener la ubicación IP (¿usando VS Code o conexión bloqueada?).")

# ----------------------------------------------------------------------
# 2. FUNCIONES DE BÚSQUEDA Y RESOLUCIÓN (PLACES API)
# ----------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def _gmaps_autocomplete_request(search_term: str, location_bias: str = None) -> list:
    """Realiza la llamada a la API de Autocompletado de Places."""
    if not gmaps:
        return []

    search_options = {
        "input": search_term,
        "language": "es",
        "types": "(address)",
    }
    
    if location_bias:
        try:
            lat, lng = map(float, location_bias.split(','))
            search_options["location"] = (lat, lng)
            search_options["radius"] = 200000 
        except:
            pass 
    
    try:
        results = gmaps.places_autocomplete(**search_options)
        return results
    except Exception as e:
        st.error(f"Error en la API de Autocompletado: {e}")
        return []

@st.cache_data(show_spinner=False, ttl=3600)
def _gmaps_place_details(place_id: str) -> dict:
    """Obtiene los detalles completos de un Place ID."""
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
        st.error(f"Error al obtener detalles del lugar: {e}")
        return None


def suggest_addresses(term: str, key_bucket: str, min_len: int = 3) -> list:
    """Busca sugerencias y las almacena temporalmente para la resolución."""
    if len(term) < min_len:
        return []

    location_bias = st.session_state.get(LOC_BIAS_KEY)
    gmaps_results = _gmaps_autocomplete_request(term, location_bias)
    
    meta_key = f"{key_bucket}_meta"
    
    if meta_key not in st.session_state:
        st.session_state[meta_key] = {}
        
    suggestions_labels = []

    for res in gmaps_results:
        label = res.get("description", res.get("place_id"))
        place_id = res.get("place_id")
        
        st.session_state[meta_key][label] = {"place_id": place_id}
        suggestions_labels.append(label)

    return suggestions_labels


def resolve_selection(selection: str, key_bucket: str) -> dict:
    """Resuelve la metadata completa (incluyendo lat/lng)."""
    meta_key = f"{key_bucket}_meta"
    resolved_meta = st.session_state.get(meta_key, {}) 
    
    temp_meta = resolved_meta.get(selection, {})
    place_id = temp_meta.get("place_id")

    if place_id:
        if temp_meta.get("lat") and temp_meta.get("lng"):
            return temp_meta
            
        details = _gmaps_place_details(place_id)
        if details:
            st.session_state[meta_key][selection] = details
            return details
    
    # Fallback: Usar Geocoding para texto que no vino de la sugerencia
    if not gmaps:
        return {"address": selection, "lat": None, "lng": None}
        
    try:
        geocode_result = gmaps.geocode(selection, language='es')
        if geocode_result:
            first_result = geocode_result[0]
            address = first_result.get('formatted_address', selection)
            location = first_result.get('geometry', {}).get('location', {})
            lat = location.get('lat')
            lng = location.get('lng')
            
            final_details = {"address": address, "lat": lat, "lng": lng}
            st.session_state[meta_key][selection] = final_details
            
            return final_details
            
        return {"address": selection, "lat": None, "lng": None}
        
    except Exception:
        return {"address": selection, "lat": None, "lng": None}


# ----------------------------------------------------------------------
# 3. FUNCIONES DE URL Y QR
# ----------------------------------------------------------------------

def build_gmaps_url(origin: str, destination: str, waypoints: list = None, mode: str = "driving", avoid: str = None, optimize: bool = True) -> str:
    """Construye una URL de Google Maps para direcciones con múltiples paradas."""
    
    # URL de Directions API (el formato más simple para múltiples paradas)
    base_url = "https://www.google.com/maps/dir/"
    
    # Lista de todos los puntos
    parts = []
    
    # 1. Origen
    parts.append(origin)
    
    # 2. Paradas intermedias
    if waypoints:
        parts.extend(waypoints)
        
    # 3. Destino
    parts.append(destination)
    
    # Unimos todas las partes con el separador '/' de la URL de dir/
    path = "/".join(parts)
    
    # Parámetros adicionales (se añaden después del path principal con un ? y &)
    params = []

    if mode and mode != "driving":
        params.append(f"travelmode={mode}")
    
    if avoid in ["tolls", "ferries", "highways"]:
        params.append(f"avoid={avoid}")
    
    query_string = f"?{'&'.join(params)}" if params else ""
    
    return f"{base_url}{path}{query_string}"

    
def make_qr(url: str) -> BytesIO:
    """Genera un código QR a partir de una URL."""
    img = make_qr_code(url)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer