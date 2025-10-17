import streamlit as st
import requests
from app_utils import address_input, resolve_selection, build_gmaps_url, make_qr

# --------------------- Estado ---------------------
def _init_state():
    if "prof_stops_count" not in st.session_state:
        st.session_state.prof_stops_count = 0
    if "prof_last_route_url" not in st.session_state:
        st.session_state.prof_last_route_url = None
    if "prof_origin_manual" not in st.session_state:
        st.session_state.prof_origin_manual = ""  # origen fijado por botón ubicación
    if "prof_open_check" not in st.session_state:
        st.session_state.prof_open_check = False

def _add_stop():
    st.session_state.prof_stops_count += 1

def _remove_stop():
    if st.session_state.prof_stops_count > 0:
        idx = st.session_state.prof_stops_count - 1
        st.session_state.pop(f"prof_stop_{idx}", None)
        st.session_state.pop(f"prof_stop_{idx}_manual", None)
        st.session_state.prof_stops_count -= 1

# --------------------- Utilidades ---------------------
def _ip_location_to_address() -> str | None:
    """
    Detecta ubicación por IP y devuelve una dirección aproximada.
    Nota: en Streamlit Cloud suele devolver la IP del servidor (no exacto).
    """
    try:
        ip = requests.get("https://ipapi.co/json/", timeout=6).json()
        lat, lon = ip.get("latitude"), ip.get("longitude")
        if lat is None or lon is None:
            city = ip.get("city") or ""
            region = ip.get("region") or ""
            country = ip.get("country_name") or ""
            guess = ", ".join([x for x in [city, region, country] if x])
            return guess if guess else None

        url = (
            "https://nominatim.openstreetmap.org/reverse?"
            f"format=json&lat={lat}&lon={lon}&zoom=16&addressdetails=0"
        )
        headers = {"User-Agent": "PlanificadorRutas/1.0 (streamlit)"}
        r = requests.get(url, headers=headers, timeout=6)
        r.raise_for_status()
        return r.json().get("display_name") or None
    except Exception as e:
        print("ip->address error:", e)
        return None

# --------------------- UI principal ---------------------
def mostrar_profesional():
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption("Planifica visitas a clientes, obras o inspecciones. La **última parada** será el **destino final**.")

    # -------- Origen (con autocompletado + campo manual + botón ubicación)
    st.markdown("**Origen**")
    origin_label = address_input("Dirección completa (origen)", "prof_origin")
    origin_manual = st.text_input("o escribir manualmente", key="prof_origin_manual_text", placeholder="Carrer / Calle, ciudad…")

    colb1, colb2 = st.columns([0.55, 0.45])
    with colb1:
        if st.button("📍 Usar mi ubicación (aprox.)", use_container_width=True):
            addr = _ip_location_to_address()
            if addr:
                st.session_state.prof_origin_manual = addr
                st.success(f"Origen fijado: {addr}")
            else:
                st.warning("No pude obtener tu ubicación. Escribe tu dirección manualmente.")
    with colb2:
        if st.session_state.prof_origin_manual:
            st.info(f"Origen actual: {st.session_state.prof_origin_manual}")

    st.caption("Sugerencia móvil: si no ves sugerencias, escribe el domicilio completo en el campo manual.")

    # -------- Paradas (dinámicas) con autocompletado + campo manual
    st.markdown("### Paradas intermedias")
    c1, c2, _ = st.columns([0.25, 0.25, 0.5])
    with c1:
        st.button("+ Añadir parada", on_click=_add_stop, use_container_width=True)
    with c2:
        st.button("Eliminar última", on_click=_remove_stop, use_container_width=True)

    stops_labels: list[str] = []
    for i in range(st.session_state.prof_stops_count):
        st.markdown(f"**Parada #{i+1}**")
        s_label = address_input(f"Buscar parada #{i+1}", f"prof_stop_{i}")
        s_manual = st.text_input("o escribir manualmente", key=f"prof_stop_{i}_manual", placeholder="Dirección completa…")
        # Preferencia: selección del searchbox > campo manual
        final_label = s_label or s_manual
        if final_label:
            stops_labels.append(final_label)

    # -------- Check 'abierto ahora'
    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

    # ---------------- Generar Ruta ----------------
    if st.button("Generar ruta profesional", type="primary"):
        # Origen: prioridad searchbox > manual > botón ubicación
        chosen_origin = origin_label or origin_manual or st.session_state.prof_origin_manual
        if not chosen_origin:
            st.error("Indica el **origen** (o usa el botón de ubicación).")
            return
        if len(stops_labels) == 0:
            st.error("Añade al menos **una parada** (será el destino final).")
            return

        # Resolver origen
        o = resolve_selection(chosen_origin, "prof_origin")

        # Destino = última parada; waypoints = anteriores
        destination_label = stops_labels[-1]
        waypoints_labels = stops_labels[:-1]

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

        # Informe “abierto ahora”
        if st.session_state.prof_open_check:
            st.markdown("### Estado de apertura (ahora)")
            # Origen
            if o.get("open_now") is True:
                st.markdown(f"**Origen:** ✅ Abierto – {o['address']}")
            elif o.get("open_now") is False:
                st.markdown(f"**Origen:** ⛔ Cerrado – {o['address']}")
            else:
                st.markdown(f"**Origen:** ℹ️ Sin datos – {o['address']}")
            # Paradas intermedias
            for title, addr, flag in open_report:
                if flag is True:
                    st.markdown(f"**{title}:** ✅ Abierto – {addr}")
                elif flag is False:
                    st.markdown(f"**{title}:** ⛔ Cerrado – {addr}")
                else:
                    st.markdown(f"**{title}:** ℹ️ Sin datos – {addr}")
            # Destino
            if d_det.get("open_now") is True:
                st.markdown(f"**Destino:** ✅ Abierto – {d_det['address']}")
            elif d_det.get("open_now") is False:
                st.markdown(f"**Destino:** ⛔ Cerrado – {d_det['address']}")
            else:
                st.markdown(f"**Destino:** ℹ️ Sin datos – {d_det['address']}")

    # -------- Última ruta
    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada (esta sesión)", expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption="QR de la última ruta")