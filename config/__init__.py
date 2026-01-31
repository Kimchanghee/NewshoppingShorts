import os
from pathlib import Path
from typing import Dict

# API keys

def _load_api_keys() -> Dict[str, str]:
    keys: Dict[str, str] = {}
    try:
        from utils.secrets_manager import SecretsManager
        secure_key = SecretsManager.get_api_key("gemini")
        if secure_key:
            keys["gemini"] = secure_key
    except Exception:
        pass
    if "gemini" not in keys and (gemini_key := os.getenv("GEMINI_API_KEY")):
        keys["gemini"] = gemini_key
        try:
            from utils.secrets_manager import SecretsManager
            SecretsManager.store_api_key("gemini", gemini_key)
        except Exception:
            pass
    return keys

GEMINI_API_KEYS = _load_api_keys()

# Gemini
GEMINI_VIDEO_MODEL = "gemini-3-pro-preview"
GEMINI_TEXT_MODEL = "gemini-2.5-flash"
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_THINKING_LEVEL = "low"
GEMINI_MEDIA_RESOLUTION = "media_resolution_low"
GEMINI_TEMPERATURE = 1.0
FONTSIZE = 25
DAESA_GILI = 1.1
ENABLE_SHEET_SYNC = False

# Vertex AI (primary) - with default credentials
# Default credential path
_config_dir = Path(__file__).parent
DEFAULT_VERTEX_JSON_PATH = _config_dir / "vertex-credentials.json"

VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "alien-baton-484113-g4")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL_ID = os.getenv("VERTEX_MODEL_ID", "gemini-1.5-flash-002")
VERTEX_JSON_KEY_PATH = os.getenv(
    "VERTEX_JSON_KEY_PATH",
    str(DEFAULT_VERTEX_JSON_PATH) if DEFAULT_VERTEX_JSON_PATH.exists() else ""
)

# Warn if using default project ID
if VERTEX_PROJECT_ID == "alien-baton-484113-g4" and not os.getenv("VERTEX_PROJECT_ID"):
    import logging
    logging.warning(
        "[Config] Using default Vertex AI project ID. "
        "Set VERTEX_PROJECT_ID environment variable for production deployments."
    )

# Payment API (web checkout + polling)
PAYMENT_API_BASE_URL = os.getenv("PAYMENT_API_BASE_URL", "https://payments.example.com/api")
CHECKOUT_POLL_INTERVAL = float(os.getenv("CHECKOUT_POLL_INTERVAL", "3"))
CHECKOUT_POLL_MAX_TRIES = int(os.getenv("CHECKOUT_POLL_MAX_TRIES", "20"))

__all__ = [
    "GEMINI_API_KEYS",
    "GEMINI_VIDEO_MODEL",
    "GEMINI_TEXT_MODEL",
    "GEMINI_TTS_MODEL",
    "GEMINI_THINKING_LEVEL",
    "GEMINI_MEDIA_RESOLUTION",
    "GEMINI_TEMPERATURE",
    "FONTSIZE",
    "DAESA_GILI",
    "ENABLE_SHEET_SYNC",
    "VERTEX_PROJECT_ID",
    "VERTEX_LOCATION",
    "VERTEX_MODEL_ID",
    "VERTEX_JSON_KEY_PATH",
    "PAYMENT_API_BASE_URL",
    "CHECKOUT_POLL_INTERVAL",
    "CHECKOUT_POLL_MAX_TRIES",
]
