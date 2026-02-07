# -*- coding: utf-8 -*-

import requests
import json
import os
import sys
import configparser
import traceback
import jwt
import threading
import time
import functools
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

# Import logging and security utilities
from utils.logging_config import get_logger
from utils.secrets_manager import get_secrets_manager
from utils.validators import validate_user_id, validate_user_identifier, validate_ip_address

logger = get_logger(__name__)
secrets_manager = get_secrets_manager()

# Generic error messages for client responses (don't expose internals)
# ???????? ?  (?? ? ? ?)
_ERROR_MESSAGES = {
    "timeout": "요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
    "connection": "서버 접속이 불안정 합니다. 고객센터에 문의 해주세요",
    "network": "서버 접속이 불안정 합니다. 고객센터에 문의 해주세요",
    "parse": "서버 응답을 처리하지 못했습니다.",
    "unexpected": "알 수 없는 오류가 발생했습니다.",
    "invalid_input": "입력값이 올바르지 않습니다.",
}

# Server URL from environment variable (secure configuration)
# ? ???? URL ??( ? )
# Production: Cloud Run, Development: localhost
main_server = os.getenv(
    "API_SERVER_URL", "https://ssmaker-auth-api-1049571775048.us-central1.run.app"
).rstrip("/")

# Production environment detection
# ? ? ?
_IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"


def _sanitize_user_id_for_logging(user_id: str) -> str:
    """
    Mask user ID for safe logging - shows only first 2 and last 2 characters.
    ? ??
??? ???ID ??-  2?? ??2? ?.

    Args:
        user_id: The user ID to sanitize

    Returns:
        Masked user ID (e.g., 'us****er' for 'username')
    """
    if not user_id or len(user_id) < 4:
        return "****"
    return f"{user_id[:2]}{'*' * (len(user_id) - 4)}{user_id[-2:]}"


def _check_https_security() -> bool:
    """
    Check if HTTPS is enforced in production environment.
    ? ?? HTTPS  ? ?.

    Returns:
        True if secure, False if insecure in production
    """
    if _IS_PRODUCTION and main_server.startswith("http://"):
        logger.critical(
            "SECURITY WARNING: Using HTTP in production environment is not allowed. "
            "Set API_SERVER_URL to use HTTPS."
        )
        return False
    elif (
        main_server.startswith("http://")
        and "localhost" not in main_server
        and "127.0.0.1" not in main_server
    ):
        logger.warning(
            "SECURITY WARNING: Using HTTP for non-localhost server. "
            "Consider using HTTPS for secure communication."
        )
    return True


def _check_token_expiration(token: str) -> bool:
    """
    Check if JWT token is expired without verification.
    ?? JWT ?   ?? ?.

    Args:
        token: JWT token to check

    Returns:
        True if token is valid (not expired), False if expired
    """
    try:
        # Decode without verification to check expiration
        # NOTE: WE DO NOT VERIFY SIGNATURE HERE because client does not possess the secret key.
        # This check is only for client-side expiration handling.
        # Server verifies signature on every API call.
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")
        if exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            if exp_datetime < datetime.now(tz=timezone.utc):
                logger.warning("JWT token is expired")
                return False
        return True
    except jwt.exceptions.DecodeError as e:
        logger.warning(f"Failed to decode JWT token for expiration check: {e}")
        # Security: Reject invalid tokens (fail secure)
        return False
    except Exception as e:
        logger.warning(f"Unexpected error checking token expiration: {e}")
        # Security: Reject on error (fail secure)
        return False


