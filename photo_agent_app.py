# aplicacion de agente fotografico.py
from google import genai
from google.genai.errors import APIError
import streamlit as st
import os
import shutil
from PIL import Image
from io import BytesIO
from datetime import datetime

# --- Configuración de Carpetas ---
# Nos aseguramos de que el directorio donde se guarda la app sea el punto de referencia
APP_DIR = os.path.dirname(os.path.abspath(__file__))
# La carpeta donde se guardarán las fotos
PHOTOS_DIR = os.path.join(APP_DIR, "app_photos_saved")
os.makedirs(PHOTOS_DIR, exist_ok=True)

# ----------------------------------------------------
# --- CONFIGURACIÓN DE GEMINI (FUNCIÓN DE CLIENTE) ---
# ----------------------------------------------------
def get_gemini_client():
    """Inicializa el cliente Gemini y verifica la clave API."""
    # Intentamos obtener la clave API de Streamlit Secrets (o entorno)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        st.error("Error: La clave GEMINI_API_KEY no está configurada.")
        st.stop()
    
    try:
        # Solo inicializa el cliente
        client = genai.Client(api_key=gemini_key)
        return client 
    except Exception as e:
        st.error(f"Error al iniciar el cliente Gemini: {e}")
        st.stop()


# --- Configuración de Streamlit ---
st.set_page_config(
    page_title="Gestor de Fotos y Archivos",
    layout="wide"
)

st.title("📸 Gestor de Fotos y Archivos (Streamlit)")
st.markdown("Sube y descarga fotos, o usa la cámara web directamente.")
st.divider()

# --------------------------------------------------------
# --- INICIALIZACIÓN GLOBAL DE GEMINI Y MODELOS (CLAVE) ---
# --------------------------------------------------------
if "client" not in st.session_state:
    st.session_state["client"] = get_gemini_client()
    
    # 1. Modelo para CHAT (Sin herramientas)
    st.session_state["model_chat"] = st.session_state["client"].models.get(
        model="gemini-2.5-flash"
    )
    
    # 2. Modelo para BUSCADOR WEB (Con herramienta de Google Search)
    st.session_state["model_search"] = st.session_state["client"].models.get(
        model="gemini-2.5-flash",
        config={"tools": [{"google_search": {}}]}
    )
# Hacemos el cliente accesible en todo el script
client = st.session_state["client"] 


# --- Funciones de Utilidad ---
def save_uploaded_file(uploaded_file):
    """Guarda el archivo subido en la carpeta de la app."""
    file_path = os.path.join(PHOTOS_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def get_photo_files():
    """Obtiene la lista de archivos de fotos guardados."""
    return sorted([
        f for f in os.listdir(PHOTOS_DIR) 
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
    ])

# --- Pestañas de Funcionalidad ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Cámara 🤳", 
    "Subir / Descargar 📥", 
    "Fotos Guardadas 📂", 
    "Chat con Gemini ✨",
    "Buscador Web 🌐",
    "Planificador de Ruta 🗺️" 
])

# === PESTAÑA 1: CÁMARA ===
with tab1:
    st.header("Tomar Foto (Webcam)")

    # Usamos columnas: 1 parte para la cámara, 2 partes vacías para reducir el ancho
    col_camera, col_spacer = st.columns([1, 2]) 

    with col_camera:
        camera_file = st.camera_input("Apunta y captura")

    if camera_file:
        st.image(camera_file, caption="Foto Capturada")

        if st.button("Guardar esta foto"):
            from datetime import datetime 
            from PIL import Image 
            from io import BytesIO
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cam_{timestamp}.jpg"

            image_data = Image.open(BytesIO(camera_file.read()))
            save_path = os.path.join(PHOTOS_DIR, filename)
            image_data.save(save_path)
            st.success(f"Foto guardada exitosamente como **{filename}**.")
            
