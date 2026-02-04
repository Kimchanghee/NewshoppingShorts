"""
Model provider abstraction: Gemini API only (Vertex disabled).
Uses user's personal Gemini API key.
"""

from __future__ import annotations

import os
from typing import Optional

import config
from utils.logging_config import get_logger

logger = get_logger(__name__)


class VertexGeminiProvider:
    """Gemini-only provider. Vertex AI is disabled."""

    def __init__(self):
        self.gemini_client = self._init_gemini()

    def _get_first_api_key(self) -> Optional[str]:
        """등록된 API 키 중 첫 번째 사용 가능한 키 반환"""
        # 1. config.GEMINI_API_KEYS에서 찾기 (api_1, api_2, ... 형식)
        if config.GEMINI_API_KEYS:
            for key_name in sorted(config.GEMINI_API_KEYS.keys()):
                key_value = config.GEMINI_API_KEYS.get(key_name)
                if key_value and key_value.strip():
                    return key_value

        # 2. 환경변수에서 찾기
        env_key = os.getenv("GEMINI_API_KEY")
        if env_key:
            return env_key

        # 3. SecretsManager에서 직접 찾기
        try:
            from utils.secrets_manager import SecretsManager
            for i in range(1, 21):
                key_value = SecretsManager.get_api_key(f"gemini_api_{i}")
                if key_value:
                    return key_value
        except Exception:
            pass

        return None

    def _init_gemini(self):
        """Initialize Gemini client with user's API key."""
        try:
            from google import genai

            key = self._get_first_api_key()
            if not key:
                logger.warning("[Provider] Gemini API 키가 없습니다. 설정에서 API 키를 등록해주세요.")
                return None

            client = genai.Client(api_key=key)
            logger.info(f"[Provider] Gemini 초기화 완료 (모델: {config.GEMINI_TEXT_MODEL})")
            return client
        except Exception as e:
            logger.warning(f"[Provider] Gemini 초기화 실패: {e}")
            return None

    def _call_gemini(self, prompt: str) -> Optional[str]:
        """Call Gemini API."""
        if not self.gemini_client:
            return None
        try:
            resp = self.gemini_client.models.generate_content(
                model=config.GEMINI_TEXT_MODEL,
                contents=prompt
            )
            return getattr(resp, "text", None)
        except Exception as e:
            logger.error(f"[Provider] Gemini call failed: {e}")
            return None

    def generate_text(self, prompt: str) -> str:
        """Generate text using Gemini API."""
        text = self._call_gemini(prompt)
        if text:
            return text
        return "Gemini API 응답 없음. API 키를 확인해주세요."

