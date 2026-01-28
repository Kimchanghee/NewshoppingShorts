"""
Error Handling Framework

This module provides centralized error handling with typed exceptions,
user-friendly messages, and recovery hints.

Replaces bare except: blocks with specific exception handling throughout the codebase.

Usage:
    from utils.error_handlers import (
        AppException,
        OCRInitializationError,
        VideoProcessingError,
        handle_errors
    )

    # Define custom exception
    raise OCRInitializationError(
        message="OCR engine unavailable",
        recovery_hint="Install Tesseract: winget install UB-Mannheim.TesseractOCR"
    )

    # Use decorator for automatic error handling
    @handle_errors(fallback_return=[], user_message="Failed to process video")
    def process_video(path: str):
        # Function implementation
        pass
"""

import logging
import os
import re
import sys
import traceback
from typing import Any, Callable, Optional, TypeVar, cast
from functools import wraps

# Type variable for decorators
F = TypeVar('F', bound=Callable[..., Any])


def _is_production() -> bool:
    """
    Check if running in production environment.
    프로덕션 환경에서 실행 중인지 확인.

    Returns:
        True if production, False otherwise
    """
    env = os.environ.get('APP_ENV', '').lower()
    return env in ('production', 'prod')


def _sanitize_path(text: str) -> str:
    """
    Sanitize file paths in error messages for security.
    보안을 위해 오류 메시지에서 파일 경로를 정리.

    Removes/masks home directory and other sensitive paths.

    Args:
        text: Text containing potential file paths

    Returns:
        Text with paths sanitized
    """
    if not text:
        return text

    # Mask home directory
    home = os.path.expanduser("~")
    if home:
        text = text.replace(home, "~")

    # Mask Windows user paths
    text = re.sub(r'C:\\Users\\[^\\]+', 'C:\\Users\\***', text, flags=re.IGNORECASE)

    # Mask Linux/Mac user paths
    text = re.sub(r'/home/[^/]+', '/home/***', text)
    text = re.sub(r'/Users/[^/]+', '/Users/***', text)

    return text


class AppException(Exception):
    """
    Base exception class for all application-specific exceptions.

    Provides structured error information including:
    - User-friendly message
    - Recovery hint/suggestion
    - Original exception (if wrapped)
    - Error code (for categorization)
    """

    def __init__(
        self,
        message: str,
        recovery_hint: str = "",
        original_error: Optional[Exception] = None,
        error_code: Optional[str] = None
    ):
        """
        Initialize application exception.

        Args:
            message: User-friendly error message
            recovery_hint: Suggestion for how to resolve the error
            original_error: Original exception if this wraps another error
            error_code: Error code for categorization (e.g., "OCR_001")

        Example:
            >>> raise AppException(
            ...     message="Failed to initialize OCR",
            ...     recovery_hint="Install Tesseract OCR",
            ...     original_error=ImportError("No module named 'pytesseract'"),
            ...     error_code="OCR_001"
            ... )
        """
        self.user_message = message
        self.recovery_hint = recovery_hint
        self.original_error = original_error
        self.error_code = error_code

        # Construct full message
        full_message = message
        if error_code:
            full_message = f"[{error_code}] {full_message}"
        if recovery_hint:
            full_message += f"\n💡 {recovery_hint}"

        super().__init__(full_message)

    def get_user_message(self) -> str:
        """
        Get user-friendly error message with recovery hint.

        Returns:
            Formatted error message for display to users
        """
        msg = self.user_message
        if self.recovery_hint:
            msg += f"\n\nHow to fix:\n{self.recovery_hint}"
        return msg

    def get_technical_details(self, sanitize: bool = True) -> str:
        """
        Get technical error details for logging.
        로깅을 위한 기술적 오류 세부 정보 가져오기.

        Security: Sanitizes sensitive paths. In production, original error details
        are hidden to prevent information disclosure.
        보안: 민감한 경로를 정리합니다. 프로덕션에서는 정보 노출을 방지하기 위해
        원본 오류 세부 정보가 숨겨집니다.

        Args:
            sanitize: Whether to sanitize sensitive information (default True)

        Returns:
            Technical error information including original exception
        """
        details = f"Error: {self.user_message}"
        if self.error_code:
            details += f"\nCode: {self.error_code}"

        # In production, don't expose original error details to prevent info leakage
        # 프로덕션에서는 정보 누출 방지를 위해 원본 오류 세부 정보를 노출하지 않음
        if self.original_error:
            if _is_production():
                details += f"\nOriginal error: {type(self.original_error).__name__}"
            else:
                details += f"\nOriginal error: {type(self.original_error).__name__}: {self.original_error}"

        # Sanitize paths if requested
        if sanitize:
            details = _sanitize_path(details)

        return details


# === OCR-related exceptions ===

