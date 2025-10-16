# photo_agent_app.py
import streamlit as st
from urllib.parse import quote_plus
from io import BytesIO
import qrcode

# --- Configuración de Streamlit ---
st.set_page_config(page_title="Planificador de Rutas Múltiples", layout="wide")

# ----------------------------------------------------
# --- FUNCIÓN PARA GENERAR URL DE GOOGLE MAPS ---
# ----------------------------------------------------
def generate_maps_url(origin: str, stops: list[str], mode_label: str = "Conduciendo") -> str:
    """
    Genera una URL de Google Maps para direcciones con paradas (waypoints).
    El último elemento de 'stops' se usa como destino; el resto como waypoints.
    """
    if not origin or not stops:
        return ""

    # Limpieza y codificación
    origin_q = quote_plus(origin.strip())
    cleaned = [s.strip() for s in stops if s and s.strip()]
    if not cleaned:
        return ""

    destination_q = quote_plus(cleaned[-1])
    waypoints_q = "|".join(quote_plus(s) for s in cleaned[:-1])

    # Mapear etiqueta en español -> travelmode de Google
    mode_map = {
        "Conduciendo": "driving",
        "Caminando": "walking",
        "Bicicleta": "bicycling",
        "Transporte Público": "transit",
        "driving": "driving",
        "walking": "walking",
        "bicycling": "bicycling",
        "transit": "transit",
    }
    travel_mode = mode_map.get(mode_label, "driving")

    # Formato oficial de Directions URL
    # https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=A|B|C&travelmode=driving
    url = f"https://www.google.com/maps/dir/?api=1&origin={origin_q}&destination={destination_q}"
    if waypoints_q:
        url += f"&waypoints={waypoints_q}"
    url += f"&travelmode={travel_mode}"
    return url

# ----------------------------------------------------
# --- UI PRINCIPAL (PLANIFICADOR DE RUTA) ---
# ----------------------------------------------------
st.title("🗺️ Planificador de Rutas Múltiples")
st.caption("Organiza una ruta visitando múltiples puntos de interés y ábrela en Google Maps.")

st.divider()

# --- 1. PUNTO DE PARTIDA ---
origin = st.text_input("1) Punto de partida", value="")

# --- 2. PUNTOS DE VISITA (WAYPOINTS) ---
st.subheader("2) Puntos de visita (paradas)")
if "stops" not in st.session_state:
    st.session_state.stops = ["Eiffel Tower, Paris", "Louvre Museum, Paris"]

new_stops: list[str] = []
for i, stop in enumerate(st.session_state.stops):
    new_value = st.text_input(f"Parada #{i+1}", value=stop, key=f"stop_{i}")
    new_stops.append(new_value)
st.session_state.stops = new_stops

col_add, col_remove, _ = st.columns([1, 1, 4])
with col_add:
    st.button("➕ Añadir parada", key="add_stop_btn",
              on_click=lambda: st.session_state.stops.append(""),
              disabled=len(st.session_state.stops) >= 20)
with col_remove:
    st.button("➖ Eliminar última", key="remove_stop_btn",
              on_click=lambda: st.session_state.stops.pop() if st.session_state.stops else None,
              disabled=len(st.session_state.stops) <= 1)

st.divider()

# --- 3. TIPO DE RUTA Y GENERACIÓN ---
st.subheader("3) Tipo de ruta y generación")

travel_mode = st.radio(
    "Modo de transporte:",
    ["Conduciendo", "Transporte Público", "Caminando", "Bicicleta"],
    index=0,
    key="travel_mode_radio"
)

generate_clicked = st.button("Generar ruta")

generated_url = ""

if generate_clicked:
    if not origin.strip():
        st.error("Por favor, introduce un punto de partida.")
    else:
        # Filtrar paradas vacías y quitar duplicados (manteniendo orden)
        valid_stops = [s.strip() for s in st.session_state.stops if s.strip()]
        valid_stops = list(dict.fromkeys(valid_stops))

        if not valid_stops:
            st.warning("Debes especificar al menos una parada (la última será el destino).")
        else:
            generated_url = generate_maps_url(origin, valid_stops, travel_mode)
            if not generated_url:
                st.error("No se pudo generar la URL. Revisa los datos introducidos.")
            else:
                st.success(f"¡Ruta generada para *{travel_mode}*!")
                st.info("La ruta se abrirá en Google Maps.")
                st.markdown(f"### [▶️ Abrir Ruta en Google Maps]({generated_url})")
                st.text_input("Enlace generado (para copiar)", generated_url, label_visibility="collapsed")

# --- QR de la URL generada (fuera de funciones) ---
if generated_url:
    try:
        buffer = BytesIO()
        img = qrcode.make(generated_url)    # crea el QR
        img.save(buffer, format="PNG")      # lo guarda en memoria
        png_bytes = buffer.getvalue()

        st.markdown("#### Código QR de la ruta")
        st.image(png_bytes, caption="Escanéalo para abrir la ruta", use_column_width=False)
        st.download_button(
            label="⬇️ Descargar QR (PNG)",
            data=png_bytes,
            file_name="ruta_qr.png",
            mime="image/png"
        )
    except Exception as e:
        st.error(f"Error generando el QR: {e}")

# ----------------------------------------------------
# --- 💡 MEJORA 1: EJEMPLO RÁPIDO Y VALIDACIÓN EXTRA ---
# ----------------------------------------------------
st.divider()
st.subheader("💡 Opciones rápidas")

if st.button("Cargar ejemplo"):
    st.session_state.stops = [
        "Sagrada Família, Barcelona",
        "Parc Güell, Barcelona",
        "Camp Nou, Barcelona"
    ]
    # Nota: el origen NO lo guardamos en sesión para que lo confirmes tú
    st.success("Ejemplo cargado en paradas. Introduce un origen y pulsa «Generar ruta».")

# Validación extra informativa
if "stops" in st.session_state:
    preview = [s for s in st.session_state.stops if s.strip()]
    if len(preview) > 15:
        st.warning("⚠️ Has añadido muchas paradas: Google Maps podría no aceptarlas todas en un único enlace.")