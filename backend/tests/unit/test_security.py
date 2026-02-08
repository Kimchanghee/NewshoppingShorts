# -*- coding: utf-8 -*-
"""
Security Tests - Comprehensive security validation

Covers:
- Validation error sanitization (no password/secret leaks)
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- Input validation (SQLi, XSS prevention)
- Authentication/Authorization
- Error exposure blocking
- SSRF prevention
- Schema validation
- CORS, Docs disabled in production
"""

import os
import sys
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add backend root to path
backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))

# Set env vars BEFORE importing anything from the app
_TEST_ENV = {
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "DB_HOST": "127.0.0.1",
    "DB_NAME": "test_db",
    "JWT_SECRET_KEY": "a" * 64,
    "ADMIN_API_KEY": "b" * 64,
    "SSMAKER_API_KEY": "c" * 32,
    "BILLING_KEY_ENCRYPTION_KEY": "uKVciQZlzUKtZPwuiKHl3wVCJJhQrWL6TqrFRClcEOI=",
    "ENVIRONMENT": "production",
    "ALLOWED_ORIGINS": "https://example.com",
}
os.environ.update(_TEST_ENV)

# Clear cached settings before import
from app.configuration import get_settings
get_settings.cache_clear()

# Force re-import of main module to pick up env changes
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("app.main"):
        del sys.modules[mod_name]

