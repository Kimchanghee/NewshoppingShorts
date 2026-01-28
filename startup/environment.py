# -*- coding: utf-8 -*-
"""
Environment setup for DPI, ffmpeg, and onnxruntime.
"""
import sys
import os
import ctypes
import warnings
from typing import List, Set, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)


def setup_dpi_awareness() -> None:
    """
    Configure Windows DPI scaling.
    - PROCESS_PER_MONITOR_DPI_AWARE (2): Each monitor's DPI is recognized
    - Works together with Qt's AA_EnableHighDpiScaling
    """
    if sys.platform != 'win32':
        return

    try:
        # Windows 8.1+: SetProcessDpiAwareness
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except AttributeError:
        # Windows 7 and below: legacy API
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception as e:
            logger.debug("Legacy DPI setup failed (non-critical): %s", e)
    except Exception as e:
        logger.debug("DPI setup failed (non-critical): %s", e)


def setup_ffmpeg_path() -> None:
    """
    Set ffmpeg path before pydub is imported.
    Suppresses 'Couldn't find ffmpeg' warning.
    """
    warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_exe and os.path.exists(ffmpeg_exe):
            os.environ["PATH"] = (
                os.path.dirname(ffmpeg_exe) + os.pathsep + os.environ.get("PATH", "")
            )
    except Exception as e:
        logger.debug("ffmpeg path setup failed (non-critical): %s", e)


def get_runtime_base() -> str:
    """
    Get the runtime base directory.
    Returns _MEIPASS for frozen builds, script directory otherwise.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def setup_onnxruntime_environment() -> None:
    """
    Configure onnxruntime environment at program startup.
    - Adds _internal/onnxruntime to PATH
    - Adds Windows DLL search paths
    """
    try:
        base = get_runtime_base()

        # exe directory (important for onedir builds)
        exe_dir = (
            os.path.dirname(sys.executable)
            if getattr(sys, "frozen", False)
            else base
        )

        # Expected _internal structure
        internal_root = os.path.join(base, "_internal")
        ort_dir = os.path.join(internal_root, "onnxruntime")
        ort_capi = os.path.join(ort_dir, "capi")

        paths: List[str] = [exe_dir, base, internal_root, ort_dir, ort_capi]

        # Add actual onnxruntime installation/bundle path
        try:
            import importlib.util
            spec = importlib.util.find_spec("onnxruntime")
            if spec and spec.origin:
                mod_dir = os.path.dirname(spec.origin)
                capi_dir = os.path.join(mod_dir, "capi")
                paths.extend([mod_dir, capi_dir])
        except Exception as e:
            logger.debug("onnxruntime spec lookup failed (non-critical): %s", e)

        # Deduplicate paths while preserving order (O(n) with Set)
        seen: Set[str] = set()
        uniq: List[str] = []
        for p in paths:
            if p and os.path.isdir(p) and p not in seen:
                seen.add(p)
                uniq.append(p)

        if not uniq:
            return

        # Update PATH environment variable
        cur = os.environ.get("PATH", "")
        for p in reversed(uniq):
            if p not in cur:
                cur = p + os.pathsep + cur
        os.environ["PATH"] = cur

        # Add DLL directories on Windows
        if sys.platform == "win32":
            add_dll = getattr(os, "add_dll_directory", None)
            if add_dll:
                for p in uniq:
                    try:
                        add_dll(p)
                    except Exception as e:
                        logger.debug("add_dll_directory failed for %s: %s", p, e)

    except Exception as e:
        logger.debug("onnxruntime environment setup failed (non-critical): %s", e)


def load_onnxruntime() -> bool:
    """
    Attempt to load onnxruntime.
    Python 3.13+ does not support onnxruntime.

    Returns:
        True if onnxruntime loaded successfully, False otherwise
    """
    if sys.version_info >= (3, 13):
        logger.debug("Python 3.13+ detected, onnxruntime not supported")
        return False

    setup_onnxruntime_environment()

    try:
        import onnxruntime  # noqa: F401
        logger.debug("onnxruntime loaded successfully")
        return True
    except Exception as e:
        logger.debug("onnxruntime load failed (fallback to Tesseract): %s", e)
        return False
