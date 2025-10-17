# photo_agent_app.py
from urllib.parse import quote_plus
from io import BytesIO
from datetime import datetime
import os, re, requests

import qrcode
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# =========================
# Variables de entorno
# =========================
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")               # para SerpApi (Google Maps/Autocomplete)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # para clima (OpenWeather)

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
# Utilidades base (rutas / QR)
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

# =========================
# Helpers SerpApi (open/close + autocomplete + turísticos)
# =========================
def _parse_latlon(text: str):
    if not text: return None
    m = re.match(r'\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)\s*', text)
    if m: return float(m.group(1)), float(m.group(3))
    return None

def serpapi_maps(query: str, origin_text: str = "", engine: str = "google_maps", extra=None, lang="es"):
    if not SERPAPI_KEY: return {"error": "Falta SERPAPI_KEY"}
    params = {"engine": engine, "api_key": SERPAPI_KEY, "hl": lang}
    if engine == "google_maps":
        params["q"] = query
        coords = _parse_latlon(origin_text)
        if coords: params["ll"] = f"@{coords[0]},{coords[1]},14z"
    elif engine == "google_autocomplete":
        params["q"] = query
    if extra: params.update(extra)
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
        if r.status_code != 200: return {"error": f"HTTP {r.status_code}"}
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def serpapi_first_place(query: str, origin_text: str = "", lang="es"):
    data = serpapi_maps(query, origin_text, engine="google_maps", lang=lang)
    if "place_results" in data and isinstance(data["place_results"], dict):
        return data["place_results"]
    if "local_results" in data and data["local_results"]:
        return data["local_results"][0]
    return {}

def extract_open_now(place: dict):
    if not place or (isinstance(place, dict) and place.get("error")):
        return ("desconocido", "Sin datos de horario")
    text_fields = []
    for k in ("opening_hours", "hours", "open_state", "status"):
        v = place.get(k)
        if isinstance(v, str): text_fields.append(v)
    text = " | ".join(text_fields).lower()
    if any(x in text for x in ["abierto ahora", "open ⋅", "open now", "abierto"]): return ("abierto", text_fields[0] if text_fields else "Abierto ahora")
    if any(x in text for x in ["cerrado", "closed"]): return ("cerrado", text_fields[0] if text_fields else "Cerrado")
    if place.get("open_now") is True: return ("abierto", "Abierto ahora")
    if place.get("open_now") is False: return ("cerrado", "Cerrado")
    return ("desconocido", "Horario no disponible")

def check_open_status_for_list(origin_text: str, stops: list[str], lang: str = "es"):
    resultados = []
    for stop in stops:
        place = serpapi_first_place(stop, origin_text, lang=lang)
        nombre = place.get("title") or place.get("name") or stop
        direccion = place.get("address") or place.get("description") or ""
        estado, detalle = extract_open_now(place)
        resultados.append((nombre, direccion, estado, detalle))
    return resultados

def serpapi_autocomplete_suggestions(partial: str):
    if not partial.strip(): return []
    data = serpapi_maps(partial, engine="google_autocomplete")
    suggestions = []
    for s in data.get("suggestions", []):
        txt = s.get("suggestion")
        if txt and txt not in suggestions:
            suggestions.append(txt)
    return suggestions[:7]

def serpapi_tourist_spots(city: str, radius_km: int = 10, max_results: int = 10):
    if not city.strip(): return []
    queries = [
        f"puntos turísticos en {city}",
        f"monumentos en {city}",
        f"museos en {city}",
        f"lugares emblemáticos en {city}"
    ]
    vistos, results = set(), []
    for q in queries:
        data = serpapi_maps(q, engine="google_maps")
        for item in data.get("local_results", []):
            title = item.get("title")
            addr = item.get("address") or item.get("description")
            if not title or (title, addr) in vistos: continue
            vistos.add((title, addr))
            results.append(title if addr is None else f"{title}, {addr}")
            if len(results) >= max_results: break
        if len(results) >= max_results: break
    return results

# =========================
# Geocodificación inversa (coord -> dirección)
# =========================
def reverse_geocode_to_address(lat: float, lon: float) -> str:
    """
    Convierte coordenadas en dirección legible usando Nominatim (OpenStreetMap).
    No requiere API key.
    """
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1},
            headers={"User-Agent": "apprutas/1.0"}
        )
        if resp.status_code != 200:
            return f"{lat:.6f}, {lon:.6f}"
        data = resp.json()
        return data.get("display_name") or f"{lat:.6f}, {lon:.6f}"
    except Exception:
        return f"{lat:.6f}, {lon:.6f}"

def resolve_origin_text(text: str) -> str:
    """
    Si el texto es 'lat, lon', lo convierte a dirección (reverse geocoding).
    Si ya es dirección, devuelve el mismo texto limpio.
    """
    coords = _parse_latlon(text)
    if coords:
        lat, lon = coords
        return reverse_geocode_to_address(lat, lon)
    return (text or "").strip()

