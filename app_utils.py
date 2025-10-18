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

# --- 1. FUNCIÓN DE SUGERENCIAS DE AUTOCOMPLETADO (FINAL) ---

def suggest_addresses(search_term: str, **kwargs) -> list[str]:
    """
    Busca sugerencias de direcciones usando la API de Google Places Autocomplete.
    Prioriza la ubicación del usuario si está activa; si no, restringe a España.
    """
    key_bucket = kwargs.get("key_bucket") 
    # Usamos el min_len que se pasa desde la llamada manual
    min_len = kwargs.get("min_len", 3) 
    
    if not key_bucket or not GOOGLE_PLACES_API_KEY or len(search_term) < min_len:
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
    
    # LÓGICA DE SESGO/RESTRICCIÓN (Corregida: o sesgo O restricción)
    if location_bias:
        params['locationbias'] = location_bias
    else:
        # Si NO hay sesgo, RESTRIÑIMOS estrictamente a España.
        params['components'] = 'country:es'
        
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/autocomplete/json",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        predictions = data.get('predictions', [])
        
        # Almacenar Place IDs en sesión para su posterior resolución (RESOLVE_SELECTION)
        st.session_state[f"{key_bucket}_suggestions"] = {
            p['description']: p['place_id'] for p in predictions
        }
        
        return [p['description'] for p in predictions]

    except Exception as e:
        return []


# --- 2. FUNCIÓN DE RESOLUCIÓN DE SELECCIÓN (FINAL) ---

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

    # 3. Si no hay Place ID (el usuario escribió sin usar el selectbox), usar Geocoding
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
        # st.error(f"Error en la geocodificación: {e}")
        pass
        
    return {"address": selection_text, "place_id": None}


# --- 3. FUNCIÓN DE CONSTRUCCIÓN DE URL DE GOOGLE MAPS (FINAL) ---

def build_gmaps_url(origin, destination, waypoints=None, mode="driving", avoid=None, optimize=False):
    """
    Construye una URL de Google Maps Directions con puntos intermedios y opciones.
    """
    
    url = f"https://www.google.com/maps/dir/{requests.utils.quote(origin)}/{requests.utils.quote(destination)}"
    
    params = []
    
    # Puntos Intermedios
    if waypoints:
        waypoints_str = '/'.join([requests.utils.quote(w) for w in waypoints])
        # Google Maps usa el formato de URL con waypoints en la ruta: /dir/A/B/C/D
        # Pero si el número de puntos es grande, es más robusto un parámetro.
        # Mantendremos el formato simple de ruta para 5 puntos o menos.
        
        # Para ser más seguros y flexibles, usaremos el formato de parámetro (más estándar)
        # Esto reemplazará el formato de URL simple /dir/A/B/C/D
        all_points = [origin] + waypoints + [destination]
        url = f"https://www.google.com/maps/dir/?api=1&origin={requests.utils.quote(origin)}&destination={requests.utils.quote(destination)}"

        if waypoints:
            waypoints_list = [requests.utils.quote(w) for w in waypoints]
            # La optimización se hace aquí
            optimize_flag = ":true" if optimize else ""
            params.append(f"waypoints={optimize_flag}|" + "|".join(waypoints_list))

    
    # Modo de viaje (el valor por defecto es 'driving')
    if mode != "driving":
        params.append(f"travelmode={mode}")
    
    # Opciones de evitar
    if avoid:
        params.append(f"avoid={avoid}")
        
    if params:
        url += "&" + "&".join(params)
        
    return url


# --- 4. FUNCIÓN DE GENERACIÓN DE QR (FINAL) ---

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