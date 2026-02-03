"""
Error Handling Framework (minimal placeholder, PyQt6 build-safe)
"""
import logging
import sys
import traceback
from typing import Any, Callable, Optional, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)
F = TypeVar('F', bound=Callable[..., Any])

# Exception classes with proper initialization
class AppException(Exception):
    """Base exception for application errors"""
    def __init__(self, message: str = "", details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details


class OCRInitializationError(AppException):
    """OCR engine initialization failed"""
    def __init__(self, message: str = "", recovery_hint: str = "", details: Optional[Any] = None):
        super().__init__(message, details)
        self.recovery_hint = recovery_hint


class OCRProcessingError(AppException):
    """OCR processing failed"""
    pass

class VideoProcessingError(AppException):
    pass

class VideoNotFoundError(AppException):
    pass

class APIError(AppException):
    pass

class APIKeyMissingError(AppException):
    pass

class ConfigurationError(AppException):
    pass


class GLMOCRError(AppException):
    """GLM-OCR API specific errors"""
    def __init__(self, message: str = "", details: Optional[Any] = None):
        super().__init__(message, details)


class GLMOCRRateLimitError(GLMOCRError):
    """Rate limit exceeded"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(message, {"retry_after": retry_after})
        self.retry_after = retry_after


class GLMOCROfflineError(GLMOCRError):
    """API unavailable, fallback to local OCR"""
    def __init__(self, message: str = "GLM-OCR API unavailable"):
        super().__init__(message)

class DependencyError(AppException):
    pass

class TrialLimitExceededError(Exception):
    """Raised when user exceeds trial usage limit"""
    def __init__(self, message: str, remaining: int = 0, total: int = 5):
        super().__init__(message)
        self.remaining = remaining
        self.total = total


# Utilities

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


def handle_errors(fallback_return=None, user_message: str = ""):
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:  # pragma: no cover
                logger.exception(user_message or f"Error in {func.__name__}: {e}")
                return fallback_return
        return wrapper  # type: ignore
    return decorator


def safe_execute(func: Callable, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:  # pragma: no cover
        logger.exception(f"safe_execute error in {func.__name__}: {e}")
        return None


def format_exception(exc: Exception) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


__all__ = [
    "global_exception_handler",
    "handle_errors",
    "safe_execute",
    "format_exception",
    "AppException",
    "OCRInitializationError",
    "OCRProcessingError",
    "VideoProcessingError",
    "VideoNotFoundError",
    "APIError",
    "APIKeyMissingError",
    "ConfigurationError",
    "DependencyError",
    "TrialLimitExceededError",
    "GLMOCRError",
    "GLMOCRRateLimitError",
    "GLMOCROfflineError",
]
