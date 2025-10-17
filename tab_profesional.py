import streamlit as st
from app_utils import address_input, resolve_selection, build_gmaps_url, make_qr

def mostrar_profesional():
    st.subheader("Ruta de trabajo")
    st.caption("Planifica visitas a clientes, obras o inspecciones.")

    col1, col2 = st.columns([1, 1])
    with col1:
        origin_label = address_input("Dirección completa (origen)", "prof_origin")
    with col2:
        dest_label = address_input("Dirección completa (destino final)", "prof_dest")

    stops_text = st.text_area("Paradas intermedias (una por línea)", height=120)
    stops = [s.strip() for s in stops_text.splitlines() if s.strip()]

    if st.button("Generar ruta profesional"):
        if not origin_label or not dest_label:
            st.error("Indica al menos origen y destino.")
        else:
            o = resolve_selection(origin_label, "prof_origin")
            d = resolve_selection(dest_label, "prof_dest")
            url = build_gmaps_url(o["address"], d["address"], stops if stops else None)
            st.success("Ruta generada")
            st.write(url)
            st.image(make_qr(url), caption="Escanea para abrir la ruta en el móvil")