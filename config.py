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
            pass

    return os.getenv(key, default)


class Config:

    # Optional: AI itinerary generation
    ANTHROPIC_API_KEY = _get_secret(
        "ANTHROPIC_API_KEY",
        ""
    )


    # Defaults
    DEFAULT_RADIUS_METERS = int(
        _get_secret(
            "DEFAULT_RADIUS_METERS",
            5000
        )
    )


    MAX_PLACES_PER_CATEGORY = int(
        _get_secret(
            "MAX_PLACES_PER_CATEGORY",
            8
        )
    )


def validate_config():

    # Google Maps removed
    # No mandatory API keys required now

    return True
