# -*- coding: utf-8 -*-

# ★★★ 필수 패키지 자동 설치 (가장 먼저 실행) ★★★
import subprocess
import sys
import io
import importlib.util

from io import TextIOBase

class _NullWriter(TextIOBase):
    def write(self, s):
        return len(s)
    def flush(self):
        pass
    def isatty(self):
        return False

def _ensure_stdio():
    # 1) PyInstaller --noconsole 등에서 stdout/stderr가 None이면 더미 writer로 채움
    if sys.stdout is None:
        sys.stdout = _NullWriter()
    if sys.stderr is None:
        sys.stderr = _NullWriter()

    # 2) Windows에서 인코딩 문제 방지 (stdout/stderr가 정상 스트림일 때만 감쌈)
    if sys.platform == "win32":
        try:
            # Python 3.7+ (가능하면 이 방식이 가장 안전)
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            else:
                if hasattr(sys.stdout, "buffer"):
                    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

        try:
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            else:
                if hasattr(sys.stderr, "buffer"):
                    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

    # 3) 일부 라이브러리가 sys.__stderr__를 직접 참조하는 경우도 방어
    if getattr(sys, "__stderr__", None) is None:
        sys.__stderr__ = sys.stderr
    if getattr(sys, "__stdout__", None) is None:
        sys.__stdout__ = sys.stdout
        
_ensure_stdio()

# Windows 콘솔 인코딩 문제 해결
# if sys.platform == 'win32':
#     try:
#         sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
#         sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
#     except:
#         pass


def has_module(mod_name: str, silent: bool = False) -> bool:
    """모듈 존재 여부 확인 (조용한 모드 지원)"""
    try:
        spec = importlib.util.find_spec(mod_name)
        if spec is None:
            return False
        return True
    except (ModuleNotFoundError, ImportError, ValueError):
        return False

def _check_and_install_packages():
    """
    프로그램 실행에 필요한 패키지를 확인합니다.
    개발 환경에서는 자동 설치를 시도하고, 빌드된 실행 파일에서는 검증만 수행합니다.
    """
    # frozen 상태 확인 (PyInstaller로 빌드된 실행 파일인지)
    is_frozen = getattr(sys, 'frozen', False)

    # 필수 패키지 목록: (import 이름, pip 패키지 이름, 선택적 여부)
    # True = 선택적 (없어도 프로그램 실행 가능), False = 필수
    required_packages = [
        # UI 및 네트워크
        ('PyQt5', 'PyQt5', False),
        ('requests', 'requests', False),

        # 기본 패키지
        ('psutil', 'psutil', False),

        # OCR 및 이미지 처리 - Python 버전에 따라 선택적
        ('cv2', 'opencv-python', False),
        ('rapidocr_onnxruntime', 'rapidocr-onnxruntime', True),  # 선택적: OCR 기능용
        ('pytesseract', 'pytesseract', True),  # 선택적: OCR 대체 엔진
        ('numpy', 'numpy', False),

        # Faster-Whisper 음성 인식 (CTranslate2 기반)
        ('faster_whisper', 'faster-whisper', True),  # 선택적: 오디오 분석 기능용
        ('ctranslate2', 'ctranslate2', True),  # 선택적: Faster-Whisper 의존성
        ('onnxruntime', 'onnxruntime', True),  # 선택적: OCR 의존성

        # 비디오 및 이미지 처리
        ('moviepy', 'moviepy', False),
        ('PIL', 'pillow', False),
        ('pydub', 'pydub', False),
        ('imageio_ffmpeg', 'imageio-ffmpeg', False),

        # AI API 클라이언트
        ('google.genai', 'google-genai', False),  # Gemini SDK (새 패키지명)
        ('anthropic', 'anthropic', False),

        # 로깅
        ('colorama', 'colorama', False),
    ]

    missing_packages = []

    for import_name, pip_name, optional in required_packages:
        if not has_module(import_name):
            if optional:
                # Package not found (optional) - silently continue
                pass
            else:
                missing_packages.append((import_name, pip_name))

    if missing_packages:
        pkg_names = [pip_name for _, pip_name in missing_packages]

        if is_frozen:
            # 빌드된 실행 파일: 패키지 누락은 치명적 오류
            # Note: Using print here as logging may not be configured yet at startup
            sys.stderr.write("\n" + "=" * 70 + "\n")
            sys.stderr.write("ERROR: 필수 패키지 누락 (빌드 오류)\n")
            sys.stderr.write("=" * 70 + "\n")
            sys.stderr.write(f"다음 패키지가 빌드에 포함되지 않았습니다: {', '.join(pkg_names)}\n")
            sys.stderr.write("개발자에게 문의하거나 재빌드가 필요합니다.\n")
            sys.stderr.write("=" * 70 + "\n\n")
            sys.exit(1)

        # 개발 환경: 자동 설치 시도
        # Missing packages detected - starting auto-installation

        failed_packages = []
        for import_name, pip_name in missing_packages:
            # Installing package silently
            try:
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install', pip_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT
                )
                # Package installed successfully
            except subprocess.CalledProcessError as e:
                # Package installation failed
                failed_packages.append(pip_name)
            except (FileNotFoundError, OSError) as e:
                # pip execution failed or not installed
                failed_packages.append(pip_name)

        # 설치 실패한 필수 패키지가 있으면 종료
        if failed_packages:
            # Note: Using stderr as logging may not be configured yet at startup
            sys.stderr.write("\n" + "=" * 70 + "\n")
            sys.stderr.write("ERROR: 필수 패키지 설치 실패\n")
            sys.stderr.write("=" * 70 + "\n")
            sys.stderr.write(f"다음 패키지를 설치할 수 없습니다: {', '.join(failed_packages)}\n")
            sys.stderr.write("\n해결 방법:\n")
            sys.stderr.write("1. 관리자 권한으로 프로그램을 실행해주세요\n")
            sys.stderr.write("2. 인터넷 연결을 확인해주세요\n")
            sys.stderr.write("3. 수동으로 설치: pip install " + " ".join(failed_packages) + "\n")
            sys.stderr.write("=" * 70 + "\n")
            input("\n아무 키나 눌러서 종료...")
            sys.exit(1)

        # Installation complete - starting program silently

# 패키지 확인 및 설치는 main entry에서만 실행
# import 시 자동 실행하면 GUI 앱이나 다른 모듈에서 블록됨


# ★★★ DPI 스케일링 설정 (가장 먼저 실행) ★★★
# Windows에서 UI가 모든 모니터에서 동일하게 보이도록 설정
import ctypes

