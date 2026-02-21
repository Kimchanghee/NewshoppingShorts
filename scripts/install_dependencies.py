"""
의존성 패키지 설치 스크립트
시스템에 맞는 패키지를 자동으로 설치합니다.
"""

import os
import sys
import platform
import subprocess
import warnings
import shutil
import logging
import hashlib
from typing import List, Tuple

logger = logging.getLogger(__name__)

_CHI_SIM_SHA256 = "fc05d89ab31d8b4e226910f16a8bcbf78e43bae3e2580bb5feefd052efdab363"



def _configure_stdio_utf8() -> None:
    """Force stdout/stderr to UTF-8 for Windows console."""
    try:
        stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
        stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
        if callable(stdout_reconfigure) and callable(stderr_reconfigure):
            stdout_reconfigure(encoding="utf-8", errors="replace")
            stderr_reconfigure(encoding="utf-8", errors="replace")
        else:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug("Failed to configure UTF-8 stdio: %s", e)


def is_windows() -> bool:
    """Check if running on Windows"""
    return platform.system().lower() == 'windows'


def is_macos() -> bool:
    """Check if running on macOS"""
    return platform.system().lower() == 'darwin'


def is_linux() -> bool:
    """Check if running on Linux"""
    return platform.system().lower() == 'linux'


