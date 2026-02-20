"""
Secure API Key Storage using System Keyring

This module provides encrypted storage for sensitive credentials like API keys.
Uses the system's native keyring (Windows Credential Manager, macOS Keychain, etc.)

Security: Added thread safety to prevent race conditions in multi-threaded apps.
보안: 멀티스레드 앱에서 경쟁 조건을 방지하기 위한 스레드 안전성 추가.

Usage:
    from utils.secrets_manager import SecretsManager

    # Store API key securely
    SecretsManager.store_api_key("gemini", "your-api-key-here")

    # Retrieve API key
    key = SecretsManager.get_api_key("gemini")
"""

import os
import re
import sys
import shutil
import base64
import hashlib
import threading
from typing import Optional, Dict
from pathlib import Path

# Fernet encryption support (AES-128-CBC with HMAC)
try:
    from cryptography.fernet import Fernet
    FERNET_AVAILABLE = True
except ImportError:
    FERNET_AVAILABLE = False


class SecretsManager:
    """
    Manages secure storage of API keys and sensitive credentials.

    Uses system keyring when available, falls back to encrypted file storage
    for compatibility across different environments.

    Security: Thread-safe operations using lock.
    보안: 잠금을 사용한 스레드 안전 작업.
    """

    SERVICE_NAME = "NewshoppingShortsMaker"

    # Thread lock for thread-safe operations
    # 스레드 안전 작업을 위한 스레드 잠금
    _lock = threading.Lock()

    # Fallback to file-based storage if keyring unavailable
    _use_keyring = True
    _fallback_file = None

    # Regex pattern for validating key names (security: prevent injection)
    # 키 이름 검증용 정규식 패턴 (보안: 주입 방지)
    _KEY_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')

    @classmethod
    def _init_keyring(cls) -> bool:
        """
        Initialize keyring backend.

        Returns:
            True if keyring available, False otherwise
        """
        try:
            import keyring
            # Test keyring functionality
            keyring.get_password(cls.SERVICE_NAME, "test")
            return True
        except Exception:
            return False

    @classmethod
    def _get_fallback_file(cls) -> Path:
        """
        Get path to fallback encrypted storage file.

        Returns:
            Path to .secrets file in user's home directory
        """
        if cls._fallback_file is not None:
            return cls._fallback_file

        candidates = cls._candidate_secret_files()

        # Prefer the primary app data path (~/.ssmaker) when writable.
        if candidates:
            preferred = candidates[0]
            if cls._ensure_dir(preferred.parent):
                if not preferred.exists():
                    # Best-effort migration from existing legacy file.
                    for legacy in candidates[1:]:
                        if legacy.exists():
                            try:
                                shutil.copy2(legacy, preferred)
                            except Exception:
                                pass
                            break
                cls._fallback_file = preferred
                return cls._fallback_file

        for candidate in candidates:
            if candidate.exists():
                cls._fallback_file = candidate
                return cls._fallback_file

        for candidate in candidates:
            if cls._ensure_dir(candidate.parent):
                cls._fallback_file = candidate
                return cls._fallback_file

        # Last-resort fallback (best effort)
        home = Path.home()
        cls._fallback_file = home / ".ssmaker" / ".secrets"
        cls._ensure_dir(cls._fallback_file.parent)
        return cls._fallback_file

    @classmethod
    def _candidate_base_dirs(cls) -> list[Path]:
        """
        Return preferred storage base directories in priority order.
        """
        candidates: list[Path] = []
        home = Path.home()

        # Primary location aligned with app-wide user data dir.
        candidates.append(home / ".ssmaker")

        if sys.platform == "win32":
            appdata = os.getenv("APPDATA", "").strip()
            localappdata = os.getenv("LOCALAPPDATA", "").strip()
            if appdata:
                candidates.append(Path(appdata) / "SSMaker")
            if localappdata:
                candidates.append(Path(localappdata) / "SSMaker")

        # Legacy path for backward compatibility.
        candidates.append(home / ".newshopping")

        unique: list[Path] = []
        seen = set()
        for p in candidates:
            key = str(p).lower()
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

    @classmethod
    def _candidate_secret_files(cls) -> list[Path]:
        return [base / ".secrets" for base in cls._candidate_base_dirs()]

    @classmethod
    def _candidate_key_files(cls) -> list[Path]:
        return [base / ".encryption_key" for base in cls._candidate_base_dirs()]

    @classmethod
    def _ensure_dir(cls, path: Path) -> bool:
        """
        Ensure directory exists and is writable.
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".perm_test"
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    @classmethod
    def _validate_key_name(cls, key_name: str) -> bool:
        """
        Validate key name format (security: prevent injection attacks).
        키 이름 형식 검증 (보안: 주입 공격 방지).

        Args:
            key_name: Key name to validate

        Returns:
            True if valid, False otherwise
        """
        if not key_name or not isinstance(key_name, str):
            return False
        return bool(cls._KEY_NAME_PATTERN.match(key_name))

    @classmethod
    def store_api_key(cls, key_name: str, key_value: str) -> bool:
        """
        Store API key securely (thread-safe).
        API 키를 안전하게 저장 (스레드 안전).

        Args:
            key_name: Name/identifier for the key (e.g., "gemini", "anthropic")
            key_value: The actual API key to store

        Returns:
            True if stored successfully, False otherwise

        Example:
            >>> SecretsManager.store_api_key("gemini", "AIza...")
            True
        """
        import logging
        logger = logging.getLogger(__name__)

        # Validate key name (security)
        if not cls._validate_key_name(key_name):
            logger.warning("Invalid key name format: rejected")
            return False

        if not key_value or not key_value.strip():
            return False

        # Thread-safe operation
        with cls._lock:
            # Try keyring first
            if cls._use_keyring and cls._init_keyring():
                try:
                    import keyring
                    keyring.set_password(cls.SERVICE_NAME, key_name, key_value)
                    # Some environments report success but fail to persist.
                    verify_value = keyring.get_password(cls.SERVICE_NAME, key_name)
                    if verify_value == key_value:
                        return True
                    logger.warning("Keyring write verification failed; falling back to file storage")
                    cls._use_keyring = False
                except Exception as e:
                    logger.debug("Keyring storage failed: %s", type(e).__name__)
                    cls._use_keyring = False

            # Fallback to file-based storage
            return cls._store_to_file(key_name, key_value)

    @classmethod
    def get_api_key(cls, key_name: str) -> Optional[str]:
        """
        Retrieve API key (thread-safe).
        API 키 검색 (스레드 안전).

        Args:
            key_name: Name/identifier for the key

        Returns:
            The API key if found, None otherwise

        Example:
            >>> key = SecretsManager.get_api_key("gemini")
            >>> if key:
            ...     print("Key found")
        """
        import logging
        logger = logging.getLogger(__name__)

        # Validate key name (security)
        if not cls._validate_key_name(key_name):
            logger.warning("Invalid key name format: rejected")
            return None

        # Thread-safe operation
        with cls._lock:
            # Try keyring first
            if cls._use_keyring and cls._init_keyring():
                try:
                    import keyring
                    value = keyring.get_password(cls.SERVICE_NAME, key_name)
                    if value:
                        return value
                except Exception as e:
                    logger.debug("Keyring retrieval failed: %s", type(e).__name__)
                    cls._use_keyring = False

            # Fallback to file-based storage
            return cls._read_from_file(key_name)

    @classmethod
    def delete_api_key(cls, key_name: str) -> bool:
        """
        Delete stored API key.

        Args:
            key_name: Name/identifier for the key

        Returns:
            True if deleted successfully, False otherwise
        """
        success = False
        with cls._lock:
            # Try keyring
            if cls._use_keyring and cls._init_keyring():
                try:
                    import keyring
                    keyring.delete_password(cls.SERVICE_NAME, key_name)
                    success = True
                except Exception:
                    pass

            # Also remove from file-based storage
            if cls._delete_from_file(key_name):
                success = True

        return success

    @classmethod
    def list_stored_keys(cls) -> list:
        """
        List all stored API key names (not the actual keys).

        Returns:
            List of key names
        """
        try:
            data = cls._read_secrets_file()
            return list(sorted(set(data.keys())))
        except Exception:
            return []

    @classmethod
    def _set_file_permissions(cls, file_path: Path) -> bool:
        """
        Set restrictive file permissions (owner only).

        On Windows, we skip restrictive permissions as they can cause
        access issues. The file content is encrypted with Fernet anyway.

        Args:
            file_path: Path to the file

        Returns:
            True if permissions set successfully, False otherwise
        """
        import logging

        logger = logging.getLogger(__name__)

        try:
            if sys.platform == 'win32':
                # Windows: Skip restrictive permissions to avoid access issues
                # The file content is already encrypted with Fernet (AES-128-CBC + HMAC)
                # which provides sufficient security
                logger.debug("Windows: Skipping file permissions (content is encrypted)")
                return True
            else:
                # Unix: Use chmod for owner-only read/write
                os.chmod(file_path, 0o600)
                logger.debug("Set Unix file permissions for: %s", file_path)
                return True

        except OSError as e:
            logger.warning("Failed to set file permissions: %s", e)
            return False
        except Exception:
            logger.warning("Unexpected error setting file permissions")
            return False

    @classmethod
    def _store_to_file(cls, key_name: str, key_value: str) -> bool:
        """Store key to encrypted file (fallback method)."""
        import logging
        import json
        logger = logging.getLogger(__name__)

        try:
            secrets_file = cls._get_fallback_file()
            data = cls._read_secrets_file()

            # Fernet encryption (AES-128-CBC with HMAC)
            encrypted = cls._simple_encrypt(key_value)
            data[key_name] = encrypted

            # Atomic write to reduce corruption risk on abrupt shutdown.
            tmp_file = secrets_file.with_suffix(secrets_file.suffix + ".tmp")
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            os.replace(tmp_file, secrets_file)

            # Set restrictive permissions (owner only) - works on both Windows and Unix
            cls._set_file_permissions(secrets_file)

            return True
        except RuntimeError as e:
            # RuntimeError from _simple_encrypt (cryptography not available, etc.)
            logger.error("Encryption error: %s", str(e))
            raise  # Re-raise to be handled by caller
        except Exception as e:
            logger.error("Failed to store key to file: %s", str(e))
            return False

    @classmethod
    def _read_from_file(cls, key_name: str) -> Optional[str]:
        """Read key from encrypted file (fallback method)."""
        try:
            data = cls._read_secrets_file()
            encrypted = data.get(key_name)
            if encrypted:
                return cls._simple_decrypt(encrypted)
        except Exception:
            pass
        return None

    @classmethod
    def _delete_from_file(cls, key_name: str) -> bool:
        """Delete key from file (fallback method)."""
        import json
        deleted = False
        try:
            # Delete from all known fallback files (current + legacy).
            for secrets_file in cls._candidate_secret_files():
                if not secrets_file.exists():
                    continue

                data = {}
                try:
                    with open(secrets_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

                if key_name not in data:
                    continue

                del data[key_name]
                tmp_file = secrets_file.with_suffix(secrets_file.suffix + ".tmp")
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                os.replace(tmp_file, secrets_file)
                deleted = True
        except Exception:
            pass
        return deleted

    @classmethod
    def _read_secrets_file(cls) -> Dict:
        """Read secrets file, return empty dict if not exists."""
        import json

        merged: Dict[str, str] = {}
        for secrets_file in cls._candidate_secret_files():
            if not secrets_file.exists():
                continue
            try:
                with open(secrets_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # Keep first occurrence by priority order.
                    for k, v in data.items():
                        if k not in merged:
                            merged[k] = v
            except Exception:
                continue
        return merged

    # Cache for machine-specific key to ensure consistency
    _cached_machine_key: Optional[bytes] = None
    # Flag to show warning only once per session
    # 세션당 한 번만 경고를 표시하기 위한 플래그
    _warning_shown: bool = False

    @classmethod
    def _get_dev_key_file(cls) -> Path:
        """
        Get path to development encryption key file.

        Returns:
            Path to .encryption_key file in user's home directory
        """
        # Reuse existing key file first for compatibility.
        for candidate in cls._candidate_key_files():
            if candidate.exists():
                return candidate

        # Otherwise pick the first writable directory.
        for candidate in cls._candidate_key_files():
            if cls._ensure_dir(candidate.parent):
                return candidate

        # Last-resort fallback.
        fallback = Path.home() / ".ssmaker" / ".encryption_key"
        cls._ensure_dir(fallback.parent)
        return fallback

    @classmethod
    def _is_production(cls) -> bool:
        """
        Check if running in production environment.

        Returns:
            True if production, False otherwise
        """
        # Explicit override for strict environments.
        if os.getenv("SECRETS_REQUIRE_ENV_KEY", "").strip() == "1":
            return True

        # Desktop packaged app should not fail key save due inherited APP_ENV.
        if getattr(sys, "frozen", False):
            return False

        env = os.getenv('APP_ENV', '').lower()
        return env in ('production', 'prod')

    @classmethod
    def _get_fernet_key(cls) -> bytes:
        """
        Get or generate a Fernet-compatible encryption key (32 bytes, base64-encoded).
        Fernet 호환 암호화 키 가져오기 또는 생성 (32바이트, base64 인코딩).

        Priority:
        1. SECRETS_ENCRYPTION_KEY environment variable (required for production)
        2. Persisted random key from file (development only)
        3. Generate and persist new random key (development only)

        Security Note:
        - For production, SECRETS_ENCRYPTION_KEY is REQUIRED (generate with: openssl rand -hex 32)
        - In development, a random key is generated and persisted to a file
        """
        import secrets as secrets_module
        import logging

        logger = logging.getLogger(__name__)

        # Priority 1: Environment variable (required for production)
        env_key = os.getenv('SECRETS_ENCRYPTION_KEY')
        if env_key and len(env_key) >= 32:
            key_hash = hashlib.sha256(env_key.encode()).digest()
            return base64.urlsafe_b64encode(key_hash)

        # In production, environment variable is required
        if cls._is_production():
            logger.error(
                "SECURITY ERROR: SECRETS_ENCRYPTION_KEY environment variable is required in production. "
                "Generate with: openssl rand -hex 32"
            )
            raise RuntimeError(
                "Encryption key configuration error. Contact administrator."
            )

        # Priority 2: Cached key (ensures consistency within session)
        if cls._cached_machine_key is not None:
            return cls._cached_machine_key

        # Priority 3: Read persisted key from file (development only)
        key_file = cls._get_dev_key_file()
        if key_file.exists():
            try:
                with open(key_file, 'r', encoding='utf-8') as f:
                    persisted_key = f.read().strip()
                if persisted_key and len(persisted_key) >= 32:
                    key_hash = hashlib.sha256(persisted_key.encode()).digest()
                    cls._cached_machine_key = base64.urlsafe_b64encode(key_hash)
                    # Show warning only once per session
                    # 세션당 한 번만 경고 표시
                    if not cls._warning_shown:
                        cls._warning_shown = True
                        logger.debug(
                            "[보안] 개발 모드: 파일 기반 암호화 키 사용 중. "
                            "프로덕션에서는 SECRETS_ENCRYPTION_KEY 환경 변수를 설정하세요."
                        )
                    return cls._cached_machine_key
            except Exception:
                pass

        # Priority 4: Generate and persist new random key (development only)
        try:
            # Ensure directory exists
            key_file.parent.mkdir(parents=True, exist_ok=True)

            # Generate cryptographically secure random key
            random_key = secrets_module.token_hex(32)

            # Persist to file for consistency across restarts
            with open(key_file, 'w', encoding='utf-8') as f:
                f.write(random_key)

            # Set restrictive permissions on key file
            cls._set_file_permissions(key_file)

            key_hash = hashlib.sha256(random_key.encode()).digest()
            cls._cached_machine_key = base64.urlsafe_b64encode(key_hash)

            # Show warning only once per session
            # 세션당 한 번만 경고 표시
            if not cls._warning_shown:
                cls._warning_shown = True
                logger.debug(
                    "[보안] 개발 모드: 새 암호화 키 생성됨. 저장 위치: %s. "
                    "프로덕션에서는 SECRETS_ENCRYPTION_KEY 환경 변수를 설정하세요.",
                    key_file
                )
            return cls._cached_machine_key

        except Exception as e:
            logger.exception("Failed to generate or persist encryption key: %s", e)
            raise RuntimeError(
                f"Encryption key configuration error: {e}"
            )

    @classmethod
    def _simple_encrypt(cls, text: str) -> str:
        """
        Encrypt text using Fernet (AES-128-CBC with HMAC).
        Fernet(AES-128-CBC + HMAC)을 사용한 텍스트 암호화.

        Requires cryptography library for secure encryption.
        """
        import logging
        logger = logging.getLogger(__name__)

        if not FERNET_AVAILABLE:
            logger.error(
                "cryptography library not available. "
                "Install with: pip install cryptography"
            )
            raise RuntimeError(
                "Secure encryption requires the cryptography library. "
                "Install with: pip install cryptography"
            )

        try:
            key = cls._get_fernet_key()
            fernet = Fernet(key)
            encrypted = fernet.encrypt(text.encode('utf-8'))
            # Prefix with 'fernet:' to identify encryption method
            return 'fernet:' + encrypted.decode('utf-8')
        except RuntimeError:
            # Re-raise RuntimeError as-is (already has generic message)
            raise
        except Exception as e:
            # Log detailed error internally, raise generic message externally
            logger.exception("Encryption failed")
            raise RuntimeError("Failed to encrypt secret. Check logs for details.") from e

    @classmethod
    def _simple_decrypt(cls, encrypted: str) -> str:
        """
        Decrypt text using appropriate method based on prefix.
        접두사에 따라 적절한 방법으로 텍스트 복호화.

        Supports:
        - fernet: prefix for Fernet-encrypted data
        - xor: prefix for legacy XOR-encrypted data (read-only, migration needed)
        """
        import logging
        logger = logging.getLogger(__name__)

        # Check for Fernet encryption (preferred)
        if encrypted.startswith('fernet:'):
            if not FERNET_AVAILABLE:
                raise RuntimeError(
                    "cryptography library required to decrypt secrets. "
                    "Install with: pip install cryptography"
                )
            try:
                key = cls._get_fernet_key()
                fernet = Fernet(key)
                encrypted_data = encrypted[7:]  # Remove 'fernet:' prefix
                decrypted = fernet.decrypt(encrypted_data.encode('utf-8'))
                return decrypted.decode('utf-8')
            except RuntimeError:
                # Re-raise RuntimeError as-is (already has generic message)
                raise
            except Exception as e:
                # Log detailed error internally, raise generic message externally
                logger.error("Fernet decryption failed: %s", e)
                raise RuntimeError("Failed to decrypt secret. Check logs for details.") from e

        # Legacy XOR decryption (read-only support for migration)
        if encrypted.startswith('xor:'):
            logger.warning(
                "Legacy XOR encryption detected. "
                "Re-save secrets to upgrade to Fernet encryption."
            )
            encrypted = encrypted[4:]  # Remove 'xor:' prefix

            try:
                decoded = base64.b64decode(encrypted.encode('utf-8')).decode('utf-8')
            except Exception:
                # Try as-is for very old format
                decoded = encrypted

            key = cls._get_fernet_key().decode('utf-8')
            decrypted = []
            for i, char in enumerate(decoded):
                key_char = key[i % len(key)]
                decrypted_char = chr(ord(char) ^ ord(key_char))
                decrypted.append(decrypted_char)
            return ''.join(decrypted)

        # Unknown format
        logger.error("Unknown encryption format detected")
        raise ValueError("Failed to decrypt secret. Data may be corrupted.")

    @classmethod
    def migrate_from_plaintext(cls, plaintext_keys: Dict[str, str]) -> int:
        """
        Migrate plaintext API keys to secure storage.

        Args:
            plaintext_keys: Dictionary of {key_name: key_value}

        Returns:
            Number of keys successfully migrated
        """
        count = 0
        for key_name, key_value in plaintext_keys.items():
            if cls.store_api_key(key_name, key_value):
                count += 1
        return count


def migrate_api_keys_from_config():
    """
    Helper function to migrate API keys from config.py to secure storage.

    Usage:
        from utils.secrets_manager import migrate_api_keys_from_config
        migrate_api_keys_from_config()
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from config import GEMINI_API_KEYS

        # Migrate Gemini keys
        migrated = 0
        for key_name, key_value in GEMINI_API_KEYS.items():
            if key_value and key_value.strip():
                if SecretsManager.store_api_key(f"gemini_{key_name}", key_value):
                    migrated += 1

        logger.info("Migrated %d API keys to secure storage", migrated)
        logger.info("You can now remove plaintext keys from config.py")

        return migrated
    except ImportError as e:
        logger.warning("Migration skipped - config module not found: %s", e)
        return 0
    except Exception as e:
        logger.error("Migration failed: %s", e)
        return 0


