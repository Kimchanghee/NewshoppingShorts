# -*- coding: utf-8 -*-
"""
Package installation and stdio initialization.
This module must be imported first before any other modules.
"""
import subprocess
import sys
import io
import importlib.util
from io import TextIOBase
from typing import List, Tuple

from .constants import REQUIRED_PACKAGES


class _NullWriter(TextIOBase):
    """Null writer for suppressing output in noconsole mode."""

    def write(self, s: str) -> int:
        return len(s)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def ensure_stdio() -> None:
    """
    Ensure stdout/stderr are properly configured.
    Handles PyInstaller --noconsole mode and Windows encoding issues.
    """
    # 1) Fill None stdout/stderr with dummy writer (PyInstaller --noconsole)
    if sys.stdout is None:
        sys.stdout = _NullWriter()
    if sys.stderr is None:
        sys.stderr = _NullWriter()

    # 2) Fix Windows encoding issues
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            elif hasattr(sys.stdout, "buffer"):
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer, encoding="utf-8", errors="replace"
                )
        except Exception:
            pass  # Non-critical, silently ignore

        try:
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            elif hasattr(sys.stderr, "buffer"):
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer, encoding="utf-8", errors="replace"
                )
        except Exception:
            pass  # Non-critical, silently ignore

    # 3) Protect against libraries that directly reference sys.__stderr__
    if getattr(sys, "__stderr__", None) is None:
        sys.__stderr__ = sys.stderr
    if getattr(sys, "__stdout__", None) is None:
        sys.__stdout__ = sys.stdout


def has_module(mod_name: str) -> bool:
    """
    Check if a module exists without importing it.

    Args:
        mod_name: The module name to check

    Returns:
        True if the module exists, False otherwise
    """
    try:
        spec = importlib.util.find_spec(mod_name)
        return spec is not None
    except (ModuleNotFoundError, ImportError, ValueError):
        return False


def check_and_install_packages() -> None:
    """
    Check and install required packages.
    In development: attempts auto-installation.
    In frozen builds: validates packages are present.
    """
    is_frozen = getattr(sys, 'frozen', False)

    missing_packages: List[Tuple[str, str]] = []

    for import_name, pip_name, optional in REQUIRED_PACKAGES:
        if not has_module(import_name):
            if not optional:
                missing_packages.append((import_name, pip_name))

    if not missing_packages:
        return

    pkg_names = [pip_name for _, pip_name in missing_packages]

    if is_frozen:
        # Frozen build: missing required packages is a fatal error
        sys.stderr.write("\n" + "=" * 70 + "\n")
        sys.stderr.write("ERROR: 필수 패키지 누락 (빌드 오류)\n")
        sys.stderr.write("=" * 70 + "\n")
        sys.stderr.write(f"다음 패키지가 빌드에 포함되지 않았습니다: {', '.join(pkg_names)}\n")
        sys.stderr.write("개발자에게 문의하거나 재빌드가 필요합니다.\n")
        sys.stderr.write("=" * 70 + "\n\n")
        sys.exit(1)

    # Development environment: attempt auto-installation
    failed_packages: List[str] = []

    for import_name, pip_name in missing_packages:
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', pip_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError:
            failed_packages.append(pip_name)
        except (FileNotFoundError, OSError):
            failed_packages.append(pip_name)

    if failed_packages:
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


# Initialize stdio immediately when module is imported
ensure_stdio()
