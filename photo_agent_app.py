# photo_agent_app.py - Código Final Funcional
import streamlit as st
import yaml
from yaml.loader import SafeLoader
from pathlib import Path
from PIL import Image
import hashlib
import os
from dotenv import load_dotenv

# --- Ocultar avisos del sistema Streamlit (líneas amarillas) ---
st.markdown(
    """
    <style>
        [data-testid="stNotification"] {
            display: none !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------- CONFIGURACIÓN GLOBAL Y SEGURIDAD -----------------
st.set_page_config(
    page_title="Planificador de Rutas",
    layout="wide",
    initial_sidebar_state="expanded",
)

CONFIG_FILE = Path('config.yaml')

def load_config():
    """Carga configuraciones de YAML. Inicializa cookies si el archivo no existe."""
    try:
        with open(CONFIG_FILE) as file:
            return yaml.load(file, Loader=SafeLoader)
    except FileNotFoundError:
        # CORRECCIÓN: Devolvemos un diccionario de configuración completo con cookies iniciales.
        return {
            'credentials': {'usernames': {}}, 
            'cookie': {
                'expiry_days': 30,
                'key': hashlib.sha256(os.urandom(32)).hexdigest(), # Clave única de seguridad
                'name': 'auth_cookie'
            }
        }

def save_config(config):
    """Guarda configuraciones en YAML."""
    with open(CONFIG_FILE, 'w') as file:
        yaml.dump(config, file, default_flow_style=False)

def hash_password(password):
    """Función simple para hashear la contraseña (usando SHA256)."""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(username, password_unhashed, config):
    """Verifica si la contraseña coincide."""
    user_data = config['credentials']['usernames'].get(username)
    if not user_data:
        return False
    
    # Comparamos el hash almacenado con el hash de la contraseña introducida
    stored_hash = user_data['password_hash']
    input_hash = hash_password(password_unhashed)
    
    return stored_hash == input_hash

def clear_route_state():
    """Función que borra las variables de ruta al cerrar sesión."""
    for key in ["prof_points", "saved_routes", "route_name_input", "saved_choice", "_current_routes_user"]:
        if key in st.session_state:
            del st.session_state[key]


# Cargar variables de entorno para Geocodificación (solo para el warning)
load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    st.sidebar.warning("⚠️ Clave API de Google no configurada. La Geocodificación será SIMULADA.")
# Fin de chequeo de API


# Cargar configuraciones
config = load_config()

# Inicialización de estado de Autenticación
st.session_state.setdefault('logged_in', False)
st.session_state.setdefault('show_register', False)
st.session_state.setdefault('username', None)
st.session_state.setdefault('name', None)


# ----------------- LÓGICA DE LA APLICACIÓN -----------------

DONATION_URL = "https://www.paypal.com/donate/?business=73LFHKS2WCQ9U&no_recurring=0&item_name=Ayuda+para+desarrolladores&currency_code=EUR"

def _import_ui():
    """Importa la UI de forma robusta."""
    try:
        from tab_profesional.ui import mostrar_profesional
        return mostrar_profesional
    except Exception:
        import importlib
        mod = importlib.import_module("tab_profesional.ui")
        return getattr(mod, "mostrar_profesional")


mostrar_profesional = _import_ui()


def main():
    st.title("🗺️ Planificador de Rutas")

    if st.session_state['logged_in']:
        # ------------------- PÁGINA PRINCIPAL (LOGEADO) -------------------
        st.sidebar.markdown("---")
        st.sidebar.subheader(f"Bienvenido, {st.session_state['name']}!") 
        
        # Botón de Logout MANUAL
        if st.sidebar.button('Logout', use_container_width=True):
            clear_route_state()
            st.session_state['logged_in'] = False
            st.session_state['username'] = None
            st.rerun() 
        
        # 2. RENDERIZAR LA APLICACIÓN PRINCIPAL
        mostrar_profesional() 
        
        # 3. MOSTRAR DONACIÓN
        st.sidebar.markdown("---")
        st.sidebar.subheader("Apoya el desarrollo 🧑‍💻")
        st.sidebar.info(
            "¿Te ha sido útil este planificador de rutas? "
            "Considera una pequeña donación para ayudarme a mantener y mejorar la aplicación."
        )
        st.sidebar.markdown(
            f"""
            <a href="{DONATION_URL}" target="_blank">
                <button style="background-color:#0070BA;color:#fff;padding:10px 20px;border:none;border-radius:5px;cursor:pointer;width:100%;">
                    Ir al enlace de donación
                </button>
            </a>
            """,
            unsafe_allow_html=True,
        )
        st.sidebar.markdown("---")

    else:
        # ------------------- PÁGINA DE LOGIN/REGISTRO -------------------
        col_spacer1, col_content, col_spacer2 = st.columns([1, 4, 1])

        with col_content:
            try:
                # Intenta cargar el logo
                logo = Image.open("logo.png")
                st.image(logo, width=150) 
            except FileNotFoundError:
                st.write("🗺️") 
                
            st.markdown("<h1 style='text-align: center; margin-top: -15px;'>Planificador de Rutas</h1>", unsafe_allow_html=True)
            st.markdown("---")

            # Muestra el formulario de Registro si se solicita
            if st.session_state['show_register']:
                st.subheader("Registro de Nuevo Usuario")
                
                with st.form("register_form"):
                    new_username = st.text_input("Nombre de Usuario", key="reg_username")
                    new_email = st.text_input("Email", key="reg_email")
                    new_name = st.text_input("Nombre Completo", key="reg_name")
                    new_password = st.text_input("Contraseña", type="password", key="reg_password")
                    
                    submitted = st.form_submit_button("Registrarse")

                    if submitted:
                        # CHEQUEO DE INTEGRIDAD FINAL
                        usernames = config['credentials']['usernames']
                        
                        if not all([new_username, new_email, new_name, new_password]):
                            st.error("Rellena todos los campos.")
                        elif new_username in usernames:
                            st.error("El nombre de usuario ya existe.")
                        else:
                            # Guardar nuevo usuario
                            config['credentials']['usernames'][new_username] = {
                                'email': new_email,
                                'name': new_name,
                                'password_hash': hash_password(new_password)
                            }
                            # No necesitamos añadir la cookie aquí, ya que load_config la inicializa
                                
                            save_config(config)
                            st.success('¡Registro exitoso! Ya puedes iniciar sesión.')
                            st.session_state['show_register'] = False
                            st.rerun()

                if st.button("Volver al Login", key='back_to_to_login'):
                    st.session_state['show_register'] = False
                    st.rerun()

            else:
                # Muestra el formulario de LOGIN
                st.subheader("Inicio de Sesión")
                
                with st.form("login_form"):
                    login_username = st.text_input("Usuario", key="login_username")
                    login_password = st.text_input("Contraseña", type="password", key="login_password")
                    
                    submitted = st.form_submit_button("Login")

                    if submitted:
                        if check_password(login_username, login_password, config):
                            user_data = config['credentials']['usernames'][login_username]
                            st.session_state['logged_in'] = True
                            st.session_state['username'] = login_username
                            st.session_state['name'] = user_data['name']
                            st.rerun()
                        else:
                            st.error("Usuario o contraseña incorrectos.")

                st.markdown("---")
                if st.button("Crear una cuenta (Registro)", type="secondary", use_container_width=True):
                    st.session_state['show_register'] = True
                    st.rerun()


if __name__ == "__main__":
    main()
