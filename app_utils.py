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
            import uuid
            st.session_state[full_key] = str(uuid.uuid4())
        else:
            st.session_state[full_key] = None
    return st.session_state[full_key]

def set_location_bias(lat, lon):
    """Establece la ubicación para sesgar los resultados de búsqueda."""
    # Usamos circle:radius@lat,lon para sesgar a un círculo de 50km alrededor del punto
    st.session_state["_loc_bias"] = f"circle:50000@{lat},{lon}"

def _use_ip_bias():
    """Simula la detección de ubicación por IP y establece el sesgo (Barcelona como ejemplo)."""
    set_location_bias(41.3851, 2.1734) 

# --- 1. FUNCIÓN DE SUGERENCIAS DE AUTOCOMPLETADO (CORRECCIÓN FINAL) ---

# Se extrae key_bucket desde **kwargs para evitar el TypeError
def suggest_addresses(search_term: str, **kwargs) -> list[str]:
    """
    Busca sugerencias de direcciones usando la API de Google Places Autocomplete.
    Prioriza la ubicación del usuario si está activa; si no, restringe a España.
    """
    key_bucket = kwargs.get("key_bucket") 
    min_len = kwargs.get("min_len", 1) # Usamos 1 aquí, pero la lógica de la API necesita más
    
    # Si la búsqueda es muy corta, devolvemos vacío para no gastar cuota (Google recomienda > 3)
    if not key_bucket or not GOOGLE_PLACES_API_KEY or len(search_term) < 1:
        return []

    session_token = _get_key(key_bucket, 'sessiontoken')
    location_bias = st.session_state.get("_loc_bias")

    # Parámetros base para la API de Places/Autocompletado
    params = {
        'input': search_term,
        'key': GOOGLE_PLACES_API_KEY,
        'types': 'address', 
        'sessiontoken': session_token,
        'language': st.session_state.get('lang', 'es'),
    }
    
    # LÓGICA DE SESGO/RESTRICCIÓN
    if location_bias:
        # Si hay sesgo, lo aplicamos. NO usamos 'components' para permitir resultados fuera de España
        # si la búsqueda es relevante, pero priorizamos la zona del usuario.
        params['locationbias'] = location_bias
    else:
        # Si NO hay sesgo (casilla desmarcada), RESTRIÑIMOS estrictamente a España.
        params['components'] = 'country:es'
        
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/autocomplete/json",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        predictions = data.get('predictions', [])
        
        # Almacenar Place IDs en sesión para su posterior resolución
        st.session_state[f"{key_bucket}_suggestions"] = {
            p['description']: p['place_id'] for p in predictions
        }
        
        return [p['description'] for p in predictions]

    except Exception as e:
        # En caso de error, devolvemos lista vacía y registramos el error en la consola
        # print(f"API Error: {e}")
        return []


# --- 2. FUNCIÓN DE RESOLUCIÓN DE SELECCIÓN (SIN CAMBIOS) ---

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
            pass

    # 3. Si no hay Place ID (el usuario escribió y presionó Enter), usar Geocoding
    try:
        params = {
            'address': selection_text,
            'key': GOOGLE_PLACES_API_KEY,
            'language': st.session_state.get('lang', 'es'),
            'components': 'country:es', # Mantenemos la restricción aquí
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


# --- 3. FUNCIÓN DE CONSTRUCCIÓN DE URL DE GOOGLE MAPS (SIN CAMBIOS) ---

def build_gmaps_url(origin, destination, waypoints=None, mode="driving", avoid=None, optimize=False):
    """
    Construye una URL de Google Maps Directions con puntos intermedios y opciones.
    """
    
    # Volvemos al formato de consulta que has usado antes, ya que es más directo.
    
    url = f"https://www.google.com/maps/dir/?api=1&origin={requests.utils.quote(origin)}&destination={requests.utils.quote(destination)}"
    
    # Puntos Intermedios
    if waypoints:
        waypoints_list = [requests.utils.quote(w) for w in waypoints]
        url += f"&waypoints={requests.utils.quote('|'.join(waypoints_list))}"
        
    # Modo de viaje
    url += f"&travelmode={mode}"
    
    # Opciones de evitar
    if avoid:
        url += f"&avoid={avoid}"
        
    return url


# --- 4. FUNCIÓN DE GENERACIÓN DE QR (SIN CAMBIOS) ---

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
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf