"""
Secure Configuration Manager

Stores sensitive runtime configuration values in an encrypted local file.
Supports loading legacy XOR format for backward compatibility.
"""

import base64
import hashlib
import json
import os
import sys
from typing import Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
    _FERNET_AVAILABLE = True
except Exception:
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]
    _FERNET_AVAILABLE = False


def _get_machine_key() -> bytes:
    """Generate a stable machine-bound key seed."""
    machine_id_parts = [
        os.name,
        sys.platform,
        os.getenv("COMPUTERNAME", "default"),
    ]
    machine_string = "-".join(machine_id_parts)
    return hashlib.sha256(machine_string.encode("utf-8")).digest()


def _legacy_xor_cipher(data: bytes, key: bytes) -> bytes:
    """Legacy XOR cipher kept only to read old config files."""
    key_len = len(key)
    return bytes(d ^ key[i % key_len] for i, d in enumerate(data))


def _get_runtime_base() -> str:
    """Return runtime base path for dev/frozen environments."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _get_fernet() -> Optional["Fernet"]:
    """Build a Fernet instance from machine-bound key material."""
    if not _FERNET_AVAILABLE:
        return None

    key_material = hashlib.sha256(_get_machine_key() + b"SSMKR_SECURE_CONFIG_V2").digest()
    fernet_key = base64.urlsafe_b64encode(key_material)
    return Fernet(fernet_key)


def _load_encrypted_config() -> Optional[dict]:
    """Load encrypted config from known runtime paths."""
    config_filename = ".secure_config.enc"

    possible_paths = [
        os.path.join(_get_runtime_base(), config_filename),
        os.path.join(_get_runtime_base(), "_internal", config_filename),
        os.path.join(os.path.dirname(_get_runtime_base()), config_filename),
    ]

    config_path = next((p for p in possible_paths if os.path.exists(p)), None)
    if not config_path:
        return None

    try:
        with open(config_path, "rb") as f:
            payload = f.read()

        if payload.startswith(b"v2:"):
            fernet = _get_fernet()
            if not fernet:
                logger.warning("[SecureConfig] cryptography is unavailable; cannot read v2 config")
                return None
            decrypted = fernet.decrypt(payload[3:])
        else:
            # Legacy format: base64(XOR(json, machine_key))
            key = _get_machine_key()
            decrypted = _legacy_xor_cipher(base64.b64decode(payload), key)

        config = json.loads(decrypted.decode("utf-8"))
        logger.debug("[SecureConfig] Encrypted config loaded successfully")
        return config

    except InvalidToken:
        logger.warning("[SecureConfig] Invalid encrypted config token")
        return None
    except Exception as e:
        logger.warning(f"[SecureConfig] Failed to load encrypted config: {e}")
        return None


def init_secure_environment():
    """Initialize environment variables from encrypted config file."""
    if os.getenv("GLM_OCR_API_KEY"):
        logger.debug("[SecureConfig] API key already configured via environment")
        return

    config = _load_encrypted_config()
    if not config:
        logger.debug("[SecureConfig] No encrypted config found, using environment variables")
        return

    if "GLM_OCR_API_KEY" in config:
        os.environ["GLM_OCR_API_KEY"] = str(config["GLM_OCR_API_KEY"])
        logger.info("[SecureConfig] API key loaded from secure config")

    for key, value in config.items():
        if key not in os.environ:
            os.environ[key] = str(value)


def create_encrypted_config(config: dict, output_path: str = None):
    """Create encrypted config file for distribution/build usage."""
    if not _FERNET_AVAILABLE:
        raise RuntimeError("cryptography package is required to create secure config")

    output_path = output_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".secure_config.enc",
    )

    fernet = _get_fernet()
    if not fernet:
        raise RuntimeError("Failed to initialize secure encryption backend")

    config_json = json.dumps(config, ensure_ascii=False).encode("utf-8")
    encrypted = b"v2:" + fernet.encrypt(config_json)

    with open(output_path, "wb") as f:
        f.write(encrypted)

    print(f"[SecureConfig] Encrypted config saved to: {output_path}")
    print("[SecureConfig] Add this file to PyInstaller with --add-data")
    return output_path


def get_api_key_status() -> dict:
    """Return whether API key is configured, without exposing secret values."""
    api_key = os.getenv("GLM_OCR_API_KEY", "")
    return {
        "configured": bool(api_key),
        "source": "environment" if api_key else "none",
    }
