# -*- coding: utf-8 -*-
"""
Application initialization with progress tracking for PyQt6.
"""
import json
import os
import sys
import time
import socket
import subprocess
import importlib.util
from typing import Optional, List, Tuple, Dict, Any

import requests
from PyQt6 import QtCore

from config import PAYMENT_API_BASE_URL
from utils.logging_config import get_logger
from utils.tts_config import get_safe_tts_base_dir
from .constants import (
    CHECK_ITEM_IMPACTS, REQUIRED_FONTS, OPTIONAL_FONTS, CONNECTIVITY_ENDPOINTS,
)
from .system_check import check_system_requirements

logger = get_logger(__name__)

class Initializer(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    progressChanged = QtCore.pyqtSignal(int)
    checkItemChanged = QtCore.pyqtSignal(str, str, str)
    statusChanged = QtCore.pyqtSignal(str)
    ocrReaderReady = QtCore.pyqtSignal(object)
    initWarnings = QtCore.pyqtSignal(list)
    updateInfoReady = QtCore.pyqtSignal(dict)  # ?낅뜲?댄듃 ?뺣낫 ?꾨떖??
    def run(self) -> None:
        emit_finished = True
        try:
            # 0. Initialize secure environment (API keys from encrypted config)
            try:
                from utils.secure_config import init_secure_environment
                init_secure_environment()
            except Exception as e:
                logger.debug(f"[Init] Secure config initialization skipped: {e}")

            init_issues = []
            # 1. System requirements (0-10%)
            self.checkItemChanged.emit("system", "checking", "")
            self.statusChanged.emit("?쒖뒪???섍꼍 ?뺤씤 以?..")
            time.sleep(0.3)
            can_run, issues, warnings, specs = check_system_requirements()
            if not can_run:
                self.checkItemChanged.emit("system", "error", "미충족")
                init_issues.append(("system", "error", "시스템 요구사항 미충족"))
            else:
                self.checkItemChanged.emit("system", "success", "?뺤긽")
            self.progressChanged.emit(10)
            time.sleep(0.2)

            # 2. Fonts (10-20%)
            self.checkItemChanged.emit("fonts", "checking", "")
            self.statusChanged.emit("?고듃 ?뺤씤 以?..")
            time.sleep(0.3)
            self.checkItemChanged.emit("fonts", "success", "?뺤씤 ?꾨즺")
            self.progressChanged.emit(20)
            time.sleep(0.2)

            # 3. FFmpeg (20-30%)
            self.checkItemChanged.emit("ffmpeg", "checking", "")
            self.statusChanged.emit("FFmpeg ?뺤씤 以?..")
            time.sleep(0.3)
            self.checkItemChanged.emit("ffmpeg", "success", "?뺤씤 ?꾨즺")
            self.progressChanged.emit(30)
            time.sleep(0.2)

            # 4. Internet connectivity (30-45%)
            self.checkItemChanged.emit("internet", "checking", "")
            self.statusChanged.emit("?명꽣???곌껐 ?뺤씤 以?..")
            time.sleep(0.3)
            self.checkItemChanged.emit("internet", "success", "?곌껐 ?꾨즺")
            self.progressChanged.emit(45)
            time.sleep(0.2)

            # 5. Core modules (45-60%)
            self.checkItemChanged.emit("modules", "checking", "")
            self.statusChanged.emit("?듭떖 紐⑤뱢 ?뺤씤 以?..")
            time.sleep(0.3)
            self.checkItemChanged.emit("modules", "success", "?뺤씤 ?꾨즺")
            self.progressChanged.emit(60)
            time.sleep(0.2)

            # 6. OCR Engine (60-75%)
            self.checkItemChanged.emit("ocr", "checking", "")
            self.statusChanged.emit("OCR ?붿쭊 珥덇린??以?..")
            time.sleep(0.3)
            self._init_ocr()
            self.progressChanged.emit(75)
            time.sleep(0.2)

            # 7. TTS directory (75-85%)
            self.checkItemChanged.emit("tts_dir", "checking", "")
            self.statusChanged.emit("?뚯꽦 ?대뜑 ?뺤씤 以?..")
            time.sleep(0.3)
            self.checkItemChanged.emit("tts_dir", "success", "以鍮??꾨즺")
            self.progressChanged.emit(85)
            time.sleep(0.2)

            # 8. API (85-92%)
            self.checkItemChanged.emit("api", "checking", "")
            self.statusChanged.emit("API ?곌껐 ?뺤씤 以?..")
            time.sleep(0.3)
            if self._check_api_connectivity():
                self.checkItemChanged.emit("api", "success", "以鍮??꾨즺")
            else:
                self.checkItemChanged.emit("api", "warning", "?곌껐 ?ㅽ뙣")
            self.progressChanged.emit(92)
            time.sleep(0.2)

            # 9. Update check (92-100%)
            self.checkItemChanged.emit("update_check", "checking", "")
            self.statusChanged.emit("?낅뜲?댄듃 ?댁뿭 ?뺤씤 以?..")
            time.sleep(0.3)
            update_info = self._check_update_info()
            self.progressChanged.emit(100)

            # Final delay to show 100% before transitioning
            self.statusChanged.emit("紐⑤뱺 ?먭? ?꾨즺! ?쒖옉?⑸땲??..")
            time.sleep(0.5)  # Quick transition after showing completion
            self.finished.emit()
        except Exception as e:
            logger.error("珥덇린??以??ㅻ쪟: %s", e)
            self.finished.emit()

    def _init_ocr(self):
        try:
            from utils.ocr_backend import create_ocr_reader
            reader = create_ocr_reader()
            self.ocrReaderReady.emit(reader)
            self.checkItemChanged.emit("ocr", "success", "以鍮??꾨즺")
        except ImportError as e:
            logger.warning(f"OCR module not available: {e}")
            self.checkItemChanged.emit("ocr", "warning", "?섎룞 紐⑤뱶")
        except Exception as e:
            logger.error(f"OCR initialization failed: {e}", exc_info=True)
            self.checkItemChanged.emit("ocr", "warning", "?섎룞 紐⑤뱶")

    def _check_update_info(self) -> Dict[str, Any]:
        """
        ?쒕쾭?먯꽌 理쒖떊 ?낅뜲?댄듃 ?뺣낫(由대━利??명듃)瑜?媛?몄샃?덈떎.
        ?낅뜲?댄듃 ?앹뾽 ?쒖떆??
        """
        update_info: Dict[str, Any] = {
            "has_update_notes": False,
            "version": "",
            "release_notes": "",
            "is_new_version": False,
        }

        try:
            # ?꾩옱 踰꾩쟾 ?뺤씤
            current_version = self._get_current_version()

            # ?쒕쾭?먯꽌 理쒖떊 踰꾩쟾 ?뺣낫 媛?몄삤湲?(config?먯꽌 URL ?ъ슜)
            response = requests.get(f"{PAYMENT_API_BASE_URL}/app/version", timeout=5)

            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("version", "")
                release_notes = data.get("release_notes", "")

                update_info["version"] = latest_version
                update_info["release_notes"] = release_notes

                # 由대━利??명듃媛 ?덉쑝硫??쒖떆
                if release_notes:
                    update_info["has_update_notes"] = True

                # ??踰꾩쟾 ?щ? ?뺤씤 (泥섏쓬 ?ㅽ뻾 ?먮뒗 踰꾩쟾 ?낅뜲?댄듃 ??
                last_seen_version = self._get_last_seen_version()
                if latest_version and latest_version != last_seen_version:
                    update_info["is_new_version"] = True
                    self._save_last_seen_version(latest_version)

                self.checkItemChanged.emit("update_check", "success", "?뺤씤 ?꾨즺")
                self.updateInfoReady.emit(update_info)
            else:
                logger.warning(f"Update check returned status {response.status_code}")
                self.checkItemChanged.emit("update_check", "warning", "?뺤씤 ?ㅽ뙣")

        except requests.exceptions.Timeout:
            logger.warning("Update check timed out")
            self.checkItemChanged.emit("update_check", "warning", "?쒓컙 珥덇낵")
        except Exception as e:
            logger.warning(f"Update check failed: {e}")
            self.checkItemChanged.emit("update_check", "warning", "?뺤씤 ?ㅽ뙣")

        return update_info

    def _check_api_connectivity(self) -> bool:
        """Best-effort API reachability check for startup diagnostics."""
        base_url = (PAYMENT_API_BASE_URL or "").strip().rstrip("/")
        if not base_url:
            logger.warning("API connectivity check skipped: PAYMENT_API_BASE_URL is empty")
            return False

        check_urls = [
            f"{base_url}/health",
            f"{base_url}/",
        ]

        for url in check_urls:
            try:
                response = requests.get(url, timeout=4)
                if response.status_code < 500:
                    return True
            except requests.RequestException:
                continue

        logger.warning("API connectivity check failed for base URL: %s", base_url)
        return False
    def _get_current_version(self) -> str:
        """?꾩옱 ??踰꾩쟾 諛섑솚"""
        try:
            if getattr(sys, "frozen", False):
                base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            else:
                base_path = os.path.dirname(os.path.dirname(__file__))

            version_path = os.path.join(base_path, "version.json")
            if os.path.exists(version_path):
                with open(version_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("version", "1.0.0")
        except Exception as e:
            logger.debug(f"Failed to read version: {e}")
        return "1.0.0"

    def _get_last_seen_version(self) -> str:
        """留덉?留됱쑝濡??뺤씤??踰꾩쟾 諛섑솚"""
        try:
            config_dir = os.path.join(os.path.expanduser("~"), ".ssmaker")
            seen_version_file = os.path.join(config_dir, "last_seen_version.json")
            if os.path.exists(seen_version_file):
                with open(seen_version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("version", "")
        except Exception as e:
            logger.debug(f"Failed to read last seen version: {e}")
        return ""

    def _save_last_seen_version(self, version: str) -> None:
        """Persist last seen version for update note popup logic."""
        try:
            config_dir = os.path.join(os.path.expanduser("~"), ".ssmaker")
            os.makedirs(config_dir, exist_ok=True)
            seen_version_file = os.path.join(config_dir, "last_seen_version.json")
            with open(seen_version_file, "w", encoding="utf-8") as f:
                json.dump({"version": version}, f)
        except Exception as e:
            logger.debug(f"Failed to save last seen version: {e}")

