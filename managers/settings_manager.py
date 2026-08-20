"""
Settings Manager for UI Preferences Persistence

Saves and loads user preferences (CTA, voice selection, font) to a JSON file.
"""

import json
import hmac
import os
import shutil
import tempfile
import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.font_catalog import (
    DEFAULT_FONT_ID,
    DEFAULT_WATERMARK_FONT_ID,
    normalize_font_id,
)
from utils.logging_config import get_logger
from utils.secrets_manager import get_secrets_manager

YOUTUBE_OAUTH_TOKEN_KEY = "youtube_oauth_token_json_v1"

logger = get_logger(__name__)


class SettingsManager:
    """Manages persistent storage of UI preferences (thread-safe)"""

    CURRENT_SETTINGS_SCHEMA_VERSION = 1

    REMOTE_SECRET_STRING_KEYS = {
        "coupang_access_key",
        "coupang_secret_key",
        "linktree_webhook_url",
        "linktree_api_key",
        "computer_use_bridge_api_key",
    }
    REMOTE_SECRET_JSON_KEYS = {
        "cookies_inpock",
        "cookies_1688",
    }

    SECURE_CREDENTIAL_KEYS = {
        "coupang_access_key": "settings_coupang_access_v1",
        "coupang_secret_key": "settings_coupang_secret_v1",
        "linktree_webhook_url": "settings_linktree_webhook_v1",
        "linktree_api_key": "settings_linktree_api_v1",
        "computer_use_bridge_api_key": "settings_computer_use_bridge_v1",
        "cookies_inpock": "settings_cookies_inpock_v1",
        "cookies_1688": "settings_cookies_1688_v1",
    }

    DEFAULT_PLATFORM_PROMPTS = {
        "youtube": {
            "title_prompt": (
                "유튜브 쇼핑 쇼츠 제목 1개를 작성해주세요. "
                "쿠팡 파트너스 링크가 포함되는 영상은 제목 첫 부분에 반드시 [광고]를 표시해주세요. "
                "핵심 키워드 1~2개를 자연스럽게 포함하고, 제품의 핵심 효익/차별점이 3초 안에 이해되도록 짧고 명확하게 써주세요. "
                "과장/오해 유도/낚시성 표현은 금지하고, 실제 영상 내용과 정확히 일치하게 작성해주세요."
            ),
            "description_prompt": (
                "유튜브 쇼츠 설명을 작성해주세요. "
                "쿠팡 파트너스 링크가 포함되면 첫 줄에 '이 게시물은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.'를 정확히 넣어주세요. "
                "첫 1~2문장에 영상 핵심 요약과 구매/탐색 CTA를 배치하고, 뒤에는 제품 특징/사용 상황/추천 포인트를 짧게 정리해주세요. "
                "각 영상마다 중복 없는 고유 문구로 작성하고, 제목과 설명의 핵심 키워드를 일관되게 맞춰 검색 노출을 높여주세요. "
                "설명은 사람이 읽기 쉽게 줄바꿈/불릿을 활용해주세요."
            ),
            "hashtag_prompt": (
                "유튜브 쇼츠용 해시태그를 3~5개 작성해주세요. "
                "구성은 1) 넓은 카테고리 1개 2) 니치 키워드 1~2개 3) 구매 의도 키워드 1~2개로 해주세요. "
                "#shorts 포함 여부를 콘텐츠 맥락에 맞게 판단하고, 영상과 직접 관련된 태그만 사용해주세요. "
                "해시태그 남발/중복/무관 태그는 제외해주세요."
            ),
        },
        "tiktok": {
            "title_prompt": (
                "틱톡 숏폼 톤에 맞춰 20자 내외의 짧고 리듬감 있는 제목 1개를 작성하세요. "
                "첫 단어에서 관심을 끌고 상품 장점을 즉시 드러내세요."
            ),
            "description_prompt": (
                "틱톡 게시글용 설명을 작성하세요. "
                "1) 공감되는 사용 상황 1문장 2) 핵심 장점 2개 3) 행동 유도 CTA 1문장 순서로 구성하세요."
            ),
            "hashtag_prompt": (
                "틱톡 검색/추천에 맞는 해시태그를 6~9개 작성하세요. "
                "제품군 해시태그, 사용 상황 해시태그, 트렌드 해시태그를 균형 있게 포함하세요."
            ),
        },
        "instagram": {
            "title_prompt": (
                "인스타그램 릴스/피드에 어울리는 감성형 제목 1개를 작성하세요. "
                "브랜드 톤을 유지하면서도 상품의 핵심 가치를 한 줄로 보여주세요."
            ),
            "description_prompt": (
                "인스타그램 캡션을 작성하세요. "
                "도입 문장 1개, 상품 핵심 포인트 2개, CTA 1개를 포함하고 읽기 쉬운 줄바꿈을 사용하세요."
            ),
            "hashtag_prompt": (
                "인스타그램용 해시태그 10개 내외를 작성하세요. "
                "대형 키워드와 니치 키워드를 섞고, 동일 의미 중복 해시태그는 제외하세요."
            ),
        },
        "threads": {
            "title_prompt": (
                "스레드에 맞는 대화형 훅 문장 1개를 작성하세요. "
                "질문형 또는 공감형 시작으로 자연스럽게 상품 주제로 연결하세요."
            ),
            "description_prompt": (
                "스레드용 본문을 작성하세요. "
                "짧은 단락 2~3개로 의견/경험을 섞어 설명하고, 마지막에 토론을 유도하는 문장을 넣으세요."
            ),
            "hashtag_prompt": (
                "스레드 문맥에 맞는 핵심 해시태그를 4~6개 작성하세요. "
                "과도한 태그 나열 대신 주제 집중도를 높이는 태그만 선택하세요."
            ),
        },
        "x": {
            "title_prompt": (
                "X(트위터) 스타일로 짧고 강한 훅 문장 1개를 작성하세요. "
                "핵심 메시지를 앞에 배치하고 불필요한 수식어를 줄이세요."
            ),
            "description_prompt": (
                "X 게시글 본문을 작성하세요. "
                "핵심 요약 1문장 + 장점 2개 + CTA 1문장 구조로 간결하게 구성하세요."
            ),
            "hashtag_prompt": (
                "X용 해시태그를 3~5개 작성하세요. "
                "검색 효율이 높은 키워드 위주로 선택하고 중복/장문 태그는 제외하세요."
            ),
        },
    }


    DEFAULT_YOUTUBE_COMMENT_PROMPT = (
        "영상에서 소개한 상품 안내입니다.\n"
        "상품: {상품설명}\n"
        "구매 링크: {구매링크}\n"
        "원상품 링크: {원상품링크}\n"
        "링크 모음: {linktree_link}\n"
        "궁금한 점은 댓글로 남겨주세요."
    )

    DEFAULT_SETTINGS = {
        "settings_schema_version": CURRENT_SETTINGS_SCHEMA_VERSION,
        "cta_id": "default",
        "font_id": DEFAULT_FONT_ID,
        "selected_voices": [],  # List of selected voice IDs
        "gender_filter": "all",
        "output_folder": "",  # 저장 폴더 경로 (빈 문자열이면 바탕화면)
        "launch_on_startup": True,  # Start SSMaker automatically after Windows login
        "theme": "light",  # 테마 설정 (light/dark)
        "tutorial_completed": False,  # 튜토리얼 완료 여부
        # 워터마크 설정
        "watermark_enabled": False,  # 워터마크 활성화 여부
        "watermark_channel_name": "",  # 채널 이름
        "watermark_position": "bottom_right",  # 위치: top_left, top_right, bottom_left, bottom_right
        "watermark_font_id": DEFAULT_WATERMARK_FONT_ID,  # 워터마크 폰트 ID
        "watermark_font_size": "medium",  # 워터마크 크기: small, medium, large
        # 워터마크가 사용자가 직접 설정한 값인지 (기본값/테스트값 자동 초기화에 사용)
        "watermark_user_configured": False,
        # 소셜 미디어 연결 설정
        "youtube_connected": False,
        "youtube_channel_id": "",
        "youtube_channel_name": "",
        "youtube_account_email": "",
        "youtube_expected_account_email": "",
        "youtube_auto_upload": False,
        "youtube_upload_interval": 60,  # 분 단위 (60, 120, 180, 240)
        # 업로드 프롬프트 설정 (채널별)
        "youtube_title_prompt": "",
        "youtube_description_prompt": "",
        "youtube_hashtag_prompt": "",
        "youtube_comment_enabled": False,
        "youtube_comment_prompt": DEFAULT_YOUTUBE_COMMENT_PROMPT,
        "youtube_comment_manual_product_link": "",
        # COMING SOON 플랫폼
        "tiktok_connected": False,
        "tiktok_account_name": "",
        "tiktok_title_prompt": "",
        "tiktok_description_prompt": "",
        "tiktok_hashtag_prompt": "",
        "instagram_connected": False,
        "instagram_account_name": "",
        "instagram_title_prompt": "",
        "instagram_description_prompt": "",
        "instagram_hashtag_prompt": "",
        "threads_connected": False,
        "threads_account_name": "",
        "threads_title_prompt": "",
        "threads_description_prompt": "",
        "threads_hashtag_prompt": "",
        "x_connected": False,
        "x_account_name": "",
        "x_title_prompt": "",
        "x_description_prompt": "",
        "x_hashtag_prompt": "",
        # Automation Settings
        "coupang_access_key": "",
        "coupang_secret_key": "",
        "linktree_webhook_url": "",
        "linktree_api_key": "",
        "linktree_profile_url": "",
        "linktree_account_email": "",
        "linktree_expected_account_email": "",
        "linktree_auto_publish": False,
        # Codex CLI bridge settings (for setup assistant computer-use handoff)
        "codex_cli_enabled": True,
        "codex_cli_path": "codex",
        "codex_cli_model": "",
        # Computer Use access policy / bridge
        "computer_use_paid_only": True,
        "computer_use_bridge_enabled": False,
        "computer_use_bridge_url": "",
        "computer_use_bridge_api_key": "",
        # Sourcing AI policy
        "sourcing_ai_provider": "gemini",
        "sourcing_use_gemini_computer_use": True,
        "sourcing_use_codex_computer_use": False,
        # Sourcing product match policy
        "sourcing_min_similarity_percent": 90,
        "sourcing_auto_skip_low_similarity": False,
        # 풀자동화는 쿠팡 상품명을 중국어로 변환한 뒤
        # 샤오홍슈·도우인·콰이쇼우에서 관련 영상을 직접 소싱한다.
        "automation_sourcing_method": "platform_video",
        # 다운로드 성공률 순서. 안전 후보 전체 중 최고 관련도를 선택한다.
        "platform_video_sources": [
            "douyin", "xiaohongshu", "kuaishou"
        ],
        "cookies_inpock": {},  # Dict to store Inpock Link cookies
        "cookies_1688": {},  # Dict to store 1688 cookies
    }

    def __init__(self, settings_file: str = "ui_preferences.json"):
        """
        Initialize the settings manager.

        Args:
            settings_file: Name of the settings file (stored in app directory)
        """
        self.settings_file = settings_file
        self._settings: Dict[str, Any] = {}
        self._recovery_issues: List[Dict[str, str]] = []
        self._lock = threading.Lock()  # Thread safety lock
        self._remote_sync_enabled = False
        self._remote_push_running = False
        self._remote_lock = threading.Lock()
        self._load_settings()

    def _get_settings_dir(self) -> str:
        """
        사용자별 설정 저장 폴더.

        NOTE:
        설정을 EXE 옆(설치 폴더)에 저장하면 업데이트/압축해제 과정에서
        테스트 설정이 같이 배포되는 문제가 생길 수 있어 사용자 홈으로 이동합니다.
        """
        return os.path.join(os.path.expanduser("~"), ".ssmaker")

    def _get_settings_path(self) -> str:
        """Get the full path to the settings file"""
        return os.path.join(self._get_settings_dir(), self.settings_file)

    def _get_legacy_settings_path(self) -> str:
        """Legacy location: next to exe / repo root (older builds)."""
        try:
            import sys
            if getattr(sys, "frozen", False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            logger.debug(f"[SettingsManager] Legacy path fallback to cwd: {e}")
            base_dir = os.getcwd()
        return os.path.join(base_dir, self.settings_file)

    def _get_legacy_settings_paths(self) -> List[str]:
        """Return historical settings locations in migration precedence order."""
        home_dir = os.path.expanduser("~")
        candidates = [
            self._get_legacy_settings_path(),
            os.path.join(home_dir, ".newshopping", self.settings_file),
        ]

        appdata_dir = os.getenv("APPDATA", "").strip()
        if appdata_dir:
            candidates.append(os.path.join(appdata_dir, "SSMaker", self.settings_file))

        # Some unpackaged builds used Local AppData even though the normal Windows
        # AppData location is Roaming.
        local_appdata_dir = os.getenv("LOCALAPPDATA", "").strip()
        if local_appdata_dir:
            candidates.append(os.path.join(local_appdata_dir, "SSMaker", self.settings_file))

        current_path = os.path.normcase(os.path.abspath(self._get_settings_path()))
        unique_paths: List[str] = []
        seen = {current_path}
        for candidate in candidates:
            normalized = os.path.normcase(os.path.abspath(candidate))
            if normalized not in seen:
                seen.add(normalized)
                unique_paths.append(candidate)
        return unique_paths

    @classmethod
    def _default_settings(cls) -> Dict[str, Any]:
        """Return defaults without sharing mutable lists/dicts between instances."""
        return deepcopy(cls.DEFAULT_SETTINGS)

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "enabled"}:
                return True
            if normalized in {"0", "false", "no", "off", "disabled", ""}:
                return False
        return default

    @staticmethod
    def _coerce_string_list(value: Any, default: List[str]) -> List[str]:
        raw_items: Any = value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raw_items = []
            else:
                try:
                    parsed = json.loads(stripped)
                except (TypeError, ValueError):
                    parsed = None
                raw_items = parsed if isinstance(parsed, list) else stripped.split(",")
        if not isinstance(raw_items, list):
            return list(default)

        cleaned: List[str] = []
        for item in raw_items:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if item and item not in cleaned:
                cleaned.append(item)
        return cleaned

    @staticmethod
    def _normalize_cookie_value(value: Any) -> Any:
        if isinstance(value, dict):
            return deepcopy(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("fernet:"):
                return stripped
            try:
                decoded = json.loads(stripped)
            except (TypeError, ValueError):
                return {}
            return decoded if isinstance(decoded, dict) else {}
        return {}

    @classmethod
    def _normalize_settings(cls, loaded: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate and normalize a validated JSON settings object."""
        normalized = cls._default_settings()

        # Unknown JSON keys can belong to a newer feature or plugin. Retain them;
        # json.load has already constrained their values to JSON-safe structures.
        for key, value in loaded.items():
            if key not in cls.DEFAULT_SETTINGS:
                normalized[key] = deepcopy(value)

        for key, default in cls.DEFAULT_SETTINGS.items():
            if key == "settings_schema_version":
                continue
            value = loaded.get(key, deepcopy(default))

            if key == "font_id":
                normalized[key] = normalize_font_id(value, DEFAULT_FONT_ID)
            elif key == "watermark_font_id":
                normalized[key] = normalize_font_id(value, DEFAULT_WATERMARK_FONT_ID)
            elif key == "youtube_upload_interval":
                if isinstance(value, str):
                    try:
                        value = int(value.strip())
                    except (TypeError, ValueError):
                        value = default
                if isinstance(value, bool) or value not in (60, 120, 180, 240):
                    value = default
                normalized[key] = value
            elif key in cls.REMOTE_SECRET_JSON_KEYS:
                normalized[key] = cls._normalize_cookie_value(value)
            elif key == "platform_video_sources":
                sources = cls._coerce_string_list(value, default)
                sources = list(dict.fromkeys(
                    source.lower()
                    for source in sources
                    if source.lower() in cls.VALID_PLATFORM_VIDEO_SOURCES
                ))
                normalized[key] = sources or list(default)
            elif isinstance(default, bool):
                normalized[key] = cls._coerce_bool(value, default)
            elif isinstance(default, list):
                normalized[key] = cls._coerce_string_list(value, default)
            elif isinstance(default, int):
                if isinstance(value, str):
                    try:
                        value = int(value.strip())
                    except (TypeError, ValueError):
                        value = default
                if isinstance(value, bool) or not isinstance(value, int):
                    value = default
                if key == "sourcing_min_similarity_percent":
                    value = max(0, min(100, value))
                normalized[key] = value
            elif isinstance(default, str):
                normalized[key] = value if isinstance(value, str) else default
            else:
                normalized[key] = deepcopy(value)

        normalized["settings_schema_version"] = cls.CURRENT_SETTINGS_SCHEMA_VERSION
        return normalized

    @staticmethod
    def _settings_component(key: str) -> str:
        if key.startswith("youtube_"):
            return "settings.youtube"
        if key.startswith("linktree_") or key == "cookies_inpock":
            return "settings.linktree"
        return "settings.core"

    @classmethod
    def _normalization_issues(
        cls,
        loaded: Dict[str, Any],
        normalized: Dict[str, Any],
        source_path: str,
    ) -> List[Dict[str, str]]:
        components = set()
        if loaded.get("settings_schema_version") != cls.CURRENT_SETTINGS_SCHEMA_VERSION:
            components.add("settings.core")
        for key in cls.DEFAULT_SETTINGS:
            if key in loaded and loaded.get(key) != normalized.get(key):
                components.add(cls._settings_component(key))

        messages = {
            "settings.youtube": "YouTube preferences were normalized to the current settings schema.",
            "settings.linktree": "Linktree preferences were normalized to the current settings schema.",
            "settings.core": "Application preferences were migrated to the current settings schema.",
        }
        return [
            {
                "code": "ST-S002",
                "component": component,
                "message": messages[component],
                "source_path": os.path.abspath(source_path),
            }
            for component in sorted(components)
        ]

    @staticmethod
    def _validated_recovery_issues(value: Any) -> List[Dict[str, str]]:
        if not isinstance(value, list):
            return []
        issues: List[Dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            code = item.get("code")
            component = item.get("component")
            source_path = item.get("source_path")
            if code not in {"ST-S001", "ST-S002", "ST-S003"}:
                continue
            if component not in {
                "settings.core",
                "settings.youtube",
                "settings.linktree",
                "settings.secure_storage",
            }:
                continue
            if not isinstance(source_path, str):
                continue
            messages = {
                ("ST-S001", "settings.core"): (
                    "The settings file could not be parsed, so safe defaults were loaded."
                ),
                ("ST-S002", "settings.core"): (
                    "Application preferences were migrated to the current settings schema."
                ),
                ("ST-S002", "settings.youtube"): (
                    "YouTube preferences were normalized to the current settings schema."
                ),
                ("ST-S002", "settings.linktree"): (
                    "Linktree preferences were normalized to the current settings schema."
                ),
                ("ST-S001", "settings.linktree"): (
                    "Linktree secure settings could not be decrypted and were reset."
                ),
                ("ST-S003", "settings.secure_storage"): (
                    "The OS credential store was unavailable, so local credentials were cleared."
                ),
            }
            safe_issue = {
                "code": code,
                "component": component,
                "message": messages.get(
                    (code, component),
                    "Application preferences required a safe startup recovery.",
                ),
                "source_path": source_path,
            }
            for optional_key in ("recovery_path", "recovered_at"):
                optional_value = item.get(optional_key)
                if isinstance(optional_value, str):
                    safe_issue[optional_key] = optional_value
            issues.append(safe_issue)
        return issues

    @staticmethod
    def _deduplicate_recovery_issues(issues: List[Dict[str, str]]) -> List[Dict[str, str]]:
        unique: List[Dict[str, str]] = []
        seen = set()
        for issue in issues:
            identity = (
                issue.get("code", ""),
                issue.get("component", ""),
                issue.get("source_path", ""),
                issue.get("message", ""),
            )
            if identity not in seen:
                seen.add(identity)
                unique.append(issue)
        return unique

    @staticmethod
    def _read_settings_dict(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as settings_stream:
            loaded = json.load(settings_stream)
        if not isinstance(loaded, dict):
            raise ValueError("settings JSON root must be an object")
        return loaded

    def _recover_invalid_settings(self, source_path: str, error: Exception) -> Dict[str, str]:
        """Copy invalid data aside and return user-support-friendly issue metadata."""
        recovered_at = datetime.now(timezone.utc)
        stamp = recovered_at.strftime("%Y%m%dT%H%M%S%fZ")
        recovery_dir = os.path.join(self._get_settings_dir(), "recovery")
        source_name = os.path.basename(source_path) or "settings.json"
        stem, extension = os.path.splitext(source_name)
        recovery_name = f"{stem}.{stamp}.corrupt{extension or '.json'}"
        recovery_path = os.path.join(recovery_dir, recovery_name)
        try:
            os.makedirs(recovery_dir, exist_ok=True)
            shutil.copy2(source_path, recovery_path)
        except Exception as copy_error:
            recovery_path = ""
            logger.warning("[SettingsManager] Could not copy invalid settings: %s", copy_error)

        invalid_root = isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError)
        metadata = {
            "code": "ST-S002" if invalid_root else "ST-S001",
            "component": "settings.core",
            "message": (
                "The settings file had an invalid schema, so safe defaults were loaded."
                if invalid_root
                else "The settings file could not be parsed, so safe defaults were loaded."
            ),
            "source_path": os.path.abspath(source_path),
            "recovery_path": os.path.abspath(recovery_path) if recovery_path else "",
            "recovered_at": recovered_at.isoformat(),
        }
        return metadata

    @classmethod
    def _empty_secure_setting_value(cls, setting_key: str) -> Any:
        return {} if setting_key in cls.REMOTE_SECRET_JSON_KEYS else ""

    @staticmethod
    def _decrypt_legacy_value(value: str) -> str:
        """Decode an older local Fernet value only for one-time migration."""
        if not value:
            return ""
        if not value.startswith("fernet:"):
            return value
        try:
            from utils.secrets_manager import SecretsManager

            return SecretsManager._simple_decrypt(value)
        except Exception as error:
            logger.warning(
                "[SettingsManager] Legacy secure setting could not be decrypted: %s",
                type(error).__name__,
            )
            return ""

    @classmethod
    def _legacy_secret_text(cls, setting_key: str, raw_value: Any) -> str:
        if setting_key in cls.REMOTE_SECRET_JSON_KEYS:
            if isinstance(raw_value, dict):
                return json.dumps(raw_value, ensure_ascii=False) if raw_value else ""
            if not isinstance(raw_value, str) or not raw_value:
                return ""
            decoded = cls._decrypt_legacy_value(raw_value)
            try:
                parsed = json.loads(decoded) if decoded else {}
            except (TypeError, ValueError):
                return ""
            return json.dumps(parsed, ensure_ascii=False) if isinstance(parsed, dict) and parsed else ""

        if not isinstance(raw_value, str):
            return ""
        return cls._decrypt_legacy_value(raw_value).strip()

    @classmethod
    def _store_secure_credential(cls, setting_key: str, value: str) -> bool:
        credential_key = cls.SECURE_CREDENTIAL_KEYS[setting_key]
        normalized = str(value or "").strip()
        manager = get_secrets_manager()
        try:
            if not normalized:
                manager.delete_credential(credential_key)
                return not bool(manager.get_credential(credential_key))
            if not manager.set_credential(credential_key, normalized):
                return False
            persisted = str(manager.get_credential(credential_key) or "")
            return hmac.compare_digest(persisted, normalized)
        except Exception as error:
            logger.warning(
                "[SettingsManager] OS credential operation failed for %s: %s",
                setting_key,
                type(error).__name__,
            )
            return False

    @classmethod
    def _read_secure_credential(cls, setting_key: str) -> str:
        try:
            return str(
                get_secrets_manager().get_credential(
                    cls.SECURE_CREDENTIAL_KEYS[setting_key]
                )
                or ""
            )
        except Exception as error:
            logger.warning(
                "[SettingsManager] OS credential read failed for %s: %s",
                setting_key,
                type(error).__name__,
            )
            return ""

    def _record_secure_storage_issue(self) -> None:
        with self._lock:
            self._recovery_issues.append(
                {
                    "code": "ST-S003",
                    "component": "settings.secure_storage",
                    "message": (
                        "OS credential storage was unavailable. Local credentials were "
                        "cleared and must be connected again."
                    ),
                    "source_path": os.path.abspath(self._get_settings_path()),
                }
            )
            self._recovery_issues = self._deduplicate_recovery_issues(
                self._recovery_issues
            )
            self._settings["settings_recovery_issues"] = deepcopy(
                self._recovery_issues
            )

    def _migrate_legacy_secret_settings(self) -> None:
        """Move every legacy JSON/Fernet secret to the OS credential store."""
        changed = False
        storage_failed = False
        corrupt_linktree_value = False

        for setting_key in self.SECURE_CREDENTIAL_KEYS:
            with self._lock:
                raw_value = deepcopy(
                    self._settings.get(
                        setting_key,
                        self._empty_secure_setting_value(setting_key),
                    )
                )
            if raw_value in (None, "", {}):
                continue

            secret_text = self._legacy_secret_text(setting_key, raw_value)
            stored = False
            if secret_text:
                stored = self._store_secure_credential(setting_key, secret_text)
                storage_failed = storage_failed or not stored
            elif setting_key in {"linktree_webhook_url", "linktree_api_key"}:
                corrupt_linktree_value = True
            else:
                storage_failed = True
            with self._lock:
                self._settings[setting_key] = self._empty_secure_setting_value(
                    setting_key
                )
                if setting_key in {"linktree_webhook_url", "linktree_api_key"} and not stored:
                    self._settings["linktree_auto_publish"] = False
                if setting_key == "computer_use_bridge_api_key" and not stored:
                    self._settings["computer_use_bridge_enabled"] = False
            changed = True

        if corrupt_linktree_value:
            with self._lock:
                self._recovery_issues.append(
                    {
                        "code": "ST-S001",
                        "component": "settings.linktree",
                        "message": (
                            "Linktree secure settings could not be decrypted and "
                            "were reset."
                        ),
                        "source_path": os.path.abspath(self._get_settings_path()),
                    }
                )
                self._recovery_issues = self._deduplicate_recovery_issues(
                    self._recovery_issues
                )
                self._settings["settings_recovery_issues"] = deepcopy(
                    self._recovery_issues
                )

        if storage_failed:
            self._record_secure_storage_issue()
        if changed or storage_failed:
            self._save_settings(sync_remote=False)

    def _load_settings(self) -> None:
        """Load settings from file (thread-safe)"""
        settings_path = self._get_settings_path()
        needs_save = False
        loaded: Optional[Dict[str, Any]] = None
        source_path = ""
        source_was_invalid = False

        with self._lock:
            if os.path.exists(settings_path):
                source_path = settings_path
                try:
                    loaded = self._read_settings_dict(settings_path)
                except Exception as error:
                    logger.warning("[SettingsManager] Settings loading failed: %s", error)
                    self._recovery_issues.append(
                        self._recover_invalid_settings(settings_path, error)
                    )
                    loaded = {}
                    source_was_invalid = True
                    needs_save = True
            else:
                for legacy_path in self._get_legacy_settings_paths():
                    if not os.path.exists(legacy_path):
                        continue
                    try:
                        loaded = self._read_settings_dict(legacy_path)
                        source_path = legacy_path
                        source_was_invalid = False
                        needs_save = True
                        self._recovery_issues.append(
                            {
                                "code": "ST-S002",
                                "component": "settings.core",
                                "message": "Application preferences were migrated from a legacy settings location.",
                                "source_path": os.path.abspath(legacy_path),
                            }
                        )
                        logger.info("[SettingsManager] Migrating settings from %s", legacy_path)
                        break
                    except Exception as error:
                        logger.warning("[SettingsManager] Legacy settings invalid: %s", error)
                        self._recovery_issues.append(
                            self._recover_invalid_settings(legacy_path, error)
                        )
                        needs_save = True

            if loaded is None:
                self._settings = self._default_settings()
            else:
                self._settings = self._normalize_settings(loaded)
                self._recovery_issues.extend(
                    self._validated_recovery_issues(loaded.get("settings_recovery_issues"))
                )
                if not source_was_invalid:
                    self._recovery_issues.extend(
                        self._normalization_issues(loaded, self._settings, source_path)
                    )
                needs_save = needs_save or self._settings != loaded

            self._recovery_issues = self._deduplicate_recovery_issues(self._recovery_issues)
            if self._recovery_issues:
                self._settings["settings_recovery_issues"] = deepcopy(self._recovery_issues)

            # Reset accidental/test watermark defaults (avoid shipping dev watermark).
            user_cfg = self._settings.get("watermark_user_configured", False)
            enabled = self._settings.get("watermark_enabled", False)
            channel = self._settings.get("watermark_channel_name", "").strip()
            suspicious = (not channel) or ("?" in channel) or ("\ufffd" in channel) or (channel == "와이엠")
            if enabled and (not user_cfg) and suspicious:
                self._settings["watermark_enabled"] = False
                self._settings["watermark_channel_name"] = ""
                logger.info("[SettingsManager] Reset suspicious watermark defaults")
                needs_save = True

        # Save outside the lock so _save_settings can acquire it normally.
        if needs_save:
            if not self._save_settings(sync_remote=False):
                logger.warning("[SettingsManager] Could not persist normalized settings from %s", source_path)

        # Secret-bearing settings from older releases must never remain in the
        # JSON preferences file, even when OS credential storage is unavailable.
        self._migrate_legacy_secret_settings()

    def _save_settings(self, sync_remote: bool = True) -> bool:
        """Save settings to file (thread-safe)"""
        settings_path = self._get_settings_path()
        temporary_path = ""

        try:
            with self._lock:
                settings_dir = os.path.dirname(settings_path) or "."
                os.makedirs(settings_dir, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=settings_dir,
                    prefix=f".{os.path.basename(settings_path)}.",
                    suffix=".tmp",
                    delete=False,
                ) as settings_stream:
                    temporary_path = settings_stream.name
                    json.dump(self._settings, settings_stream, ensure_ascii=False, indent=2)
                    settings_stream.flush()
                    os.fsync(settings_stream.fileno())
                os.replace(temporary_path, settings_path)
                temporary_path = ""
            logger.debug(f"[SettingsManager] Settings saved: {settings_path}")
            if sync_remote:
                self.schedule_remote_push()
            return True
        except Exception as e:
            if temporary_path:
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass
            logger.error(f"[SettingsManager] Settings save failed: {e}")
            return False

    # ============ Account Settings Sync ============

    @staticmethod
    def _remote_sync_disabled() -> bool:
        return os.getenv("SSMAKER_DISABLE_REMOTE_SETTINGS_SYNC", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _export_remote_settings(self) -> Dict[str, Any]:
        """
        Build a portable settings snapshot for account sync.

        Credentials and browser cookies are device-local and intentionally omitted.
        This prevents the account-settings snapshot from becoming a second secret
        store and causes a successful push to scrub legacy server-side copies.
        """
        with self._lock:
            snapshot = self._settings.copy()

        exported: Dict[str, Any] = {}
        for key, value in snapshot.items():
            if key == "settings_recovery_issues":
                # Diagnostics contain local file paths and are intentionally
                # device-local rather than part of account settings sync.
                continue
            if key in self.REMOTE_SECRET_STRING_KEYS or key in self.REMOTE_SECRET_JSON_KEYS:
                continue
            exported[key] = value
        return exported

    def _prepare_remote_settings_for_local(self, remote_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a portable server snapshot into local encrypted settings."""
        if not isinstance(remote_settings, dict):
            remote_settings = {}

        remote_copy = deepcopy(remote_settings)
        legacy_secret_values = {
            key: remote_copy.pop(key)
            for key in self.SECURE_CREDENTIAL_KEYS
            if key in remote_copy
        }

        prepared = self._normalize_settings(remote_copy)
        prepared.pop("settings_recovery_issues", None)

        storage_failed = False
        for key in self.SECURE_CREDENTIAL_KEYS:
            prepared[key] = self._empty_secure_setting_value(key)
            raw_value = legacy_secret_values.get(key)
            if raw_value in (None, "", {}):
                continue
            secret_text = self._legacy_secret_text(key, raw_value)
            if not secret_text or not self._store_secure_credential(key, secret_text):
                storage_failed = True

        if storage_failed:
            issue = {
                "code": "ST-S003",
                "component": "settings.secure_storage",
                "message": (
                    "OS credential storage was unavailable. Synced credentials "
                    "were rejected and must be connected again."
                ),
                "source_path": os.path.abspath(self._get_settings_path()),
            }
            self._recovery_issues = self._deduplicate_recovery_issues(
                [*self._recovery_issues, issue]
            )
            prepared["settings_recovery_issues"] = deepcopy(
                self._recovery_issues
            )

        return prepared

    def apply_remote_settings(self, remote_settings: Dict[str, Any]) -> bool:
        """Apply a settings snapshot pulled from the authenticated account."""
        prepared = self._prepare_remote_settings_for_local(remote_settings)
        with self._lock:
            self._settings = prepared
        saved = self._save_settings(sync_remote=False)
        self.sync_launch_on_startup()
        return saved

    def push_remote_settings(self) -> bool:
        """Upload the current local settings snapshot to the authenticated account."""
        if self._remote_sync_disabled():
            return False
        try:
            from caller import rest

            payload = self._export_remote_settings()
            result = rest.save_user_settings(payload)
            ok = bool(isinstance(result, dict) and result.get("success"))
            if ok:
                logger.debug("[SettingsSync] Remote settings saved")
            else:
                logger.debug("[SettingsSync] Remote settings save skipped/failed: %s", result)
            return ok
        except Exception as exc:
            logger.debug("[SettingsSync] Remote push failed: %s", exc)
            return False

    def pull_remote_settings(self) -> bool:
        """Download and apply settings from the authenticated account, if present."""
        if self._remote_sync_disabled():
            return False
        try:
            from caller import rest

            result = rest.fetch_user_settings()
            if not (isinstance(result, dict) and result.get("success")):
                logger.debug("[SettingsSync] Remote settings fetch skipped/failed: %s", result)
                return False

            remote_settings = result.get("settings")
            if not isinstance(remote_settings, dict) or not remote_settings:
                return False

            if self.apply_remote_settings(remote_settings):
                logger.info("[SettingsSync] Remote settings loaded")
                return True
            return False
        except Exception as exc:
            logger.debug("[SettingsSync] Remote pull failed: %s", exc)
            return False

    def sync_with_remote(self, login_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Enable account sync and reconcile local settings after login.

        Remote values win when they exist so a user logging in on another device
        immediately gets their saved setup. If no remote snapshot exists yet, the
        current local setup seeds the account.
        """
        if self._remote_sync_disabled():
            return False
        self._remote_sync_enabled = True
        pulled = self.pull_remote_settings()
        if pulled:
            return True
        return self.push_remote_settings()

    def schedule_remote_push(self) -> None:
        """Best-effort non-blocking upload after local settings changes."""
        if (
            self._remote_sync_disabled()
            or not self._remote_sync_enabled
            or self._remote_push_running
        ):
            return
        self._remote_push_running = True

        def _worker() -> None:
            with self._remote_lock:
                try:
                    self.push_remote_settings()
                finally:
                    self._remote_push_running = False

        threading.Thread(target=_worker, daemon=True).start()

    # ============ CTA Settings ============

    def get_cta_id(self) -> str:
        """Get the saved CTA selection ID"""
        return self._settings.get("cta_id", "default")

    def set_cta_id(self, cta_id: str) -> bool:
        """
        Save the CTA selection.

        Args:
            cta_id: The CTA option ID to save

        Returns:
            True if save was successful
        """
        self._settings["cta_id"] = cta_id
        return self._save_settings()

    # ============ Font Settings ============

    def get_font_id(self) -> str:
        """Get the saved font selection ID"""
        return normalize_font_id(self._settings.get("font_id"), DEFAULT_FONT_ID)

    def set_font_id(self, font_id: str) -> bool:
        """
        Save the font selection.

        Args:
            font_id: The font option ID to save

        Returns:
            True if save was successful
        """
        self._settings["font_id"] = normalize_font_id(font_id, DEFAULT_FONT_ID)
        return self._save_settings()

    # ============ Voice Settings ============

    def get_selected_voices(self) -> List[str]:
        """Get the list of selected voice IDs"""
        return self._settings.get("selected_voices", [])

    def set_selected_voices(self, voice_ids: List[str]) -> bool:
        """
        Save the selected voices.

        Args:
            voice_ids: List of voice IDs that are selected

        Returns:
            True if save was successful
        """
        self._settings["selected_voices"] = list(voice_ids)
        return self._save_settings()

    def get_gender_filter(self) -> str:
        """Get the saved gender filter setting"""
        return self._settings.get("gender_filter", "all")

    def set_gender_filter(self, gender: str) -> bool:
        """
        Save the gender filter setting.

        Args:
            gender: 'all', 'male', or 'female'

        Returns:
            True if save was successful
        """
        self._settings["gender_filter"] = gender
        return self._save_settings()

    # ============ Output Folder Settings ============

    def get_output_folder(self) -> str:
        """Get the saved output folder path"""
        return self._settings.get("output_folder", "")

    def set_output_folder(self, folder_path: str) -> bool:
        """
        Save the output folder path with validation.

        Args:
            folder_path: The folder path to save videos to

        Returns:
            True if save was successful, False if path is invalid
        """
        # Validate path: empty string is allowed (means use default desktop)
        if folder_path and not os.path.isdir(folder_path):
            logger.warning(f"[SettingsManager] Invalid output folder path: {folder_path}")
            return False
        self._settings["output_folder"] = folder_path
        return self._save_settings()

    # ============ Startup Settings ============

    def get_launch_on_startup(self) -> bool:
        """Get whether SSMaker should start automatically after Windows login."""
        return bool(self._settings.get("launch_on_startup", True))

    def sync_launch_on_startup(self) -> bool:
        """Apply the saved launch-on-startup preference to the OS."""
        if self.settings_file != "ui_preferences.json":
            return True
        try:
            from utils.autostart import sync_launch_on_startup

            return sync_launch_on_startup(self.get_launch_on_startup())
        except Exception as exc:
            logger.warning("[SettingsManager] Launch-on-startup sync failed: %s", exc)
            return False

    def set_launch_on_startup(self, enabled: bool) -> bool:
        """Save and immediately apply the launch-on-startup setting."""
        with self._lock:
            previous = bool(self._settings.get("launch_on_startup", True))
            self._settings["launch_on_startup"] = bool(enabled)
        saved = self._save_settings()
        if not saved:
            with self._lock:
                self._settings["launch_on_startup"] = previous
            return False
        synced = self.sync_launch_on_startup()
        if synced:
            return True
        with self._lock:
            self._settings["launch_on_startup"] = previous
        self._save_settings()
        return False

    # ============ Theme Settings ============

    def get_theme(self) -> str:
        """Get the saved theme setting"""
        return self._settings.get("theme", "light")

    def set_theme(self, theme: str) -> bool:
        """
        Save the theme setting.

        Args:
            theme: 'light' or 'dark'

        Returns:
            True if save was successful
        """
        if theme not in ("light", "dark"):
            theme = "light"
        self._settings["theme"] = theme
        return self._save_settings()

    # ============ Tutorial Settings ============

    def is_first_run(self) -> bool:
        """
        Check if this is the first run (tutorial not completed).

        Returns:
            True if tutorial has not been completed yet
        """
        return not self._settings.get("tutorial_completed", False)

    def mark_tutorial_completed(self) -> bool:
        """
        Mark the tutorial as completed.

        Returns:
            True if save was successful
        """
        self._settings["tutorial_completed"] = True
        return self._save_settings()

    def reset_tutorial(self) -> bool:
        """
        Reset tutorial status to show it again on next run.

        Returns:
            True if save was successful
        """
        self._settings["tutorial_completed"] = False
        return self._save_settings()

    # ============ Watermark Settings ============

    def get_watermark_enabled(self) -> bool:
        """Get whether watermark is enabled"""
        return self._settings.get("watermark_enabled", False)

    def set_watermark_enabled(self, enabled: bool) -> bool:
        """
        Save the watermark enabled setting.

        Args:
            enabled: True to enable watermark

        Returns:
            True if save was successful
        """
        with self._lock:
            self._settings["watermark_enabled"] = bool(enabled)
            self._settings["watermark_user_configured"] = True
        return self._save_settings()

    def get_watermark_channel_name(self) -> str:
        """Get the watermark channel name"""
        return self._settings.get("watermark_channel_name", "")

    def set_watermark_channel_name(self, name: str) -> bool:
        """
        Save the watermark channel name.

        Args:
            name: Channel name to display as watermark (max 50 characters)

        Returns:
            True if save was successful
        """
        # 최대 50자로 제한하여 UI 렌더링 문제 방지
        MAX_CHANNEL_NAME_LENGTH = 50
        sanitized = str(name).strip()[:MAX_CHANNEL_NAME_LENGTH]
        with self._lock:
            self._settings["watermark_channel_name"] = sanitized
            self._settings["watermark_user_configured"] = True
        return self._save_settings()

    def get_watermark_position(self) -> str:
        """Get the watermark position"""
        return self._settings.get("watermark_position", "bottom_right")

    def set_watermark_position(self, position: str) -> bool:
        """
        Save the watermark position.

        Args:
            position: One of 'top_left', 'top_right', 'bottom_left', 'bottom_right'

        Returns:
            True if save was successful
        """
        valid_positions = ("top_left", "top_right", "bottom_left", "bottom_right")
        if position not in valid_positions:
            position = "bottom_right"
        with self._lock:
            self._settings["watermark_position"] = position
            self._settings["watermark_user_configured"] = True
        return self._save_settings()

    def get_watermark_font_id(self) -> str:
        """Get the watermark font ID"""
        return normalize_font_id(
            self._settings.get("watermark_font_id"), DEFAULT_WATERMARK_FONT_ID
        )

    def set_watermark_font_id(self, font_id: str) -> bool:
        """
        Save the watermark font ID.

        Args:
            font_id: A font ID from ``config.font_catalog``.

        Returns:
            True if save was successful
        """
        font_id = normalize_font_id(font_id, DEFAULT_WATERMARK_FONT_ID)
        with self._lock:
            self._settings["watermark_font_id"] = font_id
            self._settings["watermark_user_configured"] = True
        return self._save_settings()

    def get_watermark_font_size(self) -> str:
        """Get the watermark font size key"""
        return self._settings.get("watermark_font_size", "medium")

    def set_watermark_font_size(self, size: str) -> bool:
        """
        Save the watermark font size.

        Args:
            size: One of 'small', 'medium', 'large'

        Returns:
            True if save was successful
        """
        valid_sizes = ("small", "medium", "large")
        if size not in valid_sizes:
            size = "medium"
        with self._lock:
            self._settings["watermark_font_size"] = size
            self._settings["watermark_user_configured"] = True
        return self._save_settings()

    def get_watermark_settings(self) -> Dict[str, Any]:
        """Get all watermark settings as a dictionary"""
        return {
            "enabled": self.get_watermark_enabled(),
            "channel_name": self.get_watermark_channel_name(),
            "position": self.get_watermark_position(),
            "font_id": self.get_watermark_font_id(),
            "font_size": self.get_watermark_font_size(),
        }

    # ============ Subtitle Settings ============

    def get_subtitle_settings(self) -> Dict[str, Any]:
        """Get all subtitle settings as a dictionary"""
        return {
            "overlay_on_chinese": self._settings.get("subtitle_overlay_on_chinese", True),
            "position": self._settings.get("subtitle_position", "bottom_center"),
            "custom_y_percent": self._settings.get("subtitle_custom_y_percent", 80.0),
        }

    def set_subtitle_overlay_on_chinese(self, enabled: bool) -> bool:
        """Save whether to overlay Korean subtitle on Chinese subtitle position"""
        with self._lock:
            self._settings["subtitle_overlay_on_chinese"] = bool(enabled)
        return self._save_settings()

    def set_subtitle_position(self, position: str) -> bool:
        """Save Korean subtitle position"""
        valid = ("top_center", "middle_center", "bottom_center", "custom")
        if position not in valid:
            position = "bottom_center"
        with self._lock:
            self._settings["subtitle_position"] = position
        return self._save_settings()

    def set_subtitle_custom_y(self, y_percent: float) -> bool:
        """Save custom subtitle Y position (5-95%)"""
        y_percent = max(5.0, min(95.0, float(y_percent)))
        with self._lock:
            self._settings["subtitle_custom_y_percent"] = y_percent
        return self._save_settings()

    # ============ Social Media Connection Settings ============

    @staticmethod
    def _normalize_account_email(email: str) -> str:
        return str(email or "").strip().lower()

    def _sync_youtube_connection_from_disk(self) -> None:
        """Refresh UI YouTube state from the token/channel files used by uploads."""
        if self.settings_file != "ui_preferences.json":
            return

        try:
            settings_dir = self._get_settings_dir()
            token_path = os.path.join(settings_dir, "youtube_token.json")
            token_exists = bool(
                get_secrets_manager().get_credential(YOUTUBE_OAUTH_TOKEN_KEY)
            ) or (os.path.exists(token_path) and os.path.getsize(token_path) > 0)

            channel: Dict[str, Any] = {}
            upload_settings: Dict[str, Any] = {}
            youtube_settings_path = os.path.join(settings_dir, "youtube_settings.json")
            if os.path.exists(youtube_settings_path):
                with open(youtube_settings_path, "r", encoding="utf-8-sig") as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    raw_channel = payload.get("channel")
                    raw_upload = payload.get("upload_settings")
                    if isinstance(raw_channel, dict):
                        channel = raw_channel
                    if isinstance(raw_upload, dict):
                        upload_settings = raw_upload

            with self._lock:
                current_channel_id = str(self._settings.get("youtube_channel_id", "") or "").strip()
                current_channel_name = str(self._settings.get("youtube_channel_name", "") or "").strip()
                current_email = self._normalize_account_email(
                    self._settings.get("youtube_account_email", "")
                )

            channel_id = str(channel.get("channel_id") or current_channel_id).strip()
            channel_name = str(channel.get("channel_name") or current_channel_name).strip()
            account_email = self._normalize_account_email(
                channel.get("account_email") or current_email
            )
            connected = bool(token_exists and channel_id)

            changed = False
            with self._lock:
                if connected:
                    updates = {
                        "youtube_connected": True,
                        "youtube_channel_id": channel_id,
                        "youtube_channel_name": channel_name,
                        "youtube_account_email": account_email,
                    }
                    if account_email and not self._settings.get("youtube_expected_account_email"):
                        updates["youtube_expected_account_email"] = account_email
                    if "enabled" in upload_settings:
                        updates["youtube_auto_upload"] = bool(upload_settings.get("enabled"))
                    interval = upload_settings.get("interval_minutes")
                    if interval:
                        try:
                            updates["youtube_upload_interval"] = int(interval)
                        except (TypeError, ValueError):
                            pass
                    for key, value in updates.items():
                        if self._settings.get(key) != value:
                            self._settings[key] = value
                            changed = True
                elif self._settings.get("youtube_connected") and not token_exists:
                    self._settings["youtube_connected"] = False
                    changed = True

            if changed:
                self._save_settings(sync_remote=False)
        except Exception as exc:
            logger.debug("[SettingsManager] YouTube disk sync skipped: %s", exc)

    def get_youtube_connected(self) -> bool:
        """Get YouTube connection status"""
        self._sync_youtube_connection_from_disk()
        return self._settings.get("youtube_connected", False)

    def set_youtube_connected(
        self,
        connected: bool,
        channel_id: str = "",
        channel_name: str = "",
        account_email: Optional[str] = None,
    ) -> bool:
        """Save YouTube connection status"""
        with self._lock:
            self._settings["youtube_connected"] = bool(connected)
            self._settings["youtube_channel_id"] = channel_id
            self._settings["youtube_channel_name"] = channel_name
            if account_email is not None:
                self._settings["youtube_account_email"] = self._normalize_account_email(account_email)
            if not connected:
                self._settings["youtube_account_email"] = ""
        return self._save_settings()

    def get_youtube_channel_info(self) -> Dict[str, str]:
        """Get YouTube channel info"""
        self._sync_youtube_connection_from_disk()
        return {
            "channel_id": self._settings.get("youtube_channel_id", ""),
            "channel_name": self._settings.get("youtube_channel_name", ""),
            "account_email": self._settings.get("youtube_account_email", ""),
            "expected_account_email": self._settings.get("youtube_expected_account_email", ""),
        }

    def get_youtube_account_email(self) -> str:
        """Get the verified Google account email used by YouTube OAuth."""
        self._sync_youtube_connection_from_disk()
        return self._normalize_account_email(self._settings.get("youtube_account_email", ""))

    def set_youtube_account_email(self, email: str) -> bool:
        """Save the verified Google account email used by YouTube OAuth."""
        with self._lock:
            self._settings["youtube_account_email"] = self._normalize_account_email(email)
        return self._save_settings()

    def get_youtube_expected_account_email(self) -> str:
        """Get the required Google account email for YouTube uploads."""
        return self._normalize_account_email(self._settings.get("youtube_expected_account_email", ""))

    def set_youtube_expected_account_email(self, email: str) -> bool:
        """Save the required Google account email for YouTube uploads."""
        with self._lock:
            self._settings["youtube_expected_account_email"] = self._normalize_account_email(email)
        return self._save_settings()

    def get_youtube_account_verification(self) -> Dict[str, Any]:
        """Return whether the connected YouTube OAuth account matches expectation."""
        expected = self.get_youtube_expected_account_email()
        actual = self.get_youtube_account_email()
        if not expected:
            return {"required": False, "ok": True, "expected": "", "actual": actual, "message": ""}
        if not actual:
            return {
                "required": True,
                "ok": False,
                "expected": expected,
                "actual": "",
                "message": (
                    "YouTube 기대 계정 이메일이 설정되어 있지만 OAuth 계정 이메일이 확인되지 않았습니다. "
                    "YouTube 채널을 다시 연결해 이메일 권한을 승인하세요."
                ),
            }
        if actual != expected:
            return {
                "required": True,
                "ok": False,
                "expected": expected,
                "actual": actual,
                "message": f"YouTube 연결 계정이 다릅니다. 기대: {expected}, 현재: {actual}",
            }
        return {"required": True, "ok": True, "expected": expected, "actual": actual, "message": ""}

    def get_youtube_auto_upload(self) -> bool:
        """Get YouTube auto-upload enabled status"""
        self._sync_youtube_connection_from_disk()
        return self._settings.get("youtube_auto_upload", False)

    def set_youtube_auto_upload(self, enabled: bool) -> bool:
        """Save YouTube auto-upload setting"""
        with self._lock:
            self._settings["youtube_auto_upload"] = bool(enabled)
        return self._save_settings()

    def get_youtube_upload_interval(self) -> int:
        """Get YouTube upload interval in minutes"""
        self._sync_youtube_connection_from_disk()
        return self._settings.get("youtube_upload_interval", 60)

    def set_youtube_upload_interval(self, interval_minutes: int) -> bool:
        """Save YouTube upload interval (60, 120, 180, 240 minutes)"""
        valid_intervals = (60, 120, 180, 240)
        if interval_minutes not in valid_intervals:
            interval_minutes = 60
        with self._lock:
            self._settings["youtube_upload_interval"] = interval_minutes
        return self._save_settings()

    def get_social_connection_status(self, platform: str) -> bool:
        """Get connection status for a social platform"""
        key = f"{platform}_connected"
        return self._settings.get(key, False)

    def set_social_connection_status(self, platform: str, connected: bool, account_name: str = "") -> bool:
        """Save connection status for non-YouTube social platforms."""
        normalized = str(platform or "").strip().lower()
        if normalized == "youtube":
            return self.set_youtube_connected(bool(connected), channel_name=str(account_name or "").strip())

        if normalized not in {"tiktok", "instagram", "threads", "x"}:
            logger.warning("[SettingsManager] Unsupported social platform: %s", platform)
            return False

        with self._lock:
            self._settings[f"{normalized}_connected"] = bool(connected)
            if account_name:
                self._settings[f"{normalized}_account_name"] = str(account_name).strip()
            elif not connected:
                self._settings[f"{normalized}_account_name"] = ""
        return self._save_settings()

    def get_social_account_name(self, platform: str) -> str:
        """Get stored account display name/identifier for a social platform."""
        normalized = str(platform or "").strip().lower()
        if normalized == "youtube":
            return str(self._settings.get("youtube_channel_name", "") or "").strip()
        return str(self._settings.get(f"{normalized}_account_name", "") or "").strip()

    def get_upload_settings(self) -> Dict[str, Any]:
        """Get all upload-related settings"""
        coupang_keys = self.get_coupang_keys()
        linktree_settings = self.get_linktree_settings()
        return {
            "youtube_connected": self.get_youtube_connected(),
            "youtube_channel_info": self.get_youtube_channel_info(),
            "youtube_account_verification": self.get_youtube_account_verification(),
            "youtube_auto_upload": self.get_youtube_auto_upload(),
            "youtube_upload_interval": self.get_youtube_upload_interval(),
            "tiktok_connected": self._settings.get("tiktok_connected", False),
            "instagram_connected": self._settings.get("instagram_connected", False),
            "threads_connected": self._settings.get("threads_connected", False),
            "x_connected": self._settings.get("x_connected", False),
            "coupang_connected": bool(
                coupang_keys.get("access_key") and coupang_keys.get("secret_key")
            ),
            "linktree_connected": bool(linktree_settings.get("webhook_url")),
            "linktree_account_verification": self.get_linktree_account_verification(),
            "inpock_connected": bool(self.get_inpock_cookies()),
        }

    # ============ Codex CLI Bridge Settings ============

    def get_codex_cli_settings(self) -> Dict[str, Any]:
        """Get Codex CLI bridge settings used by setup assistant."""
        path = str(self._settings.get("codex_cli_path", "") or "").strip() or "codex"
        model = str(self._settings.get("codex_cli_model", "") or "").strip()
        enabled = bool(self._settings.get("codex_cli_enabled", True))
        return {
            "enabled": enabled,
            "path": path,
            "model": model,
        }

    def set_codex_cli_settings(
        self,
        path: str = "codex",
        model: str = "",
        enabled: Optional[bool] = None,
    ) -> bool:
        """Save Codex CLI bridge settings for setup assistant."""
        normalized_path = str(path or "").strip() or "codex"
        normalized_model = str(model or "").strip()
        with self._lock:
            self._settings["codex_cli_path"] = normalized_path
            self._settings["codex_cli_model"] = normalized_model
            if enabled is not None:
                self._settings["codex_cli_enabled"] = bool(enabled)
        return self._save_settings()

    def get_computer_use_settings(self) -> Dict[str, Any]:
        """Get computer-use policy and optional server-bridge settings."""
        bridge_url = str(self._settings.get("computer_use_bridge_url", "") or "").strip()
        bridge_api_key = self._read_secure_credential(
            "computer_use_bridge_api_key"
        ).strip()
        paid_only = bool(self._settings.get("computer_use_paid_only", True))
        bridge_enabled = bool(self._settings.get("computer_use_bridge_enabled", False))
        return {
            "paid_only": paid_only,
            "bridge_enabled": bridge_enabled,
            "bridge_url": bridge_url,
            "bridge_api_key": bridge_api_key,
        }

    def set_computer_use_settings(
        self,
        *,
        paid_only: Optional[bool] = None,
        bridge_enabled: Optional[bool] = None,
        bridge_url: Optional[str] = None,
        bridge_api_key: Optional[str] = None,
    ) -> bool:
        """Save computer-use policy and optional server-bridge settings."""
        if bridge_api_key is not None and not self._store_secure_credential(
            "computer_use_bridge_api_key",
            str(bridge_api_key or "").strip(),
        ):
            self._record_secure_storage_issue()
            return False
        with self._lock:
            if paid_only is not None:
                self._settings["computer_use_paid_only"] = bool(paid_only)
            if bridge_enabled is not None:
                self._settings["computer_use_bridge_enabled"] = bool(bridge_enabled)
            if bridge_url is not None:
                self._settings["computer_use_bridge_url"] = str(bridge_url or "").strip()
            if bridge_api_key is not None:
                self._settings["computer_use_bridge_api_key"] = ""
        return self._save_settings()

    def get_sourcing_ai_policy(self) -> Dict[str, Any]:
        """
        Get sourcing AI provider policy.

        Product sourcing automation is fixed to Gemini guidance path and
        explicitly excludes Codex computer-use execution.
        """
        provider = str(self._settings.get("sourcing_ai_provider", "gemini") or "gemini").strip().lower()
        if provider != "gemini":
            provider = "gemini"
        return {
            "provider": provider,
            "use_gemini_computer_use": bool(self._settings.get("sourcing_use_gemini_computer_use", True)),
            "use_codex_computer_use": False,
        }

    def set_sourcing_ai_policy(
        self,
        *,
        use_gemini_computer_use: Optional[bool] = None,
    ) -> bool:
        """
        Persist sourcing AI policy.

        Codex computer-use is forcibly disabled for product sourcing.
        """
        with self._lock:
            self._settings["sourcing_ai_provider"] = "gemini"
            if use_gemini_computer_use is not None:
                self._settings["sourcing_use_gemini_computer_use"] = bool(use_gemini_computer_use)
            # Hard guard requested by product policy/user requirement.
            self._settings["sourcing_use_codex_computer_use"] = False
        return self._save_settings()

    @staticmethod
    def _coerce_similarity_percent(value: Any) -> int:
        try:
            percent = int(round(float(value)))
        except (TypeError, ValueError):
            percent = 90
        return max(0, min(100, percent))

    def get_sourcing_match_policy(self) -> Dict[str, Any]:
        """Get strict product-match policy for Mode 3 sourcing automation."""
        percent = self._coerce_similarity_percent(
            self._settings.get("sourcing_min_similarity_percent", 90)
        )
        return {
            "min_similarity_percent": percent,
            "min_similarity_score": percent / 100.0,
            "auto_skip_low_similarity": bool(
                self._settings.get("sourcing_auto_skip_low_similarity", False)
            ),
        }

    def set_sourcing_match_policy(
        self,
        *,
        min_similarity_percent: Optional[float] = None,
        auto_skip_low_similarity: Optional[bool] = None,
    ) -> bool:
        """Persist strict product-match policy for Mode 3 sourcing automation."""
        with self._lock:
            if min_similarity_percent is not None:
                self._settings["sourcing_min_similarity_percent"] = (
                    self._coerce_similarity_percent(min_similarity_percent)
                )
            if auto_skip_low_similarity is not None:
                self._settings["sourcing_auto_skip_low_similarity"] = bool(
                    auto_skip_low_similarity
                )
        return self._save_settings()

    # ============ Full-automation sourcing method ============

    VALID_SOURCING_METHODS = ("coupang", "platform_video")

    def get_automation_sourcing_method(self) -> str:
        """풀자동화 소싱 방식. 기존 coupang 설정은 3플랫폼 방식으로 자동 이전한다."""
        value = str(
            self._settings.get("automation_sourcing_method", "platform_video")
            or "platform_video"
        ).strip()
        if value == "coupang":
            return "platform_video"
        return value if value in self.VALID_SOURCING_METHODS else "platform_video"

    def set_automation_sourcing_method(self, method: str) -> bool:
        """Persist the full-automation sourcing method."""
        normalized = str(method or "").strip()
        if normalized not in self.VALID_SOURCING_METHODS:
            logger.warning("[SettingsManager] Unsupported sourcing method: %s", method)
            return False
        with self._lock:
            self._settings["automation_sourcing_method"] = normalized
        return self._save_settings()

    DEFAULT_PLATFORM_VIDEO_SOURCES = ["douyin", "xiaohongshu", "kuaishou"]
    VALID_PLATFORM_VIDEO_SOURCES = {"douyin", "xiaohongshu", "kuaishou"}

    def get_platform_video_sources(self) -> List[str]:
        """Enabled short-video platforms for platform_video method."""
        raw = self._settings.get("platform_video_sources", list(self.DEFAULT_PLATFORM_VIDEO_SOURCES))
        cleaned = list(dict.fromkeys(
            str(x).strip().lower() for x in (raw or [])
            if str(x).strip().lower() in self.VALID_PLATFORM_VIDEO_SOURCES
        ))
        # Migrate every historical unattended default to the new product-video
        # policy. Bilibili is intentionally removed: full automation now uses
        # only commerce-heavy Xiaohongshu, Douyin and Kuaishou clips.
        if cleaned in (
            ["douyin", "kuaishou"],
            ["douyin", "kuaishou", "xiaohongshu"],
            ["xiaohongshu", "douyin", "kuaishou"],
        ):
            return list(self.DEFAULT_PLATFORM_VIDEO_SOURCES)
        return cleaned or list(self.DEFAULT_PLATFORM_VIDEO_SOURCES)

    def set_platform_video_sources(self, sources: List[str]) -> bool:
        """Persist enabled short-video platforms."""
        cleaned = list(dict.fromkeys(
            str(x).strip().lower() for x in (sources or [])
            if str(x).strip().lower() in self.VALID_PLATFORM_VIDEO_SOURCES
        ))
        with self._lock:
            self._settings["platform_video_sources"] = cleaned or list(self.DEFAULT_PLATFORM_VIDEO_SOURCES)
        return self._save_settings()

    # ============ Upload Prompt Settings ============

    def get_platform_prompts(self, platform: str) -> Dict[str, str]:
        """Get upload prompts for a platform (title, description, hashtag)"""
        defaults = self.DEFAULT_PLATFORM_PROMPTS.get(platform, {})
        title_prompt = self._settings.get(f"{platform}_title_prompt", "")
        description_prompt = self._settings.get(f"{platform}_description_prompt", "")
        hashtag_prompt = self._settings.get(f"{platform}_hashtag_prompt", "")

        return {
            "title_prompt": str(title_prompt).strip() or defaults.get("title_prompt", ""),
            "description_prompt": str(description_prompt).strip() or defaults.get("description_prompt", ""),
            "hashtag_prompt": str(hashtag_prompt).strip() or defaults.get("hashtag_prompt", ""),
        }

    def set_platform_prompts(self, platform: str, title_prompt: str = "",
                             description_prompt: str = "", hashtag_prompt: str = "") -> bool:
        """Save upload prompts for a platform"""
        with self._lock:
            self._settings[f"{platform}_title_prompt"] = title_prompt
            self._settings[f"{platform}_description_prompt"] = description_prompt
            self._settings[f"{platform}_hashtag_prompt"] = hashtag_prompt
        return self._save_settings()

    def get_youtube_comment_enabled(self) -> bool:
        """Get YouTube comment auto-upload setting"""
        return self._settings.get("youtube_comment_enabled", False)

    def set_youtube_comment_enabled(self, enabled: bool) -> bool:
        """Save YouTube comment auto-upload setting"""
        with self._lock:
            self._settings["youtube_comment_enabled"] = bool(enabled)
        return self._save_settings()

    def get_youtube_comment_prompt(self) -> str:
        """Get YouTube auto-comment prompt"""
        prompt = str(self._settings.get("youtube_comment_prompt", "") or "").strip()
        return prompt or self.DEFAULT_YOUTUBE_COMMENT_PROMPT

    def set_youtube_comment_prompt(self, prompt: str) -> bool:
        """Save YouTube auto-comment prompt"""
        with self._lock:
            self._settings["youtube_comment_prompt"] = prompt
        return self._save_settings()

    def get_youtube_comment_manual_product_link(self) -> str:
        """Get optional manual Coupang original product link for auto-comments."""
        return str(self._settings.get("youtube_comment_manual_product_link", "") or "").strip()

    def set_youtube_comment_manual_product_link(self, url: str) -> bool:
        """Save optional manual Coupang original product link for auto-comments."""
        with self._lock:
            self._settings["youtube_comment_manual_product_link"] = str(url or "").strip()
        return self._save_settings()

    # ============ Automation Settings ============

    def get_coupang_keys(self) -> Dict[str, str]:
        """Get device-local Coupang Partners API keys from OS storage."""
        return {
            "access_key": self._read_secure_credential("coupang_access_key"),
            "secret_key": self._read_secure_credential("coupang_secret_key"),
        }

    def set_coupang_keys(self, access_key: str, secret_key: str) -> bool:
        """Save Coupang Partners API keys in the OS credential store."""
        values = {
            "coupang_access_key": str(access_key or "").strip(),
            "coupang_secret_key": str(secret_key or "").strip(),
        }
        if not all(
            self._store_secure_credential(key, value)
            for key, value in values.items()
        ):
            self._record_secure_storage_issue()
            return False
        with self._lock:
            self._settings["coupang_access_key"] = ""
            self._settings["coupang_secret_key"] = ""
        return self._save_settings()

    def get_linktree_settings(self) -> Dict[str, Any]:
        """Get Linktree webhook integration settings."""
        profile_url = str(self._settings.get("linktree_profile_url", "") or "").strip()
        account_email = self._normalize_account_email(self._settings.get("linktree_account_email", ""))
        expected_account_email = self._normalize_account_email(
            self._settings.get("linktree_expected_account_email", "")
        )
        auto_publish = bool(self._settings.get("linktree_auto_publish", False))

        webhook_url = self._read_secure_credential("linktree_webhook_url").strip()
        api_key = self._read_secure_credential("linktree_api_key").strip()
        auto_publish = auto_publish and bool(webhook_url)

        return {
            "webhook_url": webhook_url,
            "api_key": api_key,
            "profile_url": profile_url,
            "account_email": account_email,
            "expected_account_email": expected_account_email,
            "auto_publish": auto_publish,
        }

    def set_linktree_settings(
        self,
        webhook_url: str,
        api_key: str,
        profile_url: str = "",
        auto_publish: Optional[bool] = None,
        account_email: Optional[str] = None,
        expected_account_email: Optional[str] = None,
    ) -> bool:
        """Save Linktree secrets in OS storage and non-secrets in preferences."""
        secret_values = {
            "linktree_webhook_url": str(webhook_url or "").strip(),
            "linktree_api_key": str(api_key or "").strip(),
        }
        if not all(
            self._store_secure_credential(key, value)
            for key, value in secret_values.items()
        ):
            self._record_secure_storage_issue()
            return False
        with self._lock:
            self._settings["linktree_webhook_url"] = ""
            self._settings["linktree_api_key"] = ""
            self._settings["linktree_profile_url"] = str(profile_url or "").strip()
            if account_email is not None:
                self._settings["linktree_account_email"] = self._normalize_account_email(account_email)
            if expected_account_email is not None:
                self._settings["linktree_expected_account_email"] = self._normalize_account_email(
                    expected_account_email
                )
            if auto_publish is not None:
                self._settings["linktree_auto_publish"] = bool(auto_publish)
        return self._save_settings()

    def get_linktree_account_email(self) -> str:
        """Get the Linktree account email recorded by the user/setup flow."""
        return self._normalize_account_email(self._settings.get("linktree_account_email", ""))

    def set_linktree_account_email(self, email: str) -> bool:
        """Save the Linktree account email recorded by the user/setup flow."""
        with self._lock:
            self._settings["linktree_account_email"] = self._normalize_account_email(email)
        return self._save_settings()

    def get_linktree_expected_account_email(self) -> str:
        """Get the required Linktree account email for publishing."""
        return self._normalize_account_email(self._settings.get("linktree_expected_account_email", ""))

    def set_linktree_expected_account_email(self, email: str) -> bool:
        """Save the required Linktree account email for publishing."""
        with self._lock:
            self._settings["linktree_expected_account_email"] = self._normalize_account_email(email)
        return self._save_settings()

    def get_linktree_account_verification(self) -> Dict[str, Any]:
        """Return whether the recorded Linktree account matches expectation."""
        expected = self.get_linktree_expected_account_email()
        actual = self.get_linktree_account_email()
        if not expected:
            return {"required": False, "ok": True, "expected": "", "actual": actual, "message": ""}
        if not actual:
            return {
                "required": True,
                "ok": False,
                "expected": expected,
                "actual": "",
                "message": (
                    "Linktree 기대 계정 이메일이 설정되어 있지만 현재 Linktree 계정 이메일이 저장되어 있지 않습니다. "
                    "설정에서 Linktree 계정 이메일을 확인해 저장하세요."
                ),
            }
        if actual != expected:
            return {
                "required": True,
                "ok": False,
                "expected": expected,
                "actual": actual,
                "message": f"Linktree 계정이 다릅니다. 기대: {expected}, 현재: {actual}",
            }
        return {"required": True, "ok": True, "expected": expected, "actual": actual, "message": ""}

    def get_linktree_auto_publish(self) -> bool:
        """Get Linktree auto-publish flag."""
        return bool(self._settings.get("linktree_auto_publish", False))

    def set_linktree_auto_publish(self, enabled: bool) -> bool:
        """Save Linktree auto-publish flag."""
        with self._lock:
            self._settings["linktree_auto_publish"] = bool(enabled)
        return self._save_settings()

    def get_inpock_cookies(self) -> Dict[str, str]:
        """Get device-local Inpock Link cookies from OS storage."""
        raw = self._read_secure_credential("cookies_inpock")
        try:
            parsed = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def set_inpock_cookies(self, cookies: Dict[str, str]) -> bool:
        """Save Inpock Link cookies in the OS credential store."""
        normalized = cookies if isinstance(cookies, dict) else {}
        serialized = json.dumps(normalized, ensure_ascii=False) if normalized else ""
        if not self._store_secure_credential("cookies_inpock", serialized):
            self._record_secure_storage_issue()
            return False
        with self._lock:
            self._settings["cookies_inpock"] = {}
        return self._save_settings()

    def get_1688_cookies(self) -> Dict[str, str]:
        """Get device-local 1688 cookies from OS storage."""
        raw = self._read_secure_credential("cookies_1688")
        try:
            parsed = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def set_1688_cookies(self, cookies: Dict[str, str]) -> bool:
        """Save 1688 cookies in the OS credential store."""
        normalized = cookies if isinstance(cookies, dict) else {}
        serialized = json.dumps(normalized, ensure_ascii=False) if normalized else ""
        if not self._store_secure_credential("cookies_1688", serialized):
            self._record_secure_storage_issue()
            return False
        with self._lock:
            self._settings["cookies_1688"] = {}
        return self._save_settings()

    # ============ Bulk Operations ============

    def get_recovery_issues(self) -> list[dict]:
        """Return value-free startup recovery diagnostics for the UI/support flow."""
        with self._lock:
            return deepcopy(self._recovery_issues)

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary"""
        return self._settings.copy()

    def update_settings(self, updates: Dict[str, Any]) -> bool:
        """
        Update multiple settings at once.

        Args:
            updates: Dictionary of settings to update

        Returns:
            True if save was successful
        """
        if any(key in self.SECURE_CREDENTIAL_KEYS for key in updates):
            logger.warning(
                "[SettingsManager] Bulk update rejected device-local secret fields"
            )
            return False
        with self._lock:
            self._settings.update(updates)
        return self._save_settings()


# Global instance for easy access (thread-safe singleton)
_settings_manager: Optional[SettingsManager] = None
_settings_manager_lock = threading.Lock()


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance (thread-safe)"""
    global _settings_manager
    if _settings_manager is None:
        with _settings_manager_lock:
            # Double-checked locking
            if _settings_manager is None:
                _settings_manager = SettingsManager()
    return _settings_manager
