"""
Unit Tests for Input Validators

Tests path validation, API validation, and input sanitization.
"""

import pytest
from pathlib import Path
from utils.validators import PathValidator, APIValidator, ValidationError


class TestPathValidator:
    """Test path validation functionality"""

    def test_validate_video_path_success(self, tmp_path):
        """Test validation accepts valid video paths"""
        # Create temporary video file
        video = tmp_path / "test.mp4"
        video.write_text("dummy video content")

        # Should succeed
        result = PathValidator.validate_video_path(str(video))
        assert result == video.resolve()

    def test_path_traversal_blocked(self):
        """Test path traversal attacks are blocked"""
        with pytest.raises(ValidationError, match="traversal"):
            PathValidator.validate_video_path("../../etc/passwd")

    def test_invalid_extension_blocked(self, tmp_path):
        """Test non-video extensions are rejected"""
        malware = tmp_path / "malware.exe"
        malware.write_text("dummy")

        with pytest.raises(ValidationError, match="Forbidden file type"):
            PathValidator.validate_video_path(str(malware))

    def test_nonexistent_file(self):
        """Test nonexistent files are rejected"""
        with pytest.raises(ValidationError, match="not found"):
            PathValidator.validate_video_path("/nonexistent/video.mp4")

    def test_sanitize_filename(self):
        """Test filename sanitization"""
        # Dangerous characters should be replaced
        result = PathValidator.sanitize_filename("video<>file.mp4")
        assert "<" not in result
        assert ">" not in result
        assert result == "video__file.mp4"

    def test_validate_directory_success(self, tmp_path):
        """Test directory validation"""
        test_dir = tmp_path / "output"
        result = PathValidator.validate_directory(str(test_dir), must_exist=False, create_if_missing=True)
        assert result.exists()
        assert result.is_dir()


class TestAPIValidator:
    """Test API validation functionality"""

    def test_validate_api_key_success(self):
        """Test valid API key passes validation"""
        key = "sk-proj-1234567890abcdef"
        result = APIValidator.validate_api_key(key)
        assert result == key

    def test_validate_api_key_empty(self):
        """Test empty API key is rejected"""
        with pytest.raises(ValidationError, match="empty"):
            APIValidator.validate_api_key("")

    def test_validate_api_key_too_short(self):
        """Test short API key is rejected"""
        with pytest.raises(ValidationError, match="too short"):
            APIValidator.validate_api_key("short")

    def test_validate_url_success(self):
        """Test valid URL passes validation"""
        url = "https://example.com/api"
        result = APIValidator.validate_url(url)
        assert result == url

    def test_validate_url_invalid_scheme(self):
        """Test invalid URL scheme is rejected"""
        with pytest.raises(ValidationError, match="Invalid URL scheme"):
            APIValidator.validate_url("ftp://example.com")

    def test_validate_gemini_response_success(self):
        """Test valid Gemini response passes validation"""
        response = {
            "candidates": [
                {"content": {"parts": [{"text": "Hello"}]}}
            ]
        }
        result = APIValidator.validate_gemini_response(response)
        assert result == response

    def test_validate_gemini_response_error(self):
        """Test Gemini response with error is rejected"""
        response = {
            "error": {"message": "API quota exceeded"}
        }
        with pytest.raises(ValidationError, match="API error"):
            APIValidator.validate_gemini_response(response)


class TestTextValidator:
    """Test text validation functionality"""

    def test_validate_text_length_success(self):
        """Test valid text length passes validation"""
        from utils.validators import TextValidator
        text = "Valid text"
        result = TextValidator.validate_text_length(text, min_length=5, max_length=100)
        assert result == text

    def test_validate_text_too_short(self):
        """Test text that is too short is rejected"""
        from utils.validators import TextValidator
        with pytest.raises(ValidationError, match="too short"):
            TextValidator.validate_text_length("Hi", min_length=10)

    def test_validate_text_too_long(self):
        """Test text that is too long is rejected"""
        from utils.validators import TextValidator
        long_text = "a" * 1000
        with pytest.raises(ValidationError, match="too long"):
            TextValidator.validate_text_length(long_text, max_length=100)

    def test_sanitize_sql_blocks_injection(self):
        """Test SQL injection patterns are detected"""
        from utils.validators import TextValidator
        with pytest.raises(ValidationError, match="SQL injection"):
            TextValidator.sanitize_sql("'; DROP TABLE users; --")
