# photo_agent_app.py
from urllib.parse import quote_plus
from io import BytesIO

import qrcode
import streamlit as st
import streamlit.components.v1 as components

# =========================
# Configuración y estilos
# =========================
st.set_page_config(page_title="Planificador de Rutas Múltiples", layout="wide")

# Estilo "Modern Blue"
st.markdown("""
<style>
:root{
  --primary:#2563EB;      /* Azul principal */
  --primary-dark:#1E40AF; /* Azul hover */
  --text:#0f172a;         /* Gris muy oscuro */
  --muted:#6b7280;        /* Gris medio */
  --bg:#F9FAFB;           /* Fondo claro */
  --card:#FFFFFF;         /* Tarjetas */
  --border:#E5E7EB;       /* Borde sutil */
}

html, body, [data-testid="stAppViewContainer"] { background: var(--bg); color: var(--text); }
h1,h2,h3 { font-weight: 800; letter-spacing: -0.01em; }
hr, .stDivider { border-color: var(--border) !important; }

div[class^="stTextInput"] input, div[data-baseweb="select"] > div {
  border-radius: 10px; border: 1px solid var(--border);
}

div.stButton > button {
  background: var(--primary); color:#fff; border:none;
  border-radius:12px; padding:0.8rem 1rem; font-weight:700;
}
div.stButton > button:hover { background: var(--primary-dark); }

button[kind="secondary"]{
  background:#fff !important; color:var(--text) !important;
  border:1px solid var(--border) !important;
}

/* Cards suaves */
.block-container { padding-top: 2rem; }
.section-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 16px; padding: 1.25rem 1.25rem; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.helper { color: var(--muted); font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# =========================
# Utilidades
# =========================
def generate_maps_url(origin: str, stops: list[str], mode_label: str = "Conduciendo") -> str:
    """
    Genera una URL de Google Maps Directions con paradas (waypoints).
    La última parada se usa como destino; el resto como waypoints.
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

    # Mapear etiqueta → travelmode
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

    url = f"https://www.google.com/maps/dir/?api=1&origin={origin_q}&destination={destination_q}"
    if waypoints_q:
        url += f"&waypoints={waypoints_q}"
    url += f"&travelmode={travel_mode}"
    return url


def render_use_my_location_button(origin_label: str = "1) Punto de partida"):
    """
    Inyecta un botón HTML/JS que obtiene la geolocalización del navegador
    y rellena el input del origen con 'lat, lon'.
    """
    components.html(f"""
<div style="margin: 6px 0 12px 0;">
  <button onclick="getLoc()" style="
    padding:10px 14px;border-radius:10px;border:1px solid #d1d5db;
    background:#ffffff;cursor:pointer;font-weight:700">
    🎯 Usar mi ubicación
  </button>
  <span style="color:#6b7280;font-size:12px;margin-left:8px;">
    (el navegador pedirá permiso)
  </span>
</div>

<script>
function setStreamlitOrigin(value) {{
  // Busca el input por aria-label (título) o placeholder
  const inputs = window.parent.document.querySelectorAll('input');
  for (const el of inputs) {{
    const aria = el.getAttribute('aria-label') || "";
    const ph = el.getAttribute('placeholder') || "";
    if (aria.includes("{origin_label}") || ph.toLowerCase().includes("punto de partida")) {{
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      setter.call(el, value);
      el.dispatchEvent(new Event('input', {{ bubbles: true }}));
      break;
    }}
  }}
}}

function getLoc() {{
  if (!navigator.geolocation) {{
    alert("Tu navegador no soporta geolocalización.");
    return;
  }}
  navigator.geolocation.getCurrentPosition(
    function(pos) {{
      const lat = pos.coords.latitude.toFixed(6);
      const lon = pos.coords.longitude.toFixed(6);
      const coords = lat + ", " + lon;
      setStreamlitOrigin(coords);
    }},
    function(err) {{
      alert("No se pudo obtener la ubicación: " + err.message);
    }},
    {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
  );
}}
</script>
""", height=90)

# =========================
# Estado
# =========================
if "stops" not in st.session_state:
    st.session_state.stops = ["Eiffel Tower, Paris", "Louvre Museum, Paris"]

# =========================
# UI
# =========================
st.title("🗺️ Planificador de Rutas")
st.caption("Crea una ruta con paradas y ábrela en Google Maps. La **última parada** es el *destino final*.")

with st.container():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)

    # Origen + botón de ubicación
    origin = st.text_input("1) Punto de partida", value="", placeholder="Ej.: Plaça Catalunya, Barcelona")
    render_use_my_location_button(origin_label="1) Punto de partida")

    # Paradas (lista editable)
    st.subheader("2) Paradas (waypoints)")
    new_stops: list[str] = []
    for i, stop in enumerate(st.session_state.stops):
        new_val = st.text_input(f"Parada #{i+1}", value=stop, key=f"stop_{i}")
        new_stops.append(new_val)
    st.session_state.stops = new_stops

    col_add, col_remove, _ = st.columns([1, 1, 4])
    with col_add:
        st.button("➕ Añadir parada",
                  on_click=lambda: st.session_state.stops.append(""),
                  type="secondary")
    with col_remove:
        st.button("➖ Eliminar última",
                  on_click=lambda: st.session_state.stops.pop() if st.session_state.stops else None,
                  type="secondary",
                  disabled=len(st.session_state.stops) <= 1)

    st.markdown('<hr/>', unsafe_allow_html=True)

    # Modo y generar
    col_mode, _ = st.columns([2, 3])
    with col_mode:
        travel_mode = st.radio(
            "3) Modo de transporte",
            ["Conduciendo", "Transporte Público", "Caminando", "Bicicleta"],
            horizontal=True,
            index=0
        )

    generate_clicked = st.button("Generar ruta")

    generated_url = ""
    if generate_clicked:
        if not origin.strip():
            st.error("Por favor, introduce un punto de partida.")
        else:
            # Limpieza y validación
            valid_stops = [s.strip() for s in st.session_state.stops if s.strip()]
            # elimina duplicados preservando orden
            valid_stops = list(dict.fromkeys(valid_stops))

            if not valid_stops:
                st.warning("Debes especificar al menos una parada (la última será el destino).")
            else:
                generated_url = generate_maps_url(origin, valid_stops, travel_mode)
                if not generated_url:
                    st.error("No se pudo generar la URL. Revisa los datos.")
                else:
                    st.success(f"¡Ruta generada para *{travel_mode}*!")
                    st.info("La ruta se abrirá en Google Maps.")
                    st.markdown(f"### [▶️ Abrir Ruta en Google Maps]({generated_url})")
                    st.text_input("Enlace generado (para copiar)", generated_url, label_visibility="collapsed")

                    # QR
                    try:
                        buf = BytesIO()
                        img = qrcode.make(generated_url)
                        img.save(buf, format="PNG")
                        png_bytes = buf.getvalue()
                        st.image(png_bytes, caption="Escanéalo para abrir la ruta", use_column_width=False)
                        st.download_button("⬇️ Descargar QR (PNG)", png_bytes, "ruta_qr.png", "image/png")
                    except Exception as e:
                        st.error(f"Error generando el QR: {e}")

    # Opciones rápidas
    st.divider()
    st.subheader("💡 Opciones rápidas")
    if st.button("Cargar ejemplo (Barcelona)"):
        st.session_state.stops = [
            "Sagrada Família, Barcelona",
            "Parc Güell, Barcelona",
            "Camp Nou, Barcelona"
        ]
        st.info("Introduce un origen y pulsa «Generar ruta».")
    st.markdown('<p class="helper">Consejo: puedes pegar coordenadas en el origen con «🎯 Usar mi ubicación».</p>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)