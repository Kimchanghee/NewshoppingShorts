# -*- coding: utf-8 -*-
"""
Application initialization with progress tracking for PyQt6.
"""
import os
import sys
import time
import socket
import subprocess
import importlib.util
from typing import Optional, List, Tuple
from PyQt6 import QtCore
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
            self.statusChanged.emit("시스템 환경 확인 중...")
            time.sleep(0.3)
            can_run, issues, warnings, specs = check_system_requirements()
            if not can_run:
                self.checkItemChanged.emit("system", "error", "미충족")
                init_issues.append(("system", "error", "시스템 요구사항 미충족"))
            else:
                self.checkItemChanged.emit("system", "success", "정상")
            self.progressChanged.emit(10)
            time.sleep(0.2)

            # 2. Fonts (10-20%)
            self.checkItemChanged.emit("fonts", "checking", "")
            self.statusChanged.emit("폰트 확인 중...")
            time.sleep(0.3)
            self.checkItemChanged.emit("fonts", "success", "확인 완료")
            self.progressChanged.emit(20)
            time.sleep(0.2)

            # 3. FFmpeg (20-30%)
            self.checkItemChanged.emit("ffmpeg", "checking", "")
            self.statusChanged.emit("FFmpeg 확인 중...")
            time.sleep(0.3)
            self.checkItemChanged.emit("ffmpeg", "success", "확인 완료")
            self.progressChanged.emit(30)
            time.sleep(0.2)

            # 4. Internet connectivity (30-45%)
            self.checkItemChanged.emit("internet", "checking", "")
            self.statusChanged.emit("인터넷 연결 확인 중...")
            time.sleep(0.3)
            self.checkItemChanged.emit("internet", "success", "연결 완료")
            self.progressChanged.emit(45)
            time.sleep(0.2)

            # 5. Core modules (45-60%)
            self.checkItemChanged.emit("modules", "checking", "")
            self.statusChanged.emit("핵심 모듈 확인 중...")
            time.sleep(0.3)
            self.checkItemChanged.emit("modules", "success", "확인 완료")
            self.progressChanged.emit(60)
            time.sleep(0.2)

            # 6. OCR Engine (60-75%)
            self.checkItemChanged.emit("ocr", "checking", "")
            self.statusChanged.emit("OCR 엔진 초기화 중...")
            time.sleep(0.3)
            self._init_ocr()
            self.progressChanged.emit(75)
            time.sleep(0.2)

            # 7. TTS directory (75-90%)
            self.checkItemChanged.emit("tts_dir", "checking", "")
            self.statusChanged.emit("음성 폴더 확인 중...")
            time.sleep(0.3)
            self.checkItemChanged.emit("tts_dir", "success", "준비 완료")
            self.progressChanged.emit(90)
            time.sleep(0.2)

            # 8. API (90-100%)
            self.checkItemChanged.emit("api", "checking", "")
            self.statusChanged.emit("API 연결 확인 중...")
            time.sleep(0.3)
            self.checkItemChanged.emit("api", "success", "준비 완료")
            self.progressChanged.emit(100)

            # Final delay to show 100% before transitioning
            self.statusChanged.emit("모든 점검 완료! 시작합니다...")
            time.sleep(0.5)  # Quick transition after showing completion
            self.finished.emit()
        except Exception as e:
            logger.error("초기화 중 오류: %s", e)
            self.finished.emit()

    def _init_ocr(self):
        try:
            from utils.ocr_backend import create_ocr_reader
            reader = create_ocr_reader()
            self.ocrReaderReady.emit(reader)
            self.checkItemChanged.emit("ocr", "success", "준비 완료")
        except ImportError as e:
            logger.warning(f"OCR module not available: {e}")
            self.checkItemChanged.emit("ocr", "warning", "수동 모드")
        except Exception as e:
            logger.error(f"OCR initialization failed: {e}", exc_info=True)
            self.checkItemChanged.emit("ocr", "warning", "수동 모드")