# === PESTAÑA 2: SUBIR / DESCARGAR ARCHIVOS ===
with tab2:
    st.header("Subir Archivos")
    uploaded_file = st.file_uploader(
        "Sube una foto a la carpeta de la app", 
        type=['png', 'jpg', 'jpeg', 'gif', 'bmp']
    )

    if uploaded_file is not None:
        if st.button(f"Guardar {uploaded_file.name}"):
            path = save_uploaded_file(uploaded_file)
            st.success(f"Archivo subido y guardado en: {path}")

    st.header("Descargar Archivos")
    
    photo_files = get_photo_files()
    if photo_files:
        selected_file = st.selectbox("Selecciona un archivo para descargar", photo_files)
        
        if selected_file:
            file_path = os.path.join(PHOTOS_DIR, selected_file)
            with open(file_path, "rb") as file:
                st.download_button(
                    label=f"Descargar {selected_file}",
                    data=file,
                    file_name=selected_file
                )
    else:
        st.info("No hay fotos guardadas para descargar.")

# === PESTAÑA 3: FOTOS GUARDADAS ===
with tab3:
    st.header("Visualizar Fotos Guardadas")
    photo_files = get_photo_files()
    
    if photo_files:
        selected_photo = st.selectbox("Elige una foto para visualizar", photo_files)
        
        if selected_photo:
            st.image(os.path.join(PHOTOS_DIR, selected_photo), caption=selected_photo, use_column_width=True)
            st.divider()
            
            if st.button(f"🗑️ Eliminar {selected_photo}"):
                os.remove(os.path.join(PHOTOS_DIR, selected_photo))
                st.success(f"Archivo **{selected_photo}** eliminado. (Recarga la página para actualizar la lista)")
    else:
        st.info("La carpeta interna está vacía.")
        
# === PESTAÑA 4: CHAT CON GEMINI ===
with tab4:
    st.header("Chat con Gemini ✨")
    st.markdown("Mantén una conversación continua con Gemini. ¡El historial se guarda!")
    
    # 1. Obtener el modelo de chat
    model_chat = st.session_state["model_chat"]

    # --- Inicializar la sesión de chat y la historia ---
    if "chat_session" not in st.session_state:
        try:
            # Creamos la sesión de chat usando el modelo sin herramientas (model_chat)
            st.session_state["chat_session"] = client.chats.create(
                model=model_chat
            )
            st.session_state["messages"] = [{"role": "model", "content": "¡Hola! Soy Gemini. ¿En qué puedo ayudarte hoy?"}]
        except Exception as e:
            st.error(f"Error al iniciar la sesión de chat: {e}")
            st.stop()


    # --- Mostrar historial de mensajes ---
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- Capturar la entrada del usuario ---
    if prompt := st.chat_input("Pregúntale algo a Gemini..."):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)

        # --- Enviar a Gemini y obtener respuesta ---
        with st.spinner("Gemini está pensando..."):
            try:
                chat = st.session_state["chat_session"]
                response = chat.send_message(prompt)
                
                st.session_state["messages"].append({"role": "model", "content": response.text})
                
                with st.chat_message("model"):
                    st.markdown(response.text)

            except Exception as e:
                st.error(f"Error al conectar con Gemini: {e}")
                st.session_state["messages"].append({"role": "model", "content": "Lo siento, hubo un error de conexión."})
                
    # --- Botón para limpiar el historial ---
    if st.button("Reiniciar Chat", key="reset_chat"):
        st.session_state["chat_session"] = client.chats.create(
            model=model_chat
        )
        st.session_state["messages"] = [{"role": "model", "content": "Chat Reiniciado. ¿En qué puedo ayudarte?"}]
        st.rerun() 
        
# === PESTAÑA 5: BUSCADOR WEB (¡AÑADIDO Y CORREGIDO!) ===
with tab5:
    st.header("Buscador Web 🌐")
    st.markdown("Usa la inteligencia de Gemini con acceso directo a Google Search.")
    
    # 1. Obtener el modelo de búsqueda (ya configurado con la herramienta)
    model_search = st.session_state["model_search"] 

    # 2. Campo de entrada para la consulta
    prompt = st.text_input(
        "¿Qué quieres buscar?",
        placeholder="Ej: ¿Cuál es el último hallazgo en la medicina regenerativa?"
    )
    
    # 3. Botón de búsqueda
    search_button = st.button("Buscar y Responder (Gemini + Google)")
    
    # 4. Lógica de ejecución
    if search_button and prompt:
        with st.spinner(f"Buscando en Google y generando respuesta para '{prompt}'..."):
            try:
                # Llama al modelo que tiene la herramienta 'google_search' activada.
                response = model_search.generate_content(prompt)
                
                # Muestra el resultado
                st.subheader("Resultado de la Búsqueda:")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"Error al ejecutar la búsqueda con Gemini: {e}")
                

