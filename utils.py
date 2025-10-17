from urllib.parse import quote_plus
from io import BytesIO
import os, requests, streamlit as st, qrcode
from dotenv import load_dotenv
from streamlit_searchbox import st_searchbox

load_dotenv()
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")

# ... aquí copias tus funciones provider_google_autocomplete, provider_nominatim, etc.

def address_input(label, key):
    try:
        return st_searchbox(
            search_function=lambda q: suggest_addresses(q, key),
            label=label,
            key=key,
            default=None
        )
    except Exception:
        return st.text_input(label, placeholder="Escribe la dirección completa…")

# Y el resto igual que en tu versión buena