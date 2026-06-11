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

    # Sentinel for "no API key configured"
    NO_API_KEY_ERROR = "NO_API_KEY"

    def __init__(self):
        self._api_key_configured = False
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
                self._api_key_configured = False
                return None

            client = genai.Client(api_key=key)
            self._api_key_configured = True
            logger.info(f"[Provider] Gemini 초기화 완료 (모델: {config.GEMINI_TEXT_MODEL})")
            return client
        except Exception as e:
            logger.warning(f"[Provider] Gemini 초기화 실패: {e}")
            self._api_key_configured = False
            return None

    @property
    def has_api_key(self) -> bool:
        """API 키가 등록되어 있는지 여부"""
        return self._api_key_configured

    def _call_gemini(self, prompt: str) -> Optional[str]:
        """Call Gemini API."""
        if not self.gemini_client:
            return None

        def _model_chain() -> list[str]:
            chain: list[str] = []

            def _add(name: str):
                n = (name or "").strip()
                if n and n not in chain:
                    chain.append(n)

            _add(getattr(config, "GEMINI_TEXT_MODEL", "gemini-3.5-flash"))
            for env_name in os.getenv("GEMINI_TEXT_MODEL_FALLBACKS", "").split(","):
                _add(env_name)
            _add("gemini-3.5-flash")
            _add("gemini-3.1-pro-preview")
            _add("gemini-3.1-flash-lite")
            _add("gemini-2.5-pro")
            _add("gemini-2.5-flash")
            _add("gemini-flash-latest")
            return chain

        def _is_model_not_found_error(exc: Exception) -> bool:
            msg = str(exc).lower()
            return (
                ("404" in msg and "not_found" in msg)
                or "model not found" in msg
                or "no longer available to new users" in msg
            )

        last_error: Optional[Exception] = None
        primary = getattr(config, "GEMINI_TEXT_MODEL", "gemini-3.5-flash")
        candidates = _model_chain()

        for idx, model_name in enumerate(candidates, start=1):
            try:
                resp = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = getattr(resp, "text", None)
                if text and model_name != primary:
                    logger.info("[Provider] Gemini model fallback: %s -> %s", primary, model_name)
                return text
            except Exception as e:
                last_error = e
                if idx < len(candidates) and _is_model_not_found_error(e):
                    logger.warning(
                        "[Provider] Model unavailable (%s), trying fallback model",
                        model_name,
                    )
                    continue
                break

        if last_error:
            logger.error(f"[Provider] Gemini call failed: {last_error}")
        return None

    def generate_text(self, prompt: str) -> str:
        """Generate text using Gemini API."""
        if not self._api_key_configured:
            return self.NO_API_KEY_ERROR
        text = self._call_gemini(prompt)
        if text:
            return text
        return "Gemini API 호출에 실패했습니다. 잠시 후 다시 시도해주세요."
