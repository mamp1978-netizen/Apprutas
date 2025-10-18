# app_utils.py — reemplazar estas funciones

from urllib.parse import quote_plus
import os, requests, streamlit as st

REQUEST_TIMEOUT = 8

def provider_google_autocomplete(query: str, max_results: int = 8, *, country="ES", location_bias=None):
    """
    Devuelve [(label, meta), ...] desde Places Autocomplete.
    Añade components=country:ES y locationbias si se proporciona.
    También guarda en session_state un diagnóstico con status y error_message.
    """
    key = os.getenv("GOOGLE_PLACES_API_KEY") or (st.secrets.get("GOOGLE_PLACES_API_KEY") if hasattr(st, "secrets") else None)
    if not key or not query:
        # guarda diag básico
        st.session_state["_suggest_diag"] = {"q": query, "g": 0, "s": 0, "n": 0, "g_status": "NO_KEY"}
        return []

    try:
        base = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = [
            f"input={quote_plus(query)}",
            "types=geocode",                # centrado en direcciones
            f"language=es",
            f"components=country:{country}",
            f"key={key}"
        ]
        # location bias opcional (ej. "circle:50000@41.39,2.17")
        if location_bias:
            params.append(f"locationbias={quote_plus(location_bias)}")

        url = f"{base}?{'&'.join(params)}"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        status = data.get("status", "")
        err = data.get("error_message", "")
        preds = data.get("predictions", []) or []

        # guarda diagnóstico SIEMPRE
        st.session_state["_suggest_diag"] = {
            "q": query, "g": len(preds), "s": 0, "n": 0,
            "g_status": status, "err": err
        }

        if status != "OK":
            return []

        out = []
        for p in preds[:max_results]:
            desc = p.get("description")
            pid = p.get("place_id")
            if desc and pid:
                out.append((desc, {"provider": "google", "place_id": pid, "desc": desc}))
        return out
    except Exception as e:
        st.session_state["_suggest_diag"] = {"q": query, "g": 0, "s": 0, "n": 0, "g_status": "EXC", "err": str(e)}
        return []


def suggest_addresses(query: str, key_bucket: str):
    """
    Orquesta proveedores. Primero Google (mejor para números de portal).
    Siempre escribe diagnóstico en la barra lateral (counts y status).
    """
    q = (query or "").strip()
    if len(q) < 2:
        st.session_state["_suggest_diag"] = {"q": q, "g": 0, "s": 0, "n": 0, "g_status": "SHORT"}
        return []

    # location bias opcional: si tienes ciudad aprox guardada, úsala.
    # Ejemplo: círculo 50 km sobre Barcelona (lat,lon).
    # Pon None si no quieres bias.
    location_bias = st.session_state.get("prof_location_bias")  # ej. "circle:50000@41.39,2.17"

    g = provider_google_autocomplete(q, max_results=8, country="ES", location_bias=location_bias)

    # si Google no devuelve nada, podrías probar SerpAPI u OSM aquí
    s, n = [], []  # (omitidos por ahora para simplificar)

    # compacta diagnóstico (ya se escribió en provider_google_autocomplete)
    diag = st.session_state.get("_suggest_diag", {}) or {}
    # pinta mini-diagnóstico en la barra lateral SIEMPRE
    with st.sidebar:
        st.caption(f'Q="{diag.get("q","")}" | Google:{diag.get("g",0)} Serp:{diag.get("s",0)} OSM:{diag.get("n",0)} · status={diag.get("g_status","")}')
        if diag.get("err"):
            st.warning(diag["err"])

    results = g or s or n or []
    if not results:
        return []

    # guarda meta en el bucket para resolve_selection
    if "suggest_maps" not in st.session_state:
        st.session_state["suggest_maps"] = {}
    bucket = st.session_state["suggest_maps"].setdefault(key_bucket, {})
    labels = []
    for label, meta in results:
        bucket[label] = meta
        labels.append(label)
    return labels