# === PESTAÑA 6: PLANIFICADOR DE RUTA ===
def generate_maps_url(origin, stops, mode="driving"):
    """Genera una URL de Google Maps para direcciones con waypoints."""
    # Nota: El formato real de Google Maps para waypoints es más complejo,
    # pero simplificamos con un formato base para la demostración.
    base_url = "https://www.google.com/maps/dir/" # Usamos la URL correcta
    
    route_parts = [origin.replace(" ", "+")]
    for stop in stops:
        route_parts.append(stop.replace(" ", "+"))

    route_string = "/".join(route_parts)

    travel_mode_code = {
        "Conduciendo": "driving",
        "Caminando": "walking",
        "Bicicleta": "bicycling",
        "Transporte Público": "transit"
    }.get(mode, "driving")
    
    # Devolvemos una URL completa con el modo de viaje.
    return f"{base_url}{route_string}/data=!4m2!4m1!3e{travel_mode_code}"


with tab6:
    st.header("Planificador de Rutas Múltiples 📍")
    st.markdown("Organiza una ruta visitando múltiples puntos de interés (hasta 8 paradas).")

    # --- ENTRADAS ---
    origin = st.text_input("1. Punto de Partida:", value="MY_LOCATION", key="route_origin")

    # Campos de puntos de interés (Waypoints)
    st.subheader("2. Puntos de Visita (Waypoints)")

    if 'stops' not in st.session_state:
        st.session_state['stops'] = ["Eiffel Tower, Paris", "Louvre Museum, Paris"]

    new_stops = []
    for i in range(len(st.session_state['stops'])):
        stop_input = st.text_input(f"Parada {i+1}:", value=st.session_state['stops'][i], key=f"stop_{i}")
        new_stops.append(stop_input)

    st.session_state['stops'] = new_stops

    col_add, col_remove, _ = st.columns([1, 1, 4])

    # Botones dinámicos
    with col_add:
        if st.button("➕ Añadir Parada", disabled=len(st.session_state['stops']) >= 8):
            st.session_state['stops'].append("")
            st.rerun()
    with col_remove:
        if st.button("➖ Eliminar Última", disabled=len(st.session_state['stops']) <= 1):
            st.session_state['stops'].pop()
            st.rerun()

    st.divider()

    # --- BOTONES DE ACCIÓN ---
    st.subheader("3. Tipo de Ruta")

    travel_mode = st.radio(
        "Selecciona el modo de transporte:",
        ["Conduciendo", "Transporte Público", "Caminando", "Bicicleta"]
    )

    if st.button(f"Generar Ruta: {travel_mode}"):
        if not origin or not any(st.session_state['stops']):
            st.error("Por favor, introduce un punto de partida y al menos una parada válida.")
        else:
            valid_stops = [stop for stop in st.session_state['stops'] if stop.strip()]

            if not valid_stops:
                st.warning("Debes especificar al menos un destino.")
            else:
                maps_url = generate_maps_url(origin, valid_stops, travel_mode)

                st.success(f"Ruta generada para {travel_mode}!")

                st.info("La ruta se planificará en Google Maps.")
                st.markdown(f"### [▶️ Abrir Ruta en Google Maps]({maps_url})")
                st.markdown("---")

                st.subheader("💡 Ideas y Planificación Inteligente con Gemini")
                st.info("¿Quieres optimizar la ruta o crear un itinerario turístico completo?")
                st.markdown(
                    """
                    Ve a la pestaña **Chat con Gemini ✨** y pide a la IA que te ayude con:
                    * "Crea un itinerario de un día en París visitando [Tus puntos de interés]."
                    * "Sugiere un orden eficiente para visitar [Puntos de interés] en coche."
                    """
                )
