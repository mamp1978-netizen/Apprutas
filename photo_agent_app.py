# photo_agent_app.py
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
# --- CONFIGURACIÓN DE GEMINI Y HERRAMIENTAS (NUEVO) ---
# ----------------------------------------------------
def get_gemini_client():
    """Inicializa el cliente Gemini y el modelo con herramientas de búsqueda."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        st.error("Error: La clave GEMINI_API_KEY no está configurada. Por favor, añádela en los Secrets de Streamlit Cloud.")
        st.stop()
    
    try:
        client = genai.Client(api_key=gemini_key)
        # Se define el modelo con la herramienta de búsqueda de Google (Google Search)
        model = client.models.get(
            model="gemini-2.5-flash",
            config={"tools": [{"google_search": {}}]}
        )
        return client, model
    except Exception as e:
        st.error(f"Error al iniciar el cliente Gemini o el modelo: {e}")
        st.stop()


# --- Configuración de Streamlit ---
st.set_page_config(
    page_title="Gestor de Fotos y Archivos",
    layout="wide"
)

st.title("📸 Gestor de Fotos y Archivos (Streamlit)")
st.markdown("Sube y descarga fotos, o usa la cámara web directamente.")
st.divider()

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
        # Componente nativo de Streamlit para la cámara (Ahora más pequeño)
        camera_file = st.camera_input("Apunta y captura")

    # ----------------------------------------------------
    # La lógica de guardar la foto va justo DESPUÉS de las columnas
    # ----------------------------------------------------
    if camera_file:
        # 1. Muestra la foto capturada
        st.image(camera_file, caption="Foto Capturada")

        # 2. Permite al usuario guardar la foto
        if st.button("Guardar esta foto"):
            from datetime import datetime # Importamos aquí si no está al inicio
            from PIL import Image # Aseguramos el import de PIL
            from io import BytesIO
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cam_{timestamp}.jpg"

            # Guarda el archivo en la carpeta interna
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
    
    # Obtiene la lista de archivos para descargar
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
            
            # Opción para eliminar el archivo
            if st.button(f"🗑️ Eliminar {selected_photo}"):
                os.remove(os.path.join(PHOTOS_DIR, selected_photo))
                st.success(f"Archivo **{selected_photo}** eliminado. (Recarga la página para actualizar la lista)")
                # Recarga la página para mostrar el cambio
                # Es posible que necesites recargar manualmente si st.rerun no funciona en tu versión de Streamlit
    else:
        st.info("La carpeta interna está vacía.")
        
# === PESTAÑA 4: CHAT CON GEMINI ===
with tab4:
    st.header("Chat con Gemini ✨")
    st.markdown("Mantén una conversación continua con Gemini. ¡El historial se guarda!")

    # --- 1. Inicializar Cliente y Modelo ---
    # Usamos la función get_gemini_client() para garantizar que el cliente esté disponible
    if "client" not in st.session_state:
        st.session_state["client"], st.session_state["model_search"] = get_gemini_client()
        
    client = st.session_state["client"]

    # --- 2. Inicializar la sesión de chat y la historia ---
    if "chat_session" not in st.session_state:
        try:
            # Crear la sesión de chat. **IMPORTANTE: Sin la herramienta de búsqueda.**
            st.session_state["chat_session"] = client.chats.create(
                model="gemini-2.5-flash" 
            )
            st.session_state["messages"] = [{"role": "model", "content": "¡Hola! Soy Gemini. ¿En qué puedo ayudarte hoy?"}]
        except Exception as e:
            # Este error ocurre si la clave API falla, pero ya lo habías resuelto.
            st.error(f"Error al iniciar el cliente Gemini: {e}")
            st.stop()


    # --- 3. Mostrar historial de mensajes ---
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- 4. Capturar la entrada del usuario ---
    if prompt := st.chat_input("Pregúntale algo a Gemini..."):
        # Añadir prompt del usuario al historial y mostrarlo
        st.session_state["messages"].append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)

        # --- 5. Enviar a Gemini y obtener respuesta ---
        with st.spinner("Gemini está pensando..."):
            try:
                # Usar la sesión de chat guardada para mantener el contexto
                chat = st.session_state["chat_session"]
                response = chat.send_message(prompt)
                
                # Añadir respuesta del modelo al historial y mostrarla
                st.session_state["messages"].append({"role": "model", "content": response.text})
                
                with st.chat_message("model"):
                    st.markdown(response.text)

            except Exception as e:
                st.error(f"Error al conectar con Gemini: {e}")
                st.session_state["messages"].append({"role": "model", "content": "Lo siento, hubo un error de conexión."})
                
    # --- 6. Botón para limpiar el historial ---
    if st.button("Reiniciar Chat", key="reset_chat"):
        # Creamos una nueva sesión de chat para borrar el contexto
        st.session_state["chat_session"] = client.chats.create(
            model="gemini-2.5-flash"
        )
        st.session_state["messages"] = [{"role": "model", "content": "Chat Reiniciado. ¿En qué puedo ayudarte?"}]
        st.rerun() 
        
# ------------------------------------------------------------
# === PESTAÑA 5: BUSCADOR WEB (¡AÑADIDO!) ===
# ------------------------------------------------------------
with tab5:
    st.header("Buscador Web 🌐")
    st.markdown("Usa la inteligencia de Gemini con acceso directo a Google Search.")
    
    # 1. Inicializar Cliente y Modelo (Con Herramientas)
    if "client" not in st.session_state or "model" not in st.session_state:
        st.session_state["client"], st.session_state["model"] = get_gemini_client()
        
    model = st.session_state["model"] # Este modelo ya tiene la herramienta de búsqueda activada

    # 2. Campo de entrada para la consulta
    prompt = st.text_input(
        "¿Qué quieres buscar?",
        placeholder="Ej: ¿Quién ganó el último premio Nobel de física y por qué?"
    )
    
    # 3. Botón de búsqueda
    search_button = st.button("Buscar y Responder (Gemini + Google)")
    
    # 4. Lógica de ejecución
    if search_button and prompt:
        with st.spinner(f"Buscando en Google y generando respuesta para '{prompt}'..."):
            try:
                # Llama al modelo que tiene la herramienta 'google_search' activada.
                response = model.generate_content(prompt)
                
                # Muestra el resultado
                st.subheader("Resultado de la Búsqueda:")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"Error al ejecutar la búsqueda con Gemini: {e}")
                
# ------------------------------------------------------------
# === FIN DE LA PESTAÑA 5 ===
# ------------------------------------------------------------


# === PESTAÑA 6: PLANIFICADOR DE RUTA ===
def generate_maps_url(origin, stops, mode="driving"):
    """Genera una URL de Google Maps para direcciones con waypoints."""
    # Nota: El formato real de Google Maps para waypoints es más complejo,
    # pero simplificamos con un formato base para la demostración.
    base_url = "https://www.google.com/maps/dir/"

    # 1. Punto de Origen
    route_parts = [origin.replace(" ", "+")]

    # 2. Puntos de Parada (Waypoints) y Destino (El último)
    for stop in stops:
        route_parts.append(stop.replace(" ", "+"))

    # Unir todos los puntos
    route_string = "/".join(route_parts)

    # Añadir modo de transporte (Simplificado)
    travel_mode_code = {
        "Conduciendo": "driving",
        "Caminando": "walking",
        "Bicicleta": "bicycling",
        "Transporte Público": "transit"
    }.get(mode, "driving")
    
    # Usamos el parámetro de modo en la URL
    return f"{base_url}{route_string}/data=!4m2!4m1!3e{travel_mode_code}"


with tab6:
    st.header("Planificador de Rutas Múltiples 📍")
    st.markdown("Organiza una ruta visitando múltiples puntos de interés (hasta 8 paradas).")

    # --- ENTRADAS ---
    origin = st.text_input("1. Punto de Partida:", value="MY_LOCATION", key="route_origin")

    # Campos de puntos de interés (Waypoints)
    st.subheader("2. Puntos de Visita (Waypoints)")

    # Usamos st.session_state para gestionar una lista dinámica de paradas
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
        # Asegurarse de que el origen no esté vacío y haya al menos un destino
        if not origin or not any(st.session_state['stops']):
            st.error("Por favor, introduce un punto de partida y al menos una parada válida.")
        else:
            # Filtrar paradas vacías si el usuario no las usó
            valid_stops = [stop for stop in st.session_state['stops'] if stop.strip()]

            if not valid_stops:
                st.warning("Debes especificar al menos un destino.")
            else:
                # Generar la URL
                maps_url = generate_maps_url(origin, valid_stops, travel_mode)

                st.success(f"Ruta generada para {travel_mode}!")

                # Mostrar la información y el enlace directo
                st.info("La ruta se planificará en Google Maps.")
                st.markdown(f"### [▶️ Abrir Ruta en Google Maps]({maps_url})")
                st.markdown("---")

                # Opcional: Sugerencia de itinerarios con Gemini
                st.subheader("💡 Ideas y Planificación Inteligente con Gemini")
                st.info("¿Quieres optimizar la ruta o crear un itinerario turístico completo?")
                st.markdown(
                    """
                    Ve a la pestaña **Chat con Gemini ✨** y pide a la IA que te ayude con:
                    * "Crea un itinerario de un día en París visitando [Tus puntos de interés]."
                    * "Sugiere un orden eficiente para visitar [Puntos de interés] en coche."
                    """
                )