class OCRInitializationError(AppException):
    """
    Raised when OCR engine fails to initialize.

    This indicates that neither RapidOCR nor Tesseract could be initialized.
    """

    def __init__(
        self,
        message: str = "OCR engine failed to initialize",
        recovery_hint: str = "Install Tesseract OCR:\nWindows: winget install UB-Mannheim.TesseractOCR\nmacOS: brew install tesseract tesseract-lang\nLinux: sudo apt install tesseract-ocr",
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            recovery_hint=recovery_hint,
            original_error=original_error,
            error_code="OCR_001"
        )


class OCRProcessingError(AppException):
    """
    Raised when OCR processing fails on a specific frame/image.

    This is a non-fatal error (OCR initialized but failed on specific input).
    """

    def __init__(
        self,
        message: str = "OCR processing failed",
        recovery_hint: str = "Try preprocessing the image or using a different frame",
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            recovery_hint=recovery_hint,
            original_error=original_error,
            error_code="OCR_002"
        )


# === Video processing exceptions ===

class VideoProcessingError(AppException):
    """
    Raised when video processing fails.

    This covers video loading, decoding, encoding, or transformation errors.
    """

    def __init__(
        self,
        message: str = "Video processing failed",
        recovery_hint: str = "Check video file is not corrupted and FFmpeg is installed",
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            recovery_hint=recovery_hint,
            original_error=original_error,
            error_code="VIDEO_001"
        )


class VideoNotFoundError(AppException):
    """
    Raised when video file cannot be found.
    """

    def __init__(
        self,
        video_path: str,
        recovery_hint: str = "Verify the file path and ensure the file exists"
    ):
        super().__init__(
            message=f"Video file not found: {video_path}",
            recovery_hint=recovery_hint,
            error_code="VIDEO_002"
        )


# === API-related exceptions ===

class APIError(AppException):
    """
    Raised when API call fails.
    """

    def __init__(
        self,
        message: str = "API request failed",
        recovery_hint: str = "Check API key, internet connection, and service status",
        original_error: Optional[Exception] = None,
        status_code: Optional[int] = None
    ):
        self.status_code = status_code
        super().__init__(
            message=message,
            recovery_hint=recovery_hint,
            original_error=original_error,
            error_code=f"API_{status_code}" if status_code else "API_000"
        )


class APIKeyMissingError(AppException):
    """
    Raised when API key is not configured.
    """

    def __init__(
        self,
        api_name: str = "API",
        recovery_hint: str = "Set API key in environment variable or add via UI"
    ):
        super().__init__(
            message=f"{api_name} key not configured",
            recovery_hint=recovery_hint,
            error_code="API_KEY_001"
        )


# === Configuration exceptions ===

class ConfigurationError(AppException):
    """
    Raised when configuration is invalid or missing.
    """

    def __init__(
        self,
        message: str = "Configuration error",
        recovery_hint: str = "Check configuration file or environment variables",
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            recovery_hint=recovery_hint,
            original_error=original_error,
            error_code="CONFIG_001"
        )


# === Dependency exceptions ===

class DependencyError(AppException):
    """
    Raised when required dependency is missing or incompatible.
    """

    def __init__(
        self,
        dependency_name: str,
        recovery_hint: str = "Install missing dependency",
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=f"Required dependency '{dependency_name}' is missing or incompatible",
            recovery_hint=recovery_hint,
            original_error=original_error,
            error_code="DEP_001"
        )


# === Decorator for error handling ===

