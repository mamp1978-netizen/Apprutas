import streamlit as st
from app_utils import address_input, resolve_selection, build_gmaps_url, make_qr

# --------------------- Helpers de estado ---------------------
def _init_state():
    if "prof_stops_count" not in st.session_state:
        st.session_state.prof_stops_count = 0  # cuántas cajas de parada hay
    if "prof_last_route_url" not in st.session_state:
        st.session_state.prof_last_route_url = None
    if "prof_open_check" not in st.session_state:
        st.session_state.prof_open_check = False

def _add_stop():
    st.session_state.prof_stops_count += 1

def _remove_stop():
    if st.session_state.prof_stops_count > 0:
        # limpiar valor de la última parada
        idx = st.session_state.prof_stops_count - 1
        st.session_state.pop(f"prof_stop_{idx}", None)
        st.session_state.prof_stops_count -= 1

# --------------------- UI principal ---------------------
def mostrar_profesional():
    _init_state()

    st.subheader("Ruta de trabajo")
    st.caption("Planifica visitas a clientes, obras o inspecciones. Usa direcciones completas.")

    # Origen / Destino
    col1, col2 = st.columns([1, 1])
    with col1:
        origin_label = address_input("Dirección completa (origen)", "prof_origin")
    with col2:
        dest_label = address_input("Dirección completa (destino final)", "prof_dest")

    st.markdown("### Paradas intermedias")

    # Controles para añadir/eliminar paradas
    c1, c2, c3 = st.columns([0.25, 0.25, 0.5])
    with c1:
        st.button("+ Añadir parada", on_click=_add_stop, use_container_width=True)
    with c2:
        st.button("Eliminar última", on_click=_remove_stop, use_container_width=True)

    # Render dinámico de paradas con autocompletado
    stops_labels: list[str] = []
    for i in range(st.session_state.prof_stops_count):
        label = address_input(f"Parada #{i+1}", f"prof_stop_{i}")
        if label:
            stops_labels.append(label)

    # Opcional: comprobar “abierto ahora”
    st.session_state.prof_open_check = st.checkbox(
        "Comprobar si los lugares están abiertos ahora (si hay datos de Google)",
        value=st.session_state.prof_open_check
    )

    # Botón de generar ruta
    if st.button("Generar ruta profesional", type="primary"):
        if not origin_label or not dest_label:
            st.error("Indica al menos **origen** y **destino**.")
            return

        # Resolver selecciones a direcciones finales (y open_now si aplica)
        o = resolve_selection(origin_label, "prof_origin")
        d = resolve_selection(dest_label, "prof_dest")

        # Paradas: tomamos el texto tal cual (Google Maps acepta direcciones por texto)
        waypoints = []
        open_report = []

        for i, lab in enumerate(stops_labels):
            # resolvemos por si viene de Google/SerpAPI/OSM (nos puede dar open_now si Google)
            det = resolve_selection(lab, f"prof_stop_{i}")
            waypoints.append(det["address"])
            if st.session_state.prof_open_check:
                open_report.append((f"Parada #{i+1}", det.get("address"), det.get("open_now")))

        # Construir URL y QR
        url = build_gmaps_url(o["address"], d["address"], waypoints if waypoints else None)
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
            # Paradas
            for title, addr, flag in open_report:
                if flag is True:
                    st.markdown(f"**{title}:** ✅ Abierto – {addr}")
                elif flag is False:
                    st.markdown(f"**{title}:** ⛔ Cerrado – {addr}")
                else:
                    st.markdown(f"**{title}:** ℹ️ Sin datos – {addr}")
            # Destino
            if d.get("open_now") is True:
                st.markdown(f"**Destino:** ✅ Abierto – {d['address']}")
            elif d.get("open_now") is False:
                st.markdown(f"**Destino:** ⛔ Cerrado – {d['address']}")
            else:
                st.markdown(f"**Destino:** ℹ️ Sin datos – {d['address']}")

    # Si ya hay una ruta generada en esta sesión, vuelve a mostrar su QR/enlace
    if st.session_state.prof_last_route_url:
        with st.expander("Última ruta generada (esta sesión)", expanded=False):
            st.write(st.session_state.prof_last_route_url)
            st.image(make_qr(st.session_state.prof_last_route_url), caption="QR de la última ruta")