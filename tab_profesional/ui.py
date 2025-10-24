# tab_profesional/ui.py
import streamlit as st

from app_utils_core import (
    suggest_addresses,
    resolve_selection,
    build_gmaps_url,
    build_waze_url,
    build_apple_maps_url,
    gmaps,  # cliente Google Maps (o None si no hay API key)
)

# --- Constantes ---
MAX_POINTS = 10  # 1 Origen + 8 Paradas + 1 Destino


# -------------------------------
# INICIALIZACIÓN DEL ESTADO
# -------------------------------
def initialize_session_state():
    if "prof_points" not in st.session_state:
        st.session_state["prof_points"] = []
    if "selected_point_index" not in st.session_state:
        st.session_state["selected_point_index"] = 0
    if "is_editing_point" not in st.session_state:
        st.session_state["is_editing_point"] = False
    if "edit_input_value" not in st.session_state:
        st.session_state["edit_input_value"] = ""
    if "prof_text_input" not in st.session_state:
        st.session_state["prof_text_input"] = ""
    if "prof_top_suggestions" not in st.session_state:
        st.session_state["prof_top_suggestions"] = []
    if "prof_selection" not in st.session_state:
        st.session_state["prof_selection"] = ""
    if "prof_last_route_url" not in st.session_state:
        st.session_state["prof_last_route_url"] = None
    if "prof_mode" not in st.session_state:
        st.session_state["prof_mode"] = "Más rápido"
    if "prof_avoid" not in st.session_state:
        st.session_state["prof_avoid"] = "Ninguno"


# -------------------------------
# UTILIDADES DE ESTADO
# -------------------------------
def _force_rerun_with_clear():
    st.rerun()


def _reset_point_selection():
    st.session_state["is_editing_point"] = False
    st.session_state["edit_input_value"] = ""
    pts = st.session_state["prof_points"]
    if pts:
        i = st.session_state["selected_point_index"]
        st.session_state["selected_point_index"] = max(0, min(i, len(pts) - 1))
    else:
        st.session_state["selected_point_index"] = 0
    _force_rerun_with_clear()


def _add_point_from_ui():
    if len(st.session_state["prof_points"]) >= MAX_POINTS:
        return

    value = ""
    if st.session_state.get("prof_top_suggestions"):
        value = st.session_state.get("prof_selection", "")
    else:
        value = st.session_state.get("prof_text_input", "")

    value = (value or "").strip()
    if not value:
        st.warning("Escribe o selecciona una dirección válida.")
        return

    st.session_state["prof_points"].append(value)
    st.success(f"Añadido: {value}")

    st.session_state["prof_text_input"] = ""
    st.session_state["prof_top_suggestions"] = []
    st.session_state["prof_selection"] = ""
    st.session_state["selected_point_index"] = len(st.session_state["prof_points"]) - 1
    _reset_point_selection()


def _clear_points():
    st.session_state["prof_points"] = []
    st.session_state["prof_last_route_url"] = None
    st.session_state["prof_text_input"] = ""
    st.session_state["prof_top_suggestions"] = []
    st.session_state["prof_selection"] = ""
    st.session_state["selected_point_index"] = 0
    st.session_state["is_editing_point"] = False
    st.session_state["edit_input_value"] = ""
    _force_rerun_with_clear()


def _select_point(index: int):
    st.session_state["selected_point_index"] = index
    if st.session_state["is_editing_point"]:
        _reset_point_selection()
    else:
        _force_rerun_with_clear()


def _move_point(direction: str):
    i = st.session_state["selected_point_index"]
    pts = st.session_state["prof_points"]
    if direction == "up" and i > 0:
        pts.insert(i - 1, pts.pop(i))
        st.session_state["selected_point_index"] = i - 1
    elif direction == "down" and i < len(pts) - 1:
        pts.insert(i + 1, pts.pop(i))
        st.session_state["selected_point_index"] = i + 1
    _reset_point_selection()