def _setup_dpi_awareness():
    """
    Windows DPI 스케일링 설정
    - 고DPI 모니터에서 UI가 제대로 표시되도록 설정
    - PROCESS_PER_MONITOR_DPI_AWARE (2): 각 모니터의 DPI를 인식하고 Qt가 스케일링
    - Qt의 AA_EnableHighDpiScaling과 함께 사용
    """
    if sys.platform == 'win32':
        try:
            # Windows 8.1+ : SetProcessDpiAwareness
            # 2 = PROCESS_PER_MONITOR_DPI_AWARE - Qt가 각 모니터 DPI에 맞춰 스케일링
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            # DPI Aware mode activated silently
        except AttributeError:
            # Windows 7 이하: 레거시 API 사용
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                # DPI Aware mode activated (legacy)
            except Exception:
                pass
        except Exception as e:
            # Note: Early startup - logging may not be fully configured
            pass  # DPI setup failure is non-critical, silently ignore

_setup_dpi_awareness()

# ★★★ pydub 경고 방지: ffmpeg 경로를 미리 설정 ★★★
import os
import warnings
warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

def _setup_ffmpeg_path():
    """pydub가 import되기 전에 ffmpeg 경로 설정"""
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_exe and os.path.exists(ffmpeg_exe):
            os.environ["PATH"] = os.path.dirname(ffmpeg_exe) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

_setup_ffmpeg_path()

# Faster-Whisper는 CTranslate2 기반으로 동작 (PyTorch 불필요)
def _runtime_base():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def _setup_onnxruntime_environment():
    try:
        base = _runtime_base()  

        # 1) exe가 있는 폴더(dist)도 추가 (onedir에서 중요)
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else base

        # 2) 네가 기대하는 _internal 구조
        internal_root = os.path.join(base, "_internal")
        ort_dir = os.path.join(internal_root, "onnxruntime")
        ort_capi = os.path.join(ort_dir, "capi")

        paths = [exe_dir, base, internal_root, ort_dir, ort_capi]

        # 3) 실제 onnxruntime 설치/번들 경로도 추가 (가장 중요)
        try:
            import importlib.util
            spec = importlib.util.find_spec("onnxruntime")
            if spec and spec.origin:
                mod_dir = os.path.dirname(spec.origin)
                capi_dir = os.path.join(mod_dir, "capi")
                paths.extend([mod_dir, capi_dir])
        except Exception:
            pass

        # PATH + add_dll_directory 반영
        uniq = []
        for p in paths:
            if p and os.path.isdir(p) and p not in uniq:
                uniq.append(p)
        if not uniq:
            return

        cur = os.environ.get("PATH", "")
        for p in reversed(uniq):
            if p not in cur:
                cur = p + os.pathsep + cur
        os.environ["PATH"] = cur

        if sys.platform == "win32":
            add_dll = getattr(os, "add_dll_directory", None)
            if add_dll:
                for p in uniq:
                    try:
                        add_dll(p)
                    except Exception:
                        pass

    except Exception:
        pass

    
# def _setup_onnxruntime_environment():
#     """
#     onnxruntime 환경을 프로그램 시작 시 강제 설정
#     - _internal/onnxruntime 폴더를 PATH에 추가
#     - Windows DLL 검색 경로 추가
#     """
#     try:
#         bases = _runtime_bases()

#         paths_to_add = []

#         # 1. _internal/onnxruntime 경로
#         for base_path in bases:
#             internal_onnx = os.path.join(base_path, "_internal", "onnxruntime")
#             internal_capi = os.path.join(base_path, "_internal", "onnxruntime", "capi")
#             if os.path.isdir(internal_onnx):
#                 paths_to_add.append(internal_onnx)
#             if os.path.isdir(internal_capi):
#                 paths_to_add.append(internal_capi)
            
#         # 2. onnxruntime 모듈 설치 경로 (importlib로 안전하게 찾기)
#         try:
#             import importlib.util
#             spec = importlib.util.find_spec('onnxruntime')
#             if spec and spec.origin:
#                 onnx_module_path = os.path.dirname(spec.origin)
#                 if os.path.isdir(onnx_module_path):
#                     paths_to_add.append(onnx_module_path)

#                     # capi 하위 폴더 (DLL이 주로 여기 있음)
#                     capi_path = os.path.join(onnx_module_path, "capi")
#                     if os.path.isdir(capi_path):
#                         paths_to_add.append(capi_path)
#         except (ImportError, AttributeError):
#             pass  # onnxruntime 미설치 시 스킵

#         # 3. PATH 환경 변수에 추가
#         if paths_to_add:
#             current_path = os.environ.get('PATH', '')
#             new_paths = [p for p in paths_to_add if p not in current_path]

#             if new_paths:
#                 os.environ['PATH'] = os.pathsep.join(new_paths) + os.pathsep + current_path
#                 # PATH 업데이트는 조용히 처리

#             # 4. Windows DLL 검색 경로 추가
#             if sys.platform == 'win32' and new_paths:
#                 try:
#                     import ctypes
#                     kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
#                     if hasattr(kernel32, 'AddDllDirectory'):
#                         for dll_path in new_paths:
#                             kernel32.AddDllDirectory(dll_path)
#                 except:
#                     pass

#     except Exception:
#         pass  # 환경 설정 실패는 조용히 무시

# Python 3.13+ 에서는 onnxruntime 사용 불가 - Tesseract OCR로 대체
_onnxruntime_loaded = False
if sys.version_info >= (3, 13):
    # Python 3.13+ using Tesseract OCR mode (onnxruntime not supported)
    pass