# Auto-migrate on first import (optional, can be disabled)
_AUTO_MIGRATE = False
if _AUTO_MIGRATE:
    migrate_api_keys_from_config()


# Singleton instance wrapper for compatibility
class _SecretsManagerWrapper:
    """
    Wrapper providing instance methods for SecretsManager.
    Maintains compatibility with get_secrets_manager() pattern.
    """

    def set_credential(self, key_name: str, key_value: str) -> bool:
        """Store credential securely."""
        return SecretsManager.store_api_key(key_name, key_value)

    def get_credential(self, key_name: str) -> Optional[str]:
        """Retrieve credential."""
        return SecretsManager.get_api_key(key_name)

    def delete_credential(self, key_name: str) -> bool:
        """Delete credential."""
        return SecretsManager.delete_api_key(key_name)

    def list_credentials(self) -> list:
        """List all stored credential names."""
        return SecretsManager.list_stored_keys()


_secrets_manager_instance = None


def get_secrets_manager() -> _SecretsManagerWrapper:
    """
    Get secrets manager instance (singleton pattern).

    Returns:
        SecretsManager wrapper instance

    Example:
        >>> sm = get_secrets_manager()
        >>> sm.set_credential('auth_token', 'abc123')
        >>> token = sm.get_credential('auth_token')
    """
    global _secrets_manager_instance
    if _secrets_manager_instance is None:
        _secrets_manager_instance = _SecretsManagerWrapper()
    return _secrets_manager_instance
