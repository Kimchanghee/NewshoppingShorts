"""
OCR Backend Wrapper

Python 3.14+ 호환: pytesseract(Tesseract) 전용 인터페이스
Python 3.13 미만: RapidOCR 우선, Tesseract 폴백
"""

import os
import sys
import io
import shutil
import time
from typing import List, Tuple, Any, Optional

# Logging and error handling
from utils.logging_config import get_logger
from utils.error_handlers import OCRInitializationError

logger = get_logger(__name__)


def _safe_print(msg: str) -> None:
    """
    Backward compatibility function for logging.

    Deprecated: Use logger.info() instead
    Windows 콘솔에서 한글 출력 시 인코딩 오류 방지 (레거시 호환성)
    """
    logger.info(msg)


class OCRBackend:
    """
    OCR 백엔드 (Tesseract 기반, Python 3.13 미만에서는 RapidOCR 사용 가능)

    Usage:
        reader = OCRBackend()
        results = reader.readtext(image)

    Returns results in format:
        [(bbox, text, confidence), ...]
        where bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    """

    def __init__(self):
        """Initialize OCR backend (Tesseract preferred for Python 3.13+)."""
        self.engine_name = None
        self.reader = None
        self._tesseract_lang = None
        self._pytesseract = None
        self._tesseract_output = None
        self._init_backend()

    def _init_backend(self):
        """
        OCR 엔진 초기화 - Python 버전에 따라 다른 전략
        OCR 엔진 초기화 - Python version-based strategy

        Raises:
            OCRInitializationError: If all OCR engines fail to initialize
        """
        max_retries = 3
        engines = []

        # Build engine priority list based on Python version
        if sys.version_info < (3, 13):
            engines.append(("rapidocr", self._init_rapidocr))
        engines.append(("tesseract", self._init_tesseract))

        # Try each engine with retries
        for engine_name, init_func in engines:
            for attempt in range(max_retries):
                try:
                    init_func()
                    self.engine_name = engine_name
                    logger.info(f"OCR engine initialized: {engine_name}")
                    return  # Success
                except Exception as e:
                    logger.warning(
                        f"{engine_name} initialization attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(0.5)  # Wait before retry

        # All engines failed
        logger.error("All OCR engines failed to initialize")
        self._print_tesseract_install_guide()
        raise OCRInitializationError(
            message="OCR engine unavailable - no OCR backend could be initialized",
            recovery_hint="Install Tesseract OCR:\nWindows: winget install UB-Mannheim.TesseractOCR\nmacOS: brew install tesseract tesseract-lang\nLinux: sudo apt install tesseract-ocr tesseract-ocr-kor tesseract-ocr-chi-sim"
        )

    def _print_tesseract_install_guide(self):
        """Tesseract 설치 가이드 출력"""
        logger.error("=" * 60)
        logger.error("[OCR] Tesseract OCR 설치 안내")
        logger.error("=" * 60)
        if sys.platform == "win32":
            logger.error("Windows에서 Tesseract를 설치하려면:")
            logger.error("1. https://github.com/UB-Mannheim/tesseract/wiki 방문")
            logger.error("2. 최신 Windows 설치 파일(*.exe) 다운로드")
            logger.error("3. 설치 시 '추가 언어 데이터' 옵션에서 한국어(kor) 선택")
            logger.error("4. 기본 설치 경로: C:\\Program Files\\Tesseract-OCR")
            logger.error("또는 winget으로 설치:")
            logger.error("  winget install UB-Mannheim.TesseractOCR")
        elif sys.platform == "darwin":
            logger.error("macOS에서 설치:")
            logger.error("  brew install tesseract tesseract-lang")
        else:
            logger.error("Linux에서 설치:")
            logger.error("  sudo apt install tesseract-ocr tesseract-ocr-kor")
        logger.error("=" * 60)

    def _runtime_base(self) -> str:
        if getattr(sys, "frozen", False):
            return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))

    def _init_rapidocr(self):
        """RapidOCR 초기화 (Python 3.13 미만 전용)"""
        try:
            # onnxruntime 환경 설정
            self._setup_onnxruntime_environment()
            
            from rapidocr_onnxruntime import RapidOCR
            self.reader = RapidOCR()
            self._rapidocr_engine = self.reader
        except ImportError as e:
            raise ImportError(f"RapidOCR import 실패: {e!r}")
        except Exception as e:
            raise RuntimeError(f"RapidOCR 초기화 실패: {e!r}")

    def _setup_onnxruntime_environment(self):
        """onnxruntime DLL 경로 설정 (PyInstaller 대응)"""
        if sys.version_info >= (3, 13):
            return  # Python 3.13+에서는 onnxruntime 사용 안함
            
        base = self._runtime_base()
        frozen = getattr(sys, "frozen", False)
        exe_dir = os.path.dirname(sys.executable) if frozen else base

        internal_root = os.path.join(base, "_internal")
        ort_dir = os.path.join(internal_root, "onnxruntime")
        ort_capi = os.path.join(ort_dir, "capi")

        paths = [exe_dir, base, internal_root, ort_dir, ort_capi]

        try:
            import importlib.util
            spec = importlib.util.find_spec("onnxruntime")
            ort_origin = getattr(spec, "origin", None) if spec else None
            if ort_origin:
                mod_dir = os.path.dirname(ort_origin)
                capi_dir = os.path.join(mod_dir, "capi")
                paths.extend([mod_dir, capi_dir])
        except Exception:
            pass

        real_paths = [p for p in paths if p and os.path.isdir(p)]
        self._add_dll_search_paths(real_paths)

    def _add_dll_search_paths(self, paths):
        """DLL 검색 경로 추가"""
        uniq = []
        for p in paths:
            if p and os.path.isdir(p) and p not in uniq:
                uniq.append(p)
        if not uniq:
            return

        cur = os.environ.get("PATH", "")
        for p in reversed(uniq):
            if p not in cur:
                cur = p + os.pathsep + cur
        os.environ["PATH"] = cur

        if sys.platform == "win32":
            try:
                add_dll = getattr(os, "add_dll_directory", None)
                if add_dll:
                    for p in uniq:
                        try:
                            add_dll(p)
                        except Exception:
                            pass
            except Exception:
                pass

    def _find_tesseract_cmd(self) -> Optional[str]:
        """Tesseract 실행 파일 경로 찾기"""
        # 환경 변수 확인
        env_cmd = os.environ.get("TESSERACT_CMD") or os.environ.get("TESSERACT_PATH")
        if env_cmd and os.path.exists(env_cmd):
            return env_cmd

        # PATH에서 검색
        which_cmd = shutil.which("tesseract")
        if which_cmd:
            return which_cmd

        # Windows 기본 설치 경로
        if sys.platform == "win32":
            candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            ]
            for candidate in candidates:
                if os.path.exists(candidate):
                    return candidate

        return None

    def _init_tesseract(self):
        """Tesseract OCR 초기화"""
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise ImportError(f"pytesseract 미설치: pip install pytesseract")

        cmd = self._find_tesseract_cmd()
        if not cmd:
            raise RuntimeError("Tesseract 실행 파일을 찾을 수 없습니다.")

        pytesseract.pytesseract.tesseract_cmd = cmd
        self._pytesseract = pytesseract
        self._tesseract_output = Output
        
        # 한국어+영어 기본, 없으면 영어만
        self._tesseract_lang = self._detect_available_languages()
        self.reader = "tesseract"
        
        _safe_print(f"[OCR] Tesseract path: {cmd}")
        _safe_print(f"[OCR] Tesseract lang: {self._tesseract_lang}")

    def _detect_available_languages(self) -> str:
        """사용 가능한 Tesseract 언어 감지"""
        try:
            langs = self._pytesseract.get_languages()
            if "kor" in langs and "eng" in langs:
                return "kor+eng"
            elif "kor" in langs:
                return "kor"
            elif "chi_sim" in langs and "eng" in langs:
                return "chi_sim+eng"
            elif "eng" in langs:
                return "eng"
            else:
                return langs[0] if langs else "eng"
        except Exception:
            return os.environ.get("TESSERACT_LANG", "eng")

    def _to_pil_image(self, image):
        """이미지를 PIL Image로 변환"""
        try:
            from PIL import Image
        except ImportError:
            return image

        if isinstance(image, Image.Image):
            return image

        if isinstance(image, (str, os.PathLike)):
            try:
                return Image.open(image)
            except Exception:
                return image

        if isinstance(image, (bytes, bytearray)):
            try:
                return Image.open(io.BytesIO(image))
            except Exception:
                return image

        try:
            import numpy as np
            if isinstance(image, np.ndarray):
                if image.ndim == 3 and image.shape[2] == 3:
                    try:
                        import cv2
                        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    except ImportError:
                        image = image[:, :, ::-1]
                return Image.fromarray(image)
        except ImportError:
            pass

        return image

    def readtext(self, image, **kwargs) -> List[Tuple[List[List[float]], str, float]]:
        """
        이미지에서 텍스트 읽기

        Args:
            image: numpy array, 파일 경로, 또는 bytes
            **kwargs: 호환성을 위해 유지 (무시됨)

        Returns:
            List of (bbox, text, confidence) tuples
        """
        if self.reader is None:
            return []

        try:
            if self.engine_name == "tesseract":
                return self._read_with_tesseract(image)
            elif self.engine_name == "rapidocr":
                return self._read_with_rapidocr(image)
            else:
                return []
        except Exception as e:
            _safe_print(f"[OCR] Text read failed: {e}")
            return []

    def _read_with_tesseract(self, image) -> List[Tuple[List[List[float]], str, float]]:
        """Tesseract로 텍스트 읽기"""
        image = self._to_pil_image(image)
        lang = self._tesseract_lang or "eng"
        
        try:
            data = self._pytesseract.image_to_data(
                image,
                output_type=self._tesseract_output.DICT,
                lang=lang,
            )
        except Exception:
            # 언어 폴백
            if lang != "eng":
                self._tesseract_lang = "eng"
                try:
                    data = self._pytesseract.image_to_data(
                        image,
                        output_type=self._tesseract_output.DICT,
                        lang="eng",
                    )
                except Exception:
                    return []
            else:
                return []

        texts = data.get("text", [])
        confs = data.get("conf", [])
        lefts = data.get("left", [])
        tops = data.get("top", [])
        widths = data.get("width", [])
        heights = data.get("height", [])

        converted = []
        for idx, text in enumerate(texts):
            if not text or not str(text).strip():
                continue
            try:
                conf_val = float(confs[idx])
            except (ValueError, TypeError):
                conf_val = -1.0
            if conf_val < 0:
                continue

            x = int(lefts[idx])
            y = int(tops[idx])
            w = int(widths[idx])
            h = int(heights[idx])
            bbox = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            confidence = max(0.0, min(1.0, conf_val / 100.0))
            converted.append((bbox, str(text), confidence))

        return converted

    def _read_with_rapidocr(self, image) -> List[Tuple[List[List[float]], str, float]]:
        """RapidOCR로 텍스트 읽기"""
        result, elapse = self.reader(image)

        if result is None:
            return []

        converted = []
        for item in result:
            if len(item) >= 3:
                bbox = item[0]
                text = item[1]
                confidence = float(item[2])
                converted.append((bbox, text, confidence))

        return converted

    def __bool__(self):
        """OCR reader 초기화 여부 확인"""
        return self.reader is not None

    def __repr__(self):
        return f"OCRBackend(engine='{self.engine_name}')"


