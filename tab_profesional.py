# tab_profesional.py
import streamlit as st
import requests
from app_utils import suggest_addresses, resolve_selection, build_gmaps_url, make_qr

# ------------------------------
# Utilidades
# ------------------------------

def _ip_location_city() -> str | None:
    """Devuelve una ciudad aproximada por IP (solo para sesgo humano en UI)."""
    try:
        r = requests.get("https://ipapi.co/json/", timeout=6)
        r.raise_for_status()
        j = r.json()
        parts = [j.get("city") or "", j.get("region") or "", j.get("country_name") or ""]
        city = ", ".join([p for p in parts if p])
        return city or None
    except Exception:
        return None


def _remove_point(idx: int, t: dict):
    if 0 <= idx < len(st.session_state.prof_points):
        removed = st.session_state.prof_points.pop(idx)
        st.info(t.get("removed", "Eliminado: {x}").format(x=removed))


def _move_point(idx: int, direction: str):
    pts = st.session_state.prof_points
    if direction == "up" and idx > 0:
        pts[idx - 1], pts[idx] = pts[idx], pts[idx - 1]
    elif direction == "down" and idx < len(pts) - 1:
        pts[idx + 1], pts[idx] = pts[idx], pts[idx + 1]


def _add_point(value: str | None, t: dict):
    value = (value or "").strip()
    if not value:
        st.warning(t.get("type_or_select", "Escribe o elige una sugerencia."))
        return
    st.session_state.prof_points.append(value)
    st.success(t.get("added", "Añadido: {x}").format(x=value))


def _add_point_from_location(t: dict):
    guess = _ip_location_city()
    if guess:
        st.session_state.prof_last_location_guess = guess
        st.session_state.prof_points.append(guess)
        st.success(t.get("loc_added", "Añadido (aprox. por IP): {x}").format(x=guess))
    else:
        st.warning(t.get("loc_failed", "No se pudo estimar tu ubicación."))


def _init_state():
    ss = st.session_state
    ss.setdefault("prof_points", [])
    ss.setdefault("prof_last_route_url", None)
    ss.setdefault("prof_open_check", False)
    ss.setdefault("prof_last_location_guess", "")
    ss.setdefault("prof_route_type", None)
    # Estado del buscador en vivo
    ss.setdefault("prof_top_q", "")
    ss.setdefault("prof_suggestions", [])
    ss.setdefault("prof_selected_label", "")
    ss.setdefault("prof_needs_clear", False)
    # Sesgo de ubicación (texto informativo)
    ss.setdefault("prof_location_bias", _ip_location_city() or "")


# ------------------------------
# Autocompletado en vivo
# ------------------------------

def _refresh_suggestions(t: dict):
    """
    Regenera la lista de sugerencias en función del texto que el usuario va escribiendo.
    """
    q = (st.session_state.get("prof_top_q") or "").strip()
    if len(q) < 3:
        st.session_state.prof_suggestions = []
        return

    # Llamamos a nuestro proveedor unificado (Google/SerpAPI/Nominatim).
    # app_utils.suggest_addresses guarda la meta en el bucket 'prof_top'
    try:
        labels = suggest_addresses(q, "prof_top")
    except Exception:
        labels = []

    # Si no hay nada, vaciamos
    st.session_state.prof_suggestions = labels or []


def _enter_add_handler(t: dict):
    """
    Callback al pulsar ENTER en el input o al hacer clic en 'Añadir'.
    IMPORTANTE: no modificar el propio text_input aquí (para evitar la StreamlitAPIException).
    """
    sel = st.session_state.get("prof_selected_label", "") or ""
    sugs = st.session_state.get("prof_suggestions", []) or []
    q = (st.session_state.get("prof_top_q") or "").strip()

    if not (sel or sugs or q):
        st.warning(t.get("type_or_select", "Escribe o elige una sugerencia."))
        return

    # 1) prioridad a una sugerencia seleccionada
    # 2) luego la primera sugerencia
    # 3) finalmente el texto literal
    candidate = sel or (sugs[0] if sugs else q)
    _add_point(candidate, t)

    # Marcamos limpieza diferida (se hará al próximo render)
    st.session_state.prof_needs_clear = True


def search_and_add_top(t: dict):
    # Limpiamos tras un alta anterior (sin tocar el input dentro del callback)
    if st.session_state.get("prof_needs_clear", False):
        st.session_state.prof_top_q = ""
        st.session_state.prof_suggestions = []
        st.session_state.prof_selected_label = ""
        st.session_state.prof_needs_clear = False

    # Input principal (re-renderiza en cada cambio)
    st.text_input(
        label=t.get("search_label", "Buscar dirección… (pulsa ENTER para añadir)"),
        key="prof_top_q",
        placeholder="Calle, número, ciudad… / Street, number, city…",
        on_change=_enter_add_handler,  # ENTER en el input
        args=(t,),
    )

    # Refrescamos sugerencias cada render
    _refresh_suggestions(t)

    sugs = st.session_state.get("prof_suggestions", []) or []
    if sugs:
        st.caption(t.get("suggestions", "Sugerencias:"))
        st.radio(
            label=t.get("select_suggestion", "Elige una sugerencia"),
            options=sugs,
            key="prof_selected_label",
        )
    else:
        st.caption(t.get("no_suggestions", "Sin sugerencias todavía"))

    c1, c2 = st.columns([0.5, 0.5])
    with c1:
        if st.button(t.get("add_enter", "Añadir (ENTER)")):
            _enter_add_handler(t)
    with c2:
        if st.button(t.get("use_my_location", "📍 Usar mi ubicación")):
            _add_point_from_location(t)


# ----------------