import streamlit as st
import requests
from app_utils import suggest_addresses, resolve_selection, build_gmaps_url, make_qr

# ---------- Estado ----------
def _init_state():
    if "prof_points" not in st.session_state:
        st.session_state.prof_points = []
    if "prof_last_route_url" not in st.session_state:
        st.session_state.prof_last_route_url = None
    if "prof_open_check" not in st.session_state:
        st.session_state.prof_open_check = False
    if "prof_last_location_guess" not in st.session_state:
        st.session_state.prof_last_location_guess = ""
    if "prof_route_type" not in st.session_state:
        st.session_state.prof_route_type = "Más rápido"

# ---------- IP -> dirección aproximada ----------
def _ip_location_to_address() -> str | None:
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

# ---------- Añadir / Eliminar ----------
def _add_point(value: str | None):
    value = (value or "").strip()
    if not value:
        st.warning("Escribe o selecciona una dirección antes de añadir.")
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
        st.warning("No se pudo obtener tu ubicación. Inténtalo de nuevo o escribe manualmente.")

def _remove_point(idx: int):
    if 0 <= idx < len(st.session_state.prof_points):
        removed = st.session_state.prof_points.pop(idx)
        st.info(f"🗑️ Eliminado: {removed}")

# ---------- Widget: buscador con sugerencias + ENTER ----------
def search_and_add(block_key: str, label: str = "Buscar dirección…"):
    """
    Muestra un FORM; al pulsar ENTER añade la primera sugerencia si existe,
    en caso contrario añade el texto tal cual.
    """
    with st.form(key=f"{block_key}_form", clear_on_submit=True):
        q = st.text_input(label, key=f"{block_key}_q", placeholder="Calle, número, ciudad…")
        # Sugerencias en vivo (al teclear rerenderiza)
        suggestions = suggest_addresses(q, block_key) if q else []
        if suggestions:
            st.caption("Sugerencias:")
            # Mostramos solo las 6 primeras para no saturar
            for i, s in enumerate(suggestions[:6]):
                st.write(f"• {s}")
        submitted = st.form_submit_button("Añadir (ENTER)")
        if submitted:
            if suggestions:
                _add_point(suggestions[0])  # primera sugerencia
            else:
                _add_point(q)               # texto tal cual

# ---------- UI principal ----------
def mostrar_profesional():
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption(
        "Crea tu lista de puntos: el **primero** será el **origen**, el **último** el **destino**, "
        "y los demás serán **paradas intermedias**."
    )

    st.selectbox(
        "🧭 Tipo de ruta",
        ["Más rápido", "Más corto", "Evitar autopistas", "Evitar peajes", "Ruta panorámica"],
        key="prof_route_type"
    )
    st.divider()

    # Bloque superior para empezar
    if not st.session_state.prof_points:
        search_and_add("prof_top", "Buscar dirección… (pulsa ENTER para añadir)")
        c1, c2 = st.columns([0.7, 0.3])
        with c2:
            if st.button("📍 Usar mi ubicación", use_container_width=True, key="loc_start"):
                _add_point_from_location()

    st.divider()

    # Lista de puntos
    st.markdown("### Puntos de la ruta (orden de viaje)")
    if not st.session_state.prof_points:
        st.info("Aún no hay puntos. Añade uno arriba o usa 📍 Ubicación.")
    else:
        for i, p in enumerate(st.session_state.prof_points):
            col_lbl, col_btn = st.columns([0.9, 0.1])
            with col_lbl:
                prefix = "Origen" if i == 0 else ("Destino" if i == len(st.session_state.prof_points) - 1 else f"Parada #{i}")
                st.write(f"**{prefix}:** {p}")
            with col_btn:
                st.button("🗑️", key=f"del_{i}", on_click=_remove_point, args=(i,), help="Eliminar este punto", use_container_width=True)

    # Bloque inferior para seguir añadiendo
    if st.session_state.prof_points:
        st.divider()
        search_and_add("prof_bottom", "Añadir más puntos… (ENTER para añadir)")
        c1, c2 = st.columns([0.7, 0.3])
        with c2:
            if st.button("📍 Ubicación", use_container_width=True, key="loc_bottom"):
                _add_point_from_location()

    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

    # Generar ruta
    if st.button("Generar ruta profesional", type="primary", key="btn_generar_prof"):
        pts = st.session_state.prof_points
        if len(pts) < 2:
            st.error("Debes tener al menos **2 puntos** (origen y destino).")
            return

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

        # Preferencias de ruta
        mode = "driving"
        avoid = []
        pref = st.session_state.prof_route_type
        if pref == "Más corto":
            avoid = ["tolls", "highways"]
        elif pref == "Evitar autopistas":
            avoid = ["highways"]
        elif pref == "Evitar peajes":
            avoid = ["tolls"]
        elif pref == "Ruta panorámica":
            mode = "bicycling"

        url = build_gmaps_url(
            o["address"],
            d["address"],
            wp_resolved if wp_resolved else None,
            mode=mode,
            avoid=avoid,
            optimize=True
        )
        st.session_state.prof_last_route_url = url

        st.success(f"✅ Ruta generada ({pref})")
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

    # Última ruta
    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada (esta sesión)", expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption="QR de la última ruta")