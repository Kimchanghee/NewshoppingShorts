# -*- coding: utf-8 -*-
"""
TTS (Text-to-Speech) configuration and path utilities.
"""
import os
import sys
from typing import Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)


def get_safe_tts_base_dir() -> str:
    """
    Get a safe base directory for TTS output.
    Falls back to user home directory if write permission is not available.

    Returns:
        str: TTS output base directory path
    """
    # Determine base path based on frozen status
    if getattr(sys, "frozen", False):
        # PyInstaller packaged
        base_path = os.path.dirname(sys.executable)
    else:
        # Normal Python script
        base_path = os.path.dirname(os.path.abspath(__file__))
        # Go up one level from utils/ to project root
        base_path = os.path.dirname(base_path)

    base_tts_dir = os.path.join(base_path, "tts_output")

    # Test write permission
    try:
        os.makedirs(base_tts_dir, exist_ok=True)
        test_file = os.path.join(base_tts_dir, ".write_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
    except (PermissionError, OSError):
        # Fall back to user home directory
        user_dir = os.path.expanduser("~")
        base_tts_dir = os.path.join(user_dir, "shoppingShortsMaker", "tts_output")
        logger.info("[TTS] 기본 경로 쓰기 불가, 대체 경로 사용: %s", base_tts_dir)

    return base_tts_dir
