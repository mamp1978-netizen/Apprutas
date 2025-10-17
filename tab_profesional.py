# tab_profesional.py
import streamlit as st
import requests
from app_utils import address_input, resolve_selection, build_gmaps_url, make_qr

# --------------------- Estado ---------------------
def _init_state():
    if "prof_stops_count" not in st.session_state:
        st.session_state.prof_stops_count = 0
    if "prof_last_route_url" not in st.session_state:
        st.session_state.prof_last_route_url = None
    if "prof_origin_loc" not in st.session_state:
        st.session_state.prof_origin_loc = ""  # texto fijado por botón ubicación
    if "prof_open_check" not in st.session_state:
        st.session_state.prof_open_check = False

def _add_stop():
    st.session_state.prof_stops_count += 1

def _remove_stop():
    if st.session_state.prof_stops_count > 0:
        idx = st.session_state.prof_stops_count - 1
        # limpiamos posibles valores anteriores del searchbox
        st.session_state.pop(f"prof_stop_{idx}", None)
        st.session_state.prof_stops_count -= 1

# --------------------- Ubicación aprox. por IP ---------------------
def _ip_location_to_address() -> str | None:
    """Obtiene ciudad/área por IP (aprox.)."""
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

# --------------------- UI principal ---------------------
def mostrar_profesional():
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption("Planifica visitas a clientes, obras o inspecciones. La **última parada** será el **destino final**.")

    # ---------- ORIGEN (una sola barra + botón ubicación al lado)
    st.markdown("**Origen**")
    c_or, c_btn = st.columns([0.80, 0.20], vertical_alignment="bottom")
    with c_or:
        # barra con autocompletado (Google/SerpAPI/OSM) desde app_utils.address_input
        origin_label = address_input("Dirección completa (origen)", "prof_origin")
    with c_btn:
        if st.button("📍 Ubicación", use_container_width=True):
            guess = _ip_location_to_address()
            if guess:
                # Guardamos el texto para usarlo si no selecciona nada en el searchbox
                st.session_state.prof_origin_loc = guess
                st.success(f"Origen aproximado: {guess}")
            else:
                st.warning("No pude obtener tu ubicación. Escribe tu dirección o selecciona en el buscador.")
        # Mostrar estado actual del botón ubicación
        if st.session_state.prof_origin_loc:
            st.caption(f"Actual: {st.session_state.prof_origin_loc}")

    # ---------- PARADAS (dinámicas), una sola barra por parada
    st.markdown("### Paradas intermedias (la última será el destino)")
    ctrl1, ctrl2, _ = st.columns([0.25, 0.25, 0.5])
    with ctrl1:
        st.button("+ Añadir parada", on_click=_add_stop, use_container_width=True)
    with ctrl2:
        st.button("Eliminar última", on_click=_remove_stop, use_container_width=True)

    stops_labels: list[str] = []
    for i in range(st.session_state.prof_stops_count):
        lbl = address_input(f"Parada #{i+1}", f"prof_stop_{i}")
        if lbl:
            stops_labels.append(lbl)

    # ---------- Opcional: “abierto ahora”
    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

    # ---------- GENERAR RUTA ----------
    if st.button("Generar ruta profesional", type="primary"):
        # Origen: si no eligió nada en el searchbox, usamos el fijado por ubicación (si existe)
        chosen_origin = origin_label or st.session_state.prof_origin_loc
        if not chosen_origin:
            st.error("Indica el **origen** (o pulsa el botón 📍 Ubicación).")
            return
        if len(stops_labels) == 0:
            st.error("Añade al menos **una parada** (será el destino final).")
            return

        # Resolver datos (abre/cierra si procede de Google)
        o = resolve_selection(chosen_origin, "prof_origin")
        destination_label = stops_labels[-1]
        waypoints_labels  = stops_labels[:-1]

        d_det = resolve_selection(destination_label, f"prof_stop_{len(stops_labels)-1}")

        wp_resolved = []
        open_report = []
        for i, lab in enumerate(waypoints_labels):
            det = resolve_selection(lab, f"prof_stop_{i}")
            wp_resolved.append(det["address"])
            if st.session_state.prof_open_check:
                open_report.append((f"Parada #{i+1}", det.get("address"), det.get("open_now")))

        url = build_gmaps_url(o["address"], d_det["address"], wp_resolved if wp_resolved else None)
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
            _flagline("Destino", d_det)

    # ---------- Última ruta de la sesión
    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada (esta sesión)", expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption="QR de la última ruta")