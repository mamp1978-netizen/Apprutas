import streamlit as st
import googlemaps
import os
import requests
from qrcode import make as make_qr_code # Renombramos para evitar conflicto con la función
from io import BytesIO

# Carga la clave API de Google Maps desde los secretos de Streamlit
# Asegúrate de tener GOOGLE_PLACES_API_KEY en tu archivo .streamlit/secrets.toml
try:
    GMAPS_API_KEY = st.secrets["GOOGLE_PLACES_API_KEY"]
    gmaps = googlemaps.Client(key=GMAPS_API_KEY)
except KeyError:
    st.error("Error: La clave GOOGLE_PLACES_API_KEY no se encontró en 'secrets.toml'.")
    gmaps = None

# --- CONSTANTES ---
# Clave del estado de sesión para el sesgo de ubicación (geolocalización por IP)
LOC_BIAS_KEY = "_loc_bias"

# ----------------------------------------------------------------------
# 1. FUNCIONES DE UBICACIÓN Y SESGO (GEOLOCALIZACIÓN POR IP)
# ----------------------------------------------------------------------

def set_location_bias():
    """Busca la ubicación aproximada del usuario por IP si está disponible en Streamlit Cloud."""
    # Nota: Esta función solo funciona cuando se despliega en Streamlit Cloud
    # y usa headers de solicitud. En desarrollo local o VS Code, devuelve None.
    try:
        # Intenta obtener la información de la ubicación por IP (solo en Streamlit Cloud)
        session = st.runtime.get_instance().get_script_run_ctx()
        if session and hasattr(session, 'location'):
            loc = session.location
            if loc:
                lat = loc.latitude
                lng = loc.longitude
                # Formato esperado por Google Maps API: "lat,lng"
                st.session_state[LOC_BIAS_KEY] = f"{lat},{lng}"
                return
    except Exception:
        # Si falla (ej. ejecución local), no se establece el sesgo
        pass
        
    st.session_state[LOC_BIAS_KEY] = None


def _use_ip_bias():
    """Activa el sesgo de ubicación y lo almacena."""
    # Solo ejecuta la búsqueda de ubicación si aún no se ha hecho
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

    # Opciones de búsqueda
    search_options = {
        "input": search_term,
        "language": "es",
        "types": "(address)", # Prioriza direcciones
    }
    
    if location_bias:
        # Sesgo a la ubicación actual. Usa 'location' y 'radius' o 'components'
        # Usaremos 'location' y 'radius' (200km) para sesgar sin restringir
        try:
            lat, lng = map(float, location_bias.split(','))
            search_options["location"] = (lat, lng)
            search_options["radius"] = 200000 # 200 km
        except:
            pass # Si el formato falla, ignora el sesgo
    
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
        # Extrae solo la información relevante
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
    """
    Busca sugerencias de direcciones y las almacena en el estado de sesión.
    Retorna solo las etiquetas de las sugerencias para el SelectBox.
    """
    if len(term) < min_len:
        return []

    location_bias = st.session_state.get(LOC_BIAS_KEY)
    
    # Llamada a la API
    gmaps_results = _gmaps_autocomplete_request(term, location_bias)
    
    # Clave para guardar los metadatos de las sugerencias
    meta_key = f"{key_bucket}_meta"
    
    # Inicializa el diccionario de metadatos si no existe
    if meta_key not in st.session_state:
        st.session_state[meta_key] = {}
        
    suggestions_labels = []

    for res in gmaps_results:
        label = res.get("description", res.get("place_id"))
        place_id = res.get("place_id")
        
        # Almacena el Place ID asociado al texto de la etiqueta
        # Nota: Aquí solo guardamos el Place ID. Los detalles completos se obtienen más tarde.
        st.session_state[meta_key][label] = {"place_id": place_id}
        suggestions_labels.append(label)

    return suggestions_labels


def resolve_selection(selection: str, key_bucket: str) -> dict:
    """
    Busca la metadata completa de una dirección. Si no la tiene, la pide a la API.
    CORRECCIÓN: Asegura que SIEMPRE devuelve un diccionario.
    """
    meta_key = f"{key_bucket}_meta"
    
    # Intentar obtener el diccionario de metadatos (asegura que sea un dict)
    resolved_meta = st.session_state.get(meta_key, {}) 
    
    # 1. Intentar obtener el Place ID (si se usó la búsqueda)
    temp_meta = resolved_meta.get(selection, {})
    place_id = temp_meta.get("place_id")

    if place_id:
        # 2. Si hay Place ID, verificamos si ya tenemos los detalles completos (lat/lng)
        if temp_meta.get("lat") and temp_meta.get("lng"):
            return temp_meta
            
        # 3. Si no hay detalles completos, los pedimos a la API
        details = _gmaps_place_details(place_id)
        if details:
            # 4. Guardar los detalles completos de vuelta en el estado de sesión
            st.session_state[meta_key][selection] = details
            return details
    
    # 5. Si no se usó la búsqueda (se escribió manualmente o falló), 
    #    usamos Geocoding para obtener lat/lng a partir del texto de la dirección
    
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
            
            # Opcional: Guardar el resultado del Geocoding para evitar repeticiones
            st.session_state[meta_key][selection] = final_details
            
            return final_details
            
        # Si Geocoding no devuelve resultados
        return {"address": selection, "lat": None, "lng": None}
        
    except Exception as e:
        #st.error(f"Error en la geocodificación: {e}")
        return {"address": selection, "lat": None, "lng": None}


# ----------------------------------------------------------------------
# 3. FUNCIONES DE URL Y QR
# ----------------------------------------------------------------------

def build_gmaps_url(origin: str, destination: str, waypoints: list = None, mode: str = "driving", avoid: str = None, optimize: bool = True) -> str:
    """Construye una URL de Google Maps para direcciones con múltiples paradas."""
    
    base_url = "https://www.google.com/maps/dir/?api=1"
    
    # Origen y Destino (required)
    params = [
        f"origin={origin}",
        f"destination={destination}"
    ]
    
    # Waypoints (paradas)
    if waypoints:
        # Unimos las paradas con el carácter '|'
        waypoints_str = "|".join(waypoints)
        
        # Añadimos la opción de optimización
        if optimize:
            waypoints_str += "&waypoints_place_ids=optimize:true"
        
        params.append(f"waypoints={waypoints_str}")
    
    # Modo de transporte (driving, walking, bicycling, transit)
    if mode in ["driving", "walking", "bicycling", "transit"]:
        params.append(f"travelmode={mode}")
        
    # Evitar (tolls, ferries, highways)
    if avoid in ["tolls", "ferries", "highways"]:
        params.append(f"avoid={avoid}")
        
    return f"{base_url}&{'&'.join(params)}"

    
def make_qr(url: str) -> BytesIO:
    """Genera un código QR a partir de una URL."""
    img = make_qr_code(url)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer