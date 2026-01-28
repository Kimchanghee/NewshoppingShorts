import random
import os
from typing import Dict

# API keys - Load from environment variables or api_keys_config.json
# 기본 키는 비워 두고, 환경 변수 또는 UI/파일(api_keys_config.json)에서 불러옵니다.

def _load_api_keys() -> Dict[str, str]:
    """
    Load API keys from secure storage, environment variables, or api_keys_config.json.

    Priority order:
    1. Secure storage (keyring via SecretsManager)
    2. Environment variables
    3. api_keys_config.json (loaded later by ApiKeyManager)

    Environment variables checked:
    - GEMINI_API_KEY: Gemini API key

    Returns:
        Dictionary of API keys
    """
    keys = {}

    # Try loading from secure storage first
    try:
        from utils.secrets_manager import SecretsManager

        # Try to get Gemini key from secure storage
        secure_key = SecretsManager.get_api_key("gemini")
        if secure_key:
            keys["gemini"] = secure_key
    except ImportError:
        pass  # SecretsManager not available, fall back to env vars

    # Fall back to environment variables if not in secure storage
    if "gemini" not in keys:
        if gemini_key := os.getenv("GEMINI_API_KEY"):
            keys["gemini"] = gemini_key

            # Auto-migrate to secure storage if available
            try:
                from utils.secrets_manager import SecretsManager
                SecretsManager.store_api_key("gemini", gemini_key)
            except ImportError:
                pass

    # api_keys_config.json will be loaded later by ApiKeyManager
    return keys

GEMINI_API_KEYS = _load_api_keys()

# Gemini 3.0 모델 사용
GEMINI_VIDEO_MODEL = "gemini-3-pro-preview"  # 비디오 분석 및 복잡한 추론 작업용
GEMINI_TEXT_MODEL = "gemini-2.5-flash"  # 빠른 텍스트 처리용
# 사용 가능 TTS 모델 (Gemini 2.5 TTS 프리뷰)
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"

# Gemini 3.0 파라미터 설정
GEMINI_THINKING_LEVEL = "low"  # low: 최소 레이턴시 (속도 우선), high: 최대 추론 깊이
GEMINI_MEDIA_RESOLUTION = "media_resolution_low"  # 비디오: low(70 tokens/frame), high(280 tokens/frame)
GEMINI_TEMPERATURE = 1.0  # Gemini 3.0 권장 기본값

FONTSIZE = 25
DAESA_GILI = 1.1

# Google Sheet 연동 사용 여부 (False이면 시트 관련 기능이 비활성화됩니다)
