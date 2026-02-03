"""
Application Error Classes
애플리케이션 에러 클래스

Centralized error handling with consistent response format.
일관된 응답 형식을 위한 중앙화된 에러 처리.

Usage:
    from app.errors import AppError, Errors

    # Raise a validation error
    raise Errors.validation({"field": "username", "message": "Required"})

    # Raise a not found error
    raise Errors.not_found("User")
"""
from typing import Union, Optional, Any
from uuid import uuid4


# Error code type
ErrorCode = str


class AppError(Exception):
    """
    Application error class for consistent error handling.

    Attributes:
        code: Error code (e.g., 'VALIDATION_ERROR', 'AUTH_ERROR')
        status: HTTP status code
        details: Additional error details (for internal logging)
        request_id: UUID for request tracing
    """

    def __init__(
        self,
        code: ErrorCode,
        status: int,
        details: Optional[Any] = None,
        request_id: Optional[str] = None,
    ):
        self.code = code
        self.status = status
        self.details = details
        self.request_id = request_id or str(uuid4())
        self.name = "AppError"
        super().__init__(code)

    def to_dict(self, is_production: bool = True) -> dict:
        """
        Convert error to JSON-serializable dict.

        Args:
            is_production: If True, hide internal details

        Returns:
            Error response dictionary
        """
        response = {
            "success": False,
            "error": {
                "code": self.code,
                "message": self._get_public_message() if is_production else self.code,
                "requestId": self.request_id,
            },
        }

        # Include details in non-production
        if not is_production and self.details:
            response["error"]["details"] = self.details

        return response

    def _get_public_message(self) -> str:
        """Get user-friendly message for error code."""
        messages = {
            "VALIDATION_ERROR": "입력값이 올바르지 않습니다.",
            "AUTH_ERROR": "인증이 필요합니다.",
            "FORBIDDEN_ERROR": "접근 권한이 없습니다.",
            "NOT_FOUND_ERROR": "요청한 리소스를 찾을 수 없습니다.",
            "CONFLICT_ERROR": "요청이 현재 상태와 충돌합니다.",
            "RATE_LIMIT_ERROR": "요청이 너무 많습니다. 잠시 후 다시 시도하세요.",
            "INTERNAL_ERROR": "서버 오류가 발생했습니다.",
        }
        return messages.get(self.code, messages["INTERNAL_ERROR"])


class Errors:
    """Factory class for creating AppError instances."""

    @staticmethod
    def validation(details: Optional[Any] = None) -> AppError:
        """Create validation error (400)."""
        return AppError("VALIDATION_ERROR", 400, details)

    @staticmethod
    def auth(details: Optional[Any] = None) -> AppError:
        """Create authentication error (401)."""
        return AppError("AUTH_ERROR", 401, details)

    @staticmethod
    def forbidden(details: Optional[Any] = None) -> AppError:
        """Create forbidden error (403)."""
        return AppError("FORBIDDEN_ERROR", 403, details)

    @staticmethod
    def not_found(resource: str) -> AppError:
        """Create not found error (404)."""
        return AppError("NOT_FOUND_ERROR", 404, {"resource": resource})

    @staticmethod
    def conflict(details: Optional[Any] = None) -> AppError:
        """Create conflict error (409)."""
        return AppError("CONFLICT_ERROR", 409, details)

    @staticmethod
    def rate_limit(retry_after: Optional[int] = None) -> AppError:
        """Create rate limit error (429)."""
        return AppError("RATE_LIMIT_ERROR", 429, {"retryAfter": retry_after})

    @staticmethod
    def internal(details: Optional[Any] = None) -> AppError:
        """Create internal server error (500)."""
        return AppError("INTERNAL_ERROR", 500, details)
