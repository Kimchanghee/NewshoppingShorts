"""
Secure Configuration Manager

exe 빌드 시 암호화된 설정을 포함하고, 런타임에 복호화하여 사용
API 키가 GUI나 로그에 절대 노출되지 않도록 보호

Usage:
    from utils.secure_config import init_secure_environment
    init_secure_environment()  # 앱 시작 시 1회 호출
"""

import base64
import hashlib
import os
import sys
from typing import Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)


def _get_machine_key() -> bytes:
    """
    머신 고유 키 생성 (복호화에 사용)

    실행 환경에 따라 일관된 키를 생성하여
    다른 머신에서는 복호화가 불가능하도록 함
    """
    # 머신 식별자 조합 (환경에 따라 일관됨)
    machine_id_parts = [
        os.name,  # 'nt' for Windows
        sys.platform,  # 'win32'
        os.getenv("COMPUTERNAME", "default"),  # 컴퓨터 이름
    ]
    machine_string = "-".join(machine_id_parts)

    # SHA256으로 32바이트 키 생성
    return hashlib.sha256(machine_string.encode()).digest()


def _simple_xor_cipher(data: bytes, key: bytes) -> bytes:
    """간단한 XOR 암호화/복호화 (대칭)"""
    key_len = len(key)
    return bytes(d ^ key[i % key_len] for i, d in enumerate(data))


def _get_runtime_base() -> str:
    """PyInstaller 번들 또는 개발 환경의 베이스 경로"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 번들
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _load_encrypted_config() -> Optional[dict]:
    """
    암호화된 설정 파일 로드 및 복호화

    설정 파일 위치:
    - 개발: utils/.secure_config.enc
    - 빌드: _internal/.secure_config.enc
    """
    config_filename = ".secure_config.enc"

    # 가능한 경로들
    possible_paths = [
        os.path.join(_get_runtime_base(), config_filename),
        os.path.join(_get_runtime_base(), "_internal", config_filename),
        os.path.join(os.path.dirname(_get_runtime_base()), config_filename),
    ]

    config_path = None
    for path in possible_paths:
        if os.path.exists(path):
            config_path = path
            break

    if not config_path:
        # 설정 파일 없음 - 정상 (환경변수 사용)
        return None

    try:
        with open(config_path, "rb") as f:
            encrypted_data = f.read()

        # 복호화
        key = _get_machine_key()
        decrypted = _simple_xor_cipher(base64.b64decode(encrypted_data), key)

        # JSON 파싱
        import json
        config = json.loads(decrypted.decode("utf-8"))

        logger.debug("[SecureConfig] Encrypted config loaded successfully")
        return config

    except Exception as e:
        logger.warning(f"[SecureConfig] Failed to load encrypted config: {e}")
        return None


def init_secure_environment():
    """
    보안 환경 초기화 - 앱 시작 시 1회 호출

    암호화된 설정을 로드하여 환경변수로 설정
    GUI나 로그에 절대 노출되지 않음
    """
    # 이미 환경변수가 설정되어 있으면 스킵
    if os.getenv("GLM_OCR_API_KEY"):
        logger.debug("[SecureConfig] API key already configured via environment")
        return

    # 암호화된 설정 로드
    config = _load_encrypted_config()
    if not config:
        logger.debug("[SecureConfig] No encrypted config found, using environment variables")
        return

    # 환경변수로 설정 (메모리에만 존재)
    if "GLM_OCR_API_KEY" in config:
        os.environ["GLM_OCR_API_KEY"] = config["GLM_OCR_API_KEY"]
        logger.info("[SecureConfig] API key loaded from secure config")

    # 기타 설정들도 동일하게 처리 가능
    for key, value in config.items():
        if key not in os.environ:
            os.environ[key] = str(value)


def create_encrypted_config(config: dict, output_path: str = None):
    """
    설정을 암호화하여 파일로 저장 (빌드 시 사용)

    Args:
        config: 암호화할 설정 딕셔너리
        output_path: 출력 파일 경로 (기본: .secure_config.enc)

    Usage (빌드 전에 실행):
        from utils.secure_config import create_encrypted_config
        create_encrypted_config({
            "GLM_OCR_API_KEY": "your-api-key-here"
        })
    """
    import json

    output_path = output_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".secure_config.enc"
    )

    # JSON으로 직렬화
    config_json = json.dumps(config, ensure_ascii=False)

    # 암호화
    key = _get_machine_key()
    encrypted = base64.b64encode(
        _simple_xor_cipher(config_json.encode("utf-8"), key)
    )

    # 파일 저장
    with open(output_path, "wb") as f:
        f.write(encrypted)

    print(f"[SecureConfig] Encrypted config saved to: {output_path}")
    print(f"[SecureConfig] Add this file to PyInstaller with --add-data")

    return output_path


def get_api_key_status() -> dict:
    """
    API 키 상태 확인 (키 자체는 절대 노출하지 않음)

    Returns:
        상태 정보 (키 존재 여부만 표시)
    """
    api_key = os.getenv("GLM_OCR_API_KEY", "")

    return {
        "configured": bool(api_key),
        "source": "environment" if api_key else "none",
        # 키 값은 절대 반환하지 않음
    }
