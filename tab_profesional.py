import streamlit as st
import requests
from app_utils import address_input, resolve_selection, build_gmaps_url, make_qr

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
    if "prof_add_point_last" not in st.session_state:
        st.session_state.prof_add_point_last = None

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

    def add_block():
        st.markdown("**Añadir punto a la ruta**")
        new_point = address_input("Buscar dirección… (pulsa ENTER para añadir)", "prof_add_point")
        if new_point and st.session_state.prof_add_point_last != new_point:
            st.session_state.prof_add_point_last = new_point
            _add_point(new_point)

        c_add, c_loc = st.columns([0.7, 0.3])
        with c_add:
            if st.button("➕ Añadir punto", use_container_width=True):
                _add_point(new_point)
        with c_loc:
            if st.button("📍 Ubicación", use_container_width=True):
                _add_point_from_location()

        if st.session_state.prof_last_location_guess:
            st.caption(f"Última ubicación detectada: {st.session_state.prof_last_location_guess}")

    if not st.session_state.prof_points:
        add_block()

    st.divider()

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

    if st.session_state.prof_points:
        st.divider()
        add_block()

    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

    if st.button("Generar ruta