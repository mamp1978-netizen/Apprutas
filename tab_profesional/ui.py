# tab_profesional/ui.py
import streamlit as st

from app_utils_core import (
    resolve_selection,
    build_gmaps_url,
    build_waze_url,
    build_apple_maps_url,
    gmaps,
)

MAX_POINTS = 10  # 1 Origen + hasta 8 paradas + 1 Destino


# -------------------------------
# Estado
# -------------------------------
def initialize_session_state():
    ss = st.session_state
    ss.setdefault("prof_points", [])
    ss.setdefault("selected_point_index", None)   # sin selección por defecto
    ss.setdefault("is_editing_point", False)
    ss.setdefault("edit_input_value", "")
    ss.setdefault("prof_mode", "Más rápido")
    ss.setdefault("prof_avoid", "Ninguno")
    # banderas para limpiar campos tras submit
    ss.setdefault("prof_clear_search_once", False)


def _rerun():
    st.rerun()


def _clear_selection():
    ss = st.session_state
    ss["is_editing_point"] = False
    ss["edit_input_value"] = ""
    ss["selected_point_index"] = None
    _rerun()


# -------------------------------
# Acciones de lista
# -------------------------------
def _add_point_from_value(value: str):
    ss = st.session_state
    if not value:
        return
    if len(ss["prof_points"]) >= MAX_POINTS:
        return
    value = value.strip()
    if len(value) < 3:
        return
    ss["prof_points"].append(value)
    ss["selected_point_index"] = None
    # limpiar input en el siguiente render
    ss["prof_clear_search_once"] = True
    _rerun()


def _move_point(direction: str, i: int):
    ss = st.session_state
    pts = ss["prof_points"]
    if direction == "up" and i > 0:
        pts.insert(i - 1, pts.pop(i))
        ss["selected_point_index"] = i - 1
    elif direction == "down" and i < len(pts) - 1:
        pts.insert(i + 1, pts.pop(i))
        ss["selected_point_index"] = i + 1
    _rerun()


def _delete_point(i: int):
    ss = st.session_state
    pts = ss["prof_points"]
    if 0 <= i < len(pts):
        pts.pop(i)
    _clear_selection()


def _enter_edit_mode(i: int):
    ss = st.session_state
    pts = ss["prof_points"]
    if 0 <= i < len(pts):
        ss["is_editing_point"] = True
        ss["edit_input_value"] = pts[i]
        ss["selected_point_index"] = i
    _rerun()


def _save_point_from_toolbar(i: int):
    ss = st.session_state
    pts = ss["prof_points"]
    new_value = ss["edit_input_value"].strip()
    if 0 <= i < len(pts) and len(new_value) >= 3:
        pts[i] = new_value
        _clear_selection()
    else:
        st.warning("La dirección debe tener al menos 3 caracteres.")


