# -*- coding: utf-8 -*-

import requests
import json
import os
import configparser
import traceback
import jwt
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
    'timeout': "요청 시간이 초과되었습니다. 다시 시도해 주세요.",
    'connection': "서버 연결에 실패했습니다. 네트워크를 확인해 주세요.",
    'network': "네트워크 오류가 발생했습니다.",
    'parse': "서버 응답을 처리할 수 없습니다.",
    'unexpected': "예상치 못한 오류가 발생했습니다.",
    'invalid_input': "입력값이 올바르지 않습니다.",
}

# Server URL from environment variable (secure configuration)
# 환경 변수에서 서버 URL 가져오기 (보안 설정)
# Production: Cloud Run, Development: localhost
main_server = os.getenv('API_SERVER_URL', 'https://ssmaker-auth-api-1049571775048.us-central1.run.app/')

# Production environment detection
# 운영 환경 감지
_IS_PRODUCTION = os.getenv('ENVIRONMENT', 'development').lower() == 'production'

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
        return '****'
    return f"{user_id[:2]}{'*' * (len(user_id) - 4)}{user_id[-2:]}"

def _check_https_security() -> bool:
    """
    Check if HTTPS is enforced in production environment.
    운영 환경에서 HTTPS가 강제되는지 확인.

    Returns:
        True if secure, False if insecure in production
    """
    if _IS_PRODUCTION and main_server.startswith('http://'):
        logger.critical(
            "SECURITY WARNING: Using HTTP in production environment is not allowed. "
            "Set API_SERVER_URL to use HTTPS."
        )
        return False
    elif main_server.startswith('http://') and 'localhost' not in main_server and '127.0.0.1' not in main_server:
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
        exp = payload.get('exp')
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
    Create a requests session with explicit SSL verification enabled.
    명시적 SSL 검증이 활성화된 requests 세션 생성.

    Returns:
        Configured requests.Session with SSL verification
    """
    session = requests.Session()
    session.verify = True  # Explicit SSL certificate verification
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
        return secrets_manager.get_credential('auth_token')
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
            secrets_manager.set_credential('auth_token', token)
            logger.info("JWT token stored securely")
        else:
            secrets_manager.delete_credential('auth_token')
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
    user_id = data.get('userId', '')
    if not validate_user_id(user_id):
        logger.error(f"Invalid user ID format: {_sanitize_user_id_for_logging(user_id)}")
        return {"status": "error", "message": _ERROR_MESSAGES['invalid_input']}

    ip_address = data.get('ip', '')
    if not validate_ip_address(ip_address):
        logger.warning(f"Invalid IP address format: {ip_address}")
        # Continue anyway as IP validation may be too strict

    body = {
        'id': user_id,
        'pw': data.get('userPw', ''),
        'key': data.get('key', ''),
        'ip': ip_address,
        'force': data.get('force', False)
    }

    try:
        response = _secure_session.post(
            main_server + 'user/login/god',
            json=body,
            timeout=60
        )
        response.raise_for_status()
        loginObject = json.loads(response.text)

        # Store JWT token securely on successful login
        # 로그인 성공 시 JWT 토큰 안전하게 저장
        if loginObject.get('status') == True and 'data' in loginObject:
            token = loginObject.get('data', {}).get('token')
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
        return {"status": "error", "message": _ERROR_MESSAGES['timeout']}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Login connection error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES['connection']}
    except requests.exceptions.RequestException as e:
        logger.error(f"Login network error: {str(e)[:100]}")
        return {"status": "error", "message": _ERROR_MESSAGES['network']}
    except json.JSONDecodeError as e:
        logger.error(f"Login JSON parsing error: {str(e)[:50]}")
        return {"status": "error", "message": _ERROR_MESSAGES['parse']}
    except Exception as e:
        logger.exception(f"Unexpected login error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES['unexpected']}

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
    user_id = data.get('userId', '')
    if not validate_user_id(user_id):
        logger.error(f"Invalid user ID format: {_sanitize_user_id_for_logging(user_id)}")
        return "error"

    # Use stored token if available
    # 저장된 토큰이 있으면 사용
    stored_token = _get_auth_token()
    body = {
        'id': user_id,
        'key': stored_token or data.get('key', '')
    }

    try:
        response = _secure_session.post(
            main_server + 'user/logout/god',
            json=body,
            timeout=60
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
    Check login status with input validation.
    입력 검증이 포함된 로그인 상태 확인.

    Args:
        data: Check data containing userId, key, ip

    Returns:
        Check response dict
    """
    # Input validation
    user_id = data.get('userId', '')
    if not validate_user_id(user_id):
        logger.error(f"Invalid user ID format: {_sanitize_user_id_for_logging(user_id)}")
        return {"status": "error", "message": _ERROR_MESSAGES['invalid_input']}

    ip_address = data.get('ip', '')
    if not validate_ip_address(ip_address):
        logger.warning(f"Invalid IP address format: {ip_address}")

    # Use stored token if available
    stored_token = _get_auth_token()
    body = {
        'id': user_id,
        'key': stored_token or data.get('key', ''),
        'ip': ip_address,
    }

    try:
        response = _secure_session.post(
            main_server + 'user/login/god/check',
            json=body,
            timeout=60
        )
        response.raise_for_status()
        loginObject = json.loads(response.text)
        return loginObject
    except requests.exceptions.Timeout:
        logger.error("Login check request timed out")
        return {"status": "error", "message": _ERROR_MESSAGES['timeout']}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Login check connection error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES['connection']}
    except requests.exceptions.RequestException as e:
        logger.error(f"Login check network error: {str(e)[:100]}")
        return {"status": "error", "message": _ERROR_MESSAGES['network']}
    except json.JSONDecodeError as e:
        logger.error(f"Login check JSON parsing error: {str(e)[:50]}")
        return {"status": "error", "message": _ERROR_MESSAGES['parse']}
    except Exception as e:
        logger.exception(f"Unexpected login check error: {e}")
        return {"status": "error", "message": _ERROR_MESSAGES['unexpected']}

