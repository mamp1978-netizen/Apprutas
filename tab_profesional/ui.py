# tab_profesional/ui.py
import io
import json
from pathlib import Path
from typing import List

import streamlit as st
import qrcode

from app_utils_core import (
    build_gmaps_url,         # firma sin "optimize"
    build_waze_url,
    build_apple_maps_url,
    resolve_selection,
)

ROUTES_DB = Path(".streamlit/routes.json")
ROUTES_DB.parent.mkdir(parents=True, exist_ok=True)

MAX_POINTS = 10


# ---------------------------
# Estado
# ---------------------------
def _init_state():
    ss = st.session_state
    ss.setdefault("prof_points", [])
    ss.setdefault("prof_text_input", "")
    ss.setdefault("route_name_input", "")
    ss.setdefault("saved_choice", "")
    ss.setdefault("saved_routes", _load_routes_file())
    ss.setdefault("open_target", "Navegador")
    ss.setdefault("last_gmaps_url", None)
    ss.setdefault("list_version", 0)       # <- fuerza refresco visual de la lista
    ss.setdefault("ow_pending", None)      # <- nombre pendiente de sobrescritura


def _load_routes_file():
    try:
        if ROUTES_DB.exists():
            return json.loads(ROUTES_DB.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _persist_routes_file():
    try:
        ROUTES_DB.write_text(
            json.dumps(st.session_state["saved_routes"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _bump_list_version():
    st.session_state["list_version"] += 1


# ---------------------------
# Acciones lista
# ---------------------------
def _add_point(val: str):
    ss = st.session_state
    val = (val or "").strip()
    if not val:
        return
    if len(ss["prof_points"]) >= MAX_POINTS:
        st.warning(f"Límite de {MAX_POINTS} puntos.")
        return
    ss["prof_points"].append(val)
    if "prof_text_input" in ss:
        del ss["prof_text_input"]
    _bump_list_version()
    st.rerun()


def _clear_points():
    ss = st.session_state
    ss["prof_points"] = []
    ss["last_gmaps_url"] = None
    if "prof_text_input" in ss:
        del ss["prof_text_input"]
    _bump_list_version()
    st.rerun()


def _move_point_up(i: int):
    pts = st.session_state["prof_points"]
    if i > 0:
        pts[i-1], pts[i] = pts[i], pts[i-1]
        _bump_list_version()
    st.rerun()


def _move_point_down(i: int):
    pts = st.session_state["prof_points"]
    if i < len(pts) - 1:
        pts[i+1], pts[i] = pts[i], pts[i+1]
        _bump_list_version()
    st.rerun()


def _delete_point(i: int):
    pts = st.session_state["prof_points"]
    if 0 <= i < len(pts):
        pts.pop(i)
        _bump_list_version()
    st.rerun()


# ---------------------------
# Guardar / cargar (con sobrescritura)
# ---------------------------
def _save_current_route():
    ss = st.session_state
    name = (ss.get("route_name_input") or "").strip()
    if not name:
        st.warning("Pon un nombre para guardar la ruta.")
        return
    if len(ss["prof_points"]) < 1:
        st.warning("No hay puntos para guardar.")
        return

    if name in ss["saved_routes"] and ss.get("ow_pending") != name:
        ss["ow_pending"] = name
        st.rerun()
        return

    ss["saved_routes"][name] = list(ss["prof_points"])
    _persist_routes_file()
    ss["saved_choice"] = name
    ss["ow_pending"] = None
    st.success("Ruta guardada ✅")


def _confirm_overwrite(ok: bool):
    ss = st.session_state
    name = ss.get("ow_pending")
    if not name:
        return
    if ok:
        ss["saved_routes"][name] = list(ss["prof_points"])
        _persist_routes_file()
        ss["saved_choice"] = name
        st.success("Ruta sobrescrita ✅")
    ss["ow_pending"] = None
    st.rerun()


def _load_route(name: str):
    ss = st.session_state
    if not name:
        return
    data = ss["saved_routes"].get(name)
    if data is None:
        st.warning("Ruta no encontrada.")
        return
    ss["prof_points"] = list(data)
    ss["route_name_input"] = name
    _bump_list_version()
    st.rerun()


def _delete_saved_route(name: str):
    ss = st.session_state
    if name and name in ss["saved_routes"]:
        del ss["saved_routes"][name]
        _persist_routes_file()
        ss["saved_choice"] = ""
        st.success("Ruta borrada 🗑️")
        st.rerun()


# ---------------------------
# QR helper
# ---------------------------
def _qr_image_for(url: str):
    qr = qrcode.QRCode(version=2, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ---------------------------
# Columnas
# ---------------------------
def _search_col():
    st.subheader("Añade puntos")
    with st.form("add_form", clear_on_submit=False):
        st.text_input(
            "Escribe dirección (mín. 3 letras).",
            key="prof_text_input",
            placeholder="p. ej. Passeig de Gràcia 1, Barcelona",
        )
        submitted = st.form_submit_button("Añadir", type="primary", use_container_width=True)
    if submitted:
        _add_point(st.session_state.get("prof_text_input"))


def _list_col():
    st.subheader(f"Puntos ({len(st.session_state['prof_points'])}/{MAX_POINTS})  🔁")
    pts: List[str] = st.session_state["prof_points"]
    if not pts:
        st.info("Añade al menos dos puntos (origen y destino).")
    else:
        ver = st.session_state["list_version"]
        for i, p in enumerate(pts):
            row = st.columns([8,1,1,1])
            with row[0]:
                st.text_input(
                    "",
                    value=p,
                    key=f"pt_{ver}_{i}",   # <- cambia al mover => se refresca
                    disabled=True,
                    label_visibility="collapsed",
                )
            with row[1]:
                st.button("✖", key=f"del_{ver}_{i}", on_click=_delete_point, args=(i,), use_container_width=True)
            with row[2]:
                st.button("▲", key=f"up_{ver}_{i}", on_click=_move_point_up, args=(i,), use_container_width=True,
                          disabled=(i==0))
            with row[3]:
                st.button("▼", key=f"dn_{ver}_{i}", on_click=_move_point_down, args=(i,), use_container_width=True,
                          disabled=(i==len(pts)-1))

    # Limpiar debajo de la lista
    st.button("Limpiar ruta", on_click=_clear_points, use_container_width=True)


def _save_load_col():
    st.subheader("Guardar / Cargar")
    st.text_input("Nombre para guardar", key="route_name_input", placeholder="p. ej. Lunes")
    st.selectbox("Rutas guardadas",
                 options=[""] + sorted(st.session_state["saved_routes"].keys()),
                 key="saved_choice")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.button("💾 Guardar", on_click=_save_current_route, use_container_width=True)
    with c2:
        st.button("📥 Cargar",
                  on_click=lambda: _load_route(st.session_state.get("saved_choice")),
                  use_container_width=True,
                  disabled=not st.session_state.get("saved_choice"))
    with c3:
        st.button("🗑️ Borrar",
                  on_click=lambda: _delete_saved_route(st.session_state.get("saved_choice")),
                  use_container_width=True,
                  disabled=not st.session_state.get("saved_choice"))

    # Aviso de sobrescritura (si aplica)
    if st.session_state.get("ow_pending"):
        st.warning(f"La ruta «{st.session_state['ow_pending']}» ya existe. ¿Sobrescribir?")
        cA, cB = st.columns(2)
        with cA:
            st.button("✅ Sí, sobrescribir", on_click=_confirm_overwrite, args=(True,), use_container_width=True)
        with cB:
            st.button("❌ Cancelar", on_click=_confirm_overwrite, args=(False,), use_container_width=True)


# ---------------------------
# Generar y salidas
# ---------------------------
def _build_and_show_outputs():
    ss = st.session_state
    pts = ss["prof_points"]
    if len(pts) < 2:
        st.warning("Añade origen y destino (mínimo 2 puntos).")
        return

    o_text = pts[0]
    d_text = pts[-1]
    w_texts = pts[1:-1]

    o_meta = resolve_selection(o_text, None)
    d_meta = resolve_selection(d_text, None)
    waypoints_resolved = [resolve_selection(w, None).get("address", w) for w in w_texts]

    gmaps_web = build_gmaps_url(
        origin=o_meta.get("address", o_text),
        destination=d_meta.get("address", d_text),
        waypoints=waypoints_resolved if waypoints_resolved else None,
    )
    ss["last_gmaps_url"] = gmaps_web

    waze = build_waze_url(o_meta.get("address", o_text), d_meta.get("address", d_text))
    apple = build_apple_maps_url(o_meta.get("address", o_text), d_meta.get("address", d_text))

    st.success("Ruta generada. Elige cómo abrirla 👇")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.link_button("🌐 Maps (Web)", gmaps_web, use_container_width=True)
    with c2:
        st.link_button("📱 Maps (App)", gmaps_web, use_container_width=True)
    with c3:
        st.link_button("🚗 Waze", waze, use_container_width=True)
    with c4:
        st.link_button("🍎 Apple", apple, use_container_width=True)

    st.markdown("---")
    st.caption("Escanea el QR (Google Maps)")
    if ss["last_gmaps_url"]:
        img_buf = _qr_image_for(ss["last_gmaps_url"])
        st.image(img_buf, caption="QR", width=220)


# ---------------------------
# Entrada principal
# ---------------------------
def mostrar_profesional():
    _init_state()

    st.header("🧭 Planificador de Rutas")

    # 3 columnas: Buscar / Lista / Guardar
    c1, c2, c3 = st.columns([4,5,3])
    with c1: _search_col()
    with c2: _list_col()
    with c3: _save_load_col()

    st.markdown("---")
    if st.button("Generar ruta profesional", type="primary", use_container_width=True):
        _build_and_show_outputs()