# -------------------------------
# Caja de búsqueda (con Enter)
# -------------------------------
def _search_box():
    ss = st.session_state
    is_limit = len(ss.get("prof_points", [])) >= MAX_POINTS

    # limpiar input si se marcó la bandera en el ciclo anterior
    if ss.get("prof_clear_search_once"):
        # importante: establecer el valor ANTES de instanciar el widget
        ss["prof_text_input_field"] = ""
        ss["prof_clear_search_once"] = False

    # Estilo visual del input/botones
    st.markdown(
        """
        <style>
        /* Input */
        div[data-baseweb="input"] > div {
            background-color: #fafafa !important;
            border-radius: 10px !important;
            border: 1px solid #D9D9D9 !important;
            transition: all .2s ease;
        }
        div[data-baseweb="input"]:focus-within > div {
            border-color: #4C9AFF !important;
            box-shadow: 0 0 6px rgba(76,154,255,.25) !important;
        }
        /* Botón primario más suave */
        button[kind="primary"]{
            background:#ff6b6b !important;
            border:none !important;
        }
        button[kind="primary"]:hover{
            background:#e15a5a !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Usamos un form para que Enter dispare "Añadir"
    with st.form("prof_add_form", clear_on_submit=False):
        cols = st.columns([2.2, 1, 1])
        with cols[0]:
            value = st.text_input(
                "Buscar dirección…",
                key="prof_text_input_field",
                label_visibility="collapsed",
                placeholder=f"Escribe la dirección (mín. 3 letras). Límite: {MAX_POINTS} puntos.",
                disabled=is_limit,
            )
        with cols[1]:
            add = st.form_submit_button("Añadir", type="primary", use_container_width=True, disabled=is_limit)
        with cols[2]:
            clear = st.form_submit_button("Limpiar", use_container_width=True)

    if add and value and len(value.strip()) >= 3:
        _add_point_from_value(value)

    if clear:
        ss["prof_points"] = []
        _clear_selection()


# -------------------------------
# Fila visual + barra acciones
# -------------------------------
def _row_container(label: str, selected: bool):
    """Caja visual de cada fila (solo decoración)."""
    styles = {
        "border": "#4C9AFF" if selected else "#e5e5e5",
        "bg": "#E9F2FF" if selected else "#fbfbfb",
        "color": "#1f2d3d" if selected else "#333",
    }
    st.markdown(
        f"""
        <div style="
            width:100%;
            text-align:left;
            padding:12px;
            border-radius:10px;
            border:1px solid {styles['border']};
            background:{styles['bg']};
            color:{styles['color']};
            font-size:15px;
            margin-bottom:8px;
        ">{label}</div>
        """,
        unsafe_allow_html=True,
    )


def _row_toolbar(i: int):
    """Barra de acciones mostrada debajo del punto seleccionado."""
    ss = st.session_state
    pts = ss["prof_points"]
    is_editing = ss.get("is_editing_point", False)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.button("⬆️ Subir", key=f"up_{i}", on_click=_move_point, args=("up", i),
                  use_container_width=True, disabled=(i == 0))
    with c2:
        st.button("⬇️ Bajar", key=f"down_{i}", on_click=_move_point, args=("down", i),
                  use_container_width=True, disabled=(i == len(pts) - 1))
    with c3:
        if is_editing:
            st.button("💾 Guardar", key=f"save_{i}", on_click=_save_point_from_toolbar,
                      args=(i,), use_container_width=True, type="primary")
        else:
            st.button("✏️ Editar", key=f"edit_{i}", on_click=_enter_edit_mode,
                      args=(i,), use_container_width=True)
    with c4:
        if is_editing:
            st.button("❌ Cancelar", key=f"cancel_{i}", on_click=_clear_selection,
                      use_container_width=True)
        else:
            st.button("🗑️ Eliminar", key=f"del_{i}", on_click=_delete_point,
                      args=(i,), use_container_width=True)

    if is_editing:
        st.text_input(
            "Modificar dirección:",
            value=ss["edit_input_value"],
            key="edit_input_value",
            label_visibility="collapsed",
            on_change=_save_point_from_toolbar,
            args=(i,),
        )
    st.markdown("")  # respiro


# -------------------------------
# Pantalla principal
# -------------------------------
def mostrar_profesional():
    initialize_session_state()
    ss = st.session_state

    st.header("Ruta de trabajo")

    # Zona superior: buscador + selectores
    col_search, col_mode, col_avoid = st.columns([2.5, 1, 1])
    with col_search:
        _search_box()
    with col_mode:
        st.selectbox("Tipo de ruta", ["Más rápido", "Más corto"],
                     key="prof_mode", label_visibility="visible")
    with col_avoid:
        st.selectbox("Evitar", ["Ninguno", "Peajes", "Ferries"],
                     key="prof_avoid", label_visibility="visible")

    # Lista
    pts = ss["prof_points"]
    st.subheader(f"Puntos de la ruta ({len(pts)} de {MAX_POINTS} añadidos)")

    if not pts:
        st.info("Agrega al menos dos puntos (origen y destino) para generar la ruta.")
        return

    # Radio compacto para SELECCIÓN
    radio_labels = [f"{i+1}: {p}" for i, p in enumerate(pts)]

    # index=None permite que al cargar no haya seleccionado
    try:
        selected_label = st.radio(
            label="Selecciona un punto",
            options=radio_labels,
            index=(ss["selected_point_index"] if ss["selected_point_index"] is not None else None),
            key="prof_radio_select",
            label_visibility="collapsed",
        )
    except TypeError:
        # Si la versión de Streamlit no soporta index=None,
        # forzamos -1 como “ninguno” con un placeholder arriba
        radio_labels_fallback = ["— (ninguno) —"] + radio_labels
        idx = 0 if ss["selected_point_index"] is None else ss["selected_point_index"] + 1
        selected_label_fb = st.radio(
            label="Selecciona un punto",
            options=radio_labels_fallback,
            index=idx,
            key="prof_radio_select",
            label_visibility="collapsed",
        )
        selected_label = None if selected_label_fb == "— (ninguno) —" else selected_label_fb

    # Resolver índice seleccionado y guardarlo
    selected_index = None
    if selected_label is not None:
        try:
            selected_index = radio_labels.index(selected_label)
        except ValueError:
            selected_index = None

    if ss.get("selected_point_index") != selected_index:
        ss["selected_point_index"] = selected_index
        _rerun()  # para reinsertar la barra justo debajo del punto activo

    # Pintamos la lista “bonita” e insertamos la barra justo debajo del seleccionado
    for i, p in enumerate(pts):
        _row_container(f"{i+1}: {p}", selected=(selected_index == i))
        if selected_index == i:
            _row_toolbar(i)

    # Generar ruta
    st.markdown("---")
    if st.button("Generar ruta profesional", type="primary", key="prof_generate_btn"):
        if len(pts) < 2:
            st.warning("Deben haber dos o más puntos (origen y destino).")
            return
        if gmaps is None:
            st.error("ERROR: No se pudo conectar con la API de Google Maps. Revisa tu clave en secrets.toml.")
            return

        origen_label = pts[0]
        destino_label = pts[-1]
        waypoints_labels = pts[1:-1]

        origen_meta = resolve_selection(origen_label, None)
        destino_meta = resolve_selection(destino_label, None)
        waypoints_resolved = [resolve_selection(w, None).get("address", w) for w in waypoints_labels]

        avoid_map = {"Peajes": "tolls", "Ferries": "ferries", "Ninguno": None}

        gmaps_url = build_gmaps_url(
            origin=origen_meta.get("address", origen_label),
            destination=destino_meta.get("address", destino_label),
            waypoints=waypoints_resolved,
            mode="driving",
            avoid=avoid_map.get(ss["prof_avoid"]),
            optimize=True,
        )
        waze_url = build_waze_url(
            origen_meta.get("address", origen_label),
            destino_meta.get("address", destino_label),
        )
        apple_url = build_apple_maps_url(
            origen_meta.get("address", origen_label),
            destino_meta.get("address", destino_label),
        )

        st.success("¡Ruta generada correctamente! 👇")
        c1, c2, c3 = st.columns(3)
        with c1:
            if gmaps_url:
                st.link_button("🗺️ Ver en Google Maps", gmaps_url, use_container_width=True)
        with c2:
            if waze_url:
                st.link_button("🚗 Ver en Waze", waze_url, use_container_width=True)
        with c3:
            if apple_url:
                st.link_button("🍎 Ver en Apple Maps", apple_url, use_container_width=True)