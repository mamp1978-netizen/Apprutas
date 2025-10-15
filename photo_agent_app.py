# planificador_de_ruta.py
import streamlit as st
import os
from datetime import datetime

# --- Configuración de Streamlit ---
st.set_page_config(
    page_title="Planificador de Rutas Múltiples",
    layout="wide"
)

# ----------------------------------------------------
# --- FUNCIÓN PARA GENERAR URL DE GOOGLE MAPS ---
# ----------------------------------------------------
def generate_maps_url(origin, stops, mode="driving"):
    """Genera una URL de Google Maps para direcciones con waypoints (paradas)."""
    
    # Esta es una URL de ejemplo que Maps Tool genera, pero la simplificamos
    # para la demostración web ya que no estás usando la API de Maps.
    base_url = "https://www.google.com/maps/dir/"

    # Prepara el origen y las paradas, reemplazando espacios por '+'
    route_parts = [origin.replace(" ", "+")]
    for stop in stops:
        route_parts.append(stop.replace(" ", "+"))

    route_string = "/".join(route_parts)

    # Convierte el modo de viaje a un código de URL
    travel_mode_code = {
        "Conduciendo": "driving",
        "Caminando": "walking",
        "Bicicleta": "bicycling",
        "Transporte Público": "transit"
    }.get(mode, "driving")

    # Devolvemos una URL que simula el enlace a Google Maps
    return f"{base_url}{route_string}/data=!4m2!4m1!3e{travel_mode_code}"


# ----------------------------------------------------
# --- UI PRINCIPAL (PLANIFICADOR DE RUTA) ---
# ----------------------------------------------------

st.title("🗺️ Planificador de Rutas Múltiples")
st.markdown("Organiza una ruta visitando múltiples puntos de interés.")
st.divider()

# --- 1. PUNTO DE PARTIDA ---
origin = st.text_input("1. Punto de Partida:", value="MY_LOCATION", key="route_origin")

# --- 2. PUNTOS DE VISITA (WAYPOINTS) ---
st.subheader("2. Puntos de Visita (Paradas)")

if 'stops' not in st.session_state:
    st.session_state['stops'] = ["Eiffel Tower, Paris", "Louvre Museum, Paris"]

new_stops = []
for i in range(len(st.session_state['stops'])):
    # Aseguramos que la clave de la sesión se actualice correctamente
    stop_input = st.text_input(f"Parada {i+1}:", value=st.session_state['stops'][i], key=f"stop_{i}")
    new_stops.append(stop_input)

st.session_state['stops'] = new_stops

col_add, col_remove, _ = st.columns([1, 1, 4])

# Botones dinámicos para añadir/eliminar paradas
with col_add:
    if st.button("➕ Añadir Parada", key="add_stop_btn", disabled=len(st.session_state['stops']) >= 8):
        st.session_state['stops'].append("")
        st.rerun()
with col_remove:
    if st.button("➖ Eliminar Última", key="remove_stop_btn", disabled=len(st.session_state['stops']) <= 1):
        st.session_state['stops'].pop()
        st.rerun()

st.divider()

# --- 3. TIPO DE RUTA Y GENERACIÓN ---
st.subheader("3. Tipo de Ruta y Generación")

travel_mode = st.radio(
    "Selecciona el modo de transporte:",
    ["Conduciendo", "Transporte Público", "Caminando", "Bicicleta"],
    key="travel_mode_radio"
)

if st.button(f"Generar Ruta: {travel_mode}", key="generate_route_btn"):
    if not origin:
        st.error("Por favor, introduce un punto de partida.")
    else:
        # Filtramos paradas vacías
        valid_stops = [stop for stop in st.session_state['stops'] if stop.strip()]

        if not valid_stops:
            st.warning("Debes especificar al menos un destino.")
        else:
            maps_url = generate_maps_url(origin, valid_stops, travel_mode)

            st.success(f"¡Ruta generada para {travel_mode}!")
            st.info("La ruta se planificará en Google Maps.")
            st.markdown(f"### [▶️ Abrir Ruta en Google Maps]({maps_url})")
