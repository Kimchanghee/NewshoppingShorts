import os
from pathlib import Path
from typing import Dict

# API keys

def _load_api_keys() -> Dict[str, str]:
    keys: Dict[str, str] = {}
    try:
        from utils.secrets_manager import SecretsManager

        # Primary format: gemini_api_1..N -> api_1..N
        for i in range(1, 9):
            secure_key = SecretsManager.get_api_key(f"gemini_api_{i}")
            if secure_key and secure_key.strip():
                keys[f"api_{i}"] = secure_key.strip()

        # Legacy single-key format.
        if not keys:
            legacy_key = SecretsManager.get_api_key("gemini")
            if legacy_key and legacy_key.strip():
                keys["api_1"] = legacy_key.strip()
                # One-time compatibility migration.
                try:
                    SecretsManager.store_api_key("gemini_api_1", legacy_key.strip())
                except Exception:
                    pass
    except Exception:
        pass

    if not keys and (gemini_key := os.getenv("GEMINI_API_KEY")):
        keys["api_1"] = gemini_key
        try:
            from utils.secrets_manager import SecretsManager
            SecretsManager.store_api_key("gemini_api_1", gemini_key)
            # Keep legacy alias for older code paths.
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
# Set PAYMENT_API_BASE_URL via environment variable or .env file.
# Default to the main API server URL so payments work out-of-the-box in dev/prod.
_DEFAULT_API_SERVER_URL = os.getenv(
    "API_SERVER_URL",
    "https://ssmaker-auth-api-1049571775048.us-central1.run.app",
).rstrip("/")
PAYMENT_API_BASE_URL = os.getenv("PAYMENT_API_BASE_URL", _DEFAULT_API_SERVER_URL).rstrip("/")
CHECKOUT_POLL_INTERVAL = float(os.getenv("CHECKOUT_POLL_INTERVAL", "3"))
CHECKOUT_POLL_MAX_TRIES = int(os.getenv("CHECKOUT_POLL_MAX_TRIES", "20"))

from config.voice_profiles import VOICE_PROFILES, DEFAULT_MULTI_VOICE_PRESETS

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
    "VOICE_PROFILES",
    "DEFAULT_MULTI_VOICE_PRESETS",
]
