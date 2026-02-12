"""
Error Handling Framework (minimal placeholder, PyQt6 build-safe)
"""
import logging
import sys
import traceback
from typing import Any, Callable, Optional, TypeVar, Type, Tuple
from functools import wraps

logger = logging.getLogger(__name__)
F = TypeVar('F', bound=Callable[..., Any])

# Exception classes with proper initialization
class AppException(Exception):
    """Base exception for application errors (user-facing)."""

    DEFAULT_ERROR_CODE = "APP_001"
    DEFAULT_MESSAGE = "An unexpected error occurred."
    DEFAULT_RECOVERY_HINT = ""

    def __init__(
        self,
        message: str = "",
        recovery_hint: str = "",
        error_code: str = "",
        original_error: Optional[BaseException] = None,
        details: Optional[Any] = None,
    ):
        # Backward compatibility: previous versions used (message, details)
        # and some call sites may pass details positionally.
        if details is None and original_error is None:
            if error_code and not isinstance(error_code, str):
                details = error_code
                error_code = ""
            if recovery_hint and not isinstance(recovery_hint, str):
                details = recovery_hint
                recovery_hint = ""

        self.user_message = message or self.DEFAULT_MESSAGE
        self.recovery_hint = recovery_hint or self.DEFAULT_RECOVERY_HINT
        self.error_code = error_code or self.DEFAULT_ERROR_CODE
        self.original_error = original_error
        self.details = details

        # Keep legacy attribute for older call sites.
        self.message = self.user_message

        super().__init__(self.user_message)

    def __str__(self) -> str:
        if self.error_code:
            return f"{self.user_message} (code: {self.error_code})"
        return self.user_message


class OCRInitializationError(AppException):
    """OCR engine initialization failed"""

    DEFAULT_ERROR_CODE = "OCR_001"
    DEFAULT_MESSAGE = "OCR initialization failed."
    DEFAULT_RECOVERY_HINT = (
        "Install Tesseract OCR:\n"
        "Windows: winget install UB-Mannheim.TesseractOCR\n"
        "macOS: brew install tesseract tesseract-lang\n"
        "Linux: sudo apt install tesseract-ocr tesseract-ocr-kor tesseract-ocr-chi-sim"
    )


class OCRProcessingError(AppException):
    """OCR processing failed"""

    DEFAULT_ERROR_CODE = "OCR_002"
    DEFAULT_MESSAGE = "OCR processing failed."
    DEFAULT_RECOVERY_HINT = "Try a clearer image or switch OCR engine in settings."

class VideoProcessingError(AppException):
    DEFAULT_ERROR_CODE = "VIDEO_001"
    DEFAULT_MESSAGE = "Video processing failed."
    DEFAULT_RECOVERY_HINT = "Try MP4/AVI/MOV format and verify ffmpeg is available."

class VideoNotFoundError(AppException):
    DEFAULT_ERROR_CODE = "VIDEO_002"
    DEFAULT_MESSAGE = "Video file not found."
    DEFAULT_RECOVERY_HINT = "Check the file path/URL and try again."

class APIError(AppException):
    DEFAULT_ERROR_CODE = "API_001"
    DEFAULT_MESSAGE = "API error occurred."
    DEFAULT_RECOVERY_HINT = "Check API status and try again. If it persists, rotate API keys."

class APIKeyMissingError(AppException):
    DEFAULT_ERROR_CODE = "API_002"
    DEFAULT_MESSAGE = "API key is missing."
    DEFAULT_RECOVERY_HINT = "Add an API key in Settings, then retry."

class ConfigurationError(AppException):
    DEFAULT_ERROR_CODE = "CFG_001"
    DEFAULT_MESSAGE = "Configuration error."
    DEFAULT_RECOVERY_HINT = "Verify environment variables / config files and restart the app."


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
    DEFAULT_ERROR_CODE = "DEP_001"
    DEFAULT_MESSAGE = "Missing dependency."
    DEFAULT_RECOVERY_HINT = "Install required packages and restart the app."

class TrialLimitExceededError(Exception):
    """Raised when user exceeds trial usage limit"""
    def __init__(self, message: str, remaining: int = 0, total: int = 2):
        super().__init__(message)
        self.remaining = remaining
        self.total = total


# Utilities

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


def thread_exception_handler(args):
    """threading.excepthook - 스레드에서 발생한 미처리 예외 로깅"""
    logger.error(
        "Uncaught exception in thread '%s'",
        args.thread.name if args.thread else "unknown",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def handle_errors(
    fallback_return=None,
    user_message: str = "",
    catch_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
):
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except catch_exceptions as e:  # pragma: no cover
                logger.exception(user_message or f"Error in {func.__name__}: {e}")
                return fallback_return
        return wrapper  # type: ignore
    return decorator


class ErrorContext:
    """Context manager that wraps exceptions into a typed AppException."""

    def __init__(
        self,
        operation: str,
        error_class: Type[AppException] = AppException,
        user_message: str = "",
        recovery_hint: str = "",
        error_code: str = "",
    ):
        self.operation = operation
        self.error_class = error_class
        self.user_message = user_message
        self.recovery_hint = recovery_hint
        self.error_code = error_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            return False

        msg = self.user_message or f"{self.operation} failed"
        logger.exception(f"[{self.operation}] {exc}")
        raise self.error_class(
            message=msg,
            recovery_hint=self.recovery_hint,
            error_code=self.error_code,
            original_error=exc,
        ) from exc


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
    "ErrorContext",
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
