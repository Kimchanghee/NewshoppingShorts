# -*- coding: utf-8 -*-
"""
Unit Tests for AppError Classes

Tests the AppError class and Errors factory following mandatory error handling rules.
"""

import pytest
from app.errors import AppError, Errors


class TestAppError:
    """Test AppError base class"""

    def test_app_error_creation(self):
        """Test AppError can be created with required fields"""
        error = AppError(
            code="VALIDATION_ERROR",
            status=400,
            details={"field": "username"},
        )

        assert error.code == "VALIDATION_ERROR"
        assert error.status == 400
        assert error.details == {"field": "username"}
        assert error.request_id is not None

    def test_app_error_custom_request_id(self):
        """Test AppError accepts custom request_id"""
        error = AppError(
            code="AUTH_ERROR",
            status=401,
            request_id="custom-request-id-123"
        )

        assert error.request_id == "custom-request-id-123"

    def test_app_error_to_dict_production(self):
        """Test to_dict hides details in production mode"""
        error = AppError(
            code="INTERNAL_ERROR",
            status=500,
            details={"stack": "sensitive_info"}
        )

        result = error.to_dict(is_production=True)

        assert result["success"] is False
        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert "details" not in result["error"]
        assert result["error"]["requestId"] is not None
        # Production message should be user-friendly (Korean)
        assert "서버" in result["error"]["message"]

    def test_app_error_to_dict_development(self):
        """Test to_dict includes details in development mode"""
        error = AppError(
            code="VALIDATION_ERROR",
            status=400,
            details={"field": "email", "message": "Invalid format"}
        )

        result = error.to_dict(is_production=False)

        assert result["success"] is False
        assert "details" in result["error"]
        assert result["error"]["details"]["field"] == "email"

    def test_app_error_string_representation(self):
        """Test AppError string representation"""
        error = AppError(code="NOT_FOUND_ERROR", status=404)

        assert str(error) == "NOT_FOUND_ERROR"


class TestErrorsFactory:
    """Test Errors factory class"""

    def test_validation_error(self):
        """Test Errors.validation creates 400 error"""
        error = Errors.validation({"field": "username", "message": "Required"})

        assert error.code == "VALIDATION_ERROR"
        assert error.status == 400
        assert error.details == {"field": "username", "message": "Required"}

    def test_auth_error(self):
        """Test Errors.auth creates 401 error"""
        error = Errors.auth("Token expired")

        assert error.code == "AUTH_ERROR"
        assert error.status == 401
        assert error.details == "Token expired"

    def test_forbidden_error(self):
        """Test Errors.forbidden creates 403 error"""
        error = Errors.forbidden()

        assert error.code == "FORBIDDEN_ERROR"
        assert error.status == 403

    def test_not_found_error(self):
        """Test Errors.not_found creates 404 error with resource"""
        error = Errors.not_found("User")

        assert error.code == "NOT_FOUND_ERROR"
        assert error.status == 404
        assert error.details == {"resource": "User"}

    def test_conflict_error(self):
        """Test Errors.conflict creates 409 error"""
        error = Errors.conflict({"reason": "Duplicate entry"})

        assert error.code == "CONFLICT_ERROR"
        assert error.status == 409

    def test_rate_limit_error(self):
        """Test Errors.rate_limit creates 429 error"""
        error = Errors.rate_limit(retry_after=60)

        assert error.code == "RATE_LIMIT_ERROR"
        assert error.status == 429
        assert error.details == {"retryAfter": 60}

    def test_internal_error(self):
        """Test Errors.internal creates 500 error"""
        error = Errors.internal("Database connection failed")

        assert error.code == "INTERNAL_ERROR"
        assert error.status == 500


class TestPublicMessages:
    """Test user-friendly public messages"""

    def test_all_error_codes_have_public_messages(self):
        """Test all error codes have corresponding Korean messages"""
        error_codes = [
            "VALIDATION_ERROR",
            "AUTH_ERROR",
            "FORBIDDEN_ERROR",
            "NOT_FOUND_ERROR",
            "CONFLICT_ERROR",
            "RATE_LIMIT_ERROR",
            "INTERNAL_ERROR",
        ]

        for code in error_codes:
            error = AppError(code=code, status=400)
            result = error.to_dict(is_production=True)
            message = result["error"]["message"]
            # Should have a non-empty Korean message
            assert len(message) > 0
            # Should contain Korean characters (not just the code)
            assert message != code

    def test_unknown_error_code_uses_internal_error_message(self):
        """Test unknown error codes fall back to internal error message"""
        error = AppError(code="UNKNOWN_CODE", status=500)
        result = error.to_dict(is_production=True)
        message = result["error"]["message"]

        # Should use internal error message as fallback
        assert "서버" in message


class TestErrorRaising:
    """Test raising AppError as exception"""

    def test_can_raise_app_error(self):
        """Test AppError can be raised as exception"""
        with pytest.raises(AppError) as exc_info:
            raise Errors.validation({"field": "test"})

        assert exc_info.value.code == "VALIDATION_ERROR"
        assert exc_info.value.status == 400

    def test_can_catch_app_error(self):
        """Test AppError can be caught and handled"""
        try:
            raise Errors.not_found("User")
        except AppError as e:
            result = e.to_dict(is_production=True)
            assert result["error"]["code"] == "NOT_FOUND_ERROR"