else:
    # Python 3.13 미만에서만 onnxruntime 환경 설정 및 로드 시도
    _setup_onnxruntime_environment()
    try:
        import onnxruntime
        _onnxruntime_loaded = True
        # onnxruntime loaded successfully - RapidOCR available
    except Exception as e:
        # onnxruntime not installed - fallback to Tesseract OCR
        pass

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import (
    Qt, QThread, QObject, QTimer, QPoint,
    pyqtSignal, QCoreApplication
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMessageBox,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt5.QtGui import QIcon, QFont, QColor, QPixmap
import time
# Note: sys already imported at line 5
from caller import rest
from caller import ui_controller
import socket
import traceback
import platform
import struct
import logging
import tempfile
from datetime import datetime
from pathlib import Path

# 로깅 시스템 초기화 (다른 모듈 임포트 전에 설정)
# Initialize logging system BEFORE importing other modules
from utils.logging_config import AppLogger, get_logger

AppLogger.setup(
    log_dir=Path("logs"),
    level="INFO",
    console_level="INFO",
    file_level="DEBUG"
)

# Logger setup for this module
logger = get_logger(__name__)

from ui import login_Ui
from ui import process_ui


def check_system_requirements():
    """
    시스템 사양을 체크하고 결과를 반환합니다.
    Returns: (can_run: bool, issues: list, warnings: list, specs: dict)
    """
    issues = []      # 실행 불가능한 문제
    warnings = []    # 경고 (실행은 가능하지만 느릴 수 있음)
    specs = {}

    # 1. 64비트 체크
    is_64bit = struct.calcsize("P") * 8 == 64
    specs['architecture'] = '64bit' if is_64bit else '32bit'
    if not is_64bit:
        issues.append("32비트 시스템에서는 실행할 수 없습니다. 64비트 Windows가 필요합니다.")

    # 2. Windows 버전 체크
    os_version = platform.version()
    os_release = platform.release()
    specs['os'] = f"Windows {os_release} ({os_version})"
    try:
        major_version = int(os_release) if os_release.isdigit() else 10
        if major_version < 10:
            issues.append(f"Windows {os_release}은 지원되지 않습니다. Windows 10 이상이 필요합니다.")
    except (ValueError, AttributeError):
        pass  # Version parsing failed, assume compatible

    # 3. RAM 체크
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        c_ulonglong = ctypes.c_ulonglong

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', c_ulonglong),
                ('ullAvailPhys', c_ulonglong),
                ('ullTotalPageFile', c_ulonglong),
                ('ullAvailPageFile', c_ulonglong),
                ('ullTotalVirtual', c_ulonglong),
                ('ullAvailVirtual', c_ulonglong),
                ('ullAvailExtendedVirtual', c_ulonglong),
            ]

        mem_status = MEMORYSTATUSEX()
        mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))

        total_ram_gb = mem_status.ullTotalPhys / (1024 ** 3)
        avail_ram_gb = mem_status.ullAvailPhys / (1024 ** 3)
        specs['ram_total'] = f"{total_ram_gb:.1f}GB"
        specs['ram_available'] = f"{avail_ram_gb:.1f}GB"

        if total_ram_gb < 4:
            issues.append(f"RAM이 {total_ram_gb:.1f}GB로 부족합니다. 최소 8GB 이상 필요합니다.")
        elif total_ram_gb < 8:
            warnings.append(f"RAM이 {total_ram_gb:.1f}GB입니다. 8GB 이상 권장됩니다. (느릴 수 있음)")
    except Exception as e:
        specs['ram_total'] = "확인 불가"
        warnings.append("RAM 용량을 확인할 수 없습니다.")

    # 4. CPU 체크 (AVX 지원 여부는 직접 확인 어려움, 코어 수로 대체)
    cpu_count = os.cpu_count() or 1
    specs['cpu_cores'] = cpu_count
    specs['cpu_name'] = platform.processor() or "알 수 없음"

    if cpu_count < 2:
        warnings.append(f"CPU 코어가 {cpu_count}개입니다. 4코어 이상 권장됩니다.")
    elif cpu_count < 4:
        warnings.append(f"CPU 코어가 {cpu_count}개입니다. 처리 속도가 느릴 수 있습니다.")

    # 5. 디스크 공간 체크
    try:
        import shutil
        total, used, free = shutil.disk_usage(os.getcwd())
        free_gb = free / (1024 ** 3)
        specs['disk_free'] = f"{free_gb:.1f}GB"

        if free_gb < 2:
            issues.append(f"디스크 여유 공간이 {free_gb:.1f}GB로 부족합니다. 최소 5GB 필요.")
        elif free_gb < 5:
            warnings.append(f"디스크 여유 공간이 {free_gb:.1f}GB입니다. 5GB 이상 권장.")
    except OSError:
        specs['disk_free'] = "확인 불가"

    # 6. ffmpeg 체크 (강화된 검증)
    try:
        import subprocess
        ffmpeg_found = False
        ffprobe_found = False

        # ffmpeg 확인
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            if result.returncode == 0:
                ffmpeg_found = True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            # 시스템 ffmpeg 없음, imageio_ffmpeg 확인
            try:
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                if ffmpeg_path and os.path.exists(ffmpeg_path):
                    ffmpeg_found = True
            except (ImportError, AttributeError, OSError):
                pass

        # ffprobe 확인
        try:
            subprocess.run(['ffprobe', '-version'], capture_output=True, timeout=5,
                          creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            ffprobe_found = True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass

        if ffmpeg_found:
            if ffprobe_found:
                specs['ffmpeg'] = "완전 (ffmpeg + ffprobe)"
            else:
                # ffprobe가 없어도 ffmpeg만으로 충분히 동작함 - 경고 표시하지 않음
                specs['ffmpeg'] = "설치됨"
        else:
            specs['ffmpeg'] = "없음"
            warnings.append("ffmpeg가 설치되지 않았습니다. 영상 처리 기능을 사용할 수 없습니다.")
    except Exception as e:
        specs['ffmpeg'] = "확인 실패"
        warnings.append(f"ffmpeg 확인 중 오류: {e}")

    can_run = len(issues) == 0
    return can_run, issues, warnings, specs


def show_system_check_dialog():
    """시스템 사양 체크 결과를 팝업으로 표시"""
    can_run, issues, warnings, specs = check_system_requirements()

    # 사양 정보 문자열 생성
    spec_text = (
        f"[시스템 사양]\n"
        f"• OS: {specs.get('os', '알 수 없음')}\n"
        f"• 아키텍처: {specs.get('architecture', '알 수 없음')}\n"
        f"• CPU: {specs.get('cpu_name', '알 수 없음')} ({specs.get('cpu_cores', '?')}코어)\n"
        f"• RAM: {specs.get('ram_total', '알 수 없음')} (사용 가능: {specs.get('ram_available', '?')})\n"
        f"• 디스크 여유: {specs.get('disk_free', '알 수 없음')}\n"
        f"• FFmpeg: {specs.get('ffmpeg', '확인 불가')}"
    )

    if not can_run:
        # 실행 불가능 - 오류 표시 후 종료
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("시스템 요구사항 미충족")
        msg.setText("이 컴퓨터에서는 프로그램을 실행할 수 없습니다.")

        detail = spec_text + "\n\n[문제점]\n"
        for issue in issues:
            detail += f"❌ {issue}\n"
        if warnings:
            detail += "\n[경고]\n"
            for warn in warnings:
                detail += f"⚠️ {warn}\n"

        msg.setDetailedText(detail)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        return False

    elif warnings:
        # 경고가 있지만 실행 가능 - 확인 후 계속
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("시스템 사양 확인")
        msg.setText("프로그램을 실행할 수 있지만, 일부 제한이 있을 수 있습니다.\n계속 진행하시겠습니까?")

        detail = spec_text + "\n\n[경고]\n"
        for warn in warnings:
            detail += f"⚠️ {warn}\n"

        msg.setDetailedText(detail)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)

        result = msg.exec_()
        return result == QMessageBox.Yes

    else:
        # 문제 없음 - 조용히 통과 (팝업 없이)
        # System specs meet requirements
        return True


