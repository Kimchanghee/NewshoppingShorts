# -*- coding: utf-8 -*-
"""
Startup constants and configuration values.
"""

from typing import Dict, List, Tuple, Any

# =============================================================================
# System Requirements Constants
# =============================================================================

MIN_RAM_GB: int = 4
RECOMMENDED_RAM_GB: int = 8
MIN_DISK_GB: int = 2
RECOMMENDED_DISK_GB: int = 5

# =============================================================================
# Network Configuration
# =============================================================================

DEFAULT_PROCESS_PORT: int = 20022

# DNS endpoints for connectivity check (with fallbacks)
CONNECTIVITY_ENDPOINTS: List[Tuple[str, int, str]] = [
    ("8.8.8.8", 53, "Google DNS"),
    ("1.1.1.1", 53, "Cloudflare DNS"),
    ("208.67.222.222", 53, "OpenDNS"),
]

# =============================================================================
# Required Packages
# =============================================================================

# Format: (import_name, pip_name, optional)
# optional=True means the program can run without it
REQUIRED_PACKAGES: List[Tuple[str, str, bool]] = [
    # UI and networking
    ("PyQt6", "PyQt6", False),
    ("requests", "requests", False),
    # Basic packages
    ("psutil", "psutil", False),
    # OCR and image processing
    ("cv2", "opencv-python", False),
    ("rapidocr_onnxruntime", "rapidocr-onnxruntime", True),
    ("pytesseract", "pytesseract", False),
    ("numpy", "numpy", False),
    # Faster-Whisper speech recognition
    ("faster_whisper", "faster-whisper", True),
    ("ctranslate2", "ctranslate2", True),
    ("onnxruntime", "onnxruntime", True),
    # Video and image processing
    ("moviepy", "moviepy", False),
    ("PIL", "pillow", False),
    ("pydub", "pydub", False),
    ("imageio_ffmpeg", "imageio-ffmpeg", False),
    # AI API clients
    ("google.genai", "google-genai", False),
    ("anthropic", "anthropic", False),
    # Logging
    ("colorama", "colorama", False),
]

# =============================================================================
# Initialization Check Items
# =============================================================================

CHECK_ITEM_IMPACTS: Dict[str, Dict[str, Any]] = {
    "system": {
        "name": "시스템 환경",
        "critical": True,
        "impact": "프로그램 실행이 불안정하거나 느릴 수 있습니다.",
        "solution": "메모리 8GB 이상, 저장 공간 5GB 이상 확보를 권장합니다.",
    },
    "fonts": {
        "name": "자막 폰트",
        "critical": False,
        "impact": "자막 폰트가 기본 폰트로 대체되어 디자인이 다를 수 있습니다.",
        "solution": "fonts 폴더에 필요한 폰트 파일을 추가해주세요.",
    },
    "ffmpeg": {
        "name": "영상 인코더",
        "critical": True,
        "impact": "영상 생성 기능을 사용할 수 없습니다.",
        "solution": "프로그램을 재설치하거나 고객센터에 문의해주세요.",
    },
    "internet": {
        "name": "인터넷 연결",
        "critical": True,
        "impact": "번역, 음성, AI 분석 기능을 사용할 수 없습니다.",
        "solution": "인터넷 연결을 확인해주세요.",
    },
    "modules": {
        "name": "프로그램 구성요소",
        "critical": True,
        "impact": "일부 기능이 작동하지 않을 수 있습니다.",
        "solution": "프로그램을 재설치해주세요.",
    },
    "ocr": {
        "name": "자막 인식 엔진",
        "critical": False,
        "impact": "중국어 자막 자동 인식이 불가능합니다. 수동 입력만 가능합니다.",
        "solution": "첫 실행 시 자동 다운로드됩니다. 인터넷 연결을 확인해주세요.",
    },
    "tts_dir": {
        "name": "음성 저장 폴더",
        "critical": False,
        "impact": "음성 파일 저장에 문제가 있을 수 있습니다.",
        "solution": "프로그램 폴더에 쓰기 권한이 있는지 확인해주세요.",
    },
    "api": {
        "name": "서비스 연결",
        "critical": False,
        "impact": "일부 서비스 연결에 문제가 있습니다.",
        "solution": "인터넷 연결 후 다시 시도해주세요.",
    },
}

# =============================================================================
# Required Fonts
# =============================================================================

REQUIRED_FONTS: List[str] = [
    "Pretendard-ExtraBold.ttf",  # pretendard
    "GmarketSansTTFBold.ttf",  # gmarket
    "Paperlogy-9Black.ttf",  # paperlogy
    "NanumSquareEB.ttf",  # nanumsquare
    "Cafe24Ssurround.ttf",  # cafe24
    "SpoqaHanSansNeo-Bold.ttf",  # spoqa
    "IBMPlexSansKR-Bold.ttf",  # ibm_plex
]

# =============================================================================
# Optional Fonts (다운로드 소스가 불안정하여 선택사항으로 분류)
# =============================================================================

OPTIONAL_FONTS: List[str] = [
    "SeoulHangangB.ttf",  # seoul_hangang - 서울시 공식 사이트에서 다운로드
    "UnPeople.ttf",  # unpeople - un-fonts 패키지에서 다운로드
    "KoPubBatangBold.ttf",  # kopub - 한국출판인회의 사이트에서 다운로드
]