def handle_errors(
    fallback_return: Any = None,
    user_message: str = "",
    log_level: str = "ERROR",
    reraise: bool = False,
    catch_exceptions: tuple = (Exception,)
) -> Callable[[F], F]:
    """
    Decorator for consistent error handling across functions.

    This decorator:
    - Catches exceptions
    - Logs error with stack trace
    - Shows user notification (if user_message provided)
    - Returns fallback value or re-raises

    Args:
        fallback_return: Value to return if exception occurs (default: None)
        user_message: Message to show to user (empty = no notification)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        reraise: If True, re-raise exception after logging (default: False)
        catch_exceptions: Tuple of exception types to catch (default: all Exception)

    Returns:
        Decorated function

    Example:
        >>> @handle_errors(fallback_return=[], user_message="Failed to load video")
        ... def load_video(path: str) -> list:
        ...     # Function implementation
        ...     pass

        >>> @handle_errors(reraise=True)  # Log but still raise
        ... def critical_function():
        ...     pass
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)

            try:
                return func(*args, **kwargs)

            except AppException as e:
                # AppException: already has user message, just log and optionally show UI
                logger.log(
                    getattr(logging, log_level.upper(), logging.ERROR),
                    f"{func.__name__} raised AppException: {e.get_technical_details()}",
                    exc_info=True
                )

                # Show user notification if requested
                if user_message:
                    _show_user_notification(user_message, e.get_user_message())

                if reraise:
                    raise
                return fallback_return

            except catch_exceptions as e:
                # Generic exception: log with full traceback
                logger.log(
                    getattr(logging, log_level.upper(), logging.ERROR),
                    f"{func.__name__} failed: {type(e).__name__}: {e}",
                    exc_info=True
                )

                # Show user notification if requested
                if user_message:
                    _show_user_notification(user_message, str(e))

                if reraise:
                    raise
                return fallback_return

        return cast(F, wrapper)

    return decorator


def _show_user_notification(title: str, message: str):
    """
    Show error notification to user via GUI dialog or console fallback.
    GUI 대화상자 또는 콘솔 폴백을 통해 사용자에게 오류 알림 표시.

    Attempts to show notification in this order:
    1. PyQt5 QMessageBox (if Qt app is running)
    2. Tkinter messagebox (if Tk root exists)
    3. Console logging (fallback)

    Args:
        title: Notification title / 알림 제목
        message: Notification message / 알림 메시지
    """
    logger = logging.getLogger("error_handlers")

    # Try PyQt5 first (login/loading screens use PyQt5)
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app is not None:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
            logger.info(f"[USER NOTIFICATION] Shown via PyQt5: {title}")
            return
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"PyQt5 notification failed: {e}")

    # Try Tkinter (main app uses Tkinter)
    try:
        import tkinter as tk
        from tkinter import messagebox

        # Check if there's an existing Tk instance
        try:
            root = tk._default_root
            if root is not None:
                messagebox.showwarning(title, message)
                logger.info(f"[USER NOTIFICATION] Shown via Tkinter: {title}")
                return
        except Exception:
            pass
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Tkinter notification failed: {e}")

    # Fallback to console logging
    logger.error(f"[USER NOTIFICATION] {title}: {message}")


# === Context managers for error handling ===

class ErrorContext:
    """
    Context manager for handling errors in a code block.

    Usage:
        >>> with ErrorContext("Failed to process video", fallback_return=[]):
        ...     # Code that might fail
        ...     results = process_video(path)
    """

    def __init__(
        self,
        operation_name: str,
        fallback_return: Any = None,
        reraise: bool = False
    ):
        """
        Initialize error context.

        Args:
            operation_name: Name of operation (for logging)
            fallback_return: Value to return if exception occurs
            reraise: If True, re-raise after logging
        """
        self.operation_name = operation_name
        self.fallback_return = fallback_return
        self.reraise = reraise
        self.logger = logging.getLogger("error_context")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return True  # No exception

        # Log the error
        self.logger.error(
            f"{self.operation_name} failed: {exc_type.__name__}: {exc_val}",
            exc_info=(exc_type, exc_val, exc_tb)
        )

        if self.reraise:
            return False  # Re-raise exception

        return True  # Suppress exception


# === Utility functions ===

def safe_execute(
    func: Callable,
    *args,
    fallback: Any = None,
    error_message: str = "Operation failed",
    **kwargs
) -> Any:
    """
    Safely execute a function with automatic error handling.

    Args:
        func: Function to execute
        *args: Positional arguments for function
        fallback: Value to return if exception occurs
        error_message: Error message for logging
        **kwargs: Keyword arguments for function

    Returns:
        Function result or fallback value

    Example:
        >>> result = safe_execute(
        ...     risky_function,
        ...     arg1, arg2,
        ...     fallback=[],
        ...     error_message="Failed to load data"
        ... )
    """
    logger = logging.getLogger("safe_execute")

    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"{error_message}: {type(e).__name__}: {e}", exc_info=True)
        return fallback


def format_exception(exc: Exception, include_traceback: Optional[bool] = None) -> str:
    """
    Format exception for display or logging.
    표시 또는 로깅을 위한 예외 형식화.

    Security: In production, traceback is disabled by default to prevent
    information disclosure. Paths are always sanitized.
    보안: 프로덕션에서는 정보 노출 방지를 위해 기본적으로 traceback이 비활성화됩니다.
    경로는 항상 정리됩니다.

    Args:
        exc: Exception to format
        include_traceback: Whether to include full traceback
                          (defaults to False in production, True otherwise)

    Returns:
        Formatted exception string
    """
    # Default: disable traceback in production
    if include_traceback is None:
        include_traceback = not _is_production()

    if isinstance(exc, AppException):
        msg = exc.get_technical_details(sanitize=True)
    else:
        msg = f"{type(exc).__name__}: {exc}"
        msg = _sanitize_path(msg)

    if include_traceback:
        tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        # Sanitize paths in traceback
        tb = _sanitize_path(tb)
        msg += f"\n\nTraceback:\n{tb}"

    return msg
