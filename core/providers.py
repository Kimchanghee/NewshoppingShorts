"""
Model provider abstraction: Vertex AI primary, Gemini fallback.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import config
from utils.logging_config import get_logger

logger = get_logger(__name__)


class VertexGeminiProvider:
    def __init__(self):
        self.vertex_client = self._init_vertex()
        self.gemini_client = self._init_gemini()

    # ---------------- Vertex ----------------
    def _init_vertex(self):
        try:
            from vertexai import init as vertexai_init
            from google.oauth2 import service_account

            creds_path = config.VERTEX_JSON_KEY_PATH or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if creds_path and os.path.exists(creds_path):
                creds = service_account.Credentials.from_service_account_file(creds_path)
                vertexai_init(
                    project=config.VERTEX_PROJECT_ID,
                    location=config.VERTEX_LOCATION,
                    credentials=creds,
                )
            else:
                vertexai_init(
                    project=config.VERTEX_PROJECT_ID,
                    location=config.VERTEX_LOCATION,
                )
            from vertexai.generative_models import GenerativeModel

            return GenerativeModel(config.VERTEX_MODEL_ID)
        except Exception as e:
            logger.warning(f"[Provider] Vertex init failed: {e}")
            return None

    def _call_vertex(self, prompt: str) -> Optional[str]:
        if not self.vertex_client:
            return None
        try:
            resp = self.vertex_client.generate_content(prompt)
            # vertexai 1.66: resp.candidates[0].content.parts[0].text
            if hasattr(resp, "text"):
                return resp.text
            if getattr(resp, "candidates", None):
                cand = resp.candidates[0]
                parts = getattr(cand, "content", getattr(cand, "output", None))
                if parts and hasattr(parts, "parts") and parts.parts:
                    return getattr(parts.parts[0], "text", None)
            return None
        except Exception as e:
            logger.error(f"[Provider] Vertex call failed: {e}")
            return None

    # ---------------- Gemini fallback ----------------
    def _init_gemini(self):
        try:
            import google.genai as genai

            key = config.GEMINI_API_KEYS.get("gemini") or os.getenv("GEMINI_API_KEY")
            if not key:
                return None
            genai.configure(api_key=key)
            return genai.GenerativeModel(config.GEMINI_TEXT_MODEL)
        except Exception as e:
            logger.warning(f"[Provider] Gemini init failed: {e}")
            return None

    def _call_gemini(self, prompt: str) -> Optional[str]:
        if not self.gemini_client:
            return None
        try:
            resp = self.gemini_client.generate_content(prompt)
            return getattr(resp, "text", None)
        except Exception as e:
            logger.error(f"[Provider] Gemini call failed: {e}")
            return None

    # ---------------- Public API ----------------
    def generate_text(self, prompt: str) -> str:
        """Primary Vertex; fallback to Gemini; final fallback explanatory text."""
        text = self._call_vertex(prompt)
        if text:
            return text
        text = self._call_gemini(prompt)
        if text:
            return text
        return "Model response unavailable (Vertex and Gemini both unreachable)."

