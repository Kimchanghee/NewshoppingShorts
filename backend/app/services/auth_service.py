import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.user import User
from app.models.session import SessionModel
from app.models.login_attempt import LoginAttempt
from app.utils.password import verify_password, get_dummy_hash
from app.utils.subscription_utils import is_subscription_active
from app.utils.jwt_handler import create_access_token, decode_access_token
from app.configuration import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _mask_username(username: str) -> str:
    """
    Mask username for logging (privacy protection).
    로깅을 위한 사용자 이름 마스킹 (개인 정보 보호).

    Args:
        username: Username to mask

    Returns:
        Masked username (e.g., "jo****hn" for "johnsmith")
    """
    if not username:
        return "***"
    if len(username) <= 4:
        return "****"
    return f"{username[:2]}{'*' * (len(username) - 4)}{username[-2:]}"


def _hash_ip(ip_address: str) -> str:
    """
    Hash IP address for logging (privacy protection).
    로깅을 위한 IP 주소 해시 (개인 정보 보호).

    Args:
        ip_address: IP address to hash

    Returns:
        First 12 characters of SHA256 hash
    """
    if not ip_address:
        return "unknown"
    return hashlib.sha256(ip_address.encode()).hexdigest()[:12]


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def login(self, username: str, password: str, ip_address: str, force: bool) -> Dict[str, Any]:
        """Login logic with dual rate limiting (username + IP)"""
        username = username.lower()
        # Logging philosophy: INFO for important events, DEBUG for routine operations, WARNING for recoverable errors, ERROR for failures
        logger.debug(
            f"Login attempt: username={_mask_username(username)}, ip={ip_address}, force={force}"
        )

        # Rate limiting check - both username and IP based
        rate_limit_result = await self._check_rate_limit(username, ip_address)
        if not rate_limit_result["allowed"]:
            # Security: Mask username and hash IP in logs for privacy
            # 보안: 개인 정보 보호를 위해 로그에서 사용자 이름 마스킹 및 IP 해시
            logger.warning(
                f"Rate limit exceeded: username={_mask_username(username)}, ip_hash={_hash_ip(ip_address)}, reason={rate_limit_result['reason']}"
            )
            return {
                "status": "EU005",
                "message": "Too many login attempts. Please try again later.",
            }

        # Find user
        user = self.db.query(User).filter(User.username == username).first()

        # Always perform password verification to prevent timing attacks
        # Use dummy hash if user doesn't exist to ensure constant-time response
        password_hash = user.password_hash if user else get_dummy_hash()
        password_valid = verify_password(password, password_hash)

        # Security: Use unified error response to prevent user enumeration
        # 보안: 사용자 열거 공격 방지를 위해 통합된 에러 응답 사용
        # All authentication failures return the same error code (EU001)

        if not user:
            # User enumeration is allowed per user request for better UX
            self._record_login_attempt(username, ip_address, success=False)
            logger.info(f"[Login Failed] User not found: username={_mask_username(username)}, ip={ip_address}")
            return {"status": "EU001", "message": "EU001"}  # User not found - masked as invalid credentials

        if not password_valid:
            # Record failed attempt
            self._record_login_attempt(username, ip_address, success=False)
            logger.info(f"[Login Failed] Invalid password: username={_mask_username(username)}, ip={ip_address}")
            return {"status": "EU001", "message": "EU001"}  # Invalid password

        # Check subscription and active status (naive/aware-safe via utils)
        if user.subscription_expires_at and not is_subscription_active(user.subscription_expires_at):
            self._record_login_attempt(username, ip_address, success=False)
            logger.info(f"[Login Failed] Subscription expired: username={_mask_username(username)}, ip={ip_address}")
            return {"status": "EU002", "message": "EU002"}  # Subscription expired

        if not user.is_active:
            self._record_login_attempt(username, ip_address, success=False)
            logger.info(f"[Login Failed] User inactive: username={_mask_username(username)}, ip={ip_address}")
            return {"status": "EU001", "message": "EU001"}  # Unified error for inactive

        # Check existing session
        existing_session = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.user_id == user.id,
                SessionModel.is_active == True,
                SessionModel.expires_at > datetime.utcnow(),
            )
            .first()
        )

        if existing_session and not force:
            logger.info(f"[Login Failed] Duplicate login: username={_mask_username(username)}, ip={ip_address}")
            return {"status": "EU003", "message": "EU003"}  # Duplicate login

        # Force logout if needed
        if existing_session and force:
            existing_session.is_active = False
            self.db.commit()

        # Create JWT token
        token, jti, expires_at = create_access_token(user.id, ip_address)

        # Save session
        new_session = SessionModel(
            user_id=user.id,
            token_jti=jti,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        self.db.add(new_session)

        # Update user
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip_address
        user.login_count = (user.login_count or 0) + 1

        # Record success
        self._record_login_attempt(username, ip_address, success=True)

        self.db.commit()

        # Security: Hash IP in logs for privacy
        logger.info(
            f"Login successful: user_id={user.id}, ip_hash={_hash_ip(ip_address)}, login_count={user.login_count}"
        )

        # Backward compatible response with subscription info
        return {
            "status": True,
            "data": {
                "data": {
                    "id": str(user.id),
                    "username": user.username,
                    "user_type": user.user_type or "trial",
                    "subscription_expires_at": user.subscription_expires_at.isoformat()
                    if user.subscription_expires_at
                    else None,
                    "work_count": getattr(user, "work_count", -1),
                    "work_used": getattr(user, "work_used", 0),
                    "last_login_at": user.last_login_at.isoformat()
                    if user.last_login_at
                    else None,
                },
                "ip": ip_address,
                "token": token,
            },
        }

    async def logout(self, user_id: str, token: str) -> Union[bool, str]:
        """Logout logic with proper error handling"""
        try:
            payload = decode_access_token(token)
            jti = payload.get("jti")
            token_user_id = payload.get("sub")

            # Verify token belongs to the user making the request
            if str(token_user_id) != str(user_id):
                logger.warning(
                    f"Logout attempt with mismatched user_id: token={token_user_id}, request={user_id}"
                )
                return "error"

            session = (
                self.db.query(SessionModel)
                .filter(SessionModel.token_jti == jti, SessionModel.is_active == True)
                .first()
            )

            if session:
                session.is_active = False
                self.db.commit()
                logger.info(f"Logout successful: user_id={user_id}")
                return True
            return "error"
        except ValueError as e:
            logger.warning(f"Logout failed - invalid token: {e}")
            return "error"
        except Exception as e:
            logger.exception(f"Logout failed - unexpected error")
            return "error"

    async def check_session(
        self, user_id: str, token: str, ip_address: str,
        current_task: Optional[str] = None, app_version: Optional[str] = None
    ) -> dict:
        """Session check logic (called every 5 seconds)"""
        try:
            payload = decode_access_token(token)
            jti = payload.get("jti")
            token_ip = payload.get("ip")
            token_user_id = payload.get("sub")

            # Verify token belongs to the user making the request
            if str(token_user_id) != str(user_id):
                logger.warning(
                    f"Session check with mismatched user_id: token={token_user_id}, request={user_id}"
                )
                return {"status": "EU003"}

            # IP mismatch check
            if token_ip != ip_address:
                # Security: Hash IPs in logs for privacy
                logger.warning(
                    f"Session IP mismatch: token_ip_hash={_hash_ip(token_ip)}, request_ip_hash={_hash_ip(ip_address)}"
                )
                return {"status": "EU003"}  # Session from different IP

            # Database session check
            session = (
                self.db.query(SessionModel)
                .filter(
                    SessionModel.token_jti == jti,
                    SessionModel.is_active == True,
                    SessionModel.expires_at > datetime.utcnow(),
                )
                .first()
            )

            if not session:
                logger.info(f"Session not found or inactive: user_id={user_id}, jti={jti}")
                return {"status": "EU003"}  # Session invalid/expired

            # Update last activity in session
            session.last_activity_at = datetime.utcnow()
            
            # Update User heartbeat and online status
            # Ensure user_id is integer for query
            try:
                numeric_user_id = int(user_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid user_id format in session check: {user_id}")
                return {"status": "EU003"}

            user = self.db.query(User).filter(User.id == numeric_user_id).first()
            if user:
                user.last_heartbeat = datetime.utcnow()
                user.is_online = True
                if current_task is not None:
                    user.current_task = current_task
                if app_version is not None:
                    user.app_version = app_version
            
            self.db.commit()

            return {"status": True}

        except ValueError as e:
            if "expired" in str(e).lower():
                return {"status": "EU003"}
            # Don't expose internal error details
            logger.warning(f"Session check failed: {e}")
            return {"status": "error", "message": "Session verification failed"}
        except Exception as e:
            # Don't expose internal error details
            logger.exception("Session check failed unexpectedly")
            return {"status": "error", "message": "Session verification failed"}

    async def _check_rate_limit(self, username: str, ip_address: str) -> dict:
        """Check if login attempts exceed rate limit - dual check (username AND IP)"""
        cutoff_time = datetime.utcnow() - timedelta(
            minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES
        )

        # Check per-username limit (failed attempts only)
        username_attempts = (
            self.db.query(func.count(LoginAttempt.id))
            .filter(
                LoginAttempt.username == username,
                LoginAttempt.attempted_at > cutoff_time,
                LoginAttempt.success == False,
            )
            .scalar()
        )

        if username_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            return {"allowed": False, "reason": "username_limit"}

        # Check per-IP limit (all attempts - prevents enumeration)
        ip_attempts = (
            self.db.query(func.count(LoginAttempt.id))
            .filter(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.attempted_at > cutoff_time,
            )
            .scalar()
        )

        if ip_attempts >= settings.MAX_IP_ATTEMPTS:
            return {"allowed": False, "reason": "ip_limit"}

        return {"allowed": True, "reason": None}

    def _record_login_attempt(self, username: str, ip_address: str, success: bool):
        """Record login attempt for rate limiting - commits immediately for consistency"""
        attempt = LoginAttempt(
            username=username, ip_address=ip_address, success=success
        )
        self.db.add(attempt)
        self.db.commit()  # Commit immediately to ensure rate limiting works

    async def check_work_available(self, user_id: str, token: str) -> dict:
        """
        Check if user can perform work (has remaining work count).
        작업 가능 여부 확인 (잔여 작업 횟수 확인)

        Returns:
            dict with can_work, work_count, work_used, remaining
        """
        try:
            payload = decode_access_token(token)
            token_user_id = payload.get("sub")

            if str(token_user_id) != str(user_id):
                return {
                    "success": False,
                    "can_work": False,
                    "work_count": 0,
                    "work_used": 0,
                    "remaining": 0,
                }

            # Check if session is active (Revocation check)
            jti = payload.get("jti")
            session = (
                self.db.query(SessionModel)
                .filter(SessionModel.token_jti == jti, SessionModel.is_active == True)
                .first()
            )
            if not session:
                return {
                    "success": False,
                    "can_work": False,
                    "work_count": 0,
                    "work_used": 0,
                    "remaining": 0,
                }

            user = self.db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                return {
                    "success": False,
                    "can_work": False,
                    "work_count": 0,
                    "work_used": 0,
                    "remaining": 0,
                }

            work_count = getattr(user, "work_count", -1)
            work_used = getattr(user, "work_used", 0)

            # -1 means unlimited
            if work_count == -1:
                remaining = -1
                can_work = True
            else:
                remaining = max(0, work_count - work_used)
                can_work = remaining > 0

            return {
                "success": True,
                "can_work": can_work,
                "work_count": work_count,
                "work_used": work_used,
                "remaining": remaining,
            }

        except ValueError as e:
            logger.warning(f"Work check failed - invalid token: {e}")
            return {
                "success": False,
                "can_work": False,
                "work_count": 0,
                "work_used": 0,
                "remaining": 0,
            }
        except Exception as e:
            logger.exception("Work check failed unexpectedly")
            return {
                "success": False,
                "can_work": False,
                "work_count": 0,
                "work_used": 0,
                "remaining": 0,
            }

    async def use_work(self, user_id: str, token: str) -> dict:
        """
        Increment work_used count after successful work completion.
        작업 완료 후 사용 횟수 증가

        Returns:
            dict with success, message, remaining, used
        """
        try:
            payload = decode_access_token(token)
            token_user_id = payload.get("sub")

            if str(token_user_id) != str(user_id):
                return {
                    "success": False,
                    "message": "Token mismatch",
                    "remaining": None,
                    "used": None,
                }

            # Check if session is active (Revocation check)
            jti = payload.get("jti")
            session = (
                self.db.query(SessionModel)
                .filter(SessionModel.token_jti == jti, SessionModel.is_active == True)
                .first()
            )
            if not session:
                return {
                    "success": False,
                    "message": "Session expired or revoked",
                    "remaining": None,
                    "used": None,
                }

            user = self.db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                return {
                    "success": False,
                    "message": "User not found",
                    "remaining": None,
                    "used": None,
                }

            work_count = getattr(user, "work_count", -1)
            work_used = getattr(user, "work_used", 0)

            # Check if work is available (unless unlimited)
            if work_count != -1:
                remaining = work_count - work_used
                if remaining <= 0:
                    return {
                        "success": False,
                        "message": "No remaining work count",
                        "remaining": 0,
                        "used": work_used,
                    }

            # Increment work_used
            user.work_used = work_used + 1
            self.db.commit()

            new_remaining = (
                -1 if work_count == -1 else max(0, work_count - user.work_used)
            )

            logger.info(
                f"Work used: user_id={user_id}, used={user.work_used}, remaining={new_remaining}"
            )

            return {
                "success": True,
                "message": "Work count updated",
                "remaining": new_remaining,
                "used": user.work_used,
            }

        except ValueError as e:
            logger.warning(f"Use work failed - invalid token: {e}")
            return {
                "success": False,
                "message": "Invalid token",
                "remaining": None,
                "used": None,
            }
        except Exception as e:
            logger.exception("Use work failed unexpectedly")
            self.db.rollback()
            return {
                "success": False,
                "message": "Internal error",
                "remaining": None,
                "used": None,
            }
    async def cleanup_offline_users(self):
        """
        Mark users as offline if they haven't sent a heartbeat for more than 2 minutes.
        동작이 2분 이상 없는 사용자를 오프라인으로 표시.
        """
        try:
            from datetime import timedelta
            threshold = datetime.utcnow() - timedelta(minutes=2)
            
            # Find users who are marked online but haven't sent heartbeat in 2 mins
            db_users = self.db.query(User).filter(
                User.is_online == True,
                User.last_heartbeat < threshold
            ).all()
            
            for user in db_users:
                user.is_online = False
                logger.info(f"Marked user offline due to inactivity: {user.username}")
                
            if db_users:
                self.db.commit()
                
        except Exception as e:
            logger.error(f"Error cleaning up offline users: {e}")
            self.db.rollback()
