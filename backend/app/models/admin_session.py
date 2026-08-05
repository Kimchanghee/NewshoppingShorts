"""Database-backed administrator sessions.

Only a keyed digest of the opaque browser token is persisted.  A database
dump is therefore not sufficient to impersonate an administrator.
"""

from __future__ import annotations

import hashlib
import hmac

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base


def hash_admin_token(token: str, pepper: str) -> str:
    """Return the server-keyed digest used as the session lookup key."""
    return hmac.new(
        str(pepper).encode("utf-8"),
        str(token).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_ip = Column(String(45), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