def has_nvidia_gpu() -> bool:
    """Check if system has NVIDIA GPU (Windows only for now)

    Note: This function checks hardware presence only.
    It should be called AFTER wmi is installed.
    For fallback, also checks nvidia-smi existence.
    """
    if not is_windows():
        return False

    # Method 1: nvidia-smi 체크 (wmi 없어도 동작)
    try:
        result = subprocess.run(
            ['nvidia-smi'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Method 2: WMI 체크 (wmi 패키지 설치 후에만 동작)
    try:
        import wmi
        c = wmi.WMI()
        gpus = c.Win32_VideoController()
        for gpu in gpus:
            if 'nvidia' in gpu.Name.lower():
                return True
    except Exception as e:
        logger.debug("WMI GPU check failed: %s", e)

    return False


def run_command(command: List[str]) -> Tuple[bool, str]:
    """Run shell command and return success status and output"""
    try:
        logger.info("실행 중: %s", ' '.join(command))
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        return False, str(e)


def find_tesseract_cmd() -> str | None:
    env_cmd = os.environ.get("TESSERACT_CMD") or os.environ.get("TESSERACT_PATH")
    if env_cmd and os.path.exists(env_cmd):
        return env_cmd

    which_cmd = shutil.which("tesseract")
    if which_cmd:
        return which_cmd

    if is_windows():
        candidates = [
            r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

    return None


def install_tesseract_windows() -> bool:
    if not is_windows():
        return False

    if find_tesseract_cmd():
        logger.info("[Tesseract] Tesseract already installed")
        return True

    ok, _ = run_command(["winget", "--version"])
    if not ok:
        logger.warning("[Tesseract] winget을 찾을 수 없습니다. 수동 설치가 필요합니다.")
        return False

    logger.info("[Tesseract] winget으로 설치 시도 중...")
    install_cmd = [
        "winget",
        "install",
        "-e",
        "--id",
        "UB-Mannheim.TesseractOCR",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]
    ok, out = run_command(install_cmd)
    if not ok:
        logger.error("[Tesseract] 설치 실패: %s", out[:200])
        return False

    if find_tesseract_cmd():
        logger.info("[Tesseract] Tesseract already installed")
        return True

    logger.warning("[Tesseract] 설치 확인 실패 - 수동 설치 필요")
    return False


def _download_file_safe(url: str, dest_path: str) -> Tuple[bool, str]:
    """
    Download file using urllib directly (no subprocess command injection risk).
    urllib을 직접 사용하여 파일 다운로드 (subprocess 명령 주입 위험 없음)

    Security: Uses direct Python urllib calls instead of subprocess
    to prevent command injection vulnerabilities.

    Args:
        url: URL to download from (must be hardcoded/validated)
        dest_path: Destination file path

    Returns:
        Tuple of (success, error_message)
    """
    import urllib.request
    import urllib.error

    try:
        logger.info("다운로드 중: %s", url)
        urllib.request.urlretrieve(url, dest_path)
        return True, ""
    except urllib.error.URLError as e:
        return False, f"URL 오류: {str(e)}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP 오류: {e.code} {e.reason}"
    except OSError as e:
        return False, f"파일 저장 오류: {str(e)}"
    except Exception as e:
        return False, f"다운로드 오류: {str(e)}"



def _verify_sha256(file_path: str, expected_sha256: str) -> bool:
    """Verify SHA256 hash for downloaded artifact."""
    try:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        actual = sha256.hexdigest().lower()
        return actual == expected_sha256.lower()
    except Exception:
        return False

def ensure_tesseract_lang_data() -> None:
    """
    Ensure Tesseract language data is installed.
    Security: Uses hardcoded URL and direct Python download (no command injection).
    """
    cmd = find_tesseract_cmd()
    if not cmd:
        return

    tessdata_dir = os.path.join(os.path.dirname(cmd), "tessdata")
    os.makedirs(tessdata_dir, exist_ok=True)

    lang_file = os.path.join(tessdata_dir, "chi_sim.traineddata")
    if os.path.exists(lang_file) and _verify_sha256(lang_file, _CHI_SIM_SHA256):
        logger.info("[Tesseract] chi_sim language data already installed")
        return
    if os.path.exists(lang_file):
        try:
            os.remove(lang_file)
        except Exception:
            pass

    # Hardcoded URL for security - do not accept user input
    # 보안을 위해 하드코딩된 URL - 사용자 입력을 받지 않음
    url = "https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata"
    logger.info("[Tesseract] chi_sim 언어팩 다운로드 중...")

    # Use direct Python download instead of subprocess (prevents command injection)
    # subprocess 대신 직접 Python 다운로드 사용 (명령 주입 방지)
    ok, out = _download_file_safe(url, lang_file)

    if os.path.exists(lang_file) and _verify_sha256(lang_file, _CHI_SIM_SHA256):
        logger.info("[Tesseract] chi_sim language data installed (sha256 verified)")
        return
    if os.path.exists(lang_file):
        logger.error("[Tesseract] chi_sim SHA256 mismatch. Removing unsafe file.")
        try:
            os.remove(lang_file)
        except Exception:
            pass

    if not ok:
        logger.error("[Tesseract] 언어팩 다운로드 실패: %s", out[:200])

    # Try user directory as fallback
    user_tessdata = os.path.join(os.path.expanduser("~"), ".tesseract", "tessdata")
    os.makedirs(user_tessdata, exist_ok=True)
    user_lang_file = os.path.join(user_tessdata, "chi_sim.traineddata")

    ok, out = _download_file_safe(url, user_lang_file)

    if os.path.exists(user_lang_file) and _verify_sha256(user_lang_file, _CHI_SIM_SHA256):
        # Set environment variable for current process only (security best practice)
        # 현재 프로세스에만 환경 변수 설정 (보안 모범 사례)
        os.environ["TESSDATA_PREFIX"] = user_tessdata
        logger.info("[Tesseract] chi_sim 언어팩 설치 완료 (사용자 경로: %s)", user_tessdata)
        logger.info("[안내] TESSDATA_PREFIX를 영구적으로 설정하려면 환경 변수를 수동으로 설정하세요.")
        return


    if os.path.exists(user_lang_file):
        logger.error("[Tesseract] chi_sim SHA256 mismatch in user path. Removing unsafe file.")
        try:
            os.remove(user_lang_file)
        except Exception:
            pass

    if not ok:
        logger.error("[Tesseract] 사용자 경로 언어팩 다운로드 실패: %s", out[:200])
    logger.warning("[Tesseract] chi_sim 언어팩 설치 실패 - 수동 설치 필요")


def install_packages(packages: List[str], upgrade: bool = False) -> bool:
    """Install packages using pip"""
    command = [sys.executable, "-m", "pip", "install"]
    
    if upgrade:
        command.append("--upgrade")
    
    command.extend(packages)
    
    success, output = run_command(command)
    
    if success:
        logger.info("패키지 설치 성공: %s", ', '.join(packages))
        return True
    else:
        logger.error("패키지 설치 실패: %s", ', '.join(packages))
        logger.error("  오류: %s", output[:200])
        return False


def main():
    """Main installation function"""
    _configure_stdio_utf8()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info("=" * 60)
    logger.info("Shopping Shorts Maker - 의존성 패키지 설치")
    logger.info("=" * 60)

    # 시스템 정보 출력
    logger.info("플랫폼: %s %s", platform.system(), platform.machine())
    logger.info("Python: %s", sys.version)
    
    python_version = sys.version_info

    # 필수 패키지 (requirements.txt와 동기화)
    base_packages = [
        # UI 및 네트워크
        "PyQt6>=6.4.0",
        "requests>=2.31.0",

        # 기본 패키지
        "psutil>=5.9.0",
        "numpy>=1.24.0",

        # OCR 및 이미지 처리
        "opencv-python>=4.8.0",
        "pytesseract>=0.3.13",
        "pydub>=0.25.1",
        "more-itertools>=9.0.0",

        # 비디오 및 이미지 처리
        "moviepy>=1.0.3",
        "pillow>=10.0.0",
        "imageio-ffmpeg>=0.4.9",

        # AI API 클라이언트
        "google-genai>=1.0.0",
        "anthropic>=0.18.0",

        # 플랫폼 호환성
        "platformdirs>=3.10.0",

        # 로깅 및 디버깅
        "colorama>=0.4.6",
    ]

    # OCR 패키지 - Python 버전에 따라 다른 패키지 사용
    if python_version >= (3, 13):
        # Python 3.13+: pytesseract만 사용 (onnxruntime 미지원)
        logger.info("[안내] Python 3.13+에서는 Tesseract OCR을 사용합니다.")
        ocr_packages = [
            "pytesseract>=0.3.10",
            "Pillow>=10.0.0",
        ]
    else:
        # Python 3.13 미만: RapidOCR + Tesseract 폴백
        ocr_packages = [
            "rapidocr-onnxruntime>=1.3.0",
            "onnxruntime>=1.15.0",
            "pytesseract>=0.3.10",
            "Pillow>=10.0.0",
        ]

    # Whisper 패키지 - Python 버전에 따라 다른 처리
    if python_version >= (3, 13):
        logger.info("[안내] Python 3.13+에서는 faster-whisper가 지원되지 않아 건너뜁니다.")
        whisper_packages = []
    else:
        whisper_packages = [
            "faster-whisper>=1.0.0",
            "ctranslate2>=4.0.0",
            "huggingface-hub>=0.20.0",
            "tokenizers>=0.15.0",
        ]

    essential_packages = base_packages + ocr_packages + whisper_packages
    
    # 플랫폼별 패키지
    platform_specific = []
    gpu_packages = []  # GPU 패키지는 별도로 관리

    if is_windows():
        logger.info("Windows 시스템 감지")
        platform_specific.extend([
            "pywin32>=305",
            "wmi>=1.5.1",
        ])

        # 초기 NVIDIA GPU 확인 (nvidia-smi 기반)
        if has_nvidia_gpu():
            logger.info("NVIDIA GPU 감지됨 (초기 확인)")
            gpu_packages.append("cupy-cuda11x>=12.0.0")
        else:
            logger.info("NVIDIA GPU 없음 - CPU 모드로 진행")
    elif is_macos():
        logger.info("macOS 시스템 감지")
        # macOS 특별 설정
        pass
    elif is_linux():
        logger.info("Linux 시스템 감지")
        # Linux 특별 설정
        pass

    # pip 업그레이드
    logger.info("1. pip 업그레이드 중...")
    install_packages(["pip", "setuptools", "wheel"], upgrade=True)

    # 필수 패키지 설치
    logger.info("2. 필수 패키지 설치 중...")
    all_packages = essential_packages + platform_specific
    
    # 패키지를 그룹으로 나누어 설치 (한번에 너무 많으면 실패할 수 있음)
    batch_size = 5
    for i in range(0, len(all_packages), batch_size):
        batch = all_packages[i:i + batch_size]
        logger.info("  배치 %d: %s", i//batch_size + 1, ', '.join(batch))
        install_packages(batch)

    # Tesseract 설치 (Windows)
    if is_windows():
        logger.info("3. Tesseract OCR 설치 확인 중...")
        if install_tesseract_windows():
            ensure_tesseract_lang_data()

    # GPU 패키지 설치 (wmi 설치 후 재확인)
    # Try CuPy installation regardless of Python version, graceful fallback if incompatible
    # Python 버전에 관계없이 CuPy 설치 시도, 호환되지 않으면 자동 폴백
    if is_windows():
        logger.info("4. GPU 가속 패키지 확인 중...")
        # wmi가 이제 설치되었으므로 GPU 재확인
        if has_nvidia_gpu():
            # Try to install CuPy, will fail gracefully if not compatible
            # CuPy 설치 시도, 호환되지 않으면 자동으로 실패 처리
            if gpu_packages:
                logger.info("NVIDIA GPU 최종 확인 완료 - GPU 가속 패키지 설치 시도")
                install_packages(gpu_packages)
            else:
                logger.info("NVIDIA GPU 새로 감지됨 - GPU 가속 패키지 설치 시도")
                install_packages(["cupy-cuda12x>=12.0.0"])
            logger.info("[안내] Python 3.14+에서 CuPy가 설치되지 않으면 NumPy CPU 모드로 자동 전환됩니다.")
        else:
            logger.info("NVIDIA GPU 없음 - GPU 가속 패키지 건너뜀")

    # 시스템 최적화 모듈 테스트
    logger.info("5. 시스템 최적화 모듈 테스트 중...")
    try:
        from utils.system_optimizer import SystemOptimizer
        optimizer = SystemOptimizer()
        optimizer.print_system_info()
        logger.info("시스템 최적화 모듈 작동 확인")
    except ImportError as e:
        logger.error("시스템 최적화 모듈 로드 실패: %s", e)
        logger.error("  utils/system_optimizer.py 파일을 확인해주세요.")

    logger.info("=" * 60)
    logger.info("설치 완료!")
    logger.info("=" * 60)
    logger.info("다음 단계:")
    logger.info("1. 프로그램을 재시작하세요.")
    logger.info("2. 시스템이 자동으로 최적화 설정을 적용합니다.")
    logger.info("3. 문제가 있으면 로그를 확인해주세요.")

    if is_windows() and not has_nvidia_gpu():
        logger.info("참고: NVIDIA GPU가 감지되지 않았습니다.")
        logger.info("      CPU 모드로 실행되며, 처리 속도가 느릴 수 있습니다.")
        logger.info("      GPU 가속을 원하시면 NVIDIA 그래픽 카드를 설치하세요.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("설치가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.exception("설치 중 오류 발생: %s", e)
        sys.exit(1)
