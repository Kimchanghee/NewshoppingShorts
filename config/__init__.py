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

# Gemini - Available models (2026)
# gemini-2.0-flash: Fast multimodal, production-ready
# gemini-2.5-flash-preview-tts: Low-latency TTS
# gemini-2.5-pro-preview-tts: High-quality TTS
GEMINI_VIDEO_MODEL = "gemini-2.0-flash"  # Fast multimodal for video analysis
GEMINI_TEXT_MODEL = "gemini-2.0-flash"   # Fast text generation
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"  # TTS with 30 HD voices
GEMINI_THINKING_LEVEL = "low"
GEMINI_MEDIA_RESOLUTION = "media_resolution_low"
GEMINI_TEMPERATURE = 1.0

# Vertex AI disabled - Use user's Gemini API key instead
VERTEX_ENABLED = False
FONTSIZE = 25
DAESA_GILI = 1.1
ENABLE_SHEET_SYNC = False

# Vertex AI (DISABLED - kept for backwards compatibility)
# Using user's Gemini API key instead
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL_ID = os.getenv("VERTEX_MODEL_ID", "")
VERTEX_JSON_KEY_PATH = os.getenv("VERTEX_JSON_KEY_PATH", "")

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
    "VERTEX_ENABLED",
    "VERTEX_PROJECT_ID",
    "VERTEX_LOCATION",
    "VERTEX_MODEL_ID",
    "VERTEX_JSON_KEY_PATH",
    "PAYMENT_API_BASE_URL",
    "CHECKOUT_POLL_INTERVAL",
    "CHECKOUT_POLL_MAX_TRIES",
]