def _delete_point():
    i = st.session_state["selected_point_index"]
    pts = st.session_state["prof_points"]
    if 0 <= i < len(pts):
        pts.pop(i)
    _reset_point_selection()


def _enter_edit_mode():
    i = st.session_state["selected_point_index"]
    pts = st.session_state["prof_points"]
    if 0 <= i < len(pts):
        st.session_state["is_editing_point"] = True
        st.session_state["edit_input_value"] = pts[i]
    _force_rerun_with_clear()


def _save_point_from_toolbar():
    new_value = st.session_state["edit_input_value"].strip()
    i = st.session_state["selected_point_index"]
    pts = st.session_state["prof_points"]
    if new_value and len(new_value) >= 3 and 0 <= i < len(pts):
        pts[i] = new_value
        st.success(f"Punto actualizado a: {new_value}")
        _reset_point_selection()
    else:
        st.warning("La dirección no puede estar vacía y debe tener al menos 3 letras.")


def _run_search():
    term = st.session_state.get("prof_text_input", "").strip()
    if len(term) >= 3:
        suggestions = suggest_addresses(term, min_len=3, max_results=8)
        st.session_state["prof_top_suggestions"] = suggestions
        st.session_state["prof_selection"] = suggestions[0]["description"] if suggestions else ""
    else:
        st.session_state["prof_top_suggestions"] = []
        st.session_state["prof_selection"] = ""


# -------------------------------
# SEARCH BOX
# -------------------------------
def _search_box():
    st.markdown("---")

    is_limit_reached = len(st.session_state.get("prof_points", [])) >= MAX_POINTS

    st.text_input(
        "Buscar dirección...",
        key="prof_text_input",
        label_visibility="collapsed",
        placeholder=f"Escribe la dirección (mín. 3 letras). Límite: {MAX_POINTS} puntos.",
        on_change=_run_search,
        disabled=is_limit_reached,
    )

    suggestions = st.session_state.get("prof_top_suggestions", [])
    if suggestions:
        st.selectbox(
            "Selecciona la sugerencia más precisa:",
            options=[s["description"] for s in suggestions],
            key="prof_selection",
            label_visibility="visible",
        )

    col_add, col_clear = st.columns([1.5, 1])
    with col_add:
        st.button(
            "Añadir",
            on_click=_add_point_from_ui,
            type="primary",
            key="prof_add_btn",
            use_container_width=True,
            disabled=is_limit_reached,
        )
    with col_clear:
        st.button("Limpiar", on_click=_clear_points, key="prof_clear_btn", use_container_width=True)

    st.markdown("---")


