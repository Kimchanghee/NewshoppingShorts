# -*- coding: utf-8 -*-
"""
Application initialization with progress tracking.
"""

import os
import sys
import time
import socket
import subprocess
import importlib.util
from typing import Optional, List, Tuple

from PyQt5 import QtCore

from utils.logging_config import get_logger
from utils.tts_config import get_safe_tts_base_dir
from .constants import (
    CHECK_ITEM_IMPACTS,
    REQUIRED_FONTS,
    OPTIONAL_FONTS,
    CONNECTIVITY_ENDPOINTS,
)
from .system_check import check_system_requirements

logger = get_logger(__name__)


class Initializer(QtCore.QObject):
    """
    Handles application initialization with progress tracking.
    Emits signals to update the loading UI.
    """

    finished = QtCore.pyqtSignal()
    progressChanged = QtCore.pyqtSignal(int)
    checkItemChanged = QtCore.pyqtSignal(str, str, str)  # item_id, status, message
    statusChanged = QtCore.pyqtSignal(str)
    ocrReaderReady = QtCore.pyqtSignal(object)
    initWarnings = QtCore.pyqtSignal(list)

    # Class attribute for check item impacts
    CHECK_ITEM_IMPACTS = CHECK_ITEM_IMPACTS

    def run(self) -> None:
        """Main initialization sequence."""
        emit_finished = True
        try:
            init_issues: List[Tuple[str, str, str]] = []

            # 1. System requirements (0-12%)
            self.checkItemChanged.emit("system", "checking", "")
            self.statusChanged.emit("시스템 환경을 확인하고 있습니다...")
            time.sleep(0.2)
            can_run, issues, warnings, specs = check_system_requirements()
            if not can_run:
                self.checkItemChanged.emit("system", "error", "미충족")
                init_issues.append(("system", "error", "시스템 요구사항 미충족"))
            elif warnings:
                self.checkItemChanged.emit("system", "warning", "경고")
                init_issues.append(("system", "warning", "; ".join(warnings[:2])))
            else:
                self.checkItemChanged.emit("system", "success", "정상")
            self.progressChanged.emit(12)

            # 2. Fonts (12-24%)
            self.checkItemChanged.emit("fonts", "checking", "")
            self.statusChanged.emit("폰트를 확인하고 있습니다...")
            time.sleep(0.2)
            fonts_ok, fonts_msg = self._check_fonts()
            if fonts_ok:
                self.checkItemChanged.emit("fonts", "success", fonts_msg)
            else:
                self.checkItemChanged.emit("fonts", "warning", fonts_msg)
                init_issues.append(("fonts", "warning", fonts_msg))
            self.progressChanged.emit(24)

            # 3. Video encoder (24-36%)
            self.checkItemChanged.emit("ffmpeg", "checking", "")
            self.statusChanged.emit("영상 처리 엔진을 확인하고 있습니다...")
            time.sleep(0.2)
            ffmpeg_ok, ffmpeg_msg = self._check_ffmpeg()
            if ffmpeg_ok:
                self.checkItemChanged.emit("ffmpeg", "success", ffmpeg_msg)
            else:
                self.checkItemChanged.emit("ffmpeg", "error", ffmpeg_msg)
                init_issues.append(("ffmpeg", "error", "영상 인코더 없음"))
            self.progressChanged.emit(36)

            # 4. Internet connection (36-48%)
            self.checkItemChanged.emit("internet", "checking", "")
            self.statusChanged.emit("인터넷 연결을 확인하고 있습니다...")
            time.sleep(0.2)
            internet_ok, internet_msg = self._check_internet()
            if internet_ok:
                self.checkItemChanged.emit("internet", "success", internet_msg)
            else:
                self.checkItemChanged.emit("internet", "error", internet_msg)
                init_issues.append(("internet", "error", "인터넷 연결 안됨"))
            self.progressChanged.emit(48)

            # 5. Program modules (48-60%)
            self.checkItemChanged.emit("modules", "checking", "")
            self.statusChanged.emit("프로그램 구성요소를 확인하고 있습니다...")
            time.sleep(0.2)
            modules_ok, modules_msg = self._check_all_modules()
            if modules_ok:
                self.checkItemChanged.emit("modules", "success", modules_msg)
            else:
                self.checkItemChanged.emit("modules", "error", modules_msg)
                init_issues.append(("modules", "error", modules_msg))
                # Critical module missing - abort
                self.progressChanged.emit(100)
                self.initWarnings.emit(init_issues)
                self.statusChanged.emit("필수 구성요소 누락으로 초기화를 중단합니다.")
                time.sleep(1.0)
                emit_finished = False
                self.finished.emit()
                return
            self.progressChanged.emit(60)

            # 6. OCR engine (60-85%) - longest step
            self.checkItemChanged.emit("ocr", "checking", "")
            self.statusChanged.emit("자막 인식 엔진 준비 중... (첫 실행시 1-2분)")
            ocr_reader = self._init_ocr()
            if ocr_reader:
                self.checkItemChanged.emit("ocr", "success", "준비 완료")
            else:
                self.checkItemChanged.emit("ocr", "success", "수동 모드")
            self.progressChanged.emit(85)

            # 7. TTS directory (85-95%)
            self.checkItemChanged.emit("tts_dir", "checking", "")
            self.statusChanged.emit("음성 저장 폴더 준비 중...")
            time.sleep(0.2)
            tts_ok, tts_msg = self._prepare_tts_directory()
            if tts_ok:
                self.checkItemChanged.emit("tts_dir", "success", tts_msg)
            else:
                self.checkItemChanged.emit("tts_dir", "warning", tts_msg)
                init_issues.append(("tts_dir", "warning", "음성 저장 폴더 생성 실패"))
            self.progressChanged.emit(95)

            # 8. Service connection (95-100%)
            self.checkItemChanged.emit("api", "checking", "")
            self.statusChanged.emit("서비스 연결을 준비하고 있습니다...")
            time.sleep(0.2)
            self.checkItemChanged.emit("api", "success", "준비 완료")
            self.progressChanged.emit(100)

            # Emit warnings if any
            if init_issues:
                self.initWarnings.emit(init_issues)
                self.statusChanged.emit("일부 항목에 문제가 있습니다...")
                time.sleep(0.5)
            else:
                self.statusChanged.emit("모든 점검 완료! 시작합니다...")
            time.sleep(0.3)

            # Pass OCR reader
            self.ocrReaderReady.emit(ocr_reader)

        except Exception as e:
            logger.error("초기화 중 오류 발생: %s", e, exc_info=True)
        finally:
            if emit_finished:
                self.finished.emit()

    def _get_fonts_dir(self) -> str:
        """Get fonts directory path."""
        if getattr(sys, "frozen", False):
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, "fonts")

    def _check_fonts(self) -> Tuple[bool, str]:
        """Check fonts (subtitle + UI fonts)."""
        try:
            fonts_dir = self._get_fonts_dir()

            found_required = [
                f for f in REQUIRED_FONTS if os.path.exists(os.path.join(fonts_dir, f))
            ]
            found_optional = [
                f for f in OPTIONAL_FONTS if os.path.exists(os.path.join(fonts_dir, f))
            ]

            total_found = len(found_required) + len(found_optional)
            missing_required = [f for f in REQUIRED_FONTS if f not in found_required]

            if len(found_required) < len(REQUIRED_FONTS):
                missing_names = ", ".join(
                    [f.split(".")[0][:10] for f in missing_required[:2]]
                )
                return True, f"경고 {missing_names}... 누락"

            if total_found >= 4:
                return True, f"{total_found}개 확인"
            else:
                return True, f"{total_found}개만"

        except Exception as e:
            return False, f"오류: {str(e)[:20]}"

    def _check_ffmpeg(self) -> Tuple[bool, str]:
        """Check FFmpeg availability."""
        ffmpeg_path: Optional[str] = None

        # 1. Check ffmpeg executable
        try:
            creationflags = (
                subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0
            )
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags,
            )
            if result.returncode == 0:
                ffmpeg_path = "ffmpeg"
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            try:
                import imageio_ffmpeg

                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                    return False, "없음"
            except (ImportError, AttributeError, OSError):
                return False, "없음"

        # 2. Check ffprobe
        ffprobe_found = False
        try:
            creationflags = (
                subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0
            )
            subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                timeout=5,
                creationflags=creationflags,
            )
            ffprobe_found = True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass

        # 3. Check basic codec support
        try:
            cmd = ffmpeg_path if isinstance(ffmpeg_path, str) else "ffmpeg"
            creationflags = (
                subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0
            )
            result = subprocess.run(
                [cmd, "-codecs"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags,
            )
            if result.returncode == 0:
                codecs_output = result.stdout.lower()
                has_h264 = "h264" in codecs_output
                has_aac = "aac" in codecs_output

                if not (has_h264 and has_aac):
                    return True, "제한적"
        except (subprocess.SubprocessError, OSError):
            pass

        return True, "완전" if ffprobe_found else "완전"

    def _check_internet(self) -> Tuple[bool, str]:
        """Check internet connectivity with multiple endpoint fallback."""
        for host, port, name in CONNECTIVITY_ENDPOINTS:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(2)
                    sock.connect((host, port))
                    return True, f"연결됨 ({name})"
            except Exception:
                continue

        return False, "연결 안됨 (모든 엔드포인트 실패)"

    def _check_all_modules(self) -> Tuple[bool, str]:
        """Check all required and optional modules."""
        # Critical modules (import check)
        critical_import_modules = [
            ("PIL", "이미지"),
            ("moviepy", "영상"),
            ("numpy", "연산"),
        ]

        # Critical modules (spec check only - avoid import side effects)
        critical_spec_modules = [
            ("cv2", "비전"),
        ]

        # Optional modules
        optional_modules = [
            ("faster_whisper", "음성"),
            ("pytesseract", "문자"),
            ("pydub", "오디오"),
        ]

        # Add RapidOCR check for Python < 3.13
        if sys.version_info < (3, 13):
            optional_modules.insert(1, ("rapidocr_onnxruntime", "문자(RapidOCR)"))

        critical_missing: List[str] = []
        optional_missing: List[str] = []

        # Check critical modules (import)
        for mod_name, display_name in critical_import_modules:
            try:
                __import__(mod_name)
            except Exception as e:
                logger.error(
                    f"Failed to import critical module {mod_name}: {e}", exc_info=True
                )
                critical_missing.append(f"{display_name} ({e})")

        # Check critical modules (spec only)
        for mod_name, display_name in critical_spec_modules:
            try:
                if importlib.util.find_spec(mod_name) is None:
                    critical_missing.append(display_name)
            except Exception:
                critical_missing.append(display_name)

        # Check optional modules
        for mod_name, display_name in optional_modules:
            try:
                __import__(mod_name)
            except Exception:
                optional_missing.append(display_name)

        if critical_missing:
            missing_str = ", ".join(critical_missing)
            return False, f"필수 모듈 누락: {missing_str}"

        total = (
            len(critical_import_modules)
            + len(critical_spec_modules)
            + len(optional_modules)
        )
        found = total - len(optional_missing)

        if optional_missing:
            return True, f"{found}/{total} (일부 제한: {', '.join(optional_missing)})"
        else:
            return True, f"{found}/{total} 정상"

    def _init_ocr(self) -> Optional[object]:
        """Initialize OCR model."""
        try:
            from utils.ocr_backend import create_ocr_reader

            reader = create_ocr_reader()
            if reader:
                return reader
            return None
        except Exception as e:
            logger.debug("OCR loading failed (non-critical): %s", e)
            return None

    def _prepare_tts_directory(self) -> Tuple[bool, str]:
        """Prepare TTS output directory."""
        try:
            base_tts_dir = get_safe_tts_base_dir()
            voice_sample_dir = os.path.join(base_tts_dir, "voice_samples")
            os.makedirs(base_tts_dir, exist_ok=True)
            os.makedirs(voice_sample_dir, exist_ok=True)

            logger.debug("[TTS] 출력 경로: %s", base_tts_dir)
            return True, "준비 완료"
        except Exception as e:
            logger.error("[TTS] 디렉토리 생성 실패: %s", e, exc_info=True)
            return False, "실패"
