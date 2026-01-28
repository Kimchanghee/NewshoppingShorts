"""
Unit Tests for Error Handlers

Tests custom exceptions, error decorators, and error context managers.
"""

import pytest
from utils.error_handlers import (
    AppException,
    OCRInitializationError,
    VideoProcessingError,
    APIError,
    ConfigurationError,
    handle_errors,
    ErrorContext,
)


class TestAppException:
    """Test base AppException class"""

    def test_app_exception_creation(self):
        """Test AppException can be created with message and hint"""
        exc = AppException(
            message="Test error",
            recovery_hint="Try this fix",
            error_code="TEST_001"
        )

        assert exc.user_message == "Test error"
        assert exc.recovery_hint == "Try this fix"
        assert exc.error_code == "TEST_001"

    def test_app_exception_str(self):
        """Test AppException string representation"""
        exc = AppException(
            message="Test error",
            recovery_hint="Try this fix"
        )

        error_str = str(exc)
        assert "Test error" in error_str

    def test_app_exception_with_original_error(self):
        """Test AppException wraps original exception"""
        original = ValueError("Original error")
        exc = AppException(
            message="Wrapped error",
            recovery_hint="Fix it",
            original_error=original
        )

        assert exc.original_error == original


class TestOCRInitializationError:
    """Test OCRInitializationError exception"""

    def test_ocr_error_default_message(self):
        """Test OCR error has default message"""
        exc = OCRInitializationError()

        assert "OCR" in exc.user_message
        assert "Tesseract" in exc.recovery_hint
        assert exc.error_code == "OCR_001"

    def test_ocr_error_custom_message(self):
        """Test OCR error with custom message"""
        exc = OCRInitializationError(
            message="Custom OCR error",
            recovery_hint="Custom fix"
        )

        assert exc.user_message == "Custom OCR error"
        assert exc.recovery_hint == "Custom fix"


class TestVideoProcessingError:
    """Test VideoProcessingError exception"""

    def test_video_error_types(self):
        """Test different video processing error types"""
        errors = [
            VideoProcessingError(message="Invalid format"),
            VideoProcessingError(message="Codec error"),
            VideoProcessingError(message="File not found"),
        ]

        for exc in errors:
            assert exc.error_code.startswith("VIDEO_")
            assert exc.recovery_hint is not None


class TestAPIError:
    """Test APIError exception"""

    def test_api_error_creation(self):
        """Test API error creation"""
        exc = APIError(
            message="API quota exceeded",
            recovery_hint="Wait or upgrade plan"
        )

        assert "API" in exc.user_message
        assert exc.error_code.startswith("API_")


class TestHandleErrorsDecorator:
    """Test handle_errors decorator"""

    def test_decorator_catches_exception(self):
        """Test decorator catches and handles exceptions"""
        @handle_errors(fallback_return=[], user_message="Operation failed")
        def failing_function():
            raise ValueError("Test error")

        result = failing_function()
        assert result == []

    def test_decorator_allows_success(self):
        """Test decorator allows successful execution"""
        @handle_errors(fallback_return=None)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_decorator_with_args(self):
        """Test decorator works with function arguments"""
        @handle_errors(fallback_return=0)
        def add_numbers(a, b):
            return a + b

        result = add_numbers(2, 3)
        assert result == 5

    def test_decorator_catches_specific_exceptions(self):
        """Test decorator catches specific exception types"""
        @handle_errors(
            catch_exceptions=(ValueError, TypeError),
            fallback_return="error"
        )
        def type_error_function():
            raise TypeError("Type error")

        result = type_error_function()
        assert result == "error"

    def test_decorator_does_not_catch_other_exceptions(self):
        """Test decorator lets other exceptions through"""
        @handle_errors(
            catch_exceptions=(ValueError,),
            fallback_return="error"
        )
        def runtime_error_function():
            raise RuntimeError("Runtime error")

        with pytest.raises(RuntimeError):
            runtime_error_function()


class TestErrorContext:
    """Test ErrorContext context manager"""

    def test_error_context_catches_exception(self):
        """Test ErrorContext catches and transforms exceptions"""
        with pytest.raises(AppException) as exc_info:
            with ErrorContext(
                operation="test operation",
                error_class=AppException,
                user_message="Operation failed",
                recovery_hint="Try again"
            ):
                raise ValueError("Original error")

        assert "Operation failed" in str(exc_info.value)
        assert exc_info.value.recovery_hint == "Try again"

    def test_error_context_allows_success(self):
        """Test ErrorContext allows successful execution"""
        result = None
        with ErrorContext(
            operation="test operation",
            error_class=AppException
        ):
            result = "success"

        assert result == "success"

    def test_error_context_wraps_original_error(self):
        """Test ErrorContext wraps original exception"""
        with pytest.raises(AppException) as exc_info:
            with ErrorContext(
                operation="test",
                error_class=AppException
            ):
                raise ValueError("Original")

        assert exc_info.value.original_error is not None
        assert isinstance(exc_info.value.original_error, ValueError)


class TestErrorRecoveryHints:
    """Test error recovery hints are helpful"""

    def test_ocr_error_has_installation_hint(self):
        """Test OCR error has installation instructions"""
        exc = OCRInitializationError()

        hint = exc.recovery_hint
        # Should mention installation method
        assert any(keyword in hint for keyword in ["install", "winget", "brew", "apt"])

    def test_video_error_has_format_hint(self):
        """Test video error has format suggestions"""
        exc = VideoProcessingError(
            message="Invalid video format",
            recovery_hint="Use MP4, AVI, or MOV format"
        )

        hint = exc.recovery_hint
        # Should mention video formats
        assert any(fmt in hint for fmt in ["MP4", "AVI", "MOV"])

    def test_api_error_has_actionable_hint(self):
        """Test API error has actionable recovery hint"""
        exc = APIError(
            message="API key invalid",
            recovery_hint="Check API key in settings"
        )

        hint = exc.recovery_hint
        # Should be actionable
        assert len(hint) > 0
        assert any(word in hint.lower() for word in ["check", "verify", "update", "set"])


class TestErrorCodes:
    """Test error codes are unique and consistent"""

    def test_error_codes_unique(self):
        """Test each error type has unique code"""
        errors = [
            OCRInitializationError(),
            VideoProcessingError(message="test"),
            APIError(message="test"),
            ConfigurationError(message="test"),
        ]

        codes = [e.error_code for e in errors]
        # All codes should be different
        assert len(codes) == len(set(codes))

    def test_error_code_format(self):
        """Test error codes follow format"""
        errors = [
            OCRInitializationError(),
            VideoProcessingError(message="test"),
            APIError(message="test"),
        ]

        for exc in errors:
            code = exc.error_code
            # Should be CATEGORY_NUMBER format
            assert "_" in code
            category, number = code.split("_")
            assert category.isupper()
            assert number.isdigit()