def create_ocr_reader() -> Optional[OCRBackend]:
    """
    OCR reader 팩토리 함수

    Returns:
        OCRBackend instance or None if initialization fails
    """
    try:
        backend = OCRBackend()
        if backend.reader is not None:
            return backend
        return None
    except Exception as e:
        _safe_print(f"[OCR] OCRBackend creation failed: {e}")
        return None


def check_ocr_availability() -> dict:
    """
    OCR 가용성 체크
    
    Returns:
        dict with availability info
    """
    info = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "rapidocr_available": False,
        "tesseract_available": False,
        "tesseract_path": None,
        "recommended_engine": None,
    }
    
    # RapidOCR 체크 (Python 3.13 미만)
    if sys.version_info < (3, 13):
        try:
            from rapidocr_onnxruntime import RapidOCR
            info["rapidocr_available"] = True
        except ImportError:
            pass
    
    # Tesseract 체크
    try:
        import pytesseract
        cmd = shutil.which("tesseract")
        if not cmd and sys.platform == "win32":
            for path in [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
                if os.path.exists(path):
                    cmd = path
                    break
        if cmd:
            info["tesseract_available"] = True
            info["tesseract_path"] = cmd
    except ImportError:
        pass
    
    # 추천 엔진
    if sys.version_info >= (3, 13):
        info["recommended_engine"] = "tesseract"
    elif info["rapidocr_available"]:
        info["recommended_engine"] = "rapidocr"
    elif info["tesseract_available"]:
        info["recommended_engine"] = "tesseract"
    else:
        info["recommended_engine"] = None
    
    return info
