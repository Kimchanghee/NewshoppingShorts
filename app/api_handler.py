"""
API key management helper without Tkinter.
Uses SecretsManager + custom dialogs built on PyQt6 helper functions.
"""

import json
import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ui.components.custom_dialog import show_info, show_warning, show_error, show_question
from ui.theme_manager import get_theme_manager
from core.api import ApiKeyManager
from utils.logging_config import get_logger
from utils.secrets_manager import SecretsManager
import config

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI  # pragma: no cover

logger = get_logger(__name__)

GEMINI_API_KEY_PATTERN = re.compile(r"^AIza[A-Za-z0-9_-]{35,96}$")


class APIHandler:
    """Handles API key load/save logic (UI-light PyQt6 variant)."""

    def __init__(self, app: "VideoAnalyzerGUI"):
        self.app = app

    # ------------------- loading / migration -------------------
    def load_saved_api_keys(self):
        try:
            api_manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
            loaded_keys = api_manager.api_keys
            if loaded_keys:
                config.GEMINI_API_KEYS = loaded_keys.copy()
                logger.debug(f"[API Handler] {len(loaded_keys)}개 API 키 로드 (SecretsManager)")
                return
            self._migrate_legacy_keys()
        except Exception as e:
            logger.exception(f"[API Handler] API 키 로드 실패: {e}")

    def _migrate_legacy_keys(self):
        try:
            api_keys_file = getattr(self.app, "api_keys_file", None)
            if not api_keys_file or not os.path.exists(api_keys_file):
                return

            with open(api_keys_file, "r", encoding="utf-8") as f:
                saved_keys = json.load(f)

            if saved_keys.get("migrated_to_secure_storage"):
                return
            if "gemini" not in saved_keys or not isinstance(saved_keys["gemini"], dict):
                return

            normalized = {}
            migrated_count = 0
            for idx, (_, val) in enumerate(saved_keys["gemini"].items(), start=1):
                if not val:
                    continue
                key_name = f"api_{idx}"
                normalized[key_name] = val
                try:
                    if SecretsManager.store_api_key(f"gemini_api_{idx}", val):
                        migrated_count += 1
                except Exception as migrate_err:
                    logger.warning(f"[API Handler] 마이그레이션 실패 {key_name}: {migrate_err}")

            if migrated_count > 0:
                config.GEMINI_API_KEYS = normalized
                logger.info(f"[API Handler] {migrated_count}개 API 키 마이그레이션 완료")
                backup_data = {
                    "gemini": {},
                    "migrated_to_secure_storage": True,
                    "migrated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                with open(api_keys_file, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.exception(f"[API Handler] 마이그레이션 오류: {e}")

    # ------------------- lightweight UI hooks -------------------
    def show_api_key_manager(self):
        """Minimal UX: prompt user to add keys via SecretsManager/ENV."""
        current = len(config.GEMINI_API_KEYS)
        msg = (
            f"등록된 Gemini API 키: {current}개\n\n"
            "키를 추가하려면 Settings 화면의 입력 창 또는 환경변수/SecretsManager를 사용하세요."
        )
        show_info(self.app, "API 키 상태", msg)

    def save_api_keys_from_ui(self, window=None):
        """Expect the GUI to populate self.app.api_key_entries (list of strings)."""
        entries = getattr(self.app, "api_key_entries", [])
        new_keys = {}
        invalid = []
        for idx, entry in enumerate(entries, start=1):
            key_value = entry.strip() if isinstance(entry, str) else ""
            if not key_value:
                continue
            if GEMINI_API_KEY_PATTERN.match(key_value):
                new_keys[f"api_{idx}"] = key_value
            else:
                invalid.append(idx)

        if invalid or not new_keys:
            msg = "유효한 키를 최소 1개 입력해주세요."
            if invalid:
                msg += f"\n잘못된 키: {invalid}"
            show_warning(self.app, "검증 실패", msg)
            return

        stored = 0
        for name, value in new_keys.items():
            try:
                if SecretsManager.store_api_key(f"gemini_{name}", value):
                    stored += 1
            except Exception as e:
                logger.error(f"[API Handler] {name} 저장 실패: {e}")

        if stored == 0:
            show_error(self.app, "저장 실패", "SecretsManager에 저장하지 못했습니다.")
            return

        config.GEMINI_API_KEYS = new_keys
        self.app.api_key_manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
        show_success = getattr(__import__("ui.components.custom_dialog", fromlist=["show_success"]), "show_success")
        show_success(self.app, "저장 완료", f"{stored}개의 API 키가 저장되었습니다.")

    def clear_all_api_keys(self, window=None):
        if show_question(self.app, "확인", "모든 API 키를 삭제하시겠습니까?"):
            config.GEMINI_API_KEYS = {}
            self.app.api_key_entries = []
            show_info(self.app, "완료", "모든 API 키가 삭제되었습니다.")

    def save_api_keys_to_file(self) -> bool:
        try:
            stored_count = 0
            for key_name, key_value in config.GEMINI_API_KEYS.items():
                if not key_value:
                    continue
                idx = key_name.replace("api_", "")
                secret_key_name = f"gemini_api_{idx}"
                if SecretsManager.store_api_key(secret_key_name, key_value):
                    stored_count += 1
            if stored_count > 0:
                logger.info(f"[API Handler] {stored_count}개 API 키 저장 완료")
                return True
            logger.warning("[API Handler] 저장할 API 키가 없습니다.")
            return False
        except Exception as e:
            logger.exception(f"[API Handler] 파일 저장 오류: {e}")
            return False

    def show_api_status(self):
        api_key_manager = getattr(self.app, "api_key_manager", None)
        if api_key_manager is None:
            show_warning(self.app, "경고", "API 키 관리자가 초기화되지 않았습니다.")
            return
        status = api_key_manager.get_status()
        key_count = len(config.GEMINI_API_KEYS)
        title = f"API 키 상태 ({key_count}개 등록)"
        show_info(self.app, title, f"현재 API 키 상태:\n\n{status}")