def _create_secure_session() -> requests.Session:
    """
    Create a requests session with connection pooling and SSL verification.
    ? ???SSL  ?? requests ?
 ?.

    Returns:
        Configured requests.Session with SSL verification and connection pooling
    """
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.verify = True  # Explicit SSL certificate verification

    # Retry configuration:
    # - total=3: maximum retries
    # - backoff_factor=1.0: exponential backoff (1, 2, 4 seconds)
    # - status_forcelist: retry on common transient HTTP errors
    # - allowed_methods: enable retries for idempotent methods
    retry_strategy = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    # Connection pool optimization:
    # - pool_connections=50: Support up to 50 concurrent different hosts
    # - pool_maxsize=100: Allow up to 100 total connections per host
    # This improves performance for high-concurrency scenarios
    adapter = HTTPAdapter(
        pool_connections=50,   # Increased from 10 (concurrent hosts)
        pool_maxsize=100,      # Increased from 20 (total connections per host)
        max_retries=retry_strategy,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


# Create a module-level secure session for reuse
_secure_session = _create_secure_session()


def _friendly_login_message(login_object: Dict[str, Any]) -> str:
    """
    Convert server/login status codes into user-friendly Korean messages.
    """
    status = login_object.get("status")
    # Clean up the message, removing status codes if they are prepended
    raw_message = str(login_object.get("message") or "").strip()
    
    # If the server returned a clear Korean message (not just an error code), use it.
    if raw_message and raw_message not in ["EU001", "EU002", "EU003", "EU004", "EU005"] and len(raw_message) > 10:
         return raw_message

    # Map known status codes from the backend
    if status in ("EU001", "EU004", "INVALID_CREDENTIALS", "AUTH_FAIL", False):
        # Security: Unified error for user not found and invalid password
        return "아이디 또는 비밀번호가 틀렸습니다."
    if status == "EU002":
        return "구독 또는 체험판 사용 기간이 만료되었습니다."
    if status == "EU003":
        return "이미 다른 기기(또는 브라우저)에서 로그인 중입니다."
    if status == "EU005":
        return "너무 많은 로그인 시도가 있었습니다. 잠시 후 다시 시도해주세요."
    
    if status in ("EU429", 429):
        return "로그인 요청이 일시적으로 제한되었습니다. 잠시 후 시도해주세요."

    # Fallback generic message
    return "로그인에 실패했습니다. 잠시 후 다시 시도하거나 관리자에게 문의하세요."


def _get_auth_token() -> Optional[str]:
    """
    Get stored JWT token from secure credential manager.
     credential manager? JWT ?  ??

    Returns:
        JWT token or None if not set
    """
    try:
        token = secrets_manager.get_credential("auth_token")

        # Fail-safe: do not keep using an expired token. This prevents
        # confusing UX where the app looks "logged in" but all work/subscription
        # checks silently fail (and may be misinterpreted as trial exhaustion).
        if token and not _check_token_expiration(token):
            logger.info("Stored JWT token is expired. Clearing local token.")
            _set_auth_token(None)
            return None

        return token
    except Exception as e:
        logger.warning(f"Failed to retrieve auth token: {e}")
        return None


def _set_auth_token(token: Optional[str]) -> None:
    """
    Store JWT token in secure credential manager.
    JWT ? ?? credential manager?????

    Args:
        token: JWT token to store, or None to clear
    """
    try:
        if token:
            secrets_manager.set_credential("auth_token", token)
            logger.info("JWT token stored securely")
        else:
            secrets_manager.delete_credential("auth_token")
            logger.info("JWT token cleared")
    except Exception as e:
        logger.error(f"Failed to store auth token: {e}")


def login(**data) -> Dict[str, Any]:
    """
    User login with input validation.
    ?
   ????????

    Args:
        data: Login data containing userId, userPw, key, ip, force

    Returns:
        Login response dict
    """
    # HTTPS security check for production
    # ? ?? HTTPS  ?
    if not _check_https_security():
        return {"status": "error", "message": "Secure connection required"}

    # Input validation
    # ?
    user_id = (data.get("userId", "") or "").strip().lower()
    if not validate_user_id(user_id):
        logger.error(
            f"Invalid user ID format: {_sanitize_user_id_for_logging(user_id)}"
        )
        return {"status": "error", "message": _ERROR_MESSAGES["invalid_input"]}

    ip_address = data.get("ip", "")
    if not validate_ip_address(ip_address):
        logger.warning(f"Invalid IP address format: {ip_address}")
        # Continue anyway as IP validation may be too strict

    body = {
        "id": user_id,
        "pw": data.get("userPw", ""),
        "key": data.get("key", ""),
        "ip": ip_address,
        "force": data.get("force", False),
    }

    try:
        # Logging philosophy: INFO for important events, DEBUG for routine operations, WARNING for recoverable errors, ERROR for failures
        logger.info(f"[Login] Requesting login to: {main_server}/user/login/god")
        logger.debug(f"[Login] Params: id={_sanitize_user_id_for_logging(user_id)}, ip={ip_address}, force={data.get('force', False)}")
        
        start_time = time.time()
        response = _secure_session.post(
            f"{main_server}/user/login/god",
            json=body,
            timeout=(3, 10),
        )
        elapsed = time.time() - start_time
        
        logger.info(f"[Login] Response received in {elapsed:.2f}s, Status: {response.status_code}")
        # Raw response logged at TRACE level only (contains token)
        logger.debug("[Login] Raw response received (length=%d)", len(response.text))
        
        # Parse response body for logging (mask sensitive data)
        try:
            loginObject = json.loads(response.text)
            # ??? ??? ? ?
            safe_log_obj = loginObject.copy()
            if "data" in safe_log_obj and isinstance(safe_log_obj["data"], dict):
                data_part = safe_log_obj["data"].copy()
                if "token" in data_part:
                    data_part["token"] = "MASKED_TOKEN"
                safe_log_obj["data"] = data_part
            logger.info(f"[Login] Response body: {json.dumps(safe_log_obj, ensure_ascii=False)}")
        except Exception:
            logger.warning("[Login] Failed to parse response body for logging")

        response.raise_for_status()

        # Store JWT token securely on successful login
        if loginObject.get("status") == True and "data" in loginObject:
            token = loginObject.get("data", {}).get("token")
            if token:
                if _check_token_expiration(token):
                    _set_auth_token(token)
                    logger.info("[Login] New auth token stored successfully")
                else:
                    logger.warning("[Login] Received expired JWT token from server")
            else:
                logger.warning("[Login] No token found in successful login response")
        else:
            # Normalize message for common failure cases
            loginObject["message"] = _friendly_login_message(loginObject)

        return loginObject
    except requests.exceptions.Timeout:
        logger.error("Login request timed out")
        return {"status": "error", "message": _ERROR_MESSAGES["timeout"]}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Login connection error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES["connection"]}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return {
                "status": "error",
                "message": "아이디 또는 비밀번호가 올바르지 않습니다.",
            }
        elif e.response.status_code == 404:
            return {"status": "error", "message": "해당 계정을 찾을 수 없습니다."}
        elif e.response.status_code == 403:
            return {
                "status": "error",
                "message": "접근이 거부되었습니다. (인증 또는 권한 오류)",
            }
        elif e.response.status_code == 429:
            # 서버가 rate limit을 반환해도 사용자에게는 일반 로그인 오류만 알림
            return {
                "status": "error",
                "message": "아이디 또는 비밀번호가 올바르지 않습니다.",
            }
        return {
            "status": "error",
            "message": f"서버 오류가 발생했습니다. (HTTP {e.response.status_code})",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Login network error: {str(e)[:100]}")
        return {"status": "error", "message": _ERROR_MESSAGES["network"]}
    except json.JSONDecodeError as e:
        logger.error(f"Login JSON parsing error: {str(e)[:50]}")
        return {"status": "error", "message": _ERROR_MESSAGES["parse"]}
    except Exception as e:
        logger.exception(f"Unexpected login error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES["unexpected"]}


def logOut(**data) -> str:
    """
    User logout with secure token cleanup.
     ?  ? ???????.

    Args:
        data: Logout data containing userId, key

    Returns:
        Status string ('success' or 'error')
    """
    # Input validation
    # NOTE: Backend user ids can be numeric (e.g. "22"), so use the broader validator.
    user_id = data.get("userId", "")
    if not validate_user_identifier(user_id):
        logger.error(
            f"Invalid user ID format: {_sanitize_user_id_for_logging(str(user_id))}"
        )
        # Security: ensure local auth token is not kept on logout failure.
        _set_auth_token(None)
        return "error"

    # Use stored token if available
    # ?? ? ?????
    stored_token = _get_auth_token()
    body = {"id": user_id, "key": stored_token or data.get("key", "")}

    try:
        response = _secure_session.post(
            f"{main_server}/user/logout/god", json=body, timeout=60
        )
        response.raise_for_status()
        loginObject = json.loads(response.text)

        # Clear token on logout (success or failure)
        # ? ???  ???(?/? ?)
        _set_auth_token(None)

        return loginObject.get("status", "error")
    except requests.exceptions.Timeout:
        logger.error("Logout request timed out")
        _set_auth_token(None)
        return "error"
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Logout connection error: {e}")
        _set_auth_token(None)
        return "error"
    except requests.exceptions.RequestException as e:
        logger.error(f"Logout network error: {str(e)[:100]}")
        _set_auth_token(None)
        return "error"
    except json.JSONDecodeError as e:
        logger.error(f"Logout JSON parsing error: {str(e)[:50]}")
        _set_auth_token(None)
        return "error"
    except Exception as e:
        logger.exception(f"Unexpected logout error: {e}")
        _set_auth_token(None)
        return "error"


def loginCheck(**data) -> Dict[str, Any]:
    """
    Check login status (heartbeat).
    ??? ? (?).

    Args:
        data: Check data containing userId, key, ip

    Returns:
        Check response dict
    """
    user_id = data.get("userId", "")
    # ? ???? ????? (?  ?)
    if not user_id:
        return {"status": "skip", "message": "No user ID"}

    ip_address = data.get("ip", "")
    if not validate_ip_address(ip_address):
        logger.warning(f"Invalid IP address format: {ip_address}")

    # Use stored token if available
    stored_token = _get_auth_token()
    if not stored_token:
        return {"status": "AUTH_REQUIRED", "message": "No auth token"}
    body = {
        "id": user_id,
        "key": stored_token,
        "ip": ip_address,
        "current_task": data.get("current_task"),
        "app_version": data.get("app_version")
    }

    try:
        response = _secure_session.post(
            f"{main_server}/user/login/god/check", json=body, timeout=60
        )
        response.raise_for_status()
        loginObject = json.loads(response.text)
        return loginObject
    except requests.exceptions.Timeout:
        logger.error("Login check request timed out")
        return {"status": "error", "message": _ERROR_MESSAGES["timeout"]}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Login check connection error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES["connection"]}
    except requests.exceptions.RequestException as e:
        logger.error(f"Login check network error: {str(e)[:100]}")
        return {"status": "error", "message": _ERROR_MESSAGES["network"]}
    except json.JSONDecodeError as e:
        logger.error(f"Login check JSON parsing error: {str(e)[:50]}")
        return {"status": "error", "message": _ERROR_MESSAGES["parse"]}
    except Exception as e:
        logger.exception(f"Unexpected login check error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES["unexpected"]}


def getVersion() -> str:
    """
    Get server version with fallback.
    ???? ?   ??

    Returns:
        Version string
    """
    try:
        response = _secure_session.get(
            f"{main_server}/free/lately/?item=22", timeout=15
        )
        response.raise_for_status()
        bodyObject = json.loads(response.text)
        version = bodyObject.get("version", "1.0.0")
        logger.info(f"Server version: {version}")
        return version
    except (
        requests.exceptions.ConnectTimeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    ):
        logger.debug("Version check server timeout - using default version")
        return "1.0.0"
    except requests.exceptions.RequestException as e:
        logger.debug(f"Version check failed: {e} - using default version")
        return "1.0.0"
    except json.JSONDecodeError as e:
        logger.debug(f"Version response parsing failed: {e} - using default version")
        return "1.0.0"
    except Exception as e:
        logger.debug(f"Unexpected version check error: {e} - using default version")
        return "1.0.0"


def submitRegistrationRequest(
    name: str, username: str, password: str, contact: str, email: str
) -> Dict[str, Any]:
    """
    Submit a registration request to the server.
    ?????????????

    Args:
        name: ?
 ?        username: ??????        password: ?
        contact: ??
        email: ???
    Returns:
        Response dict with 'success' boolean and optional 'message'
    """
    # HTTPS security check
    if not _check_https_security():
        return {"success": False, "message": "Secure connection required."}

    # Input validation
    if not name or len(name.strip()) < 2:
        return {"success": False, "message": "Name must be at least 2 characters."}

    if not validate_user_id(username):
        return {"success": False, "message": "Username format is invalid."}

    if not password or len(password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters."}

    # 연락처: 숫자/하이픈만 허용되므로 미리 정제
    import re
    cleaned_contact = re.sub(r"[^0-9\-]", "", contact or "")
    if not cleaned_contact or len(cleaned_contact) < 10:
        return {
            "success": False,
            "message": "연락처는 숫자/하이픈 10자리 이상 입력해주세요.",
        }

    # Email validation (simple check)
    if not email or "@" not in email or "." not in email:
        return {
            "success": False,
            "message": "올바른 이메일 주소를 입력해주세요.",
        }

    body = {
        "name": name.strip(),
        "username": username.strip().lower(),
        "password": password,
        "contact": cleaned_contact,
        "email": email.strip()
    }

    try:
        logger.info(
            f"Sending registration request to: {main_server}/user/register/request"
        )
        masked_contact = cleaned_contact[:3] + "****" + cleaned_contact[-4:] if len(cleaned_contact) >= 7 else "****"
        logger.info(
            "Registration payload: name=%s username=%s contact=%s",
            _sanitize_user_id_for_logging(name),
            _sanitize_user_id_for_logging(username),
            masked_contact,
        )
        response = _secure_session.post(
            f"{main_server}/user/register/request", json=body, timeout=30
        )

        logger.info(f"Registration response status: {response.status_code}")

        if response.status_code == 409:
            # Username already exists
            return {
                "success": False,
                "message": "Username already exists.",
            }

        if response.status_code == 422:
            # FastAPI validation error
            try:
                detail = response.json().get("detail", [])
                if detail and isinstance(detail, list):
                    msg = detail[0].get("msg", "")
                    return {
                        "success": False,
                        "message": f"입력값이 올바르지 않습니다. {msg}",
                    }
            except Exception:
                pass
            return {
                "success": False,
                "message": "입력값이 올바르지 않습니다. (연락처는 숫자/하이픈 10자리 이상)",
            }

        if response.status_code == 429:
            try:
                error_data = response.json()
                error_info = error_data.get("error", {})
                retry_after = error_info.get(
                    "retry_after", "1? ??? ???."
                )
                return {
                    "success": False,
                    "message": f"??????? ?.\n{retry_after} ??? ???.",
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "message": "??????? ?.\n?  ??? ???.",
                }

        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            logger.info(
                f"Registration request submitted for: {_sanitize_user_id_for_logging(username)}"
            )
            # Return full result to allow auto-login
            return result
        else:
            # Server-side error handling (SQL or validation issues)
            server_message = result.get("message", "Registration failed.")

            if (
                "Duplicate entry" in server_message
                or "IntegrityError" in server_message
                or "1062" in str(server_message)
            ):
                server_message = (
                    "Username or contact already exists. Please use different values."
                )
            elif "SQL" in server_message or "pymysql" in server_message:
                server_message = "Server database error. Please try again later."

            logger.error(f"Registration failed: {server_message}")
            return {"success": False, "message": server_message}

    except requests.exceptions.Timeout:
        logger.error("Registration request timed out")
        return {"success": False, "message": _ERROR_MESSAGES["timeout"]}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Registration connection error: {e}")
        return {"success": False, "message": _ERROR_MESSAGES["connection"]}
    except requests.exceptions.RequestException as e:
        logger.error(f"Registration network error: {str(e)[:100]}")
        return {"success": False, "message": _ERROR_MESSAGES["network"]}
    except json.JSONDecodeError as e:
        logger.error(f"Registration JSON parsing error: {str(e)[:50]}")
        return {"success": False, "message": _ERROR_MESSAGES["parse"]}
    except Exception as e:
        logger.exception(f"Unexpected registration error: {e}")
        return {"success": False, "message": _ERROR_MESSAGES["unexpected"]}


def checkWorkAvailable(user_id: str) -> Dict[str, Any]:
    """
    Check if user has remaining work count available.
    ?? ? ?
 ? ?.

    Args:
        user_id: User ID

    Returns:
        dict with success, can_work, work_count, work_used, remaining
    """
    stored_token = _get_auth_token()
    if not stored_token:
        return {
            "success": False,
            "can_work": False,
            "work_count": 0,
            "work_used": 0,
            "remaining": 0,
            "message": "No auth token",
        }

    body = {"user_id": str(user_id), "token": stored_token}

    try:
        response = _secure_session.post(
            f"{main_server}/user/work/check", json=body, timeout=10
        )
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.Timeout:
        logger.error("Work check request timed out")
        return {
            "success": False,
            "can_work": False,  # Security: deny access on verification failure
            "message": _ERROR_MESSAGES["timeout"],
        }
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Work check connection error: {e}")
        return {
            "success": False,
            "can_work": False,  # Security: deny access on verification failure
            "message": _ERROR_MESSAGES["connection"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Work check network error: {str(e)[:100]}")
        return {
            "success": False,
            "can_work": False,  # Security: deny access on verification failure
            "message": _ERROR_MESSAGES["network"],
        }
    except Exception as e:
        logger.exception(f"Unexpected work check error: {e}")
        return {
            "success": False,
            "can_work": False,  # Security: deny access on verification failure
            "message": _ERROR_MESSAGES["unexpected"],
        }


def check_work_available(user_id: str) -> Dict[str, Any]:
    """
    Check if user has trial uses remaining.
    ?? ??? ? ? (checkWorkAvailable ).

    Returns:
        dict with available (bool), remaining (int), total (int), used (int)
    """
    try:
        result = checkWorkAvailable(user_id)

        # Transform response to match expected format.
        # NOTE: On verification failure (token expired, no token, network, etc),
        # do NOT pretend the user used 5/5. Preserve any numeric fields when
        # present and attach a message so callers can show a correct prompt.
        if result.get("success"):
            return {
                "success": True,
                "available": result.get("can_work", False),
                "remaining": result.get("remaining", 0),
                "total": result.get("work_count", 0),
                "used": result.get("work_used", 0),
            }

        msg = result.get("message") or "작업 가능 여부 확인에 실패했습니다. 다시 로그인해주세요."
        logger.error(f"Failed to check work availability: {msg}")

        work_count = result.get("work_count", 0)
        work_used = result.get("work_used", 0)
        remaining = result.get("remaining", 0)

        return {
            "success": False,
            "available": False,
            "remaining": remaining if isinstance(remaining, int) else 0,
            "total": work_count if isinstance(work_count, int) else 0,
            "used": work_used if isinstance(work_used, int) else 0,
            "message": msg,
        }
    except Exception as e:
        logger.error(f"Failed to check work availability: {e}")
        return {
            "success": False,
            "available": False,
            "remaining": 0,
            "total": 0,
            "used": 0,
            "message": _ERROR_MESSAGES["unexpected"],
        }


def useWork(user_id: str) -> Dict[str, Any]:
    """
    Increment work_used count after successful work completion.
    ?
 ? ??? ? ?.

    Args:
        user_id: User ID

    Returns:
        dict with success, message, remaining, used
    """
    stored_token = _get_auth_token()
    if not stored_token:
        return {
            "success": False,
            "message": "No auth token",
            "remaining": None,
            "used": None,
        }

    body = {"user_id": str(user_id), "token": stored_token}

    try:
        response = _secure_session.post(
            f"{main_server}/user/work/use", json=body, timeout=10
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"Work used: remaining={result.get('remaining')}")
        return result
    except requests.exceptions.Timeout:
        logger.error("Use work request timed out")
        return {"success": False, "message": _ERROR_MESSAGES["timeout"]}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Use work connection error: {e}")
        return {"success": False, "message": _ERROR_MESSAGES["connection"]}
    except requests.exceptions.RequestException as e:
        logger.error(f"Use work network error: {str(e)[:100]}")
        return {"success": False, "message": _ERROR_MESSAGES["network"]}
    except Exception as e:
        logger.exception(f"Unexpected use work error: {e}")
        return {"success": False, "message": _ERROR_MESSAGES["unexpected"]}


def setPort() -> bool:
    """
    Set port configuration from info.on file.
    info.on ?? ? ? .

    Returns:
        True if successful, False otherwise
    """
    try:
        # Frozen builds must not rely on CWD or embedded file layout (onefile extraction).
        # Use per-user location for config presence checks.
        if bool(getattr(sys, "frozen", False)):
            info_file_path = str((Path.home() / ".newshopping" / "info.on"))
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            info_file_path = os.path.join(current_dir, "..", "info.on")
            info_file_path = os.path.normpath(info_file_path)

        if not os.path.exists(info_file_path):
            logger.warning(f"Config file not found: {info_file_path}")
            return False

        config = configparser.ConfigParser()
        config.read(info_file_path, encoding="utf-8")

        if "Config" in config and "version" in config["Config"]:
            version = config["Config"]["version"]
            logger.info(f"Config version loaded: {version}")
            return True
        else:
            logger.warning("Config section or version not found in info.on")
            return False

    except configparser.Error as e:
        logger.error(f"Config parsing error: {e}")
        return False
    except IOError as e:
        logger.error(f"Config file I/O error: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected setPort error: {e}")
        traceback.print_exc()
        return False


# ===== Subscription API Functions =====


def getSubscriptionStatus(user_id: str) -> Dict[str, Any]:
    """
    Get detailed subscription status for the user.
    ?? ? 
 ? .

    Args:
        user_id: User ID

    Returns:
        dict with is_trial, work_count, work_used, remaining, can_work, has_pending_request
    """
    stored_token = _get_auth_token()
    if not stored_token:
        return {
            "success": False,
            "is_trial": True,
            "work_count": 0,
            "work_used": 0,
            "remaining": 0,
            "can_work": False,
            "has_pending_request": False,
            "message": "No auth token",
        }

    headers = {"X-User-ID": str(user_id), "Authorization": f"Bearer {stored_token}"}

    try:
        response = _secure_session.get(
            f"{main_server}/user/subscription/my-status", headers=headers, timeout=10
        )
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.Timeout:
        logger.error("Subscription status request timed out")
        return {
            "success": False,
            "is_trial": True,
            "can_work": False,  # Security: deny access on verification failure
            "message": _ERROR_MESSAGES["timeout"],
        }
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Subscription status connection error: {e}")
        return {
            "success": False,
            "is_trial": True,
            "can_work": False,  # Security: deny access on verification failure
            "message": _ERROR_MESSAGES["connection"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Subscription status network error: {str(e)[:100]}")
        return {
            "success": False,
            "is_trial": True,
            "can_work": False,  # Security: deny access on verification failure
            "message": _ERROR_MESSAGES["network"],
        }
    except Exception as e:
        logger.exception(f"Unexpected subscription status error: {e}")
        return {
            "success": False,
            "is_trial": True,
            "can_work": False,  # Security: deny access on verification failure
            "message": _ERROR_MESSAGES["unexpected"],
        }


def submitSubscriptionRequest(user_id: str, message: str = "") -> Dict[str, Any]:
    """
    Submit a subscription request.
    
 ? ??????

    Args:
        user_id: User ID
        message: Optional message for the request

    Returns:
        Response dict with 'success' boolean and 'message'
    """
    stored_token = _get_auth_token()
    if not stored_token:
        return {"success": False, "message": "? ????"}

    headers = {"X-User-ID": str(user_id), "Authorization": f"Bearer {stored_token}"}

    body = {"message": message}

    try:
        logger.info(
            f"Submitting subscription request for user: {_sanitize_user_id_for_logging(str(user_id))}"
        )
        response = _secure_session.post(
            f"{main_server}/user/subscription/request",
            headers=headers,
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            logger.info("Subscription request submitted successfully")
        else:
            logger.warning(f"Subscription request failed: {result.get('message')}")

        return result
    except requests.exceptions.Timeout:
        logger.error("Subscription request timed out")
        return {"success": False, "message": _ERROR_MESSAGES["timeout"]}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Subscription request connection error: {e}")
        return {"success": False, "message": _ERROR_MESSAGES["connection"]}
    except requests.exceptions.RequestException as e:
        logger.error(f"Subscription request network error: {str(e)[:100]}")
        return {"success": False, "message": _ERROR_MESSAGES["network"]}
    except Exception as e:
        logger.exception(f"Unexpected subscription request error: {e}")
        return {"success": False, "message": _ERROR_MESSAGES["unexpected"]}


# ============================================================================
# ?? ?  ????? 
# ============================================================================


def with_retry(max_retries: int = 3, backoff_factor: float = 1.0):
    """
    ??????? ?? ? ??? ???
    Args:
        max_retries: ? ????
        backoff_factor: ???? (?

    Returns:
        ?????
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.RequestException,
                    TimeoutError,
                    ConnectionError,
                ) as e:
                    last_exception = e

                    if attempt < max_retries:
                        wait_time = backoff_factor * (2**attempt)
                        logger.warning(
                            f"요청 실패: {type(e).__name__}. "
                            f"{wait_time:.1f}초 후 재시도({attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"재시도 실패: {type(e).__name__}")
                except Exception as e:
                    # ?? ? ? ? ??? ?
                    raise

            if last_exception:
                raise last_exception
            raise RuntimeError("재시도 실패")

        return wrapper

    return decorator


def handle_token_expiry(func):
    """
    ?    ???? 401 ? ???    ?

    Args:
        func: ???  ?

    Returns:
        ?????
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Be liberal in what we accept here: in tests/mocks we may not get
            # a real requests.exceptions.HTTPError instance.
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code == 401:
                msg = "인증 토큰이 만료되었습니다. 다시 로그인해주세요."
                logger.warning(msg)
                raise PermissionError(msg) from e
            raise

    return wrapper


class SubscriptionStateManager:
    """
    
 ? : ? ?? ?

    ???? 
 ?????? ? ?? ,
    ??  ?? ? ? ? ? ?/???
    """

    def __init__(self):
        self._last_known_state = None
        self._state_lock = threading.RLock()
        self._inconsistent_count = 0
        self._max_inconsistent_before_reset = 3

    def update_state(self, new_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        ? ?
?
        
        ???  ??? ?  ?
????
        
        Args:
            new_state: ???? ???            
        Returns:
            ?
???? ???        """
        with self._state_lock:
            # First observation: cache only successful state.
            if self._last_known_state is None:
                if new_state.get("success", False):
                    self._last_known_state = new_state
                return new_state

            # If API call failed, do not overwrite last known good state.
            if not new_state.get("success", False):
                return new_state

            # Same state: stable again, clear any in-progress inconsistency counter.
            if new_state == self._last_known_state:
                self._inconsistent_count = 0
                return new_state

            # Detect inconsistent state flips (trial/subscriber etc).
            if self._detect_inconsistency(new_state):
                self._inconsistent_count += 1

                # Keep old state for a few inconsistent responses.
                if self._inconsistent_count <= self._max_inconsistent_before_reset:
                    return self._last_known_state

                # After repeated inconsistencies, accept the new state (switch) and
                # reset the counter. This avoids leaving the cache empty and makes
                # behavior deterministic under concurrency.
                self._inconsistent_count = 0
                self._log_state_changes(self._last_known_state, new_state)
                self._last_known_state = new_state
                return new_state

            # Consistent update: accept and reset inconsistency counter.
            self._inconsistent_count = 0
            self._log_state_changes(self._last_known_state, new_state)
            self._last_known_state = new_state
            return new_state

    def _log_state_changes(self, old_state: Dict[str, Any], new_state: Dict[str, Any]):
        """? ?? 
"""
        if not new_state.get("success", False):
            return

        key_fields = ["is_trial", "can_work", "has_pending_request", "remaining", "work_count"]
        changes = []
        
        for field in key_fields:
            old_val = old_state.get(field)
            new_val = new_state.get(field)
            if old_val != new_val:
                changes.append(f"{field}: {old_val} -> {new_val}")
        
        if changes:
            logger.info(f"State changed: {', '.join(changes)}")

    def _detect_inconsistency(self, new_state: Dict[str, Any]) -> bool:
        """? ?? """
        if not new_state.get("success", False):
            return False

        old_state = self._last_known_state
        if old_state is None:
            return False

        key_fields = ["is_trial", "can_work", "has_pending_request"]

        for field in key_fields:
            old_value = old_state.get(field)
            new_value = new_state.get(field)
            if old_value is not None and new_value is not None:
                if old_value != new_value:
                    return True

        return False

    def _reset_state(self):
        """Reset cached subscription state and inconsistency counter."""
        self._last_known_state = None
        self._inconsistent_count = 0
        logger.info("Subscription state reset")

    def get_last_state(self) -> Optional[Dict[str, Any]]:
        """Return last known subscription state."""
        return self._last_known_state


# ? ?  ??
_subscription_state_manager = SubscriptionStateManager()


def get_subscription_status_with_consistency(user_id: str) -> Dict[str, Any]:
    """
    ????? 
 ? 

    Args:
        user_id: ???ID

    Returns:
        ???? 
 ?
    """
    raw_status = getSubscriptionStatus(user_id)

    validated_status = _subscription_state_manager.update_state(raw_status)

    return validated_status


def safe_subscription_request(user_id: str, message: str = "") -> Dict[str, Any]:
    """
    ? ??
 ? : ?????  ?

    Args:
        user_id: ???ID
        message: ?  

    Returns:
        ?  
    """

    @with_retry(max_retries=2, backoff_factor=1.5)
    @handle_token_expiry
    def _make_request():
        return submitSubscriptionRequest(user_id, message)

    try:
        return _make_request()
    except PermissionError as e:
        logger.error(f"Permission error during subscription request: {e}")
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"Subscription request failed: {e}")
        return {"success": False, "message": "Subscription request failed."}
