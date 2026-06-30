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

DEFAULT_LINKTREE_PROFILE_URL = "https://linktr.ee/studio.idol"
COUPANG_AFFILIATE_DISCLOSURE = (
    "이 게시물은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)


class LinktreeManager:
    """Manages Linktree webhook publishing for generated affiliate links."""

    DEFAULT_TIMEOUT_SECONDS = 12
    MAX_PRODUCT_TITLE_LENGTH = 40

    def __init__(self):
        self.settings = get_settings_manager()

    @classmethod
    def _build_concise_product_title(cls, product_name: str) -> str:
        """
        Build a concise product title for Linktree.

        Rules:
        - Should remain recognizable as the product name
        - Must stay compact enough for Linktree cards
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

        # Keep the title compact, trying to preserve whole words first.
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

    @staticmethod
    def _coerce_publish_index(index: Any) -> Optional[int]:
        try:
            if isinstance(index, str):
                match = re.search(r"\d+", index)
                if not match:
                    return None
                value = int(match.group(0))
            else:
                value = int(index)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @classmethod
    def format_publish_index(cls, index: Any) -> str:
        value = cls._coerce_publish_index(index)
        return f"[{value:03d}]" if value else ""

    @classmethod
    def _build_numbered_product_title(cls, product_name: str, index: Any) -> str:
        marker = cls.format_publish_index(index)
        concise = cls._build_concise_product_title(product_name)
        if not marker:
            return concise

        prefix = f"{marker} "
        body_limit = max(1, cls.MAX_PRODUCT_TITLE_LENGTH - len(prefix))
        body = concise[:body_limit].rstrip()
        return (prefix + body).strip()

    def get_settings(self) -> Dict[str, Any]:
        """Return current Linktree settings from SettingsManager."""
        return self.settings.get_linktree_settings()

    def get_profile_url(self) -> str:
        """Return configured public Linktree profile URL."""
        return str(self.get_settings().get("profile_url", "")).strip() or DEFAULT_LINKTREE_PROFILE_URL

    def is_connected(self) -> bool:
        """Return whether any Linktree publish path is available."""
        webhook_url = str(self.get_settings().get("webhook_url", "")).strip()
        if webhook_url:
            return True
        try:
            from managers.linktree_browser_publisher import browser_publish_enabled

            return browser_publish_enabled()
        except Exception:
            return False

    def get_connection_issue(self) -> str:
        """Return a user-facing reason why automatic Linktree publish cannot run."""
        settings = self.get_settings()
        issues = []
        verification = self.settings.get_linktree_account_verification()
        if verification.get("required") and not verification.get("ok"):
            issues.append(str(verification.get("message") or "Linktree 계정 이메일 확인이 필요합니다."))

        webhook_url = str(settings.get("webhook_url", "")).strip()
        if not webhook_url:
            try:
                from managers.linktree_browser_publisher import browser_publish_enabled

                if browser_publish_enabled():
                    return " ".join(issues)
            except Exception as exc:
                issues.append(f"Linktree 브라우저 자동 발행을 준비하지 못했습니다: {exc}")
            issues.append(
                "Linktree 자동 발행이 켜져 있지만 Webhook URL이 없습니다. "
                "설정 > Coupang/Linktree 자동화에서 Webhook URL을 연결하거나 "
                "Linktree 자동 발행 체크를 끄고 다시 실행하세요."
            )
        elif not re.match(r"^https?://", webhook_url, re.IGNORECASE):
            issues.append("Linktree Webhook URL은 http:// 또는 https:// 형식이어야 합니다.")
        return " ".join(issues)

    def require_connected_for_publish(self) -> tuple[bool, str]:
        """Return whether Linktree publish can run, plus the blocking message."""
        issue = self.get_connection_issue()
        return (not issue, issue)

    def is_auto_publish_enabled(self) -> bool:
        """Return whether automatic Linktree publish is enabled."""
        settings = self.get_settings()
        if not bool(settings.get("auto_publish", False)):
            return False
        if bool(str(settings.get("webhook_url", "")).strip()):
            return True
        try:
            from managers.linktree_browser_publisher import browser_publish_enabled

            return browser_publish_enabled()
        except Exception:
            return False

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
            target_url = str(url or "").strip()
            if not target_url:
                logger.warning("[Linktree] Empty target URL. Skipping publish.")
                return False
            try:
                from managers.linktree_browser_publisher import (
                    browser_publish_enabled,
                    publish_link_via_visible_browser,
                )

                if not browser_publish_enabled():
                    logger.warning(
                        "[Linktree] Webhook URL is empty and visible browser fallback is disabled."
                    )
                    return False

                browser_result = publish_link_via_visible_browser(
                    title=str(title or "").strip() or "Shopping Shorts Link",
                    url=target_url,
                    number=str((extra or {}).get("display_number", "")).strip(),
                    profile_url=str(settings.get("profile_url", "")).strip(),
                    timeout_seconds=int(timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS),
                )
                if browser_result.get("ok"):
                    logger.info("[Linktree] Link published through browser fallback.")
                    return True
                logger.warning("[Linktree] Browser fallback publish failed: %s", browser_result)
                return False
            except Exception as exc:
                logger.warning("[Linktree] Browser fallback publish crashed: %s", exc)
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
        with [001], [002], ... so the Linktree page reads as a numbered
        curation list.
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
        """Reset the [001] prefix counter back to 0."""
        import json, os
        path = self._counter_path()
        try:
            if os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"count": 0}, f)
        except OSError:
            pass

    def publish_coupang_link_with_metadata(
        self,
        product_name: str,
        coupang_url: str,
        source_url: str = "",
    ) -> Dict[str, Any]:
        """Publish Coupang deep-link payload and return numbering metadata.

        Title format: "[001] 상품명" where the number is the monotonic upload order.
        Reuse this index on connected channels so users can match the Linktree
        card to YouTube descriptions, comments, and future social posts.
        """
        index = self._next_publish_index()
        number = self.format_publish_index(index)
        title = self._build_numbered_product_title(product_name, index)
        description = COUPANG_AFFILIATE_DISCLOSURE
        ok = self.publish_link(
            title=title,
            url=coupang_url,
            description=description,
            source_url=source_url,
            extra={
                "channel": "shopping_shorts_maker",
                "publish_index": index,
                "display_number": number,
            },
        )
        if ok:
            logger.info("[Linktree] Published #%d → %s", index, title)
        return {
            "ok": bool(ok),
            "publish_index": index,
            "number": number,
            "title": title,
            "url": coupang_url,
            "description": description,
        }

    def publish_coupang_link(self, product_name: str, coupang_url: str, source_url: str = "") -> bool:
        """Publish Coupang deep-link payload for the generated product."""
        result = self.publish_coupang_link_with_metadata(
            product_name=product_name,
            coupang_url=coupang_url,
            source_url=source_url,
        )
        ok = bool(result.get("ok"))
        return ok

    def test_connection(self) -> bool:
        """Send a test payload to verify webhook/API key wiring."""
        return self.publish_link(
            title="SSMaker Linktree Test",
            url="https://link.coupang.com/a/test",
            description=COUPANG_AFFILIATE_DISCLOSURE,
            source_url="https://www.coupang.com/",
            extra={"test": True},
        )


_linktree_manager: Optional[LinktreeManager] = None


def get_linktree_manager() -> LinktreeManager:
    global _linktree_manager
    if _linktree_manager is None:
        _linktree_manager = LinktreeManager()
    return _linktree_manager
