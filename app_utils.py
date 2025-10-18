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
    """
    Función que simula la detección de ubicación por IP y establece el sesgo.
    NOTA: En producción, usarías un servicio de geolocalización IP.
    Aquí se establece una ubicación fija de ejemplo (Barcelona) para la demostración.
    """
    # Geocodificación para Barcelona
    set_location_bias(41.3851, 2.1734) 
    # Aseguramos que la aplicación se recargue para aplicar el sesgo inmediatamente
    # st.rerun() # Descomenta si usas esta función directamente desde un botón

# --- 1. FUNCIÓN DE SUGERENCIAS DE AUTOCOMPLETADO (APLICANDO SESGO) ---

def suggest_addresses(search_term: str, key_bucket: str, **kwargs) -> list[str]:
    """
    Busca sugerencias de direcciones usando la API de Google Places Autocomplete,
    sesgando los resultados hacia la ubicación del usuario si está disponible.
    """
    if not GOOGLE_PLACES_API_KEY or len(search_term) < kwargs.get("min_len", 3):
        return []

    session_token = _get_key(key_bucket, 'sessiontoken')
    
    # Obtener el sesgo de ubicación si existe (establecido por _use_ip_bias)
    location_bias = st.session_state.get("_loc_bias")

    # Parámetros para la API de Places/Autocompletado
    params = {
        'input': search_term,
        'key': GOOGLE_PLACES_API_KEY,
        'types': 'address', 
        'sessiontoken': session_token,
        'language': st.session_state.get('lang', 'es'),
        # Eliminamos 'components: country:es'
    }
    
    # AÑADIMOS EL SESGO DE UBICACIÓN si la casilla "Usar mi ubicación" está marcada
    if location_bias:
        params['locationbias'] = location_bias
        # Opcionalmente, podemos seguir sesgando a España para mantener la relevancia
        params['components'] = 'country:es'

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

    suggestions = st.session_state.get(f"{key_bucket}_suggestions", {})
    place_id = suggestions.get(selection_text)

    # 1. Usar Place Details (más precisa)
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

    # 2. Usar Geocoding
    try:
        params = {
            'address': selection_text,
            'key': GOOGLE_PLACES_API_KEY,
            'language': st.session_state.get('lang', 'es'),
            'components': 'country:es', # Mantener la restricción aquí por si el usuario escribe
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
# (Se mantiene igual)

def build_gmaps_url(origin, destination, waypoints=None, mode="driving", avoid=None, optimize=False):
    """
    Construye una URL de Google Maps Directions con puntos intermedios y opciones.
    """
    # Nota: Google ya no soporta 'maps.google.com/maps' para direcciones, es mejor usar el formato directo
    base_url = "https://www.google.com/maps/dir/"
    
    # El formato es: /@/ORIGEN/DESTINO/WAYPOINTS/data=!4m...
    # Usaremos el formato de query más simple con Place IDs o direcciones
    
    # 1. Origen y Destino
    url = f"https://www.google.com/maps/dir/?api=1&origin={requests.utils.quote(origin)}&destination={requests.utils.quote(destination)}"
    
    # 2. Puntos Intermedios (Waypoints)
    if waypoints:
        waypoints_str = '|'.join([requests.utils.quote(w) for w in waypoints])
        
        # Parámetro de optimización
        optimize_str = "true" if optimize else "false"
        url += f"&waypoints={waypoints_str}&optimize={optimize_str}"
        
    # 3. Modo de viaje
    url += f"&travelmode={mode}"
    
    # 4. Opciones de evitar
    if avoid:
        url += f"&avoid={avoid}"
        
    return url

# --- 4. FUNCIÓN DE GENERACIÓN DE QR ---
# (Se mantiene igual)

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