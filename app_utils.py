import streamlit as st
import requests
import os
import qrcode
from io import BytesIO

# --- CONFIGURACIÓN DE CLAVES ---
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# --- FUNCIONES DE GESTIÓN DE ESTADO DE SESIÓN (KEYS) ---
def _get_key(bucket, key_name):
    """Obtiene una clave de estado de sesión anidada o la inicializa."""
    full_key = f"{bucket}_{key_name}"
    if full_key not in st.session_state:
        # Inicializa un token de sesión si no existe
        if key_name == 'sessiontoken':
            # Generar un UUID o un token simple para la API de Places
            import uuid
            st.session_state[full_key] = str(uuid.uuid4())
        else:
            st.session_state[full_key] = None
    return st.session_state[full_key]

def set_location_bias(lat, lon):
    """Establece la ubicación para sesgar los resultados de búsqueda."""
    st.session_state["_loc_bias"] = f"point:{lat},{lon}"

def _use_ip_bias():
    """Simula el uso de sesgo de ubicación por IP (para demostración/desarrollo)."""
    # En un entorno real, esto se haría con un servicio de geolocalización IP
    # Aquí establecemos un punto de ejemplo en España (Barcelona)
    set_location_bias(41.3851, 2.1734) 

# --- 1. FUNCIÓN DE SUGERENCIAS DE AUTOCOMPLETADO (CORECCIÓN APLICADA) ---

def suggest_addresses(search_term: str, key_bucket: str, **kwargs) -> list[str]:
    """
    Busca sugerencias de direcciones usando la API de Google Places Autocomplete.
    El resultado se restringe a España.
    """
    if not GOOGLE_PLACES_API_KEY or len(search_term) < kwargs.get("min_len", 3):
        return []

    # Obtener el token de sesión (clave de caché)
    session_token = _get_key(key_bucket, 'sessiontoken')
    
    # Obtener el sesgo de ubicación si existe
    location_bias = st.session_state.get("_loc_bias")

    # Parámetros para la API de Places/Autocompletado
    params = {
        'input': search_term,
        'key': GOOGLE_PLACES_API_KEY,
        'types': 'address', 
        'sessiontoken': session_token,
        'language': st.session_state.get('lang', 'es'),
        # --- CORRECCIÓN CLAVE: RESTRINGIR A ESPAÑA ---
        'components': 'country:es',  # Restringe los resultados solo a España
    }
    
    # Añadir sesgo si está disponible
    if location_bias:
        params['locationbias'] = location_bias

    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/autocomplete/json",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        # Almacenar los Place IDs en sesión para su posterior resolución
        predictions = data.get('predictions', [])
        
        # Usamos una clave de sesión específica para almacenar los place_id y la descripción
        st.session_state[f"{key_bucket}_suggestions"] = {
            p['description']: p['place_id'] for p in predictions
        }
        
        # Devolver solo las descripciones (texto) para el st_searchbox
        return [p['description'] for p in predictions]

    except Exception as e:
        # En caso de error, puedes devolver una lista vacía y registrar el error
        st.error(f"Error interno en la búsqueda de sugerencias: {e}")
        return []


# --- 2. FUNCIÓN DE RESOLUCIÓN DE SELECCIÓN ---

def resolve_selection(selection_text: str, key_bucket: str) -> dict:
    """
    Resuelve la dirección a partir del texto de la sugerencia o la geocodifica
    si no se encuentra en caché.
    """
    if not selection_text:
        return {"address": "", "place_id": None}

    # 1. Intentar resolver desde el caché (si el usuario seleccionó una sugerencia)
    suggestions = st.session_state.get(f"{key_bucket}_suggestions", {})
    place_id = suggestions.get(selection_text)

    # 2. Si hay Place ID, usar la API de Place Details (más precisa)
    if place_id:
        try:
            params = {
                'place_id': place_id,
                'key': GOOGLE_PLACES_API_KEY,
                'language': st.session_state.get('lang', 'es'),
            }
            response = requests.get(
                "https://maps.googleapis.com/maps/api/place/details/json",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            result = data.get('result', {})
            
            return {
                "address": result.get('formatted_address', selection_text),
                "place_id": place_id
            }

        except Exception:
            # Fallback a Geocoding si falla Place Details
            pass

    # 3. Si no hay Place ID (el usuario escribió y presionó Enter), usar Geocoding
    try:
        params = {
            'address': selection_text,
            'key': GOOGLE_PLACES_API_KEY,
            'language': st.session_state.get('lang', 'es'),
            # También restringimos a España aquí para consistencia
            'components': 'country:es', 
        }
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params=params
        )
        response.raise_for_status()
        data = response.json()
        
        if data['results']:
            result = data['results'][0]
            return {
                "address": result.get('formatted_address', selection_text),
                "place_id": result.get('place_id')
            }
        
    except Exception as e:
        st.error(f"Error en la geocodificación: {e}")
        
    return {"address": selection_text, "place_id": None}


# --- 3. FUNCIÓN DE CONSTRUCCIÓN DE URL DE GOOGLE MAPS ---

def build_gmaps_url(origin, destination, waypoints=None, mode="driving", avoid=None, optimize=False):
    """
    Construye una URL de Google Maps Directions con puntos intermedios y opciones.
    """
    base_url = "https://www.google.com/maps/dir/?api=1"
    
    # 1. Origen y Destino
    url = f"{base_url}&origin={requests.utils.quote(origin)}&destination={requests.utils.quote(destination)}"
    
    # 2. Puntos Intermedios (Waypoints)
    if waypoints:
        waypoints_str = '|'.join([requests.utils.quote(w) for w in waypoints])
        
        # Optimización (CRUCIAL para rutas profesionales)
        optimize_str = "true" if optimize else "false"
        url += f"&waypoints={waypoints_str}&optimizeWaypoints={optimize_str}"
        
    # 3. Modo de viaje
    url += f"&travelmode={mode}"
    
    # 4. Opciones de evitar
    if avoid:
        url += f"&avoid={avoid}"
        
    return url

# --- 4. FUNCIÓN DE GENERACIÓN DE QR ---

def make_qr(url):
    """Genera un código QR a partir de una URL y lo devuelve como BytesIO."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Guardar en un buffer en memoria
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf