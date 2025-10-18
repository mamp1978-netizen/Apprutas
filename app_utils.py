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

# --- 1. FUNCIÓN DE SUGERENCIAS DE AUTOCOMPLETADO (CORRECCIÓN APLICADA AQUÍ) ---

# Hemos quitado 'key_bucket' como argumento posicional y lo extraemos de kwargs.
def suggest_addresses(search_term: str, **kwargs) -> list[str]:
    """
    Busca sugerencias de direcciones usando la API de Google Places Autocomplete.
    """
    # **Extracción del key_bucket desde kwargs** (SOLUCIONA EL TypeError)
    key_bucket = kwargs.get("key_bucket") 
    min_len = kwargs.get("min_len", 3)
    
    if not key_bucket or not GOOGLE_PLACES_API_KEY or len(search_term) < min_len:
        return []

    session_token = _get_key(key_bucket, 'sessiontoken')
    location_bias = st.session_state.get("_loc_bias")

    # Parámetros para la API de Places/Autocompletado
    params = {
        'input': search_term,
        'key': GOOGLE_PLACES_API_KEY,
        'types': 'address', 
        'sessiontoken': session_token,
        'language': st.session_state.get('lang', 'es'),
        # Mantenemos 'components' para restringir a España, a menos que el sesgo esté activo
        'components': 'country:es', 
    }
    
    # AÑADIMOS EL SESGO DE UBICACIÓN (locationbias) si está disponible
    if location_bias:
        params['locationbias'] = location_bias
        # Si hay un sesgo de ubicación, podemos permitir resultados globales
        # o mantener la restricción si el sesgo es dentro de España.
        # Por simplicidad, mantendremos la restricción a España si está en uso.
        
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/autocomplete/json",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        predictions = data.get('predictions', [])
        
        st.session_state[f"{key_bucket}_suggestions"] = {
            p['description']: p['place_id'] for p in predictions
        }
        
        return [p['description'] for p in predictions]

    except Exception as e:
        # En caso de error de la API, podemos devolver una lista vacía y mostrar un error específico si es necesario
        # st.error(f"Error interno en la búsqueda de sugerencias: {e}")
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


# --- 3. FUNCIÓN DE CONSTRUCCIÓN DE URL DE GOOGLE MAPS ---

def build_gmaps_url(origin, destination, waypoints=None, mode="driving", avoid=None, optimize=False):
    """
    Construye una URL de Google Maps Directions con puntos intermedios y opciones.
    """
    base_url = "https://www.google.com/maps/dir/"
    
    # 1. Origen
    url = f"{base_url}{requests.utils.quote(origin)}/"
    
    # 2. Puntos Intermedios (Waypoints)
    waypoints_str = ""
    if waypoints:
        waypoints_str = '/'.join([requests.utils.quote(w) for w in waypoints])
        url += f"{waypoints_str}/"
        
    # 3. Destino
    url += f"{requests.utils.quote(destination)}"
    
    # 4. Parámetros de Query (optimizar, modo, evitar)
    params = {}
    if optimize:
        params['waypoints'] = f"{waypoints_str}&optimize=true" # Esto es complicado, es mejor dejar que Google lo maneje por defecto si no se optimiza
        
    if mode != "driving":
        params['travelmode'] = mode
        
    avoid_map = {
        "tolls": "tolls",
        "ferries": "ferries",
    }
    if avoid and avoid_map.get(avoid):
        params['avoid'] = avoid_map[avoid]
        
    if params:
        # Esto no es totalmente correcto para el formato de URL de Google Maps
        # Pero para una ruta optimizada, el formato base es el más robusto.
        # Mantendremos el formato simple que usa el usuario final.
        pass

    # Para optimización, el formato de URL simple no soporta la bandera `optimize`.
    # Dado que estamos usando la API para obtener los datos correctos antes,
    # enviaremos la URL simple para que el usuario la abra.
    # El formato que mejor funciona para optimización de waypoints es:
    # https://www.google.com/maps/dir/Origen/PuntoA/PuntoB/Destino/data=!4m2!4m1!3e0!4e1
    # Pero nos quedaremos con el formato simple de direcciones.
    
    # Volvemos al formato de consulta que has usado antes, ya que es más directo.
    
    url = f"https://www.google.com/maps/dir/?api=1&origin={requests.utils.quote(origin)}&destination={requests.utils.quote(destination)}"
    
    # Puntos Intermedios
    if waypoints:
        waypoints_list = [requests.utils.quote(w) for w in waypoints]
        url += f"&waypoints={requests.utils.quote('|'.join(waypoints_list))}"
        
        if optimize:
            # Google usa 'optimize:true' como parte del valor del parámetro 'waypoints', pero la API simplificada
            # de URL (api=1) no lo soporta directamente en el parámetro. Lo mejor es omitir 'optimize'
            # del código del QR, ya que la optimización solo se garantiza con la API Directions.
            pass
            
    # Modo de viaje
    url += f"&travelmode={mode}"
    
    # Opciones de evitar
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
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf