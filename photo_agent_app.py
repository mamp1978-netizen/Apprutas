# photo_agent_app.py
from urllib.parse import quote_plus
from io import BytesIO
from datetime import datetime

import qrcode
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()
SERPAPI_KEY = os.getenv("509069584263d87bb53b7a37a256e6bf14ba088c0db5531f0d87efbca9875732")

# =========================
# Configuración + estilos
# =========================
st.set_page_config(page_title="Planificador de Rutas", layout="wide")
st.markdown("""
<style>
:root{
  --primary:#2563EB; --primary-dark:#1E40AF;
  --text:#0f172a; --muted:#6b7280;
  --bg:#F9FAFB; --card:#FFFFFF; --border:#E5E7EB;
}
html, body, [data-testid="stAppViewContainer"] { background: var(--bg); color: var(--text); }
h1,h2,h3 { font-weight: 800; letter-spacing: -0.01em; }
.section-card{ background:var(--card); border:1px solid var(--border);
  border-radius:16px; padding:1.25rem; box-shadow:0 2px 12px rgba(0,0,0,0.04);}
div.stButton > button {
  background: var(--primary); color:#fff; border:none; border-radius:12px;
  padding:0.8rem 1rem; font-weight:700;
}
div.stButton > button:hover { background: var(--primary-dark); }
button[kind="secondary"]{
  background:#fff !important; color:var(--text) !important; border:1px solid var(--border) !important;
}
.helper{ color:var(--muted); font-size:0.9rem; }
.badge{ display:inline-block; padding:.2rem .5rem; border-radius:999px; border:1px solid var(--border); color:var(--muted); }
</style>
""", unsafe_allow_html=True)

# =========================
# Utilidades
# =========================
def generate_maps_url(origin: str, stops: list[str], mode_label: str = "Conduciendo") -> str:
    if not origin or not stops: return ""
    origin_q = quote_plus(origin.strip())
    cleaned = [s.strip() for s in stops if s and s.strip()]
    if not cleaned: return ""
    destination_q = quote_plus(cleaned[-1])
    waypoints_q = "|".join(quote_plus(s) for s in cleaned[:-1])
    mode_map = {"Conduciendo":"driving","Caminando":"walking","Bicicleta":"bicycling","Transporte Público":"transit",
                "driving":"driving","walking":"walking","bicycling":"bicycling","transit":"transit"}
    travel = mode_map.get(mode_label, "driving")
    url = f"https://www.google.com/maps/dir/?api=1&origin={origin_q}&destination={destination_q}"
    if waypoints_q: url += f"&waypoints={waypoints_q}"
    url += f"&travelmode={travel}"
    return url

def show_qr_for(url: str):
    if not url: return
    buf = BytesIO(); qrcode.make(url).save(buf, format="PNG")
    st.image(buf.getvalue(), caption="Escanéalo para abrir la ruta", use_column_width=False)
    st.download_button("⬇️ Descargar QR (PNG)", buf.getvalue(),
                       f"ruta_{datetime.now().strftime('%Y%m%d_%H%M')}.png", "image/png")

def location_button_for(label_text: str):
    """Botón 'Usar mi ubicación' que rellena el input (lat, lon)."""
    components.html(f"""
<div style="margin: 0 0 10px 0;">
  <button onclick="getLoc()" style="
    padding:9px 12px;border-radius:10px;border:1px solid #d1d5db;background:#fff;cursor:pointer;font-weight:700">
    🎯 Usar mi ubicación
  </button>
  <span style="color:#6b7280;font-size:12px;margin-left:8px;">(el navegador pedirá permiso)</span>
</div>
<script>
function writeToInput(value){{
  const inputs = window.parent.document.querySelectorAll('input');
  for (const el of inputs){{
    const aria = (el.getAttribute('aria-label')||"");
    const ph = (el.getAttribute('placeholder')||"");
    if (aria.includes("{label_text}") || ph.toLowerCase().includes("punto de partida")){{
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      setter.call(el, value);
      el.dispatchEvent(new Event('input', {{ bubbles: true }}));
      break;
    }}
  }}
}}
function getLoc(){{
  if (!navigator.geolocation){{ alert("Tu navegador no soporta geolocalización."); return; }}
  navigator.geolocation.getCurrentPosition(
    (pos)=>{{ const v = pos.coords.latitude.toFixed(6)+", "+pos.coords.longitude.toFixed(6); writeToInput(v); }},
    (err)=>{{ alert("No se pudo obtener la ubicación: " + err.message); }},
    {{ enableHighAccuracy:true, timeout:10000, maximumAge:0 }}
  );
}}
</script>
""", height=80)

# =========================
# Estado
# =========================
if "stops_prof" not in st.session_state: st.session_state.stops_prof = ["Cliente 1, Barcelona", "Cliente 2, Barcelona"]
if "stops_trip" not in st.session_state: st.session_state.stops_trip = ["Eiffel Tower, Paris", "Louvre Museum, Paris"]
if "stops_tour" not in st.session_state: st.session_state.stops_tour = ["Sagrada Família", "Parc Güell", "Casa Batlló"]

# =========================
# Cabecera y Pestañas
# =========================
st.title("🗺️ Planificador de Rutas")
st.caption("Crea una ruta con paradas y ábrela en Google Maps. La **última parada** es el *destino final*.")

tab1, tab2, tab3 = st.tabs(["👷 Profesional", "✈️ Viajero", "🏛️ Turístico"])

