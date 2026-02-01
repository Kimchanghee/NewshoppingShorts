import jwt
import uuid
from datetime import datetime, timedelta
from app.configuration import get_settings

settings = get_settings()


def create_access_token(user_id: int, ip_address: str) -> tuple[str, str, datetime]:
    """
    Create JWT token
    Returns: (token, jti, expires_at)
    """
    jti = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)

    payload = {
        "sub": user_id,  # Subject (user ID)
        "jti": jti,  # JWT ID (for revocation)
        "ip": ip_address,  # IP binding
        "exp": expires_at,  # Expiration
        "iat": datetime.utcnow(),  # Issued at
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")
