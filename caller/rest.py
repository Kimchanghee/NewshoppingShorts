# -*- coding: utf-8 -*-

import requests
import json
import os
import configparser
import traceback
import jwt
import threading
import time
import functools
from typing import Optional, Dict, Any
from datetime import datetime, timezone

# Import logging and security utilities
from utils.logging_config import get_logger
from utils.secrets_manager import get_secrets_manager
from utils.validators import validate_user_id, validate_ip_address

logger = get_logger(__name__)
secrets_manager = get_secrets_manager()

# Generic error messages for client responses (don't expose internals)
# 클라이언트 응답용 일반 오류 메시지 (내부 정보 노출 방지)
_ERROR_MESSAGES = {
    "timeout": "요청 시간이 초과되었습니다. 다시 시도해 주세요.",
    "connection": "서버 연결에 실패했습니다. 네트워크를 확인해 주세요.",
    "network": "네트워크 오류가 발생했습니다.",
    "parse": "서버 응답을 처리할 수 없습니다.",
    "unexpected": "예상치 못한 오류가 발생했습니다.",
    "invalid_input": "입력값이 올바르지 않습니다.",
}

# Server URL from environment variable (secure configuration)
# 환경 변수에서 서버 URL 가져오기 (보안 설정)
# Production: Cloud Run, Development: localhost
main_server = os.getenv(
    "API_SERVER_URL", "https://ssmaker-auth-api-1049571775048.us-central1.run.app/"
)

# Production environment detection
# 운영 환경 감지
_IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"


def _sanitize_user_id_for_logging(user_id: str) -> str:
    """
    Mask user ID for safe logging - shows only first 2 and last 2 characters.
    안전한 로깅을 위해 사용자 ID 마스킹 - 처음 2자와 마지막 2자만 표시.

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
    운영 환경에서 HTTPS가 강제되는지 확인.

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
    검증 없이 JWT 토큰 만료 여부 확인.

    Args:
        token: JWT token to check

    Returns:
        True if token is valid (not expired), False if expired
    """
    try:
        # Decode without verification to check expiration
        # 만료 확인을 위해 검증 없이 디코딩
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
        return True  # Allow storage if we can't decode (might be different format)
    except Exception as e:
        logger.warning(f"Unexpected error checking token expiration: {e}")
        return True


