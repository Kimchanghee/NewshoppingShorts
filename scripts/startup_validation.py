"""
Startup Validation Script

Pre-flight system checks before running the application.
Validates dependencies, OCR engines, GPU, FFmpeg, and API keys.

Usage:
    python scripts/startup_validation.py
"""

import sys
import os
import shutil
from pathlib import Path
from typing import List, Tuple, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from colorama import Fore, Style, init as colorama_init
    COLORAMA_AVAILABLE = True
    colorama_init(autoreset=True)
except ImportError:
    COLORAMA_AVAILABLE = False
    class Fore:
        GREEN = RED = YELLOW = CYAN = ''
    class Style:
        BRIGHT = RESET_ALL = ''


class StartupValidator:
    """
    System startup validator.

    Checks all prerequisites before running the application.
    """

    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = 0

    def validate_all(self) -> Tuple[bool, List[str]]:
        """
        Run all validation checks.

        Returns:
            (success, error_messages)
        """
        print("\n" + "=" * 60)
        print("NewshoppingShortsMaker - Startup Validation")
        print("시스템 사전 검사")
        print("=" * 60 + "\n")

        errors = []

        # Run checks
        checks = [
            ("Python Version", self._check_python_version),
            ("Required Packages", self._check_required_packages),
            ("OCR Engine", self._check_ocr),
            ("GPU Availability", self._check_gpu),
            ("FFmpeg", self._check_ffmpeg),
            ("File Permissions", self._check_permissions),
        ]

        for name, check_func in checks:
            try:
                success, message = check_func()
                if success:
                    self._print_success(f"{name}: {message}")
                    self.checks_passed += 1
                else:
                    self._print_error(f"{name}: {message}")
                    errors.append(f"{name}: {message}")
                    self.checks_failed += 1
            except Exception as e:
                self._print_error(f"{name}: Unexpected error - {e}")
                errors.append(f"{name}: {e}")
                self.checks_failed += 1

        # Print summary
        print("\n" + "=" * 60)
        print(f"Summary: {self.checks_passed} passed, {self.checks_failed} failed, {self.warnings} warnings")
        print("=" * 60)

        if self.checks_failed > 0:
            print("\n" + Fore.RED + "⚠ Some checks failed. Please fix the issues above.")
            print("일부 검사가 실패했습니다. 위의 문제를 해결해주세요.")
            return False, errors
        else:
            print("\n" + Fore.GREEN + "✓ All checks passed! Ready to run.")
            print("모든 검사 통과! 실행 준비 완료.")
            return True, []

    def _check_python_version(self) -> Tuple[bool, str]:
        """Check Python version"""
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"

        if version.major == 3 and version.minor >= 12:
            return True, f"Python {version_str} ✓"
        else:
            return False, f"Python {version_str} (require 3.12+)"

    def _check_required_packages(self) -> Tuple[bool, str]:
        """Check required Python packages"""
        required = [
            "PyQt6",
            "requests",
            "opencv-python",
            "numpy",
            "moviepy",
            "psutil",
        ]

        missing = []
        for package in required:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing.append(package)

        if missing:
            return False, f"Missing packages: {', '.join(missing)}"
        else:
            return True, f"{len(required)} packages installed"

    def _check_ocr(self) -> Tuple[bool, str]:
        """Check OCR engine availability"""
        try:
            # Try importing OCR backend
            from utils.ocr_backend import check_ocr_availability

            info = check_ocr_availability()

            if info.get("tesseract_available"):
                return True, f"Tesseract OCR available at {info.get('tesseract_path')}"
            elif info.get("rapidocr_available"):
                return True, "RapidOCR available"
            else:
                return False, "No OCR engine found (install Tesseract)"

        except Exception as e:
            return False, f"OCR check failed: {e}"

    def _check_gpu(self) -> Tuple[bool, str]:
        """Check GPU availability"""
        try:
            import cupy as cp
            device_count = cp.cuda.runtime.getDeviceCount()
            if device_count > 0:
                return True, f"{device_count} CUDA device(s) available"
            else:
                self.warnings += 1
                self._print_warning("GPU: No CUDA devices (CPU mode)")
                return True, "No GPU (CPU mode)"
        except ImportError:
            self.warnings += 1
            self._print_warning("GPU: CuPy not installed (CPU mode)")
            return True, "CuPy not installed (CPU mode)"
        except Exception as e:
            self.warnings += 1
            self._print_warning(f"GPU: {e} (CPU mode)")
            return True, "GPU unavailable (CPU mode)"

    def _check_ffmpeg(self) -> Tuple[bool, str]:
        """Check FFmpeg installation"""
        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")

        if ffmpeg_path and ffprobe_path:
            return True, f"FFmpeg available at {ffmpeg_path}"
        elif ffmpeg_path:
            self.warnings += 1
            self._print_warning("FFmpeg: ffprobe not found")
            return True, "FFmpeg found, ffprobe missing"
        else:
            return False, "FFmpeg not found (required for video processing)"

    def _check_permissions(self) -> Tuple[bool, str]:
        """Check file system permissions"""
        # Check write permission in current directory
        test_file = Path(".startup_validation_test")
        try:
            test_file.write_text("test")
            test_file.unlink()
            return True, "Write permissions OK"
        except Exception as e:
            return False, f"Cannot write to current directory: {e}"

    def _print_success(self, message: str):
        """Print success message"""
        print(Fore.GREEN + "  ✓ " + Style.RESET_ALL + message)

    def _print_error(self, message: str):
        """Print error message"""
        print(Fore.RED + "  ✗ " + Style.RESET_ALL + message)

    def _print_warning(self, message: str):
        """Print warning message"""
        print(Fore.YELLOW + "  ⚠ " + Style.RESET_ALL + message)


def main():
    """Run startup validation"""
    validator = StartupValidator()
    success, errors = validator.validate_all()

    if not success:
        print("\n" + Fore.CYAN + "Installation help:")
        print("  pip install -r requirements.txt")
        print("  python install_dependencies.py")
        print("\nFor Tesseract OCR:")
        if sys.platform == "win32":
            print("  winget install UB-Mannheim.TesseractOCR")
        elif sys.platform == "darwin":
            print("  brew install tesseract tesseract-lang")
        else:
            print("  sudo apt install tesseract-ocr tesseract-ocr-kor")

        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
