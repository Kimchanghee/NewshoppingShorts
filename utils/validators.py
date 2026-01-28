"""
Input Validation Module

This module provides comprehensive validation for user inputs, file paths, and API responses.
Prevents security vulnerabilities such as path traversal, injection attacks, and malformed data.

Usage:
    from utils.validators import PathValidator, APIValidator, ValidationError

    # Validate video path
    try:
        safe_path = PathValidator.validate_video_path(user_input)
    except ValidationError as e:
        print(f"Invalid path: {e}")

    # Validate API response
    response_data = APIValidator.validate_gemini_response(api_response)
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import mimetypes


class ValidationError(Exception):
    """
    Exception raised when validation fails.

    This is the base exception for all validation errors in the application.
    """

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        """
        Initialize validation error.

        Args:
            message: Human-readable error message
            field: Field name that failed validation (optional)
            value: Value that failed validation (optional, for logging)
        """
        self.message = message
        self.field = field
        self.value = value
        super().__init__(message)

    def __str__(self) -> str:
        if self.field:
            return f"Validation failed for '{self.field}': {self.message}"
        return self.message


class PathValidator:
    """
    Validator for file and directory paths.

    Prevents path traversal attacks, validates file extensions,
    and ensures files/directories exist and are accessible.
    """

    # Allowed video file extensions (whitelist)
    ALLOWED_VIDEO_EXTENSIONS: Set[str] = {
        '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv',
        '.m4v', '.mpg', '.mpeg', '.3gp', '.webm'
    }

    # Allowed audio file extensions
    ALLOWED_AUDIO_EXTENSIONS: Set[str] = {
        '.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'
    }

    # Allowed image file extensions
    ALLOWED_IMAGE_EXTENSIONS: Set[str] = {
        '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff'
    }

    # Forbidden file extensions (executables, scripts)
    FORBIDDEN_EXTENSIONS: Set[str] = {
        '.exe', '.bat', '.cmd', '.sh', '.ps1', '.vbs',
        '.js', '.jar', '.msi', '.app', '.deb', '.rpm'
    }

    # Maximum path length (Windows limit)
    MAX_PATH_LENGTH = 260

    @staticmethod
    def validate_video_path(path: str, must_exist: bool = True) -> Path:
        """
        Validate video file path.

        Checks for:
        - Path traversal attacks
        - Valid video file extension
        - File existence (optional)
        - File readability

        Args:
            path: Path to validate
            must_exist: If True, file must exist (default: True)

        Returns:
            Validated Path object (absolute, resolved)

        Raises:
            ValidationError: If path is invalid or unsafe

        Example:
            >>> safe_path = PathValidator.validate_video_path("/videos/sample.mp4")
            >>> print(safe_path.name)
            sample.mp4
        """
        return PathValidator._validate_file_path(
            path,
            allowed_extensions=PathValidator.ALLOWED_VIDEO_EXTENSIONS,
            file_type="video",
            must_exist=must_exist
        )

    @staticmethod
    def validate_audio_path(path: str, must_exist: bool = True) -> Path:
        """
        Validate audio file path.

        Args:
            path: Path to validate
            must_exist: If True, file must exist

        Returns:
            Validated Path object

        Raises:
            ValidationError: If path is invalid
        """
        return PathValidator._validate_file_path(
            path,
            allowed_extensions=PathValidator.ALLOWED_AUDIO_EXTENSIONS,
            file_type="audio",
            must_exist=must_exist
        )

    @staticmethod
    def validate_image_path(path: str, must_exist: bool = True) -> Path:
        """
        Validate image file path.

        Args:
            path: Path to validate
            must_exist: If True, file must exist

        Returns:
            Validated Path object

        Raises:
            ValidationError: If path is invalid
        """
        return PathValidator._validate_file_path(
            path,
            allowed_extensions=PathValidator.ALLOWED_IMAGE_EXTENSIONS,
            file_type="image",
            must_exist=must_exist
        )

    @staticmethod
    def validate_directory(path: str, must_exist: bool = True, create_if_missing: bool = False) -> Path:
        """
        Validate directory path.

        Args:
            path: Directory path to validate
            must_exist: If True, directory must exist
            create_if_missing: If True, create directory if it doesn't exist

        Returns:
            Validated Path object

        Raises:
            ValidationError: If path is invalid

        Example:
            >>> output_dir = PathValidator.validate_directory(
            ...     "/output",
            ...     must_exist=False,
            ...     create_if_missing=True
            ... )
        """
        if not path:
            raise ValidationError("Directory path is empty", field="directory_path")

        try:
            resolved_path = Path(path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid directory path: {e}", field="directory_path", value=path)

        # Check for path traversal
        PathValidator._check_path_traversal(resolved_path, path)

        # Check path length
        if len(str(resolved_path)) > PathValidator.MAX_PATH_LENGTH:
            raise ValidationError(
                f"Path too long (max {PathValidator.MAX_PATH_LENGTH} characters)",
                field="directory_path"
            )

        # Create if requested
        if create_if_missing and not resolved_path.exists():
            try:
                resolved_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValidationError(f"Cannot create directory: {e}", field="directory_path")

        # Check existence
        if must_exist and not resolved_path.exists():
            raise ValidationError(f"Directory not found: {resolved_path}", field="directory_path")

        # Verify it's a directory
        if resolved_path.exists() and not resolved_path.is_dir():
            raise ValidationError(f"Path is not a directory: {resolved_path}", field="directory_path")

        # Check write permissions if exists
        if resolved_path.exists():
            if not os.access(resolved_path, os.W_OK):
                raise ValidationError(f"Directory not writable: {resolved_path}", field="directory_path")

        return resolved_path

    @staticmethod
    def _validate_file_path(
        path: str,
        allowed_extensions: Set[str],
        file_type: str,
        must_exist: bool
    ) -> Path:
        """
        Internal method for validating file paths.

        Args:
            path: Path to validate
            allowed_extensions: Set of allowed extensions
            file_type: Type description (for error messages)
            must_exist: Whether file must exist

        Returns:
            Validated Path object

        Raises:
            ValidationError: If path is invalid
        """
        if not path:
            raise ValidationError(f"{file_type.capitalize()} path is empty", field="file_path")

        # Basic path validation
        try:
            resolved_path = Path(path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid path: {e}", field="file_path", value=path)

        # Check for path traversal
        PathValidator._check_path_traversal(resolved_path, path)

        # Check path length
        if len(str(resolved_path)) > PathValidator.MAX_PATH_LENGTH:
            raise ValidationError(
                f"Path too long (max {PathValidator.MAX_PATH_LENGTH} characters)",
                field="file_path"
            )

        # Check extension
        extension = resolved_path.suffix.lower()

        # Block forbidden extensions
        if extension in PathValidator.FORBIDDEN_EXTENSIONS:
            raise ValidationError(
                f"Forbidden file type: {extension}",
                field="file_path",
                value=extension
            )

        # Check allowed extensions
        if extension not in allowed_extensions:
            allowed_str = ', '.join(sorted(allowed_extensions))
            raise ValidationError(
                f"Invalid {file_type} format: {extension}. Allowed: {allowed_str}",
                field="file_path",
                value=extension
            )

        # Check existence
        if must_exist:
            if not resolved_path.exists():
                raise ValidationError(f"File not found: {resolved_path}", field="file_path")

            # Verify it's a file (not directory)
            if not resolved_path.is_file():
                raise ValidationError(f"Path is not a file: {resolved_path}", field="file_path")

            # Check readability
            if not os.access(resolved_path, os.R_OK):
                raise ValidationError(f"File not readable: {resolved_path}", field="file_path")

            # Check file size (must be > 0)
            if resolved_path.stat().st_size == 0:
                raise ValidationError(f"File is empty: {resolved_path}", field="file_path")

        return resolved_path

    @staticmethod
    def _check_path_traversal(resolved_path: Path, original_path: str):
        """
        Check for path traversal attempts.

        Args:
            resolved_path: Resolved absolute path
            original_path: Original user-provided path

        Raises:
            ValidationError: If path traversal detected
        """
        # Check for ".." in path components
        if ".." in resolved_path.parts:
            raise ValidationError(
                "Path traversal detected (contains ..)",
                field="file_path",
                value=original_path
            )

        # Check for absolute path pointing outside expected directories
        # (This is application-specific, can be customized)
        dangerous_dirs = ['/etc', '/sys', '/proc', 'C:\\Windows', 'C:\\System32']
        for dangerous_dir in dangerous_dirs:
            try:
                if resolved_path.is_relative_to(dangerous_dir):
                    raise ValidationError(
                        f"Access to system directory forbidden: {dangerous_dir}",
                        field="file_path"
                    )
            except (ValueError, AttributeError):
                # is_relative_to not available in older Python versions
                if str(resolved_path).startswith(dangerous_dir):
                    raise ValidationError(
                        f"Access to system directory forbidden: {dangerous_dir}",
                        field="file_path"
                    )

    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        """
        Sanitize filename by removing dangerous characters.

        Args:
            filename: Original filename
            max_length: Maximum filename length (default: 255)

        Returns:
            Sanitized filename

        Example:
            >>> PathValidator.sanitize_filename("video<>file.mp4")
            'video__file.mp4'
        """
        if not filename:
            return "unnamed"

        # Remove path separators
        filename = filename.replace('/', '_').replace('\\', '_')

        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*\x00-\x1f]', '_', filename)

        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')

        # Ensure not empty after sanitization
        if not filename:
            filename = "unnamed"

        # Truncate to max length
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            filename = name[:max_length - len(ext)] + ext

        return filename


class APIValidator:
    """
    Validator for API responses and data structures.

    Ensures API responses conform to expected schemas and contain valid data.
    """

    @staticmethod
    def validate_gemini_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Gemini API response structure.

        Args:
            response: API response dict

        Returns:
            Validated response dict

        Raises:
            ValidationError: If response is malformed

        Example:
            >>> response = {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
            >>> validated = APIValidator.validate_gemini_response(response)
        """
        if not isinstance(response, dict):
            raise ValidationError("API response must be a dictionary", field="api_response")

        # Check for error field
        if "error" in response:
            error_msg = response.get("error", {}).get("message", "Unknown error")
            raise ValidationError(f"API error: {error_msg}", field="api_response")

        # Validate structure (basic check)
        if "candidates" in response:
            candidates = response.get("candidates")
            if not isinstance(candidates, list):
                raise ValidationError("Invalid response: 'candidates' must be a list", field="api_response")

        return response

    @staticmethod
    def validate_api_key(api_key: str, key_name: str = "API key") -> str:
        """
        Validate API key format.

        Args:
            api_key: API key string
            key_name: Name of the key (for error messages)

        Returns:
            Validated API key

        Raises:
            ValidationError: If API key is invalid
        """
        if not api_key:
            raise ValidationError(f"{key_name} is empty", field="api_key")

        if not isinstance(api_key, str):
            raise ValidationError(f"{key_name} must be a string", field="api_key")

        # Check minimum length
        if len(api_key) < 10:
            raise ValidationError(f"{key_name} is too short (minimum 10 characters)", field="api_key")

        # Check for whitespace
        if api_key != api_key.strip():
            raise ValidationError(f"{key_name} contains leading/trailing whitespace", field="api_key")

        return api_key

    @staticmethod
    def validate_url(url: str, allowed_schemes: Optional[Set[str]] = None) -> str:
        """
        Validate URL format and scheme.

        Args:
            url: URL string to validate
            allowed_schemes: Set of allowed URL schemes (default: {'http', 'https'})

        Returns:
            Validated URL string

        Raises:
            ValidationError: If URL is invalid

        Example:
            >>> url = APIValidator.validate_url("https://example.com/api")
        """
        from urllib.parse import urlparse

        if not url:
            raise ValidationError("URL is empty", field="url")

        if allowed_schemes is None:
            allowed_schemes = {'http', 'https'}

        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValidationError(f"Invalid URL: {e}", field="url", value=url)

        # Check scheme
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(
                f"Invalid URL scheme: {parsed.scheme}. Allowed: {', '.join(allowed_schemes)}",
                field="url"
            )

        # Check netloc (domain)
        if not parsed.netloc:
            raise ValidationError("URL missing domain", field="url")

        return url