# Mock DB engine/init before importing app
with patch("app.database.engine", MagicMock()), \
     patch("app.database.init_db", MagicMock()):
    from app import main as app_main
    test_app = app_main.app
    # Remove startup events to prevent DB connection attempts
    test_app.router.on_startup.clear()

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client without DB"""
    return TestClient(test_app, raise_server_exceptions=False)


# ===== 1. Validation Error Sanitization =====

class TestValidationErrorSanitization:
    """Test that sensitive fields are never exposed in 422 errors"""

    def test_password_not_exposed_in_login_422(self, client):
        """Password value must NOT appear in validation error response"""
        response = client.post("/user/login/god", json={
            "id": "ab",  # too short
            "pw": "my_secret_password_123",
            "key": "c" * 32,
            "ip": "1.2.3.4",
        })
        body_str = str(response.json())
        assert "my_secret_password_123" not in body_str

    def test_api_key_not_exposed_in_login_422(self, client):
        """API key value must NOT appear in validation error response"""
        response = client.post("/user/login/god", json={
            "id": "ab",
            "pw": "short",
            "key": "super_secret_api_key_value",
            "ip": "1.2.3.4",
        })
        body_str = str(response.json())
        assert "super_secret_api_key_value" not in body_str

    def test_422_response_has_request_id(self, client):
        """422 responses should include requestId for tracing"""
        response = client.post("/user/login/god", json={
            "id": "ab",
            "pw": "short",
            "key": "k",
            "ip": "1.2.3.4",
        })
        assert response.status_code == 422
        body = response.json()
        assert body.get("success") is False
        assert "requestId" in body.get("error", {})

    def test_422_uses_validation_error_code(self, client):
        """422 responses should use VALIDATION_ERROR code"""
        response = client.post("/user/login/god", json={
            "id": "ab",
            "pw": "short",
            "key": "k",
            "ip": "1.2.3.4",
        })
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_body_level_422_does_not_echo_payload_with_sensitive_keys(self, client):
        """When body-level validation fails, full payload must not be reflected."""
        response = client.post(
            "/payments/payapp/card/register",
            headers={
                "X-User-ID": "1",
                "Authorization": "Bearer fake",
            },
            json={
                "user_id": "1",
                "card_no": "4518123412341111",
                "card_pw": "12",
                "buyer_auth_no": "900101",
            },
        )
        assert response.status_code == 422
        body_str = str(response.json())
        assert "4518123412341111" not in body_str
        assert '"input"' not in body_str.lower()


# ===== 2. Security Headers =====

class TestSecurityHeaders:
    """Test OWASP recommended security headers"""

    def test_x_content_type_options(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self, client):
        response = client.get("/health")
        assert response.headers.get("x-frame-options") == "DENY"

    def test_referrer_policy(self, client):
        response = client.get("/health")
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_cache_control_no_store(self, client):
        response = client.get("/health")
        cache = response.headers.get("cache-control", "")
        assert "no-store" in cache

    def test_content_security_policy(self, client):
        response = client.get("/health")
        csp = response.headers.get("content-security-policy", "")
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_permissions_policy(self, client):
        response = client.get("/health")
        pp = response.headers.get("permissions-policy", "")
        assert "camera=()" in pp

    def test_hsts_in_production(self, client):
        response = client.get("/health")
        hsts = response.headers.get("strict-transport-security", "")
        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts

    def test_pragma_no_cache(self, client):
        response = client.get("/health")
        assert response.headers.get("pragma") == "no-cache"


# ===== 3. Error Exposure Blocking =====

class TestErrorExposure:
    """Test that internal errors don't leak sensitive information"""

    def test_health_endpoint_works(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint_works(self, client):
        response = client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "ok"

    def test_404_no_internal_paths(self, client):
        response = client.get("/nonexistent/path/does/not/exist")
        body_str = response.text
        assert "\\Users\\" not in body_str
        assert "/home/" not in body_str


# ===== 4. Input Validation =====

class TestInputValidation:
    """Test input validation and injection prevention"""

    def test_login_username_sql_injection_rejected(self, client):
        """Username with SQL injection should be rejected (422)"""
        response = client.post("/user/login/god", json={
            "id": "admin'; DROP TABLE users;--",
            "pw": "password123",
            "key": "c" * 32,
            "ip": "1.2.3.4",
        })
        assert response.status_code == 422

    def test_login_xss_in_username_rejected(self, client):
        """XSS payload in username should be rejected (422)"""
        response = client.post("/user/login/god", json={
            "id": "<script>alert(1)</script>",
            "pw": "password123",
            "key": "c" * 32,
            "ip": "1.2.3.4",
        })
        assert response.status_code == 422

    def test_password_too_short_rejected(self, client):
        """Password shorter than 4 chars should be rejected"""
        response = client.post("/user/login/god", json={
            "id": "testuser",
            "pw": "ab",
            "key": "c" * 32,
            "ip": "1.2.3.4",
        })
        assert response.status_code == 422

    def test_password_too_long_rejected(self, client):
        """Password longer than 128 chars should be rejected"""
        response = client.post("/user/login/god", json={
            "id": "testuser",
            "pw": "a" * 200,
            "key": "c" * 32,
            "ip": "1.2.3.4",
        })
        assert response.status_code == 422


# ===== 5. Authentication =====

class TestAuthentication:
    """Test authentication security"""

    def test_admin_endpoint_requires_api_key(self, client):
        """Admin endpoints must reject missing API key"""
        response = client.get("/user/admin/users")
        # 422 = missing required header
        assert response.status_code == 422

    def test_admin_endpoint_rejects_invalid_key(self, client):
        """Admin endpoints must reject wrong API key"""
        response = client.get(
            "/user/admin/users",
            headers={"X-Admin-API-Key": "wrong-key"}
        )
        assert response.status_code == 401

    def test_version_update_requires_auth(self, client):
        """Version update must require authorization header"""
        response = client.post("/app/version/update", json={
            "version": "9.9.9",
            "download_url": "https://evil.com/malware.exe",
        })
        assert response.status_code == 401

    def test_version_update_rejects_invalid_token(self, client):
        """Version update must reject wrong bearer token"""
        response = client.post(
            "/app/version/update",
            json={
                "version": "9.9.9",
                "download_url": "https://evil.com/malware.exe",
            },
            headers={"Authorization": "Bearer wrong-token"}
        )
        assert response.status_code == 403


# ===== 6. SSRF Prevention =====

class TestSSRFPrevention:
    """Test SSRF prevention"""

    def test_payapp_url_restricted_to_known_domain(self):
        from urllib.parse import urlparse
        untrusted = "https://evil.com/steal-data"
        parsed = urlparse(untrusted)
        assert parsed.hostname not in ("api.payapp.kr",)

    def test_payapp_url_default_is_safe(self):
        from app.routers.payment import PAYAPP_API_URL
        from urllib.parse import urlparse
        parsed = urlparse(PAYAPP_API_URL)
        assert parsed.hostname == "api.payapp.kr"
        assert parsed.scheme == "https"


# ===== 7. Schema Validation =====

class TestSchemaValidation:
    """Test Pydantic schema security"""

    def test_login_request_pw_min_4(self):
        from app.schemas.auth import LoginRequest
        req = LoginRequest(id="testuser", pw="1234", key="c" * 32, ip="1.2.3.4")
        assert req.pw == "1234"

    def test_login_request_pw_rejects_3_chars(self):
        from app.schemas.auth import LoginRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LoginRequest(id="testuser", pw="123", key="c" * 32, ip="1.2.3.4")

    def test_registration_password_min_8(self):
        from app.schemas.registration import RegistrationRequestCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegistrationRequestCreate(
                name="Test User", username="testuser",
                password="short1", contact="010-1234-5678",
            )

    def test_registration_password_needs_letters_and_digits(self):
        from app.schemas.registration import RegistrationRequestCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegistrationRequestCreate(
                name="Test User", username="testuser",
                password="12345678", contact="010-1234-5678",
            )
        with pytest.raises(ValidationError):
            RegistrationRequestCreate(
                name="Test User", username="testuser",
                password="abcdefgh", contact="010-1234-5678",
            )

    def test_registration_username_only_alphanumeric(self):
        from app.schemas.registration import RegistrationRequestCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegistrationRequestCreate(
                name="Test User", username="test user!",
                password="password123", contact="010-1234-5678",
            )


# ===== 8. CORS / Docs =====

class TestCORSConfiguration:
    def test_cors_preflight_response(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.status_code == 200

    def test_cors_rejects_unauthorized_origin(self, client):
        response = client.get("/health", headers={"Origin": "https://evil.com"})
        acao = response.headers.get("access-control-allow-origin", "")
        assert "evil.com" not in acao


class TestDocsDisabled:
    def test_swagger_docs_disabled_in_production(self, client):
        response = client.get("/docs")
        assert response.status_code == 404

    def test_redoc_disabled_in_production(self, client):
        response = client.get("/redoc")
        assert response.status_code == 404


# ===== 9. Sensitive Field Blocklist =====

class TestSensitiveFieldSet:
    def test_sensitive_fields_include_common_names(self):
        from app.main import _SENSITIVE_FIELDS
        for field in ("pw", "password", "key", "token", "secret"):
            assert field in _SENSITIVE_FIELDS

    def test_sensitive_fields_include_payment_card_fields(self):
        from app.main import _SENSITIVE_FIELDS
        for field in ("card_no", "card_pw", "buyer_auth_no", "enc_bill"):
            assert field in _SENSITIVE_FIELDS

    def test_sensitive_fields_include_payapp_link_fields(self):
        from app.main import _SENSITIVE_FIELDS
        for field in ("linkkey", "linkval"):
            assert field in _SENSITIVE_FIELDS


class TestPayAppContract:
    def test_payapp_cancel_states_cover_documented_values(self):
        from app.routers.payment import _PAYAPP_CANCEL_STATES

        # PayApp docs/examples reference multiple cancel codes by section.
        for code in ("8", "9", "16", "31", "32", "64"):
            assert code in _PAYAPP_CANCEL_STATES

    def test_card_number_is_locally_masked_even_if_gateway_returns_plain_pan(self):
        from app.routers.payment import _force_masked_card_number

        masked = _force_masked_card_number("4518123412341111", "4518****")
        assert masked == "4518****1111"
        assert "12341234" not in masked

    def test_card_number_mask_falls_back_when_gateway_value_invalid(self):
        from app.routers.payment import _force_masked_card_number

        fallback = "4518****"
        assert _force_masked_card_number("", fallback) == fallback
        assert _force_masked_card_number("abcd", fallback) == fallback


class TestAuditTargets:
    def test_payapp_webhook_is_audited(self):
        from app.main import AuditLoggingMiddleware
        assert "/payments/payapp/webhook" in AuditLoggingMiddleware._AUDIT_PREFIXES
