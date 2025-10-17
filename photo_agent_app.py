from urllib.parse import quote_plus

def build_gmaps_url(origin: str, destination: str, waypoints=None, *, mode="driving", avoid=None, optimize=True):
    """
    origin, destination: direcciones en texto
    waypoints: lista de paradas intermedias (texto)
    mode: driving | walking | bicycling | transit
    avoid: lista de strings: {"tolls","highways","ferries","indoor"}
    optimize: si True y hay varios waypoints, deja que Google los optimice (optimize:true)
    """
    base = "https://www.google.com/maps/dir/?api=1"
    parts = [
        f"origin={quote_plus(origin)}",
        f"destination={quote_plus(destination)}",
        f"travelmode={mode}"
    ]
    if avoid:
        parts.append(f"avoid={quote_plus(','.join(avoid))}")

    if waypoints:
        wp = "|".join(waypoints)
        if optimize and len(waypoints) > 1:
            wp = f"optimize:true|{wp}"
        parts.append(f"waypoints={quote_plus(wp)}")

    return base + "&" + "&".join(parts)