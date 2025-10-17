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

# ---------- Acciones de lista ----------
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

def _move_point(idx: int, direction: str):
    pts = st.session_state.prof_points
    if direction == "up" and idx > 0:
        pts[idx-1], pts[idx] = pts[idx], pts[idx-1]
    elif direction == "down" and idx < len(pts) - 1:
        pts[idx+1], pts[idx] = pts[idx], pts[idx+1]

# ---------- Barra de búsqueda única (sugerencias + ENTER) ----------
def search_and_add_top():
    with st.form(key="prof_top_form", clear_on_submit=True):
        q = st.text_input("Buscar dirección… (pulsa ENTER para añadir)",
                          key="prof_top_q",
                          placeholder="Calle, número, ciudad…")
        suggestions = suggest_addresses(q, "prof_top") if q else []
        if suggestions:
            st.caption("Sugerencias:")
            for s in suggestions[:6]:
                st.write(f"• {s}")
        c1, c2 = st.columns([0.7, 0.3])
        submitted = c1.form_submit_button("Añadir (ENTER)")
        loc = c2.form_submit_button("📍 Usar mi ubicación")

        if submitted:
            if suggestions:
                _add_point(suggestions[0])   # primera sugerencia
            else:
                _add_point(q)                 # texto tal cual
        if loc:
            _add_point_from_location()

# ---------- UI principal ----------
def mostrar_profesional():
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption(
        "Añade puntos con la barra de arriba. El **primero** es **origen**, el **último** es **destino**; "
        "los demás son **paradas intermedias**. Puedes reordenar con las flechas y eliminar cualquier punto."
    )

    st.selectbox(
        "🧭 Tipo de ruta",
        ["Más rápido", "Más corto", "Evitar autopistas", "Evitar peajes", "Ruta panorámica"],
        key="prof_route_type"
    )
    st.divider()

    # --- ÚNICA barra arriba
    search_and_add_top()

    # --- Lista compacta debajo (sin segundo formulario)
    st.markdown("### Puntos de la ruta (orden de viaje)")
    pts = st.session_state.prof_points
    if not pts:
        st.info("Añade al menos dos puntos (origen y destino) para generar la ruta.")
    else:
        for i, p in enumerate(pts):
            prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}")
            c_lbl, c_up, c_down, c_del = st.columns([0.76, 0.08, 0.08, 0.08])
            with c_lbl:
                st.write(f"**{prefix}:** {p}")
            with c_up:
                st.button("↑", key=f"up_{i}_{len(pts)}", on_click=_move_point, args=(i, "up"),
                          disabled=(i == 0), use_container_width=True)
            with c_down:
                st.button("↓", key=f"down_{i}_{len(pts)}", on_click=_move_point, args=(i, "down"),
                          disabled=(i == len(pts)-1), use_container_width=True)
            with c_del:
                st.button("🗑️", key=f"del_{i}_{len(pts)}", on_click=_remove_point, args=(i,),
                          use_container_width=True)

    st.divider()

    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

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

    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada (esta sesión)", expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption="QR de la última ruta")