# ---------- 👷 PROFESIONAL ----------
with tab1:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Ruta de trabajo")
    st.markdown('<span class="badge">Jornada</span> Planifica visitas a clientes, obras o inspecciones.', unsafe_allow_html=True)

    # Origen (estructurado opcional: País + Calle + Nº)
    colA, colB, colC = st.columns([2,2,1])
    with colA:
        pais_prof = st.text_input("País", placeholder="Ej.: España")
    with colB:
        calle_prof = st.text_input("Calle", placeholder="Ej.: Gran Via, Madrid")
    with colC:
        num_prof = st.text_input("Nº", placeholder="Ej.: 24")
    origin_prof = " ".join([s for s in [pais_prof, calle_prof, num_prof] if s]).strip()
    location_button_for("País")

    # Paradas
    st.markdown("**Paradas**")
    new_stops = []
    for i, stop in enumerate(st.session_state.stops_prof):
        new_stops.append(st.text_input(f"Parada #{i+1}", value=stop, key=f"prof_stop_{i}"))
    st.session_state.stops_prof = new_stops
    col1, col2, _ = st.columns([1,1,4])
    with col1:
        st.button("➕ Añadir", key="prof_add", type="secondary",
                  on_click=lambda: st.session_state.stops_prof.append(""))
    with col2:
        st.button("➖ Quitar última", key="prof_rm", type="secondary",
                  on_click=lambda: st.session_state.stops_prof.pop() if st.session_state.stops_prof else None,
                  disabled=len(st.session_state.stops_prof)<=1)

    mode_prof = st.radio("Modo", ["Conduciendo","Transporte Público","Caminando","Bicicleta"], horizontal=True, key="mode_prof")
    if st.button("Generar ruta (Profesional)"):
        valid = [s.strip() for s in st.session_state.stops_prof if s.strip()]
        valid = list(dict.fromkeys(valid))
        if not origin_prof:
            st.error("Introduce el origen (País, Calle, Nº) o usa 🎯.")
        elif not valid:
            st.warning("Añade al menos una parada.")
        else:
            url = generate_maps_url(origin_prof, valid, mode_prof)
            st.success("¡Ruta generada!")
            st.markdown(f"[▶️ Abrir en Google Maps]({url})")
            st.text_input("Enlace", url, label_visibility="collapsed")
            show_qr_for(url)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- ✈️ VIAJERO ----------
with tab2:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Viajero (itinerario conocido)")
    st.markdown('<span class="badge">Importar</span> Pega tus destinos (una línea por parada).', unsafe_allow_html=True)

    origin_trip = st.text_input("Punto de partida", placeholder="Ej.: Aeropuerto de Barcelona")
    location_button_for("Punto de partida")

    # Textarea para paradas
    lista = st.text_area("Paradas", value="\n".join(st.session_state.stops_trip), height=120)
    if st.button("Aplicar lista"):
        st.session_state.stops_trip = [s.strip() for s in lista.splitlines() if s.strip()]

    col1, col2 = st.columns([1,1])
    with col1:
        mode_trip = st.selectbox("Modo", ["Conduciendo","Transporte Público","Caminando","Bicicleta"])
    with col2:
        go_trip = st.button("Generar ruta (Viajero)")

    if go_trip:
        valid = [s.strip() for s in st.session_state.stops_trip if s.strip()]
        valid = list(dict.fromkeys(valid))
        if not origin_trip:
            st.error("Introduce el origen o usa 🎯.")
        elif not valid:
            st.warning("Añade al menos una parada.")
        else:
            url = generate_maps_url(origin_trip, valid, mode_trip)
            st.success("¡Ruta generada!")
            st.markdown(f"[▶️ Abrir en Google Maps]({url})")
            st.text_input("Enlace", url, label_visibility="collapsed")
            show_qr_for(url)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- 🏛️ TURÍSTICO ----------
with tab3:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Turístico (descubre y elige)")
    st.markdown('<span class="badge">Explorar</span> Indica tu ubicación o ciudad y selecciona lugares emblemáticos.', unsafe_allow_html=True)

    origin_tour = st.text_input("Ciudad o ubicación", placeholder="Ej.: Barcelona, España")
    location_button_for("Ciudad o ubicación")

    # Radio de acción (preparado para futura integración con Places/OSM)
    radius_km = st.slider("Radio de acción (km)", 1, 30, 10)
    st.caption("Más adelante conectaremos con Google Places u OpenStreetMap para sugerencias reales.")

    chosen = st.multiselect("Elige lugares", st.session_state.stops_tour, default=st.session_state.stops_tour[:2])
    mode_tour = st.radio("Modo", ["Conduciendo","Transporte Público","Caminando","Bicicleta"], horizontal=True, key="mode_tour")

    if st.button("Generar ruta (Turístico)"):
        valid = [s.strip() for s in chosen if s.strip()]
        if not origin_tour:
            st.error("Introduce una ciudad/ubicación o usa 🎯.")
        elif not valid:
            st.warning("Selecciona al menos un lugar.")
        else:
            url = generate_maps_url(origin_tour, valid, mode_tour)
            st.success("¡Ruta generada!")
            st.markdown(f"[▶️ Abrir en Google Maps]({url})")
            st.text_input("Enlace", url, label_visibility="collapsed")
            show_qr_for(url)
    st.markdown('</div>', unsafe_allow_html=True)