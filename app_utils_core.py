import urllib.parse

# ---------------------------------------------------------------------------
# Autocompletado / resolución simulada (puedes enganchar tu API real si quieres)
# ---------------------------------------------------------------------------
def suggest_addresses(query, min_len=3, max_results=8):
    if not query or len(query.strip()) < min_len:
        return []
    return [{"description": query.strip()}]

def resolve_selection(label, meta=None):
    return {"address": (label or "").strip()}

# ---------------------------------------------------------------------------
# Construcción de URLs Google / Waze / Apple
#   - SIN "optimize:true"
#   - Waypoints codificados y separados por %7C (NO '|')
# ---------------------------------------------------------------------------
def _encode(s: str) -> str:
    return urllib.parse.quote_plus(s or "")

def _join_waypoints(wps):
    enc = [_encode(w.strip()) for w in (wps or []) if (w or "").strip()]
    # Para QR y enlaces fiables, usa '%7C' entre waypoints (no '|')
    return "%7C".join(enc) if enc else ""

def build_gmaps_url(origin, destination, waypoints=None, mode="driving", avoid=None):
    """
    URL web estándar que entiende el móvil, el navegador y el QR.
    https://www.google.com/maps/dir/?api=1&origin=...&destination=...&travelmode=driving&waypoints=wp1%7Cwp2
    """
    params = [
        "api=1",
        f"origin={_encode(origin)}",
        f"destination={_encode(destination)}",
        f"travelmode={_encode(mode)}",
    ]
    wp = _join_waypoints(waypoints)
    if wp:
        params.append(f"waypoints={wp}")
    if avoid:
        params.append(f"avoid={_encode(avoid)}")
    return "https://www.google.com/maps/dir/?" + "&".join(params)

def build_gmaps_android_intent_url(origin, destination, waypoints=None, mode="driving", avoid=None):
    """
    Preferimos intent simple (solo destino) para abrir la app directo.
    Si hay waypoints, devolvemos la URL web (Android suele abrir la app igualmente).
    """
    if waypoints:
        return build_gmaps_url(origin, destination, waypoints, mode, avoid)
    # Intent nativo de navegación
    mode_map = {"driving": "d", "walking": "w", "bicycling": "b", "transit": "r"}
    m = mode_map.get(mode, "d")
    return f"google.navigation:q={_encode(destination)}&mode={m}"

def build_waze_url(origin, destination):
    # En waze el esquema público fiable para compartir suele ser URL web también
    # (waze:// funciona bien desde Android/iOS, pero para QR es más robusto https)
    return (
        "https://waze.com/ul"
        f"?ll={_encode(destination)}"
        f"&navigate=yes&from={_encode(origin)}"
    )

def build_apple_maps_url(origin, destination, waypoints=None):
    """
    Apple Maps no documenta oficialmente múltiples paradas por URL.
    Usamos saddr/daddr (origen/destino). Si hay waypoints, los ignoramos en Apple (limitación).
    """
    return (
        "https://maps.apple.com/"
        f"?saddr={_encode(origin)}"
        f"&daddr={_encode(destination)}"
        "&dirflg=d"
    )

# Bandera de “API disponible” (simulada)
gmaps = True