# =========================
# OpenWeather – clima por parada
# =========================
def get_weather_for(place_text: str, lang="es"):
    if not OPENWEATHER_API_KEY:
        return {"error": "Falta OPENWEATHER_API_KEY"}
    city = place_text.split(",")[0].strip() if place_text else ""
    if not city: return {"error": "Ciudad vacía"}
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": lang}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200: return {"error": f"HTTP {r.status_code}"}
        d = r.json()
        desc = (d.get("weather") or [{}])[0].get("description", "").capitalize()
        temp = d.get("main", {}).get("temp")
        feels = d.get("main", {}).get("feels_like")
        wind = d.get("wind", {}).get("speed")
        return {"city": city, "desc": desc, "temp": temp, "feels": feels, "wind": wind}
    except Exception as e:
        return {"error": str(e)}

def weather_list(stops: list[str]):
    rows = []
    for s in stops:
        w = get_weather_for(s)
        if "error" in w:
            rows.append(f"🌥️ {s} — {w['error']}")
        else:
            rows.append(f"🌥️ {w['city']}: {w['desc']}, {w['temp']}°C (sensación {w['feels']}°C), viento {w['wind']} m/s")
    return rows

# =========================
# UI helpers (botón ubicación)
# =========================
def location_button_for(label_text: str):
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
    if (aria.includes("{label_text}") || ph.toLowerCase().includes("punto de partida") || ph.toLowerCase().includes("ciudad o ubicación") || ph.toLowerCase().includes("dirección completa (origen)")){{
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
# Estado inicial
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

    # ===== Origen: barra única =====
    origin_prof_full = st.text_input(
        "Dirección completa (origen)",
        placeholder="Ej.: Gran Via 24, Madrid | Plaça Catalunya, Barcelona"
    )
    location_button_for("Dirección completa (origen)")

    # Autocompletar (opcional)
    with st.expander("🔎 Autocompletar origen (SerpApi)"):
        partial = st.text_input("Escribe para buscar", placeholder="Ej.: Gran Via 24, Madrid")
        if st.button("Buscar sugerencias (Profesional)"):
            if not SERPAPI_KEY:
                st.error("Falta SERPAPI_KEY.")
            else:
                sugs = serpapi_autocomplete_suggestions(partial)
                if sugs:
                    choice = st.selectbox("Elige una sugerencia", sugs, key="prof_auto_choice")
                    if st.button("Usar sugerencia", key="prof_use_suggestion"):
                        st.session_state["__origin_prof_prefill"] = choice
                        st.experimental_rerun()
                else:
                    st.info("Sin sugerencias.")
    if "__origin_prof_prefill" in st.session_state:
        origin_prof_full = st.session_state.pop("__origin_prof_prefill")

    # ===== Paradas =====
    st.markdown("**Paradas**")
    new_stops = []
    for i, stop in enumerate(st.session_state.stops_prof):
        new_stops.append(st.text_input(f"Parada #{i+1}", value=stop, key=f"prof_stop_{i}"))
    st.session_state.stops_prof = new_stops

    col1, col2, col3, col4 = st.columns([1.2, 1.6, 2, 2])
    with col1:
        st.button("➕ Añadir", key="prof_add", type="secondary",
                  on_click=lambda: st.session_state.stops_prof.append(""))
    with col2:
        st.button("➖ Quitar última", key="prof_rm", type="secondary",
                  on_click=lambda: st.session_state.stops_prof.pop() if st.session_state.stops_prof else None,
                  disabled=len(st.session_state.stops_prof) <= 1)
    with col3:
        check_prof = st.button("🔔 Comprobar horarios (beta)")
    with col4:
        w_prof = st.button("🌦️ Ver clima")

    # Resolver origen (convierte coords -> dirección si hace falta)
    origin_prof_resolved = resolve_origin_text(origin_prof_full)

    if check_prof:
        if not SERPAPI_KEY:
            st.error("No está configurado SERPAPI_KEY.")
        else:
            valid = [s.strip() for s in st.session_state.stops_prof if s.strip()]
            if not origin_prof_resolved:
                st.error("Introduce la dirección de origen o usa 🎯.")
            elif not valid:
                st.info("Añade paradas primero.")
            else:
                for nombre, direccion, estado, detalle in check_open_status_for_list(origin_prof_resolved, valid):
                    if estado == "abierto":
                        st.success(f"✅ {nombre} — {detalle}\n\n{direccion}")
                    elif estado == "cerrado":
                        st.warning(f"⚠️ {nombre} — {detalle}\n\n{direccion}")
                    else:
                        st.info(f"ℹ️ {nombre} — {detalle}\n\n{direccion}")

    if w_prof:
        valid = [s.strip() for s in st.session_state.stops_prof if s.strip()]
        for line in weather_list(valid):
            st.write(line)

    mode_prof = st.radio("Modo", ["Conduciendo","Transporte Público","Caminando","Bicicleta"], horizontal=True, key="mode_prof")
    if st.button("Generar ruta (Profesional)"):
        valid = [s.strip() for s in st.session_state.stops_prof if s.strip()]
        valid = list(dict.fromkeys(valid))
        if not origin_prof_resolved:
            st.error("Introduce la dirección de origen o usa 🎯.")
        elif not valid:
            st.warning("Añade al menos una parada.")
        else:
            url = generate_maps_url(origin_prof_resolved, valid, mode_prof)
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

    with st.expander("🔎 Autocompletar origen (SerpApi)"):
        partial2 = st.text_input("Escribe para buscar (Viajero)", placeholder="Ej.: Plaça Catalunya, Barcelona")
        if st.button("Buscar sugerencias (Viajero)"):
            if not SERPAPI_KEY:
                st.error("Falta SERPAPI_KEY.")
            else:
                sugs = serpapi_autocomplete_suggestions(partial2)
                st.write(sugs if sugs else "Sin sugerencias.")

    lista = st.text_area("Paradas", value="\n".join(st.session_state.stops_trip), height=120)
    if st.button("Aplicar lista"):
        st.session_state.stops_trip = [s.strip() for s in lista.splitlines() if s.strip()]

    col1, col2, col3 = st.columns([1.2, 1.6, 2])
    with col1:
        mode_trip = st.selectbox("Modo", ["Conduciendo","Transporte Público","Caminando","Bicicleta"])
    with col2:
        go_trip = st.button("Generar ruta (Viajero)")
    with col3:
        check_trip = st.button("🔔 Comprobar horarios (beta)")
    st.write("")
    if st.button("🌦️ Ver clima (Viajero)"):
        valid = [s.strip() for s in st.session_state.stops_trip if s.strip()]
        for line in weather_list(valid): st.write(line)

    if check_trip:
        if not SERPAPI_KEY:
            st.error("No está configurado SERPAPI_KEY.")
        else:
            valid = [s.strip() for s in st.session_state.stops_trip if s.strip()]
            if not valid:
                st.info("Añade paradas primero.")
            else:
                for nombre, direccion, estado, detalle in check_open_status_for_list(origin_trip, valid):
                    if estado == "abierto":
                        st.success(f"✅ {nombre} — {detalle}\n\n{direccion}")
                    elif estado == "cerrado":
                        st.warning(f"⚠️ {nombre} — {detalle}\n\n{direccion}")
                    else:
                        st.info(f"ℹ️ {nombre} — {detalle}\n\n{direccion}")

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

    with st.expander("🔎 Autocompletar ciudad (SerpApi)"):
        partial3 = st.text_input("Buscar ciudad", placeholder="Ej.: Sevilla, España")
        if st.button("Buscar sugerencias (Turístico)"):
            if not SERPAPI_KEY:
                st.error("Falta SERPAPI_KEY.")
            else:
                sugs = serpapi_autocomplete_suggestions(partial3)
                st.write(sugs if sugs else "Sin sugerencias.")

    radius_km = st.slider("Radio de acción (km)", 1, 30, 10)

    if st.button("✨ Sugerir lugares emblemáticos"):
        if not SERPAPI_KEY:
            st.error("Falta SERPAPI_KEY.")
        elif not origin_tour.strip():
            st.error("Introduce una ciudad o usa 🎯.")
        else:
            sugeridos = serpapi_tourist_spots(origin_tour, radius_km, max_results=10)
            if sugeridos:
                st.session_state.stops_tour = sugeridos
                st.success(f"Se sugirieron {len(sugeridos)} lugares.")
            else:
                st.info("No se encontraron lugares. Prueba con otra ciudad.")

    chosen = st.multiselect("Elige lugares", st.session_state.stops_tour,
                            default=st.session_state.stops_tour[: min(3, len(st.session_state.stops_tour))])

    col1, col2, col3 = st.columns([1.2, 1.6, 2])
    with col1:
        mode_tour = st.radio("Modo", ["Conduciendo","Transporte Público","Caminando","Bicicleta"],
                             horizontal=True, key="mode_tour")
    with col2:
        go_tour = st.button("Generar ruta (Turístico)")
    with col3:
        check_tour = st.button("🔔 Comprobar horarios (beta)")
    st.write("")
    if st.button("🌦️ Ver clima (Turístico)"):
        for line in weather_list(chosen): st.write(line)

    if check_tour:
        if not SERPAPI_KEY:
            st.error("No está configurado SERPAPI_KEY.")
        else:
            valid = [s.strip() for s in chosen if s.strip()]
            if not valid:
                st.info("Selecciona lugares primero.")
            else:
                for nombre, direccion, estado, detalle in check_open_status_for_list(origin_tour, valid):
                    if estado == "abierto":
                        st.success(f"✅ {nombre} — {detalle}\n\n{direccion}")
                    elif estado == "cerrado":
                        st.warning(f"⚠️ {nombre} — {detalle}\n\n{direccion}")
                    else:
                        st.info(f"ℹ️ {nombre} — {detalle}\n\n{direccion}")

    if go_tour:
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