def _create_secure_session() -> requests.Session:
    """
    Create a requests session with connection pooling and SSL verification.
    연결 풀링 및 SSL 검증이 활성화된 requests 세션 생성.

    Returns:
        Configured requests.Session with SSL verification and connection pooling
    """
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.verify = True  # Explicit SSL certificate verification

    # 향상된 재시도 전략: 구독 시스템에 최적화
    # - total=3: 최대 3회 재시도
    # - backoff_factor=1.0: 지수 백오프 (1, 2, 4초)
    # - status_forcelist: 서버 오류 시 재시도
    # - method_whitelist: GET, POST, PUT, DELETE 모두 재시도
    retry_strategy = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(
        pool_connections=10,  # 증가된 연결 풀
        pool_maxsize=20,
        max_retries=retry_strategy,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


# Create a module-level secure session for reuse
# 재사용을 위한 모듈 수준 보안 세션 생성
_secure_session = _create_secure_session()


def _get_auth_token() -> Optional[str]:
    """
    Get stored JWT token from secure credential manager.
    보안 credential manager에서 JWT 토큰 가져오기.

    Returns:
        JWT token or None if not set
    """
    try:
        return secrets_manager.get_credential("auth_token")
    except Exception as e:
        logger.warning(f"Failed to retrieve auth token: {e}")
        return None


def _set_auth_token(token: Optional[str]) -> None:
    """
    Store JWT token in secure credential manager.
    JWT 토큰을 보안 credential manager에 저장.

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
    입력 검증이 포함된 사용자 로그인.

    Args:
        data: Login data containing userId, userPw, key, ip, force

    Returns:
        Login response dict
    """
    # HTTPS security check for production
    # 운영 환경에서 HTTPS 보안 확인
    if not _check_https_security():
        return {"status": "error", "message": "Secure connection required"}

    # Input validation
    # 입력 검증
    user_id = data.get("userId", "")
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
        response = _secure_session.post(
            main_server + "user/login/god",
            json=body,
            timeout=(
                3,
                10,
            ),  # (connect_timeout, read_timeout) - 빠른 연결, 적절한 읽기 시간
        )
        response.raise_for_status()
        loginObject = json.loads(response.text)

        # Store JWT token securely on successful login
        # 로그인 성공 시 JWT 토큰 안전하게 저장
        if loginObject.get("status") == True and "data" in loginObject:
            token = loginObject.get("data", {}).get("token")
            if token:
                # Check token expiration before storing
                # 저장 전 토큰 만료 확인
                if _check_token_expiration(token):
                    _set_auth_token(token)
                else:
                    logger.warning("Received expired JWT token from server")

        return loginObject
    except requests.exceptions.Timeout:
        logger.error("Login request timed out")
        return {"status": "error", "message": _ERROR_MESSAGES["timeout"]}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Login connection error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES["connection"]}
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
    보안 토큰 정리가 포함된 사용자 로그아웃.

    Args:
        data: Logout data containing userId, key

    Returns:
        Status string ('success' or 'error')
    """
    # Input validation
    user_id = data.get("userId", "")
    if not validate_user_id(user_id):
        logger.error(
            f"Invalid user ID format: {_sanitize_user_id_for_logging(user_id)}"
        )
        return "error"

    # Use stored token if available
    # 저장된 토큰이 있으면 사용
    stored_token = _get_auth_token()
    body = {"id": user_id, "key": stored_token or data.get("key", "")}

    try:
        response = _secure_session.post(
            main_server + "user/logout/god", json=body, timeout=60
        )
        response.raise_for_status()
        loginObject = json.loads(response.text)

        # Clear token on logout (success or failure)
        # 로그아웃 시 토큰 클리어 (성공/실패 무관)
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
    로그인 상태 확인 (하트비트).

    Args:
        data: Check data containing userId, key, ip

    Returns:
        Check response dict
    """
    user_id = data.get("userId", "")
    # 하트비트 체크는 검증 실패 시 조용히 스킵 (에러 로그 없이)
    if not user_id:
        return {"status": "skip", "message": "No user ID"}

    ip_address = data.get("ip", "")
    if not validate_ip_address(ip_address):
        logger.warning(f"Invalid IP address format: {ip_address}")

    # Use stored token if available
    stored_token = _get_auth_token()
    body = {
        "id": user_id,
        "key": stored_token or data.get("key", ""),
        "ip": ip_address,
    }

    try:
        response = _secure_session.post(
            main_server + "user/login/god/check", json=body, timeout=60
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
    폴백이 있는 서버 버전 가져오기.

    Returns:
        Version string
    """
    try:
        response = _secure_session.get(main_server + "free/lately/?item=22", timeout=5)
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
        logger.warning("Version check server timeout - using default version")
        return "1.0.0"
    except requests.exceptions.RequestException as e:
        logger.warning(f"Version check failed: {e} - using default version")
        return "1.0.0"
    except json.JSONDecodeError as e:
        logger.error(f"Version response parsing failed: {e} - using default version")
        return "1.0.0"
    except Exception as e:
        logger.exception(f"Unexpected version check error: {e} - using default version")
        return "1.0.0"


def submitRegistrationRequest(
    name: str, username: str, password: str, contact: str
) -> Dict[str, Any]:
    """
    Submit a registration request to the server.
    서버에 회원가입 요청을 제출합니다.

    Args:
        name: 가입자 명
        username: 사용할 아이디
        password: 비밀번호
        contact: 연락처

    Returns:
        Response dict with 'success' boolean and optional 'message'
    """
    # HTTPS security check
    if not _check_https_security():
        return {"success": False, "message": "보안 연결이 필요합니다."}

    # Input validation
    if not name or len(name.strip()) < 2:
        return {"success": False, "message": "가입자 명은 2자 이상이어야 합니다."}

    if not validate_user_id(username):
        return {"success": False, "message": "아이디 형식이 올바르지 않습니다."}

    if not password or len(password) < 6:
        return {"success": False, "message": "비밀번호는 6자 이상이어야 합니다."}

    if not contact or len(contact.strip()) < 10:
        return {"success": False, "message": "연락처를 올바르게 입력해주세요."}

    body = {
        "name": name.strip(),
        "username": username.strip(),
        "password": password,
        "contact": contact.strip(),
    }

    try:
        logger.info(
            f"Sending registration request to: {main_server}user/register/request"
        )
        response = _secure_session.post(
            main_server + "user/register/request", json=body, timeout=30
        )

        # 모든 응답 로깅 (디버깅용)
        logger.info(f"Registration response status: {response.status_code}")
        logger.info(f"Registration response body: {response.text[:500]}")

        if response.status_code == 409:
            # Username already exists or pending
            return {
                "success": False,
                "message": "이미 사용 중이거나 승인 대기 중인 아이디입니다.",
            }

        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            logger.info(
                f"Registration request submitted for: {_sanitize_user_id_for_logging(username)}"
            )
            return {"success": True, "message": "회원가입 요청이 접수되었습니다."}
        else:
            # 서버에서 온 에러 메시지 그대로 전달
            server_message = result.get("message", "요청 처리에 실패했습니다.")
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
    사용자의 잔여 작업 횟수 확인.

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
            main_server + "user/work/check", json=body, timeout=10
        )
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.Timeout:
        logger.error("Work check request timed out")
        return {
            "success": False,
            "can_work": True,
            "message": _ERROR_MESSAGES["timeout"],
        }
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Work check connection error: {e}")
        return {
            "success": False,
            "can_work": True,
            "message": _ERROR_MESSAGES["connection"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Work check network error: {str(e)[:100]}")
        return {
            "success": False,
            "can_work": True,
            "message": _ERROR_MESSAGES["network"],
        }
    except Exception as e:
        logger.exception(f"Unexpected work check error: {e}")
        return {
            "success": False,
            "can_work": True,
            "message": _ERROR_MESSAGES["unexpected"],
        }


def useWork(user_id: str) -> Dict[str, Any]:
    """
    Increment work_used count after successful work completion.
    작업 완료 후 사용 횟수 증가.

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
            main_server + "user/work/use", json=body, timeout=10
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
    info.on 파일에서 포트 설정.

    Returns:
        True if successful, False otherwise
    """
    try:
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
    사용자의 상세 구독 상태 조회.

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
            main_server + "user/subscription/my-status", headers=headers, timeout=10
        )
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.Timeout:
        logger.error("Subscription status request timed out")
        return {
            "success": False,
            "is_trial": True,
            "can_work": True,
            "message": _ERROR_MESSAGES["timeout"],
        }
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Subscription status connection error: {e}")
        return {
            "success": False,
            "is_trial": True,
            "can_work": True,
            "message": _ERROR_MESSAGES["connection"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Subscription status network error: {str(e)[:100]}")
        return {
            "success": False,
            "is_trial": True,
            "can_work": True,
            "message": _ERROR_MESSAGES["network"],
        }
    except Exception as e:
        logger.exception(f"Unexpected subscription status error: {e}")
        return {
            "success": False,
            "is_trial": True,
            "can_work": True,
            "message": _ERROR_MESSAGES["unexpected"],
        }


def submitSubscriptionRequest(user_id: str, message: str = "") -> Dict[str, Any]:
    """
    Submit a subscription request.
    구독 신청을 제출합니다.

    Args:
        user_id: User ID
        message: Optional message for the request

    Returns:
        Response dict with 'success' boolean and 'message'
    """
    stored_token = _get_auth_token()
    if not stored_token:
        return {"success": False, "message": "로그인이 필요합니다."}

    headers = {"X-User-ID": str(user_id), "Authorization": f"Bearer {stored_token}"}

    body = {"message": message}

    try:
        logger.info(
            f"Submitting subscription request for user: {_sanitize_user_id_for_logging(str(user_id))}"
        )
        response = _secure_session.post(
            main_server + "user/subscription/request",
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
# 에지 케이스 처리 및 재시도 유틸리티
# ============================================================================


def with_retry(max_retries: int = 3, backoff_factor: float = 1.0):
    """
    재시도 데코레이터: 네트워크 오류 시 자동 재시도

    Args:
        max_retries: 최대 재시도 횟수
        backoff_factor: 지수 백오프 계수 (초)

    Returns:
        데코레이터 함수
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
                ) as e:
                    last_exception = e

                    if attempt < max_retries:
                        wait_time = backoff_factor * (2**attempt)
                        logger.warning(
                            f"네트워크 오류 발생: {type(e).__name__}. "
                            f"{wait_time:.1f}초 후 재시도 ({attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"최대 재시도 횟수 초과: {type(e).__name__}")
                except Exception as e:
                    # 네트워크 오류가 아닌 다른 예외는 즉시 전파
                    raise e

            if last_exception:
                raise last_exception
            raise RuntimeError("재시도 로직 오류")

        return wrapper

    return decorator


def handle_token_expiry(func):
    """
    토큰 만료 처리 데코레이터: 401 에러 시 토큰 갱신 시도

    Args:
        func: 데코레이트할 함수

    Returns:
        데코레이터 함수
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning("토큰 만료 감지, 로그인 필요")
                raise PermissionError(
                    "인증 토큰이 만료되었습니다. 다시 로그인해주세요."
                )
            raise e

    return wrapper


class SubscriptionStateManager:
    """
    구독 상태 관리자: 상태 불일치 감지 및 복구

    이 클래스는 구독 상태의 일관성을 유지하고,
    네트워크 문제나 경쟁 조건으로 인한 상태 불일치를 감지/복구합니다.
    """

    def __init__(self):
        self._last_known_state = None
        self._state_lock = threading.RLock()
        self._inconsistent_count = 0
        self._max_inconsistent_before_reset = 3

    def update_state(self, new_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        상태 업데이트 및 불일치 감지

        Args:
            new_state: 새로운 상태 데이터

        Returns:
            검증된 상태 데이터
        """
        with self._state_lock:
            if self._last_known_state is None:
                self._last_known_state = new_state
                return new_state

            is_inconsistent = self._detect_inconsistency(new_state)

            if is_inconsistent:
                self._inconsistent_count += 1
                logger.warning(
                    f"구독 상태 불일치 감지 ({self._inconsistent_count}/"
                    f"{self._max_inconsistent_before_reset}): {new_state}"
                )

                if self._inconsistent_count >= self._max_inconsistent_before_reset:
                    logger.error("너무 많은 상태 불일치 발생, 상태 재설정")
                    self._reset_state()
                    return new_state

                return self._last_known_state
            else:
                self._inconsistent_count = 0
                self._last_known_state = new_state
                return new_state

    def _detect_inconsistency(self, new_state: Dict[str, Any]) -> bool:
        """상태 불일치 감지 로직"""
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
        """상태 재설정"""
        self._last_known_state = None
        self._inconsistent_count = 0
        logger.info("구독 상태 관리자 재설정 완료")

    def get_last_state(self) -> Optional[Dict[str, Any]]:
        """마지막으로 알려진 상태 반환"""
        return self._last_known_state


# 전역 상태 관리자 인스턴스
_subscription_state_manager = SubscriptionStateManager()


def get_subscription_status_with_consistency(user_id: str) -> Dict[str, Any]:
    """
    일관성 있는 구독 상태 조회

    Args:
        user_id: 사용자 ID

    Returns:
        일관성 검증된 구독 상태
    """
    raw_status = getSubscriptionStatus(user_id)

    # 상태 관리자를 통해 일관성 검증
    validated_status = _subscription_state_manager.update_state(raw_status)

    return validated_status


def safe_subscription_request(user_id: str, message: str = "") -> Dict[str, Any]:
    """
    안전한 구독 신청: 재시도 및 에러 처리 포함

    Args:
        user_id: 사용자 ID
        message: 신청 메시지

    Returns:
        신청 결과
    """

    @with_retry(max_retries=2, backoff_factor=1.5)
    @handle_token_expiry
    def _make_request():
        return submitSubscriptionRequest(user_id, message)

    try:
        return _make_request()
    except PermissionError as e:
        logger.error(f"인증 오류로 구독 신청 실패: {e}")
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"구독 신청 중 예상치 못한 오류: {e}")
        return {"success": False, "message": "내부 오류가 발생했습니다."}
