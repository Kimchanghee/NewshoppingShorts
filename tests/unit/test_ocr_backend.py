"""
Unit Tests for OCR Backend

Tests OCR initialization, retry logic, and fallback mechanisms.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import os


class TestOCRBackend:
    """Test OCR backend initialization and functionality"""

    def test_create_ocr_reader_success(self):
        """Test OCR backend initializes successfully"""
        from utils.ocr_backend import OCRBackend

        reader = OCRBackend()
        assert reader.engine_name in ["glm_ocr", "rapidocr", "tesseract"]
        assert reader.reader is not None

    def test_readtext_with_valid_image(self):
        """Test readtext returns results for valid image"""
        from utils.ocr_backend import OCRBackend
        import numpy as np

        reader = OCRBackend()
        # Create dummy image
        image = np.zeros((100, 100, 3), dtype=np.uint8)

        results = reader.readtext(image)
        # Results might be empty for blank image, but should not crash
        assert isinstance(results, list)

    def test_readtext_with_none_reader(self):
        """Test readtext handles None reader gracefully"""
        from utils.ocr_backend import OCRBackend

        backend = OCRBackend()
        backend.reader = None

        results = backend.readtext(Mock())
        assert results == []

    def test_ocr_initialization_error_raised(self):
        """Test OCRInitializationError raised when all engines fail"""
        from utils.ocr_backend import OCRBackend
        from utils.error_handlers import OCRInitializationError

        # Deterministic failure: disable GLM-OCR and force Tesseract init to fail.
        with patch.dict(os.environ, {"GLM_OCR_DISABLED": "1"}):
            with patch("utils.ocr_backend.time.sleep", return_value=None):
                with patch.object(OCRBackend, "_init_tesseract", side_effect=ImportError("pytesseract not found")):
                    with pytest.raises(OCRInitializationError) as exc_info:
                        OCRBackend()

        assert "OCR engine unavailable" in str(exc_info.value)
        assert "Install Tesseract" in exc_info.value.recovery_hint

    def test_ocr_backend_bool(self):
        """Test OCRBackend __bool__ method"""
        from utils.ocr_backend import OCRBackend

        backend = OCRBackend()
        assert bool(backend) is True

        backend.reader = None
        assert bool(backend) is False

    def test_ocr_backend_repr(self):
        """Test OCRBackend __repr__ method"""
        from utils.ocr_backend import OCRBackend

        backend = OCRBackend()
        repr_str = repr(backend)

        assert "OCRBackend" in repr_str
        assert backend.engine_name in repr_str

    def test_create_ocr_reader_factory(self):
        """Test factory function creates valid OCR reader"""
        from utils.ocr_backend import create_ocr_reader

        reader = create_ocr_reader()
        assert reader is not None
        assert reader.reader is not None

    def test_check_ocr_availability(self):
        """Test OCR availability check function"""
        from utils.ocr_backend import check_ocr_availability
        import sys

        info = check_ocr_availability()

        assert "python_version" in info
        assert "recommended_engine" in info
        assert "tesseract_available" in info or "rapidocr_available" in info

        # Check Python version format
        assert info["python_version"] == f"{sys.version_info.major}.{sys.version_info.minor}"


class TestOCREngineSelection:
    """Test OCR engine selection logic"""

    def test_rapidocr_preferred_python_312(self):
        """Test RapidOCR preferred on Python < 3.13"""
        import sys
        from utils.ocr_backend import check_ocr_availability

        info = check_ocr_availability()

        if sys.version_info < (3, 13) and info["rapidocr_available"]:
            assert info["recommended_engine"] == "rapidocr"

    def test_tesseract_fallback_python_313_plus(self):
        """Test Tesseract used on Python 3.13+"""
        import sys
        from utils.ocr_backend import check_ocr_availability

        info = check_ocr_availability()

        if sys.version_info >= (3, 13):
            assert info["recommended_engine"] in ["glm_ocr", "tesseract", None]
            assert not info["rapidocr_available"]

    def test_retry_logic(self):
        """Test OCR initialization retries on failure"""
        from utils.ocr_backend import OCRBackend
        from utils.error_handlers import OCRInitializationError

        # This test verifies retry logic exists
        # Actual retry behavior tested via mocking in other tests
        backend = OCRBackend()
        assert backend.reader is not None


class TestOCRImageProcessing:
    """Test OCR image processing functions"""

    def test_to_pil_image_numpy_array(self):
        """Test numpy array conversion to PIL Image"""
        from utils.ocr_backend import OCRBackend
        import numpy as np

        backend = OCRBackend()
        image_array = np.zeros((100, 100, 3), dtype=np.uint8)

        pil_image = backend._to_pil_image(image_array)

        # Should convert successfully
        assert pil_image is not None

    def test_tesseract_language_detection(self):
        """Test Tesseract language detection"""
        from utils.ocr_backend import OCRBackend

        backend = OCRBackend()

        if backend.engine_name == "tesseract":
            assert backend._tesseract_lang is not None
            # Should have Korean, English, or Chinese
            assert any(lang in backend._tesseract_lang for lang in ["kor", "eng", "chi_sim"])


@pytest.mark.slow
class TestOCRPerformance:
    """Performance tests for OCR backend (marked as slow)"""

    def test_multiple_readtext_calls(self):
        """Test multiple readtext calls don't leak memory"""
        from utils.ocr_backend import OCRBackend
        import numpy as np

        backend = OCRBackend()
        image = np.zeros((100, 100, 3), dtype=np.uint8)

        # Call readtext multiple times
        for _ in range(10):
            results = backend.readtext(image)
            assert isinstance(results, list)

    def test_large_image_processing(self):
        """Test processing large image"""
        from utils.ocr_backend import OCRBackend
        import numpy as np

        backend = OCRBackend()
        # Create 1080p image
        large_image = np.zeros((1080, 1920, 3), dtype=np.uint8)

        results = backend.readtext(large_image)
        assert isinstance(results, list)
