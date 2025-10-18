# --- EN app_utils.py, sustituye la función suggest_addresses ---

def suggest_addresses(query: str, *args, **kwargs):
    """Obtiene sugerencias de direcciones de múltiples proveedores."""
    
    # Extraemos los argumentos necesarios de **kwargs (que contiene func_kwargs y args extra)
    # *args captura argumentos posicionales extra (como default_value) y los ignora.
    key_bucket = kwargs.get("key_bucket")
    min_len = kwargs.get("min_len", 1) 
    
    if not key_bucket:
        # Si aún recibes este mensaje, significa que func_kwargs NO está funcionando
        # o la aplicación no ha cargado la nueva firma.
        return ["Error interno: Falta key_bucket en la función de búsqueda."]

    q = (query or "").strip()
    
    if len(q) < min_len:
        return []

    # ... (el resto de la lógica de búsqueda, que está correcta) ...
    
    # Google primero. Si no responde, caemos a SerpAPI y luego OSM.
    results = provider_google_autocomplete(q) \
              or provider_serpapi_maps(q) \
              or provider_nominatim(q) \
              or []

    # sanea
    clean = []
    for item in results:
        # Aseguramos que el resultado es un (label, meta) y que label es string
        if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str):
            clean.append(item)
    if not clean:
        return []

    # bucket por campo (para poder resolver place_id luego)
    if "suggest_maps" not in st.session_state:
        st.session_state["suggest_maps"] = {}
    bucket = st.session_state["suggest_maps"].setdefault(key_bucket, {})

    labels = []
    for label, meta in clean:
        bucket[label] = meta
        labels.append(label)
    return labels