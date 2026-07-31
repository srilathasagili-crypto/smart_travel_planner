import os
from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit as st
    _HAS_STREAMLIT_SECRETS = True
except ImportError:
    st = None
    _HAS_STREAMLIT_SECRETS = False


def _get_secret(key: str, default: str = "") -> str:
    
    if _HAS_STREAMLIT_SECRETS:
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            # st.secrets raises if no secrets.toml exists at all (e.g. local run without one) -
            # that's fine, just fall through to env vars.
            pass
    return os.getenv(key, default)


class Config:
    # Google Maps (server-side key: Places API, Geocoding API, Distance Matrix API)
    GOOGLE_MAPS_API_KEY = _get_secret("GOOGLE_MAPS_API_KEY", "")

    # Optional: used to generate a natural-language itinerary narrative.
    # If not set, the app falls back to a rule-based itinerary generator (still fully functional).
    ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY", "")

    # Defaults
    DEFAULT_RADIUS_METERS = int(_get_secret("DEFAULT_RADIUS_METERS", 5000))
    MAX_PLACES_PER_CATEGORY = int(_get_secret("MAX_PLACES_PER_CATEGORY", 8))


def validate_config():

    missing = []
    if not Config.GOOGLE_MAPS_API_KEY:
        missing.append("GOOGLE_MAPS_API_KEY")
    if missing:
        raise EnvironmentError(
            f"Missing required secret/environment variable(s): {', '.join(missing)}. "
            f"Locally: copy .env.example to .env and fill it in. "
            f"On Streamlit Cloud: add it under App settings -> Secrets."
        )