# -------------------------------
# UI PRINCIPAL
# -------------------------------
def mostrar_profesional():
    initialize_session_state()
    st.header("Ruta de trabajo")

    # Opciones de ruta
    col_mode, col_avoid = st.columns([1, 1])
    with col_mode:
        st.selectbox("Tipo de ruta", ["Más rápido", "Más corto"], key="prof_mode", label_visibility="visible")
    with col_avoid:
        st.selectbox("Evitar", ["Ninguno", "Peajes", "Ferries"], key="prof_avoid", label_visibility="visible")

    # Buscador
    _search_box()

    # Lista de puntos
    pts = st.session_state["prof_points"]
    pts_count = len(pts)
    st.subheader(f"Puntos de la ruta ({pts_count} de {MAX_POINTS} añadidos)")

    if pts_count == 0:
        st.info("Agrega al menos dos puntos (origen y destino) para generar la ruta.")
        return

    current_index = st.session_state["selected_point_index"]
    is_editing = st.session_state["is_editing_point"]

    st.markdown("---")
    for i, p in enumerate(pts):
        prefix = "Origen" if i == 0 else ("Destino" if i == len(pts) - 1 else f"Parada #{i}")
        display_text = f"**{prefix}**: {p}"

        col_select, col_text = st.columns([0.5, 4])
        is_selected = (i == current_index)

        with col_select:
            btn_label = "📍" if is_selected else " "
            btn_type = "primary" if is_selected else "secondary"
            st.button(
                btn_label,
                key=f"select_point_{i}",
                on_click=_select_point,
                args=(i,),
                use_container_width=True,
                type=btn_type,
                help="Selecciona este punto para moverlo, editarlo o eliminarlo.",
            )

        with col_text:
            bg_color = "#E6F7FF" if is_selected else "transparent"
            st.markdown(
                f"""
                <div style='background-color: {bg_color}; padding: 10px; border-radius: 5px; margin-left: -15px;'>
                    {display_text}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Barra de herramientas
    st.markdown(f"**Punto Activo:** {current_index + 1} de {len(pts)}")
    col_up, col_down, col_edit, col_del = st.columns(4)

    with col_up:
        if current_index > 0 and not is_editing:
            st.button("⬆️", key="btn_up", on_click=_move_point, args=("up",), use_container_width=True)
    with col_down:
        if current_index < len(pts) - 1 and not is_editing:
            st.button("⬇️", key="btn_down", on_click=_move_point, args=("down",), use_container_width=True)
    with col_edit:
        if is_editing:
            st.button("💾", key="btn_save", on_click=_save_point_from_toolbar, use_container_width=True, type="primary")
        else:
            st.button("✏️", key="btn_edit", on_click=_enter_edit_mode, use_container_width=True)
    with col_del:
        if not is_editing:
            st.button("🗑️", key="btn_delete", on_click=_delete_point, use_container_width=True)
        else:
            st.button("❌", key="btn_cancel", on_click=_reset_point_selection, use_container_width=True)

    # Campo de edición
    if is_editing:
        st.text_input(
            f"Modificar punto seleccionado (Índice {current_index + 1}):",
            value=st.session_state["edit_input_value"],
            key="edit_input_value",
            label_visibility="visible",
            on_change=_save_point_from_toolbar,
        )
        st.markdown("---")

    # Generar ruta
    st.markdown("---")
    if st.button("Generar ruta profesional", type="primary", key="prof_generate_btn"):
        if len(pts) < 2:
            st.warning("Deben haber dos o más puntos (origen y destino).")
            return

        if gmaps is None:
            st.error("ERROR CRÍTICO: No se pudo conectar con la API de Google Maps. Revisa tu clave en secrets.toml.")
            return

        origen_label = pts[0]
        destino_label = pts[-1]
        waypoints_labels = pts[1:-1]

        # Resuelve direcciones
        origen_meta = resolve_selection(origen_label, None)
        destino_meta = resolve_selection(destino_label, None)
        waypoints_resolved = [
            resolve_selection(label, None).get("address", label) for label in waypoints_labels
        ]

        # Evitar peajes/ferries (Google Maps)
        avoid_map = {"Peajes": "tolls", "Ferries": "ferries", "Ninguno": None}

        gmaps_url = build_gmaps_url(
            origin=origen_meta.get("address", origen_label),
            destination=destino_meta.get("address", destino_label),
            waypoints=waypoints_resolved,
            mode="driving",
            avoid=avoid_map.get(st.session_state["prof_avoid"]),
            optimize=True,
        )

        # Waze y Apple Maps no aceptan waypoints en nuestras utilidades
        waze_url = build_waze_url(
            origen_meta.get("address", origen_label),
            destino_meta.get("address", destino_label),
        )
        apple_url = build_apple_maps_url(
            origen_meta.get("address", origen_label),
            destino_meta.get("address", destino_label),
        )

        st.session_state["prof_last_route_url"] = gmaps_url

        st.success("¡Ruta generada correctamente! 👇")
        col_gmaps, col_waze, col_apple = st.columns(3)
        with col_gmaps:
            if gmaps_url:
                st.link_button("🗺️ Google Maps", gmaps_url)
        with col_waze:
            if waze_url:
                st.link_button("🚗 Waze", waze_url)
        with col_apple:
            if apple_url:
                st.link_button("🍎 Apple Maps", apple_url)