class TextValidator:
    """
    Validator for text inputs.

    Prevents injection attacks and validates text format.
    """

    @staticmethod
    def validate_text_length(text: str, min_length: int = 0, max_length: int = 10000) -> str:
        """
        Validate text length.

        Args:
            text: Text to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length

        Returns:
            Validated text

        Raises:
            ValidationError: If text length is invalid
        """
        if not isinstance(text, str):
            raise ValidationError("Text must be a string", field="text")

        if len(text) < min_length:
            raise ValidationError(
                f"Text too short (minimum {min_length} characters)",
                field="text"
            )

        if len(text) > max_length:
            raise ValidationError(
                f"Text too long (maximum {max_length} characters)",
                field="text"
            )

        return text

    @staticmethod
    def sanitize_sql(text: str) -> str:
        """
        Basic SQL injection prevention (paranoid mode).

        Note: This is NOT a replacement for parameterized queries.
        Always use parameterized queries for database operations.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text

        Raises:
            ValidationError: If SQL keywords detected
        """
        dangerous_patterns = [
            r'\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|EXEC|UNION)\b',
            r'--',
            r'/\*',
            r'\*/',
            r';',
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                raise ValidationError(
                    "Potential SQL injection detected",
                    field="text",
                    value=text[:50]  # Log only first 50 chars
                )

        return text


# Convenience validation functions for common use cases
# 일반적인 사용 사례를 위한 편의 검증 함수

def validate_url(url: str) -> bool:
    """
    Validate URL format (convenience wrapper).
    URL 형식 검증 (편의 래퍼).

    Args:
        url: URL string

    Returns:
        True if valid, False otherwise
    """
    try:
        APIValidator.validate_url(url)
        return True
    except ValidationError:
        return False


def validate_user_id(user_id: str) -> bool:
    """
    Validate user ID format.
    사용자 ID 형식 검증.

    Args:
        user_id: User ID string

    Returns:
        True if valid, False otherwise

    Rules:
        - Not empty
        - Length between 3-50 characters
        - Alphanumeric, underscore, dash, dot, @ allowed
        - No SQL injection patterns
    """
    if not user_id or not isinstance(user_id, str):
        return False

    # Length check
    if not (3 <= len(user_id) <= 50):
        return False

    # Character whitelist
    # Allows: alphanumeric, underscore, dash, dot, @
    if not re.match(r'^[a-zA-Z0-9_\-\.@]+$', user_id):
        return False

    # SQL injection check
    try:
        TextValidator.sanitize_sql(user_id)
    except ValidationError:
        return False

    return True


def validate_ip_address(ip: str) -> bool:
    """
    Validate IP address format (IPv4 or IPv6).
    IP 주소 형식 검증 (IPv4 또는 IPv6).

    Args:
        ip: IP address string

    Returns:
        True if valid, False otherwise
    """
    if not ip or not isinstance(ip, str):
        return False

    # IPv4 validation
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, ip):
        # Check each octet is 0-255
        octets = ip.split('.')
        try:
            return all(0 <= int(octet) <= 255 for octet in octets)
        except ValueError:
            return False

    # IPv6 validation (basic)
    ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){7}[0-9a-fA-F]{0,4}$'
    if re.match(ipv6_pattern, ip):
        return True

    # IPv6 compressed format
    if '::' in ip:
        # Basic IPv6 compressed validation
        parts = ip.split('::')
        if len(parts) == 2:
            return True

    return False