def getVersion() -> str:
    """
    Get server version with fallback.
    폴백이 있는 서버 버전 가져오기.

    Returns:
        Version string
    """
    try:
        response = _secure_session.get(main_server + 'free/lately/?item=22', timeout=5)
        response.raise_for_status()
        bodyObject = json.loads(response.text)
        version = bodyObject.get("version", "1.0.0")
        logger.info(f"Server version: {version}")
        return version
    except (requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout):
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


def submitRegistrationRequest(name: str, username: str, password: str, contact: str) -> Dict[str, Any]:
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
        'name': name.strip(),
        'username': username.strip(),
        'password': password,
        'contact': contact.strip()
    }

    try:
        response = _secure_session.post(
            main_server + 'user/register/request',
            json=body,
            timeout=30
        )

        if response.status_code == 409:
            # Username already exists or pending
            return {"success": False, "message": "이미 사용 중이거나 승인 대기 중인 아이디입니다."}

        response.raise_for_status()
        result = response.json()

        if result.get('success'):
            logger.info(f"Registration request submitted for: {_sanitize_user_id_for_logging(username)}")
            return {"success": True, "message": "회원가입 요청이 접수되었습니다."}
        else:
            return {"success": False, "message": result.get('message', '요청 처리에 실패했습니다.')}

    except requests.exceptions.Timeout:
        logger.error("Registration request timed out")
        return {"success": False, "message": _ERROR_MESSAGES['timeout']}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Registration connection error: {e}")
        return {"success": False, "message": _ERROR_MESSAGES['connection']}
    except requests.exceptions.RequestException as e:
        logger.error(f"Registration network error: {str(e)[:100]}")
        return {"success": False, "message": _ERROR_MESSAGES['network']}
    except json.JSONDecodeError as e:
        logger.error(f"Registration JSON parsing error: {str(e)[:50]}")
        return {"success": False, "message": _ERROR_MESSAGES['parse']}
    except Exception as e:
        logger.exception(f"Unexpected registration error: {e}")
        return {"success": False, "message": _ERROR_MESSAGES['unexpected']}

def setPort() -> bool:
    """
    Set port configuration from info.on file.
    info.on 파일에서 포트 설정.

    Returns:
        True if successful, False otherwise
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        info_file_path = os.path.join(current_dir, '..', 'info.on')
        info_file_path = os.path.normpath(info_file_path)

        if not os.path.exists(info_file_path):
            logger.warning(f"Config file not found: {info_file_path}")
            return False

        config = configparser.ConfigParser()
        config.read(info_file_path, encoding='utf-8')

        if 'Config' in config and 'version' in config['Config']:
            version = config['Config']['version']
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