def get_safe_tts_base_dir():
    """
    TTS 출력을 위한 안전한 기본 디렉토리를 반환합니다.
    쓰기 권한이 없으면 사용자 홈 디렉토리를 사용합니다.

    Returns:
        str: TTS 출력 기본 디렉토리 경로
    """
    # 프로그램 기본 경로 (frozen 여부에 따라 다름)
    if getattr(sys, "frozen", False):
        # PyInstaller로 패키징된 경우
        base_path = os.path.dirname(sys.executable)
    else:
        # 일반 Python 스크립트 실행
        base_path = os.path.dirname(os.path.abspath(__file__))

    # 기본 경로에 쓰기 권한이 있는지 확인
    base_tts_dir = os.path.join(base_path, "tts_output")

    # 쓰기 권한 확인을 위한 테스트
    try:
        os.makedirs(base_tts_dir, exist_ok=True)
        test_file = os.path.join(base_tts_dir, ".write_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
    except (PermissionError, OSError):
        # 기본 경로에 쓰기 권한이 없으면 사용자 홈 디렉토리 사용
        user_dir = os.path.expanduser("~")
        base_tts_dir = os.path.join(user_dir, "shoppingShortsMaker", "tts_output")
        logger.info("[TTS] 기본 경로 쓰기 불가, 대체 경로 사용: %s", base_tts_dir)

    return base_tts_dir


class Initializer(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    progressChanged = QtCore.pyqtSignal(int)
    checkItemChanged = QtCore.pyqtSignal(str, str, str)  # item_id, status, message
    statusChanged = QtCore.pyqtSignal(str)  # status message
    ocrReaderReady = QtCore.pyqtSignal(object)  # OCR reader 전달
    initWarnings = QtCore.pyqtSignal(list)  # 초기화 경고/오류 목록 전달

    # 각 검사 항목의 영향 설명 (사용자 친화적 메시지)
    CHECK_ITEM_IMPACTS = {
        "system": {
            "name": "시스템 환경",
            "critical": True,
            "impact": "프로그램 실행이 불안정하거나 느릴 수 있습니다.",
            "solution": "메모리 8GB 이상, 저장 공간 5GB 이상 확보를 권장합니다."
        },
        "fonts": {
            "name": "자막 폰트",
            "critical": False,
            "impact": "자막 폰트가 기본 폰트로 대체되어 디자인이 다를 수 있습니다.",
            "solution": "fonts 폴더에 필요한 폰트 파일을 추가해주세요."
        },
        "ffmpeg": {
            "name": "영상 인코더",
            "critical": True,
            "impact": "영상 생성 기능을 사용할 수 없습니다.",
            "solution": "프로그램을 재설치하거나 고객센터에 문의해주세요."
        },
        "internet": {
            "name": "인터넷 연결",
            "critical": True,
            "impact": "번역, 음성, AI 분석 기능을 사용할 수 없습니다.",
            "solution": "인터넷 연결을 확인해주세요."
        },
        "modules": {
            "name": "프로그램 구성요소",
            "critical": True,
            "impact": "일부 기능이 작동하지 않을 수 있습니다.",
            "solution": "프로그램을 재설치해주세요."
        },
        "ocr": {
            "name": "자막 인식 엔진",
            "critical": False,
            "impact": "중국어 자막 자동 인식이 불가능합니다. 수동 입력만 가능합니다.",
            "solution": "첫 실행 시 자동 다운로드됩니다. 인터넷 연결을 확인해주세요."
        },
        "tts_dir": {
            "name": "음성 저장 폴더",
            "critical": False,
            "impact": "음성 파일 저장에 문제가 있을 수 있습니다.",
            "solution": "프로그램 폴더에 쓰기 권한이 있는지 확인해주세요."
        },
        "api": {
            "name": "서비스 연결",
            "critical": False,
            "impact": "일부 서비스 연결에 문제가 있습니다.",
            "solution": "인터넷 연결 후 다시 시도해주세요."
        }
    }

    def run(self):
        emit_finished = True  # finally에서 finished.emit() 호출 여부 제어
        try:
            # 경고/오류 수집용 리스트
            init_issues = []  # [(item_id, status, message), ...]

            # 1. 시스템 사양 확인 (0-12%)
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

            # 2. 폰트 확인 (12-24%)
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

            # 3. 영상 인코더 확인 (24-36%)
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

            # 4. 인터넷 연결 확인 (36-48%)
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

            # 5. 프로그램 구성요소 확인 (48-60%)
            self.checkItemChanged.emit("modules", "checking", "")
            self.statusChanged.emit("프로그램 구성요소를 확인하고 있습니다...")
            time.sleep(0.2)
            modules_ok, modules_msg = self._check_all_modules()
            if modules_ok:
                self.checkItemChanged.emit("modules", "success", modules_msg)
            else:
                self.checkItemChanged.emit("modules", "error", modules_msg)
                init_issues.append(("modules", "error", modules_msg))
                # 필수 모듈 누락 시 초기화 중단
                self.progressChanged.emit(100)
                self.initWarnings.emit(init_issues)
                self.statusChanged.emit("❌ 필수 구성요소 누락으로 초기화를 중단합니다.")
                time.sleep(1.0)
                emit_finished = False  # finally에서 중복 emit 방지
                self.finished.emit()
                return
            self.progressChanged.emit(60)

            # 6. 자막 인식 엔진 로딩 (60-85%) - 가장 오래 걸림
            self.checkItemChanged.emit("ocr", "checking", "")
            self.statusChanged.emit("🔍 자막 인식 엔진 준비 중... (첫 실행시 1-2분)")
            ocr_reader = self._init_ocr()
            if ocr_reader:
                self.checkItemChanged.emit("ocr", "success", "준비 완료")
            else:
                # OCR 없어도 수동 자막 입력으로 사용 가능 - 경고 표시하지 않음
                self.checkItemChanged.emit("ocr", "success", "수동 모드")
            self.progressChanged.emit(85)

            # 7. 음성 저장 폴더 준비 (85-95%)
            self.checkItemChanged.emit("tts_dir", "checking", "")
            self.statusChanged.emit("📁 음성 저장 폴더 준비 중...")
            time.sleep(0.2)
            tts_ok, tts_msg = self._prepare_tts_directory()
            if tts_ok:
                self.checkItemChanged.emit("tts_dir", "success", tts_msg)
            else:
                self.checkItemChanged.emit("tts_dir", "warning", tts_msg)
                init_issues.append(("tts_dir", "warning", "음성 저장 폴더 생성 실패"))
            self.progressChanged.emit(95)

            # 8. 서비스 연결 준비 (95-100%)
            self.checkItemChanged.emit("api", "checking", "")
            self.statusChanged.emit("서비스 연결을 준비하고 있습니다...")
            time.sleep(0.2)
            self.checkItemChanged.emit("api", "success", "준비 완료")
            self.progressChanged.emit(100)

            # 경고/오류가 있으면 신호 발송
            if init_issues:
                self.initWarnings.emit(init_issues)
                self.statusChanged.emit("⚠️ 일부 항목에 문제가 있습니다...")
                time.sleep(0.5)
            else:
                self.statusChanged.emit("✨ 모든 점검 완료! 시작합니다...")
            time.sleep(0.3)

            # OCR reader 전달
            self.ocrReaderReady.emit(ocr_reader)

        except Exception as e:
            logger.error("초기화 중 오류 발생: %s", e, exc_info=True)
        finally:
            if emit_finished:
                self.finished.emit()

    def _get_fonts_dir(self):
        """폰트 폴더 경로 반환"""
        if getattr(sys, "frozen", False):
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, "fonts")

    def _check_fonts(self):
        """폰트 확인 (자막용 + UI용 통합) - 필수 폰트 검증 강화"""
        try:
            fonts_dir = self._get_fonts_dir()
            # 필수 폰트 (자막 렌더링에 실제 사용)
            required_fonts = [
                "SeoulHangangB.ttf",      # seoul_hangang
                "Pretendard-Bold.ttf",    # pretendard
                "GmarketSansTTFBold.ttf", # gmarket
                "Paperlogy-9Black.ttf",   # paperlogy
            ]
            # 선택적 폰트
            optional_fonts = [
                "유앤피플 고딕 KS.ttf"  # uandpeople (UI용)
            ]

            found_required = [f for f in required_fonts if os.path.exists(os.path.join(fonts_dir, f))]
            found_optional = [f for f in optional_fonts if os.path.exists(os.path.join(fonts_dir, f))]

            total_found = len(found_required) + len(found_optional)
            missing_required = [f for f in required_fonts if f not in found_required]

            # 필수 폰트 누락 시 경고
            if len(found_required) < len(required_fonts):
                missing_names = ", ".join([f.split('.')[0][:10] for f in missing_required[:2]])
                return True, f"⚠ {missing_names}... 누락"

            # 모든 폰트 정상
            if total_found >= 4:
                return True, f"{total_found}개 확인"
            else:
                return True, f"{total_found}개만"

        except Exception as e:
            return False, f"오류: {str(e)[:20]}"

    def _check_ffmpeg(self):
        """FFmpeg 확인 - ffmpeg, ffprobe, 기본 코덱 지원 확인"""
        import subprocess

        ffmpeg_path = None
        ffprobe_path = None

        # 1. ffmpeg 실행 파일 확인
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5,
                                  creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            if result.returncode == 0:
                ffmpeg_path = 'ffmpeg'
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            # 시스템 ffmpeg 없음, imageio_ffmpeg 확인
            try:
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                    return False, "없음"
            except (ImportError, AttributeError, OSError):
                return False, "없음"

        # 2. ffprobe 확인 (메타데이터 읽기에 필요)
        try:
            subprocess.run(['ffprobe', '-version'], capture_output=True, timeout=5,
                          creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            ffprobe_path = 'ffprobe'
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            # ffprobe가 없으면 경고 (일부 기능 제한)
            pass

        # 3. 기본 코덱 지원 확인 (h264, aac)
        try:
            result = subprocess.run([ffmpeg_path if isinstance(ffmpeg_path, str) else 'ffmpeg', '-codecs'],
                                  capture_output=True, text=True, timeout=5,
                                  creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            if result.returncode == 0:
                codecs_output = result.stdout
                has_h264 = 'h264' in codecs_output.lower()
                has_aac = 'aac' in codecs_output.lower()

                if not (has_h264 and has_aac):
                    return True, "제한적"  # ffmpeg는 있지만 주요 코덱 누락
        except (subprocess.SubprocessError, OSError):
            pass  # 코덱 확인 실패해도 ffmpeg 자체는 있으므로 계속

        # 모든 확인 통과 - ffprobe 없어도 정상 동작
        return True, "완전"

    def _check_internet(self):
        """인터넷 연결 확인 (다중 엔드포인트 fallback + 안전한 소켓 처리)"""
        # 여러 엔드포인트 시도 (방화벽/사내망 대응)
        endpoints = [
            ("8.8.8.8", 53, "Google DNS"),
            ("1.1.1.1", 53, "Cloudflare DNS"),
            ("208.67.222.222", 53, "OpenDNS"),
        ]

        for host, port, name in endpoints:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((host, port))
                return True, f"연결됨 ({name})"
            except Exception:
                continue
            finally:
                # 소켓이 생성되었으면 항상 닫기
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

        # 모든 엔드포인트 실패
        return False, "연결 안됨 (모든 엔드포인트 실패)"

    def _check_all_modules(self):
        import importlib.util

        # 1) 필수 모듈: 실제 import로 확인 (여기서 DLL이 로드될 수 있음)
        #    -> cv2는 제외!
        critical_import_modules = [
            ('PIL', '이미지'),
            ('moviepy', '영상'),
            ('numpy', '연산'),
        ]

        # 2) 필수 모듈(존재만 확인): import 없이 스펙만 확인
        critical_spec_modules = [
            ('cv2', '비전'),
        ]

        # 3) 선택적 모듈: import로 확인해도 되지만, cv2는 여기에도 넣지 말 것
        # Python 3.13+에서는 rapidocr_onnxruntime 체크 제외
        optional_modules = [
            ('faster_whisper', '음성'),
            ('pytesseract', '문자'),
            ('pydub', '오디오'),
        ]
        # Python 3.13 미만에서만 RapidOCR 체크
        if sys.version_info < (3, 13):
            optional_modules.insert(1, ('rapidocr_onnxruntime', '문자(RapidOCR)'))

        critical_missing = []
        optional_missing = []

        # --- 필수(import) 검사 ---
        for mod_name, display_name in critical_import_modules:
            try:
                __import__(mod_name)
            except Exception:
                critical_missing.append(display_name)

        # --- 필수(spec) 검사 (cv2는 import 금지) ---
        for mod_name, display_name in critical_spec_modules:
            try:
                if importlib.util.find_spec(mod_name) is None:
                    critical_missing.append(display_name)
            except Exception:
                critical_missing.append(display_name)

        # --- 선택적(import) 검사 ---
        for mod_name, display_name in optional_modules:
            try:
                __import__(mod_name)
            except Exception:
                optional_missing.append(display_name)

        # 핵심 모듈이 하나라도 없으면 오류
        if critical_missing:
            missing_str = ', '.join(critical_missing)
            return False, f"필수 모듈 누락: {missing_str}"

        # 선택적 모듈이 없으면 경고
        total = len(critical_import_modules) + len(critical_spec_modules) + len(optional_modules)
        found = total - len(optional_missing)
        if optional_missing:
            return True, f"{found}/{total} (일부 제한: {', '.join(optional_missing)})"
        else:
            return True, f"{found}/{total} 정상"


    def _init_ocr(self):
        """OCR 모델 초기화 - RapidOCR 우선, Tesseract 폴백"""
        
        try:
            from utils.ocr_backend import create_ocr_reader
            reader = create_ocr_reader()
            if reader:
                # OCR engine loaded successfully
                return reader
            # OCR engine not available - OCR disabled
            return None
        except Exception:
            import traceback
            # OCR loading failed
            traceback.print_exc()
            return None

    def _prepare_tts_directory(self):
        """TTS 출력 디렉토리 준비 - 안전한 쓰기 가능 경로 사용"""
        try:
            # 공통 함수를 사용하여 안전한 기본 디렉토리 확보
            base_tts_dir = get_safe_tts_base_dir()

            voice_sample_dir = os.path.join(base_tts_dir, "voice_samples")
            os.makedirs(base_tts_dir, exist_ok=True)
            os.makedirs(voice_sample_dir, exist_ok=True)

            logger.debug("[TTS] 출력 경로: %s", base_tts_dir)
            return True, "준비 완료"
        except Exception as e:
            logger.error("[TTS] 디렉토리 생성 실패: %s", e, exc_info=True)
            return False, "실패"

    def showCustomMessageBox(self, title, message):
        icon_path = 'resource/trayIcon.png'
        msgBox = QtWidgets.QMessageBox()
        msgBox.setWindowTitle(title)
        msgBox.setWindowIcon(QtGui.QIcon(icon_path))
        msgBox.setText(f" \nㅤㅤ{message}ㅤㅤㅤ\n ")
        msgBox.exec_()
            
            
class ProcessWindow(QMainWindow, process_ui.Process_Ui):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('resource/icons/trayIcon.png'))
        self.setupUi(self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        
class Login(QMainWindow, login_Ui.Ui_LoginWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        login_Ui.Ui_LoginWindow.__init__(self)
        self.setWindowIcon(QIcon('resource/trayIcon.png'))
        
        if self.setPort() :
            
            self.setupUi(self)
                        
            ui_controller.userLoadInfo(self)
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.loginButton.clicked.connect(self._loginCheck)
            self.minimumButton.clicked.connect(self._minimumWindow)
            self.exitButton.clicked.connect(self._closeWindow)
            self.registerRequestButton.clicked.connect(self._openRegistrationDialog)
        
        else :
            self.showCustomMessageBox('프로그램 실행 오류', '이미 실행중인 프로그램이 있습니다') 
            sys.exit()
    
    def setPort(self) :
        self.PROCESS_PORT = 20022  
        
        try :
            serverSocket  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            serverSocket.bind(('localhost', self.PROCESS_PORT))
            serverSocket.listen(3)
            self.serverSocket = serverSocket

            return True
        except (OSError, socket.error) as e:
            # Port may be in use or socket creation failed
            return False
        
    def closeSocket(self):
        if hasattr(self, 'serverSocket'):
            self.serverSocket.close()
        
    def _loginCheck(self):
        try:
            # 네트워크 연결을 통한 IP 확인
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(5)  # 5초 타임아웃
            s.connect(("8.8.8.8", 80))
            userIp = s.getsockname()[0]
            s.close()
        except (socket.timeout, socket.error, OSError) as e:
            logger.warning("[Login] 네트워크 오류: %s", e, exc_info=True)
            self.showCustomMessageBox('네트워크 오류', '인터넷 연결을 확인해주세요')
            return

        userId = self.idEdit.text()
        userPw = self.pwEdit.text()
        cbSaveInfo = self.idpw_checkbox.isChecked()

        try:
            version = rest.getVersion()
        except Exception as e:
            logger.error("[Login] 버전 확인 실패: %s", e, exc_info=True)
            self.showCustomMessageBox('서버 연결 오류', '서버에 접속할 수 없습니다\n잠시 후 다시 시도해주세요')
            return

        force = False
        ui_controller.userSaveInfo(self, cbSaveInfo, userId, userPw, version)

        data = {'userId':userId,'userPw':userPw, "key":"ssmaker" ,"ip":userIp, "force":force}

        try:
            loginCheckInfo = rest.login(**data)
        except Exception as e:
            logger.error("[Login] 로그인 요청 실패: %s", e, exc_info=True)
            self.showCustomMessageBox('서버 연결 오류', '로그인 서버에 접속할 수 없습니다\n잠시 후 다시 시도해주세요')
            return

        # 응답 검증
        if not isinstance(loginCheckInfo, dict):
            logger.warning("[Login] 잘못된 응답 형식 수신")
            self.showCustomMessageBox('로그인 오류', '서버 응답이 올바르지 않습니다')
            return

        loginStatus = loginCheckInfo.get('status', False)
        # SECURITY: Do not log loginCheckInfo or loginStatus as they may contain sensitive data
        loginMessage = ""
        if loginStatus == False:
            loginMessage = loginCheckInfo.get('message', '')

        try:
            if loginStatus != True:
                if loginStatus == "EU001" or loginMessage == "EU001":
                    self.showCustomMessageBox('로그인 에러', '올바른 계정정보를 입력해주세요')

                elif loginStatus == "EU002" or loginMessage == "EU002":
                    self.showCustomMessageBox('로그인 에러', '이용기간이 만료되었습니다')

                elif loginStatus == "EU003" or loginMessage == "EU003":
                    self.showOtherPlaceMessageBox('중복 로그인', '다른 장소에서 로그인 중입니다 \nㅤㅤ접속을 끊고 로그인하시겠습니까???ㅤㅤ')
                else:
                    # 알 수 없는 오류
                    msg = loginMessage if loginMessage else "알 수 없는 오류가 발생했습니다"
                    self.showCustomMessageBox('로그인 에러', msg)
            else:
                # 로그인 성공 - data 필드 깊이 검증
                if 'data' not in loginCheckInfo:
                    logger.warning("[Login] 응답에 'data' 필드 없음")
                    self.showCustomMessageBox('로그인 오류', '서버 응답이 올바르지 않습니다')
                    return

                # data 타입 검증
                if not isinstance(loginCheckInfo.get('data'), dict):
                    logger.warning("[Login] 응답의 'data'가 dict가 아님: %s", type(loginCheckInfo.get('data')).__name__)
                    self.showCustomMessageBox('로그인 오류', '서버 응답 형식이 올바르지 않습니다')
                    return

                # data.data.id 구조 검증 (main.py 1471에서 사용)
                inner_data = loginCheckInfo['data'].get('data')
                if not isinstance(inner_data, dict):
                    logger.warning("[Login] 응답의 'data.data'가 dict가 아님: %s", type(inner_data).__name__)
                    self.showCustomMessageBox('로그인 오류', '서버 응답 구조가 올바르지 않습니다')
                    return

                if 'id' not in inner_data:
                    logger.warning("[Login] 응답의 'data.data.id' 필드 없음")
                    self.showCustomMessageBox('로그인 오류', '사용자 정보가 올바르지 않습니다')
                    return

                loginCheckInfo['data']['ip'] = userIp

                # 컨트롤러를 통해 로딩 단계로 전환
                if hasattr(self, 'controller') and self.controller:
                    self.controller.on_login_success(loginCheckInfo)
                else:
                    # 폴백: 기존 방식
                    self.close()
                    app = QtWidgets.QApplication.instance()
                    if app is not None:
                        app.login_data = loginCheckInfo
                    QtCore.QCoreApplication.quit()

        except Exception as e:
            logger.error("[Login] 로그인 처리 중 오류: %s", e, exc_info=True)
            self.showCustomMessageBox('로그인 오류', '로그인 처리 중 오류가 발생했습니다')
            
    def showOtherPlaceMessageBox(self, title, message):
        icon_path = 'resource/trayIcon.png'
        msgBox = QtWidgets.QMessageBox()
        msgBox.setWindowTitle(title)
        msgBox.setWindowIcon(QtGui.QIcon(icon_path))
        msgBox.setText(f" \nㅤㅤㅤ{message}ㅤㅤ\n ")
            
        yes_button = msgBox.addButton("확인", QtWidgets.QMessageBox.YesRole)
        no_button = msgBox.addButton("취소", QtWidgets.QMessageBox.NoRole)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1) 
        button_layout.addWidget(yes_button)
        button_layout.addWidget(no_button)
        button_layout.addStretch(1)
        
        layout = msgBox.layout()
        item_count = layout.count()
        # for i in range(item_count - 1, -1, -1):
        #     item = layout.itemAt(i)
        #     if isinstance(item.widget(), QtWidgets.QPushButton):
        #         layout.removeItem(item)
        layout.addLayout(button_layout, layout.rowCount(), 0, 1, layout.columnCount())
        reply = msgBox.exec_()

        if msgBox.clickedButton() == yes_button:
            try:
                # 네트워크 연결을 통한 IP 확인
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(5)
                s.connect(("8.8.8.8", 80))
                userIp = s.getsockname()[0]
                s.close()
            except (socket.timeout, socket.error, OSError) as e:
                logger.warning("[Login] 네트워크 오류: %s", e, exc_info=True)
                self.showCustomMessageBox('네트워크 오류', '인터넷 연결을 확인해주세요')
                return

            userId = self.idEdit.text()
            userPw = self.pwEdit.text()

            data = {'userId':userId,'userPw':userPw, "key":"ssmaker" ,"ip":userIp, "force": True}

            try:
                loginCheckInfo = rest.login(**data)
            except Exception as e:
                logger.error("[Login] 강제 로그인 요청 실패: %s", e, exc_info=True)
                self.showCustomMessageBox('서버 연결 오류', '로그인 서버에 접속할 수 없습니다\n잠시 후 다시 시도해주세요')
                return

            # 응답 검증
            if not isinstance(loginCheckInfo, dict):
                logger.warning("[Login] 잘못된 응답 형식 수신")
                self.showCustomMessageBox('로그인 오류', '서버 응답이 올바르지 않습니다')
                return

            # 로그인 성공 여부 확인
            loginStatus = loginCheckInfo.get('status', False)
            if loginStatus != True:
                loginMessage = loginCheckInfo.get('message', '강제 로그인에 실패했습니다')
                self.showCustomMessageBox('로그인 오류', loginMessage)
                return

            # data 필드 검증
            if 'data' not in loginCheckInfo or not isinstance(loginCheckInfo['data'], dict):
                logger.warning("[Login] 응답에 'data' 필드 없음")
                self.showCustomMessageBox('로그인 오류', '서버 응답이 올바르지 않습니다')
                return

            # data.data.id 구조 검증 (정상 로그인과 동일)
            inner_data = loginCheckInfo['data'].get('data')
            if not isinstance(inner_data, dict):
                logger.warning("[Login] 강제 로그인 응답의 'data.data'가 dict가 아님: %s", type(inner_data).__name__)
                self.showCustomMessageBox('로그인 오류', '서버 응답 구조가 올바르지 않습니다')
                return

            if 'id' not in inner_data:
                logger.warning("[Login] 강제 로그인 응답의 'data.data.id' 필드 없음")
                self.showCustomMessageBox('로그인 오류', '사용자 정보가 올바르지 않습니다')
                return

            loginCheckInfo['data']['ip'] = userIp

            # 컨트롤러를 통해 로딩 단계로 전환
            if hasattr(self, 'controller') and self.controller:
                self.controller.on_login_success(loginCheckInfo)
            else:
                self.close()
                app = QtWidgets.QApplication.instance()
                if app is not None:
                    app.login_data = loginCheckInfo
                QtCore.QCoreApplication.quit()
        
    def showCustomMessageBox(self, title, message):
        icon_path = 'resource/trayIcon.png'
        msgBox = QtWidgets.QMessageBox()
        msgBox.setWindowTitle(title)
        msgBox.setWindowIcon(QtGui.QIcon(icon_path))
        msgBox.setText(f" \nㅤㅤ{message}ㅤㅤㅤ\n ")
        msgBox.exec_()
    
    def _openRegistrationDialog(self):
        """회원가입 요청 다이얼로그 열기"""
        from ui.login_ui_modern import RegistrationRequestDialog

        # 다이얼로그 생성
        self.registrationDialog = RegistrationRequestDialog(self)
        self.registrationDialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.registrationDialog.setFixedSize(400, 580)

        # 시그널 연결
        self.registrationDialog.backRequested.connect(self._closeRegistrationDialog)
        self.registrationDialog.registrationRequested.connect(self._submitRegistrationRequest)

        # 중앙에 위치
        self.registrationDialog.move(
            self.x() + (self.width() - self.registrationDialog.width()) // 2,
            self.y() + (self.height() - self.registrationDialog.height()) // 2
        )
        self.registrationDialog.show()

    def _closeRegistrationDialog(self):
        """회원가입 요청 다이얼로그 닫기"""
        if hasattr(self, 'registrationDialog') and self.registrationDialog:
            self.registrationDialog.close()
            self.registrationDialog = None

    def _submitRegistrationRequest(self, name: str, username: str, password: str, contact: str):
        """회원가입 요청 제출"""
        try:
            # 백엔드 API 호출
            result = rest.submitRegistrationRequest(
                name=name,
                username=username,
                password=password,
                contact=contact
            )

            if result.get('success'):
                self.showCustomMessageBox(
                    '가입 요청 완료',
                    '회원가입 요청이 접수되었습니다.\n관리자 승인 후 로그인이 가능합니다.'
                )
                self._closeRegistrationDialog()
            else:
                error_msg = result.get('message', '회원가입 요청에 실패했습니다.')
                self.showCustomMessageBox('요청 실패', error_msg)

        except Exception as e:
            logger.error("[Registration] 회원가입 요청 실패: %s", e, exc_info=True)
            self.showCustomMessageBox(
                '요청 실패',
                '서버 연결에 실패했습니다.\n잠시 후 다시 시도해주세요.'
            )
        
    def _minimumWindow(self):
        self.showMinimized()

    def _closeWindow(self):
        self.closeSocket()
        QCoreApplication.instance().quit()
                
    def keyPressEvent(self, e): 
        if e.key() in [Qt.Key_Return, Qt.Key_Enter] :
            self._loginCheck()
    
    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.oldPos != None :
                
            delta = QPoint (event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y()+ delta.y())
            self.oldPos = event.globalPos()
            
    def mouseReleaseEvent(self, event) :
        self.oldPos =None

class AppController:
    """로그인 → 로딩 → 메인앱 흐름 제어"""
    def __init__(self, app):
        self.app = app
        self.login_data = None
        self.ocr_reader = None
        self.login_window = None
        self.loading_window = None
        self.thread = None
        self.initializer = None
        self.init_issues = []  # 초기화 문제 저장

    def start(self):
        """로그인 창 표시"""
        self.login_window = Login()
        self.login_window.controller = self  # 컨트롤러 참조 전달
        self.login_window.show()

    def on_login_success(self, login_data):
        """로그인 성공 시 호출"""
        self.login_data = login_data
        self.login_window.closeSocket()  # 소켓 정리
        self.login_window.close()

        # 로딩 창 표시
        self.loading_window = ProcessWindow()
        self.loading_window.show()

        # 초기화 시작
        self.initializer = Initializer()
        self.thread = QtCore.QThread()
        self.initializer.moveToThread(self.thread)

        self.initializer.progressChanged.connect(self._update_progress)
        self.initializer.checkItemChanged.connect(self.loading_window.updateCheckItem)
        self.initializer.statusChanged.connect(self.loading_window.statusLabel.setText)
        self.initializer.ocrReaderReady.connect(self._on_ocr_ready)
        self.initializer.initWarnings.connect(self._on_init_warnings)
        self.initializer.finished.connect(self._on_loading_finished)

        self.thread.started.connect(self.initializer.run)
        self.thread.start()

    def _update_progress(self, value):
        self.loading_window.progressBar.setValue(value)
        self.loading_window.percentLabel.setText(f"{value}%")

    def _on_ocr_ready(self, ocr_reader):
        self.ocr_reader = ocr_reader

    def _on_init_warnings(self, issues):
        """초기화 경고/오류 처리"""
        self.init_issues = issues

    def _show_init_warnings_popup(self):
        """초기화 문제 안내 팝업 표시"""
        if not self.init_issues:
            return True  # 문제 없으면 계속 진행

        # 심각한 오류와 경고 분리
        errors = [(item_id, msg) for item_id, status, msg in self.init_issues if status == "error"]
        warnings = [(item_id, msg) for item_id, status, msg in self.init_issues if status == "warning"]

        # critical 항목 오류 확인 (Hard Stop)
        has_critical_error = any(
            Initializer.CHECK_ITEM_IMPACTS.get(item_id, {}).get("critical", False)
            for item_id, _ in errors
        )

        # 메시지 구성
        msg_parts = []

        if errors:
            msg_parts.append("❌ 심각한 문제 (기능 제한):\n")
            for item_id, msg in errors:
                impact_info = Initializer.CHECK_ITEM_IMPACTS.get(item_id, {})
                name = impact_info.get("name", item_id)
                impact = impact_info.get("impact", "기능에 영향이 있을 수 있습니다.")
                solution = impact_info.get("solution", "")
                msg_parts.append(f"• {name}: {impact}\n")
                if msg:  # 구체적인 오류 메시지 추가 (예: 누락된 모듈 목록)
                    msg_parts.append(f"  상세: {msg}\n")
                if solution:
                    msg_parts.append(f"  → {solution}\n")
            msg_parts.append("\n")

        if warnings:
            msg_parts.append("⚠️ 경고 (일부 기능 제한):\n")
            for item_id, msg in warnings:
                impact_info = Initializer.CHECK_ITEM_IMPACTS.get(item_id, {})
                name = impact_info.get("name", item_id)
                impact = impact_info.get("impact", "일부 기능이 제한될 수 있습니다.")
                msg_parts.append(f"• {name}: {impact}\n")
                if msg:  # 구체적인 경고 메시지 추가
                    msg_parts.append(f"  상세: {msg}\n")

        detail_text = "".join(msg_parts)

        # critical 항목 오류 시 Hard Stop (계속 진행 불가)
        if has_critical_error:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("필수 구성요소 누락")
            msg.setText("필수 구성요소가 없어 프로그램을 실행할 수 없습니다.")
            msg.setInformativeText("프로그램을 종료합니다.")
            msg.setDetailedText(detail_text)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return False  # 강제 종료

        # 심각한 오류가 있으면 경고 팝업 (계속 진행 여부 선택 가능)
        if errors:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("초기화 문제 발견")
            msg.setText("일부 필수 구성요소에 문제가 있습니다.\n계속 진행하시겠습니까?")
            msg.setInformativeText("일부 기능이 정상적으로 작동하지 않을 수 있습니다.")
            msg.setDetailedText(detail_text)
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            result = msg.exec_()
            return result == QMessageBox.Yes
        else:
            # 경고만 있으면 정보 팝업 (계속 진행)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("초기화 알림")
            msg.setText("일부 구성요소에 주의가 필요합니다.")
            msg.setInformativeText("프로그램은 정상적으로 실행됩니다.")
            msg.setDetailedText(detail_text)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return True

    def _on_loading_finished(self):
        self.thread.quit()

        # 초기화 문제가 있으면 팝업 표시
        should_continue = self._show_init_warnings_popup()

        self.loading_window.close()

        if should_continue:
            # Qt 종료하고 Tkinter로 전환
            QtCore.QCoreApplication.quit()
        else:
            # 사용자가 취소함 - 프로그램 종료
            self.login_data = None  # 메인앱 시작 방지
            QtCore.QCoreApplication.quit()


if __name__ == "__main__":
    # 프로그램 시작 전 패키지 확인 및 설치
    _check_and_install_packages()

    try:
        # Qt HighDPI 스케일링 설정
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

        # PyQt5 5.6+ HighDPI 속성
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

        # PyQt5 5.14+ 추가 속성 (고DPI 모니터에서 더 나은 렌더링)
        try:
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_Use96Dpi, False)
        except AttributeError:
            pass  # PyQt5 버전이 낮으면 무시

        app = QApplication(sys.argv)

        # 폰트 DPI 설정 (고DPI 화면에서 텍스트 선명도 개선)
        font = app.font()
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        app.setFont(font)

        logger.debug("[DPI] Qt HighDPI 스케일링 활성화 완료")

        # 앱 컨트롤러 생성 및 시작
        controller = AppController(app)
        controller.start()

        # Qt 이벤트 루프 실행
        exit_code = app.exec_()

        # 로그인 성공 후 메인 앱 실행
        if controller.login_data:
            import tkinter as tk
            from main import VideoAnalyzerGUI

            root = tk.Tk()
            gui = VideoAnalyzerGUI(root, login_data=controller.login_data, preloaded_ocr=controller.ocr_reader)
            root.mainloop()

        sys.exit(exit_code)

    except Exception as e:
        logger.critical("프로그램 실행 중 치명적 오류 발생: %s", e, exc_info=True)
        # Write error log to temp directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_log_path = os.path.join(tempfile.gettempdir(), f"ssmaker_error_{timestamp}.txt")
        try:
            with open(error_log_path, "w", encoding="utf-8") as f:
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Error: {e}\n\n")
                f.write(traceback.format_exc())
            logger.info("Error log saved to: %s", error_log_path)
        except Exception as log_err:
            logger.error("Failed to write error log: %s", log_err)
        raise
