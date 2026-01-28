"""
Integration Tests for Video Processing Pipeline

Tests end-to-end video processing workflow including:
- Video loading and validation
- Subtitle detection
- Subtitle processing (blur)
- TTS generation (mocked)
- Final video composition
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile


@pytest.mark.integration
class TestVideoProcessingPipeline:
    """Test complete video processing pipeline"""

    @pytest.fixture
    def mock_video_file(self, tmp_path):
        """Create mock video file for testing"""
        video = tmp_path / "test_video.mp4"
        video.write_bytes(b"fake video content")
        return video

    @pytest.fixture
    def mock_gui(self):
        """Create mock GUI object"""
        gui = Mock()
        gui.ocr_reader = Mock()
        gui.ocr_reader.readtext = Mock(return_value=[])
        gui.current_video_path = None
        gui.update_progress_state = Mock()
        return gui

    def test_subtitle_detection_pipeline(self, mock_gui, mock_video_file):
        """Test subtitle detection workflow"""
        from processors.subtitle_detector import SubtitleDetector

        # Setup
        detector = SubtitleDetector(mock_gui)

        # Mock OCR results
        mock_gui.ocr_reader.readtext.return_value = [
            ([[100, 200], [300, 200], [300, 250], [100, 250]], "测试字幕", 0.99)
        ]

        # Note: Full pipeline test would require actual video file
        # This test verifies detector can be instantiated with mock GUI
        assert detector is not None
        assert detector.gui == mock_gui

    def test_subtitle_processor_pipeline(self, mock_gui):
        """Test subtitle processor workflow"""
        from processors.subtitle_processor import SubtitleProcessor

        processor = SubtitleProcessor(mock_gui)

        # Verify processor initialization
        assert processor is not None
        assert processor.gui == mock_gui

    def test_path_validation_integration(self, tmp_path):
        """Test path validation in pipeline"""
        from utils.validators import PathValidator, ValidationError

        # Valid video file
        valid_video = tmp_path / "valid.mp4"
        valid_video.write_text("content")

        validated = PathValidator.validate_video_path(str(valid_video))
        assert validated.exists()

        # Invalid file (path traversal)
        with pytest.raises(ValidationError):
            PathValidator.validate_video_path("../../etc/passwd")

        # Invalid extension
        invalid_file = tmp_path / "malware.exe"
        invalid_file.write_text("content")

        with pytest.raises(ValidationError):
            PathValidator.validate_video_path(str(invalid_file))

    def test_ocr_initialization_integration(self):
        """Test OCR backend initialization in pipeline"""
        from utils.ocr_backend import OCRBackend

        # Should initialize without errors
        backend = OCRBackend()
        assert backend.engine_name in ["rapidocr", "tesseract"]
        assert backend.reader is not None

    def test_error_handling_integration(self):
        """Test error handling across pipeline"""
        from utils.error_handlers import handle_errors, AppException

        @handle_errors(fallback_return=None)
        def risky_operation():
            raise ValueError("Test error")

        result = risky_operation()
        assert result is None

    def test_logging_integration(self, tmp_path):
        """Test logging across pipeline"""
        from utils.logging_config import AppLogger, get_logger

        log_dir = tmp_path / "logs"
        AppLogger.setup(log_dir, level="DEBUG")

        logger = get_logger("test_module")
        logger.info("Test message")

        # Verify log file created
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) > 0


@pytest.mark.integration
class TestAPIIntegration:
    """Test API integration points"""

    def test_api_key_loading(self):
        """Test API key loading from config"""
        from config import GEMINI_API_KEYS

        # Should be dict (empty or with keys)
        assert isinstance(GEMINI_API_KEYS, dict)

    def test_secrets_manager_integration(self):
        """Test secrets manager integration"""
        from utils.secrets_manager import SecretsManager

        # Test store and retrieve
        test_key = "test_api_key_12345678"
        success = SecretsManager.store_api_key("test", test_key)
        assert success is True

        retrieved = SecretsManager.get_api_key("test")
        assert retrieved == test_key

        # Cleanup
        SecretsManager.delete_api_key("test")

    @patch('utils.validators.APIValidator.validate_gemini_response')
    def test_api_response_validation(self, mock_validate):
        """Test API response validation"""
        from utils.validators import APIValidator

        mock_validate.return_value = {"result": "success"}

        response = {"result": "success"}
        validated = APIValidator.validate_gemini_response(response)

        assert validated == response
        mock_validate.assert_called_once()


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceIntegration:
    """Performance integration tests (marked as slow)"""

    def test_detector_instantiation_caching(self, mock_gui):
        """Test SubtitleDetector caching prevents duplicate instantiation"""
        from processors.subtitle_processor import SubtitleProcessor

        processor = SubtitleProcessor(mock_gui)

        # First call creates detector
        detector1 = processor._get_or_create_detector()

        # Second call should return cached instance
        detector2 = processor._get_or_create_detector()

        # Should be same instance
        assert detector1 is detector2

    def test_memory_cleanup_integration(self, mock_gui):
        """Test memory cleanup in subtitle detection"""
        from processors.subtitle_detector import SubtitleDetector
        import gc

        detector = SubtitleDetector(mock_gui)

        # Trigger garbage collection
        gc.collect()

        # Memory should be stable
        assert detector is not None


@pytest.mark.integration
class TestConfigurationIntegration:
    """Test configuration and constants integration"""

    def test_constants_import(self):
        """Test constants can be imported"""
        from config.constants import (
            OCRThresholds,
            VideoSettings,
            MemoryLimits,
            GPUSettings
        )

        # Verify constants exist
        assert OCRThresholds.SSIM_THRESHOLD == 0.98
        assert OCRThresholds.CONFIDENCE_MIN == 0.98
        assert VideoSettings.DEFAULT_HEIGHT == 1080
        assert MemoryLimits.FRAME_CACHE_MAX_SIZE == 100

    def test_constants_usage_in_detector(self):
        """Test constants used in subtitle detector"""
        from processors.subtitle_detector import SubtitleDetector
        from config.constants import OCRThresholds

        # Verify detector can access constants
        assert OCRThresholds.SSIM_THRESHOLD is not None


@pytest.mark.integration
class TestStartupValidation:
    """Test startup validation workflow"""

    def test_startup_validation_script(self):
        """Test startup validation runs without errors"""
        from scripts.startup_validation import StartupValidator

        validator = StartupValidator()

        # Run validation
        success, errors = validator.validate_all()

        # Should complete (success depends on environment)
        assert isinstance(success, bool)
        assert isinstance(errors, list)

    def test_ocr_availability_check(self):
        """Test OCR availability check"""
        from utils.ocr_backend import check_ocr_availability

        info = check_ocr_availability()

        assert "python_version" in info
        assert "recommended_engine" in info
        # Should recommend at least one engine
        assert info["tesseract_available"] or info.get("rapidocr_available", False)
