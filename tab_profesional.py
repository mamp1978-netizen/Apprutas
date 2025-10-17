# tab_profesional.py
import streamlit as st
import requests
from app_utils import address_input, resolve_selection, build_gmaps_url, make_qr

# --------------------- Estado ---------------------
def _init_state():
    # Lista ordenada de puntos (str). [p0, p1, p2, ...]
    if "prof_points" not in st.session_state:
        st.session_state.prof_points: list[str] = []
    if "prof_last_route_url" not in st.session_state:
        st.session_state.prof_last_route_url = None
    if "prof_open_check" not in st.session_state:
        st.session_state.prof_open_check = False
    if "prof_last_location_guess" not in st.session_state:
        st.session_state.prof_last_location_guess = ""

# --------------------- Ubicación aprox. por IP ---------------------
def _ip_location_to_address() -> str | None:
    """Obtiene ciudad/área por IP (aprox.). En la nube puede no ser exacto."""
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        city = ip.get("city") or ""
        region = ip.get("region") or ""
        country = ip.get("country_name") or ""
        s = ", ".join([x for x in (city, region, country) if x])
        return s or None
    except Exception as e:
        print("ip->address error:", e)
        return None

# --------------------- Acciones ---------------------
def _add_point_from_input(value: str | None):
    value = (value or "").strip()
    if not value:
        st.warning("Escribe o selecciona una dirección para añadirla.")
        return
    st.session_state.prof_points.append(value)
    st.success(f"➕ Añadido: {value}")

def _add_point_from_location():
    guess = _ip_location_to_address()
    if guess:
        st.session_state.prof_last_location_guess = guess
        st.session_state.prof_points.append(guess)
        st.success(f"📍 Añadido por ubicación (aprox.): {guess}")
    else:
        st.warning("No pude obtener tu ubicación. Escribe tu dirección o selecciona en el buscador.")

def _remove_point(idx: int):
    if 0 <= idx < len(st.session_state.prof_points):
        removed = st.session_state.prof_points.pop(idx)
        st.info(f"🗑️ Eliminado: {removed}")

# --------------------- UI principal ---------------------
def mostrar_profesional():
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption(
        "Crea tu lista de puntos: el **primero** será el **origen**, el **último** el **destino**, "
        "y los demás serán **paradas intermedias**."
    )

    # ---------- Barra única para añadir puntos + botones
    st.markdown("**Añadir punto**")
    c_input, c_add, c_loc = st.columns([0.65, 0.18, 0.17], vertical_alignment="bottom")

    with c_input:
        new_point = address_input("Buscar dirección…", "prof_add_point")

    with c_add:
        if st.button("➕ Añadir", use_container_width=True):
            _add_point_from_input(new_point)

    with c_loc:
        if st.button("📍 Ubicación", use_container_width=True):
            _add_point_from_location()

    if st.session_state.prof_last_location_guess:
        st.caption(f"Última ubicación aproximada detectada: {st.session_state.prof_last_location_guess}")

    st.divider()

    # ---------- Lista de puntos actuales (con eliminar individual)
    st.markdown("### Puntos de la ruta (arriba a abajo)")
    if not st.session_state.prof_points:
        st.info("Aún no hay puntos. Añade uno con la barra de arriba o con 📍 Ubicación.")
    else:
        for i, p in enumerate(st.session_state.prof_points):
            col_lbl, col_btn = st.columns([0.9, 0.1])
            with col_lbl:
                prefix = "Origen" if i == 0 else ("Destino" if i == len(st.session_state.prof_points) - 1 else f"Parada #{i}")
                st.write(f"**{prefix}:** {p}")
            with col_btn:
                st.button("🗑️", key=f"del_{i}", on_click=_remove_point, args=(i,), help="Eliminar este punto", use_container_width=True)

    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

    # ---------- Generar ruta ----------
    if st.button("Generar ruta profesional", type="primary"):
        pts = st.session_state.prof_points
        if len(pts) < 2:
            st.error("Necesitas al menos **2 puntos** (origen y destino).")
            return

        # Resolver direcciones a formato final (aprovecha Google si hay selection previa)
        # origen, destino, waypoints
        o_raw = pts[0]
        d_raw = pts[-1]
        wp_raw = pts[1:-1]

        o = resolve_selection(o_raw, "prof_point_0")
        d = resolve_selection(d_raw, f"prof_point_{len(pts)-1}")

        wp_resolved = []
        open_report = []
        for i, label in enumerate(wp_raw, start=1):
            det = resolve_selection(label, f"prof_point_{i}")
            wp_resolved.append(det["address"])
            if st.session_state.prof_open_check:
                open_report.append((f"Parada #{i}", det.get("address"), det.get("open_now")))

        url = build_gmaps_url(o["address"], d["address"], wp_resolved if wp_resolved else None)
        st.session_state.prof_last_route_url = url

        st.success("✅ Ruta generada")
        st.write(url)
        st.image(make_qr(url), caption="Escanea para abrir la ruta en el móvil")

        if st.session_state.prof_open_check:
            st.markdown("### Estado de apertura (ahora)")
            def _flagline(prefix, det):
                if det.get("open_now") is True:
                    st.markdown(f"**{prefix}:** ✅ Abierto – {det['address']}")
                elif det.get("open_now") is False:
                    st.markdown(f"**{prefix}:** ⛔ Cerrado – {det['address']}")
                else:
                    st.markdown(f"**{prefix}:** ℹ️ Sin datos – {det['address']}")
            _flagline("Origen", o)
            for title, addr, flag in open_report:
                if flag is True:
                    st.markdown(f"**{title}:** ✅ Abierto – {addr}")
                elif flag is False:
                    st.markdown(f"**{title}:** ⛔ Cerrado – {addr}")
                else:
                    st.markdown(f"**{title}:** ℹ️ Sin datos – {addr}")
            _flagline("Destino", d)

    # ---------- Última ruta de la sesión
    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada (esta sesión)", expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption="QR de la última ruta")