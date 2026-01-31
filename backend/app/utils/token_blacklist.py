"""
JWT Token Blacklist for Secure Logout
Prevents token reuse after logout
"""
from datetime import datetime, timedelta
from typing import Set, Optional
import threading

class TokenBlacklist:
    """In-memory token blacklist (use Redis for production)"""

    def __init__(self):
        self._blacklist: Set[str] = set()
        self._lock = threading.Lock()

    def add(self, jti: str, expires_at: datetime) -> None:
        """Add token JTI to blacklist"""
        with self._lock:
            self._blacklist.add(jti)

    def is_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        with self._lock:
            return jti in self._blacklist

    def cleanup_expired(self) -> None:
        """Remove expired tokens (called periodically)"""
        # In production, Redis with TTL handles this automatically
        pass

# Global instance
_token_blacklist = TokenBlacklist()

def get_token_blacklist() -> TokenBlacklist:
    return _token_blacklist
