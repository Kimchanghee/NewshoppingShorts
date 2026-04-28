"""
Linktree publishing manager (webhook-based).

Linktree does not provide a broadly available write API for adding links directly.
For app-side automation we send payloads to a user-provided webhook endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import re

import requests

from managers.settings_manager import get_settings_manager
from utils.logging_config import get_logger

logger = get_logger(__name__)


class LinktreeManager:
    """Manages Linktree webhook publishing for generated affiliate links."""

    DEFAULT_TIMEOUT_SECONDS = 12
    MAX_PRODUCT_TITLE_LENGTH = 15

    def __init__(self):
        self.settings = get_settings_manager()

    @classmethod
    def _build_concise_product_title(cls, product_name: str) -> str:
        """
        Build a concise product title for Linktree.

        Rules:
        - Should remain recognizable as the product name
        - Must be 15 characters or fewer
        """
        name = str(product_name or "").strip()
        if not name:
            return "추천상품"

        # Remove common noisy wrappers and normalize whitespace.
        normalized = re.sub(r"\[[^\]]*\]|\([^)]*\)|\{[^}]*\}", " ", name)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            normalized = name

        # Prefer the first meaningful chunk before heavy option separators.
        chunks = re.split(r"[|/,;]| - | – | — |·", normalized)
        candidate = next((chunk.strip() for chunk in chunks if chunk and chunk.strip()), normalized)

        # Keep up to 15 chars, trying to preserve whole words first.
        if len(candidate) > cls.MAX_PRODUCT_TITLE_LENGTH and " " in candidate:
            words = candidate.split()
            kept_words = []
            for word in words:
                trial = (" ".join(kept_words + [word])).strip()
                if len(trial) <= cls.MAX_PRODUCT_TITLE_LENGTH:
                    kept_words.append(word)
                else:
                    break
            if kept_words:
                candidate = " ".join(kept_words).strip()

        if len(candidate) > cls.MAX_PRODUCT_TITLE_LENGTH:
            candidate = candidate[: cls.MAX_PRODUCT_TITLE_LENGTH].rstrip()

        if not candidate:
            candidate = name[: cls.MAX_PRODUCT_TITLE_LENGTH].strip()

        return candidate or "추천상품"

    def get_settings(self) -> Dict[str, Any]:
        """Return current Linktree settings from SettingsManager."""
        return self.settings.get_linktree_settings()

    def get_profile_url(self) -> str:
        """Return configured public Linktree profile URL."""
        return str(self.get_settings().get("profile_url", "")).strip()

    def is_connected(self) -> bool:
        """A webhook URL is required for Linktree publishing."""
        webhook_url = str(self.get_settings().get("webhook_url", "")).strip()
        return bool(webhook_url)

    def is_auto_publish_enabled(self) -> bool:
        """Return whether automatic Linktree publish is enabled."""
        settings = self.get_settings()
        return bool(settings.get("auto_publish", False)) and bool(settings.get("webhook_url"))

    @staticmethod
    def _build_headers(api_key: str) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        key = str(api_key or "").strip()
        if key:
            # Support common gateway conventions.
            headers["Authorization"] = f"Bearer {key}"
            headers["X-API-Key"] = key
        return headers

    def publish_link(
        self,
        title: str,
        url: str,
        description: str = "",
        source_url: str = "",
        extra: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        """
        Publish one link record to the configured webhook endpoint.

        The remote endpoint can then upsert/update Linktree entries.
        """
        settings = self.get_settings()
        webhook_url = str(settings.get("webhook_url", "")).strip()
        if not webhook_url:
            # Linktree는 직접 쓰기 API가 없어서 이 매니저는 webhook 중계만 지원합니다.
            # 설정 → 링크트리 탭에서 webhook URL(또는 Make/Zapier/n8n 자동화 endpoint)을
            # 설정해야 자동 발행이 동작합니다. 직접 linktr.ee 로그인 자동화가 필요한 경우는
            # 별도의 브라우저 자동화 매니저가 필요합니다 (현재 미구현).
            logger.warning(
                "[Linktree] Webhook URL이 비어 있어 자동 발행을 건너뜁니다. "
                "설정 탭에서 webhook URL을 입력하거나, 별도의 직접 발행 모듈을 구성해주세요."
            )
            return False

        target_url = str(url or "").strip()
        if not target_url:
            logger.warning("[Linktree] Empty target URL. Skipping publish.")
            return False

        payload: Dict[str, Any] = {
            "title": str(title or "").strip() or "Shopping Shorts Link",
            "url": target_url,
            "description": str(description or "").strip(),
            "source_url": str(source_url or "").strip(),
            "platform": "coupang",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            payload["extra"] = dict(extra)

        headers = self._build_headers(str(settings.get("api_key", "")))
        timeout = int(timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS)

        try:
            response = requests.post(webhook_url, json=payload, headers=headers, timeout=timeout)
            if 200 <= response.status_code < 300:
                logger.info("[Linktree] Link published successfully.")
                return True
            logger.warning(
                "[Linktree] Publish failed with status=%s body=%s",
                response.status_code,
                response.text[:300],
            )
            return False
        except requests.RequestException as exc:
            logger.warning("[Linktree] Publish request failed: %s", exc)
            return False

    _COUNTER_FILE_NAME = "linktree_counter.json"

    def _counter_path(self) -> str:
        """Per-user persisted counter file."""
        import os
        base = os.path.join(os.path.expanduser("~"), ".ssmaker")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, self._COUNTER_FILE_NAME)

    def _next_publish_index(self) -> int:
        """Increment & return monotonic publish counter persisted on disk.

        First call returns 1, then 2, 3, ... — used to prefix card titles
        with [N] so the Linktree page reads as a numbered curation list.
        """
        import json
        path = self._counter_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            current = int(data.get("count", 0))
        except (OSError, ValueError, TypeError):
            current = 0
        new_index = current + 1
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"count": new_index}, f)
        except OSError as exc:
            logger.warning("[Linktree] Counter persist failed: %s", exc)
        return new_index

    def reset_publish_counter(self) -> None:
        """Reset the [N] prefix counter back to 0 (next publish becomes [1])."""
        import json, os
        path = self._counter_path()
        try:
            if os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"count": 0}, f)
        except OSError:
            pass

    def publish_coupang_link(self, product_name: str, coupang_url: str, source_url: str = "") -> bool:
        """Publish Coupang deep-link payload for the generated product.

        Title format: "[N] 상품명" where N is the monotonic upload order.
        Final length is still capped at MAX_PRODUCT_TITLE_LENGTH after the prefix
        so it stays readable on Linktree cards.
        """
        concise = self._build_concise_product_title(product_name)
        index = self._next_publish_index()
        prefix = f"[{index}] "
        # Trim concise body so prefix + body fits the visual budget.
        compose_cap = self.MAX_PRODUCT_TITLE_LENGTH
        body = concise[: max(1, compose_cap - len(prefix))]
        title = (prefix + body).strip()

        description = "Coupang product link generated by Shopping Shorts automation."
        ok = self.publish_link(
            title=title,
            url=coupang_url,
            description=description,
            source_url=source_url,
            extra={"channel": "shopping_shorts_maker", "publish_index": index},
        )
        if ok:
            logger.info("[Linktree] Published #%d → %s", index, title)
        return ok

    def test_connection(self) -> bool:
        """Send a test payload to verify webhook/API key wiring."""
        return self.publish_link(
            title="SSMaker Linktree Test",
            url="https://link.coupang.com/a/test",
            description="Linktree webhook integration test payload.",
            source_url="https://www.coupang.com/",
            extra={"test": True},
        )


_linktree_manager: Optional[LinktreeManager] = None


def get_linktree_manager() -> LinktreeManager:
    global _linktree_manager
    if _linktree_manager is None:
        _linktree_manager = LinktreeManager()
    return _linktree_manager
