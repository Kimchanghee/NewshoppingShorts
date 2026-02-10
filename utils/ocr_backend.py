"""
OCR Backend Wrapper

엔진 우선순위:
1. GLM-OCR API (Z.ai) - 가장 높은 정확도, 온라인 필요
2. RapidOCR (Python 3.13 미만) - 로컬 대안
3. Tesseract - 최종 폴백

Python 3.14+ 호환: pytesseract(Tesseract) 전용 인터페이스
Python 3.13 미만: RapidOCR 우선, Tesseract 폴백
"""

import os
import sys
import io
import shutil
import time
import threading
from typing import List, Tuple, Any, Optional

# Logging and error handling
from utils.logging_config import get_logger
from utils.error_handlers import OCRInitializationError, GLMOCROfflineError

logger = get_logger(__name__)

_OCR_CACHE_LOCK = threading.Lock()
_OCR_CACHED_BACKEND = None
_OCR_INIT_ATTEMPTED = False
_OCR_LAST_ERROR: Optional[str] = None

# GLM-OCR 사용 가능 여부 플래그
GLM_OCR_AVAILABLE = False
try:
    from utils.glm_ocr_client import GLMOCRClient, check_glm_ocr_availability
    GLM_OCR_AVAILABLE = True
except ImportError:
    GLMOCRClient = None
    check_glm_ocr_availability = None


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
        OCR 엔진 초기화 - 우선순위에 따라 다른 전략
        OCR 엔진 초기화 - Priority-based strategy

        Priority:
        1. GLM-OCR API (Z.ai) - highest accuracy, requires internet
        2. RapidOCR (Python < 3.13) - local alternative
        3. Tesseract - final fallback

        Raises:
            OCRInitializationError: If all OCR engines fail to initialize
        """
        max_retries = 3
        engines = []

        # Priority 1: GLM-OCR API (online, highest accuracy)
        if GLM_OCR_AVAILABLE and not os.getenv("GLM_OCR_DISABLED"):
            engines.append(("glm_ocr", self._init_glm_ocr))

        # Priority 2: RapidOCR (Python < 3.13 only)
        if sys.version_info < (3, 13):
            engines.append(("rapidocr", self._init_rapidocr))

        # Priority 3: Tesseract (final fallback)
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
                    if not self._should_retry_init(engine_name, e):
                        break
                    if attempt < max_retries - 1:
                        time.sleep(0.5)  # Wait before retry

        # All engines failed
        logger.error("All OCR engines failed to initialize")
        self._print_tesseract_install_guide()
        
        msg = "OCR engine unavailable - no OCR backend could be initialized"
        if sys.version_info >= (3, 13):
            msg += "\n(Note: RapidOCR is not supported on Python 3.13+. You MUST install Tesseract.)"
            
        raise OCRInitializationError(
            message=msg,
            recovery_hint="Install Tesseract OCR:\nWindows: winget install UB-Mannheim.TesseractOCR\nmacOS: brew install tesseract tesseract-lang\nLinux: sudo apt install tesseract-ocr tesseract-ocr-kor tesseract-ocr-chi-sim"
        )

    @staticmethod
    def _should_retry_init(engine_name: str, error: Exception) -> bool:
        """
        Decide whether init failure is likely transient and worth retrying.
        """
        msg = str(error)
        msg_lower = msg.lower()

        # Non-retryable: GLM API disabled/offline
        if engine_name == "glm_ocr":
            if "glmocrofflineerror" in msg_lower or "api not available" in msg_lower:
                return False

        # Non-retryable: RapidOCR package missing
        if engine_name == "rapidocr":
            if "import" in msg_lower and ("no module named" in msg_lower or "실패" in msg):
                return False

        # Non-retryable: Tesseract executable or package missing
        if engine_name == "tesseract":
            non_retry_markers = [
                "찾을 수 없습니다",
                "미설치",
                "not found",
                "no such file",
                "no module named",
            ]
            if any(marker in msg_lower for marker in [m.lower() for m in non_retry_markers]):
                return False

        return True

    def _init_glm_ocr(self):
        """Initialize GLM-OCR API client"""
        if not GLM_OCR_AVAILABLE:
            raise ImportError("GLM-OCR client not available")

        try:
            self._glm_client = GLMOCRClient()

            # Check if API is available
            if not self._glm_client.is_available():
                raise GLMOCROfflineError("GLM-OCR API not available")

            self.reader = "glm_ocr"
            logger.info("[OCR] GLM-OCR API initialized successfully")

        except Exception as e:
            raise RuntimeError(f"GLM-OCR initialization failed: {e!r}")

    def _read_with_glm_ocr(self, image) -> List[Tuple[List[List[float]], str, float]]:
        """GLM-OCR API text recognition"""
        if not hasattr(self, '_glm_client') or self._glm_client is None:
            return []

        try:
            results = self._glm_client.recognize_single(image)
            return results
        except GLMOCROfflineError:
            # API went offline - trigger fallback
            logger.warning("[OCR] GLM-OCR went offline, results may be incomplete")
            return []
        except Exception as e:
            logger.warning(f"[OCR] GLM-OCR read error: {e}")
            return []

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
        # Prefer bundled runtime in frozen (PyInstaller) builds.
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            bundled_root = os.path.join(base, "tesseract")
            exe_name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
            bundled_exe = os.path.join(bundled_root, exe_name)
            if os.path.exists(bundled_exe):
                return bundled_exe

        # Also support "next to executable" layouts (some update/unpack flows).
        exe_dir = os.path.dirname(sys.executable)
        exe_name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
        adjacent_exe = os.path.join(exe_dir, "tesseract", exe_name)
        if os.path.exists(adjacent_exe):
            return adjacent_exe

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

    def _find_tessdata_dir(self) -> Optional[str]:
        """Find tessdata directory for language packs."""
        env_dir = os.environ.get("TESSDATA_PREFIX")
        candidates = []
        if env_dir:
            candidates.append(env_dir)

        # Prefer bundled tessdata in frozen (PyInstaller) builds.
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            candidates.append(os.path.join(base, "tesseract", "tessdata"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "tesseract", "tessdata"))

        candidates.extend(
            [
                os.path.join(os.path.expandvars(r"%LOCALAPPDATA%"), "Tesseract-OCR", "tessdata"),
                r"C:\Program Files\Tesseract-OCR\tessdata",
                r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
            ]
        )

        for candidate in candidates:
            if candidate and os.path.isdir(candidate):
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

        # Ensure dependent DLLs are discoverable on Windows (bundled tesseract ships DLLs next to the exe).
        cmd_dir = os.path.dirname(cmd)
        if cmd_dir and os.path.isdir(cmd_dir):
            os.environ["PATH"] = cmd_dir + os.pathsep + os.environ.get("PATH", "")
            if sys.platform == "win32":
                try:
                    add_dll = getattr(os, "add_dll_directory", None)
                    if add_dll:
                        add_dll(cmd_dir)
                except Exception:
                    pass

        pytesseract.pytesseract.tesseract_cmd = cmd
        self._pytesseract = pytesseract
        self._tesseract_output = Output
        tessdata_dir = self._find_tessdata_dir()
        if tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = tessdata_dir
        
        # 한국어+영어 기본, 없으면 영어만
        self._tesseract_lang = self._detect_available_languages()
        self.reader = "tesseract"
        
        _safe_print(f"[OCR] Tesseract path: {cmd}")
        _safe_print(f"[OCR] Tesseract lang: {self._tesseract_lang}")

    def _detect_available_languages(self) -> str:
        """사용 가능한 Tesseract 언어 감지"""
        try:
            langs_raw = self._pytesseract.get_languages()
            # Some environments return values like "tessdata/kor".
            langs = {
                str(lang).replace("\\", "/").split("/")[-1].strip()
                for lang in (langs_raw or [])
                if str(lang).strip()
            }
            # Prefer including Simplified Chinese for subtitle blur detection.
            preferred = []
            if "chi_sim" in langs:
                preferred.append("chi_sim")
            if "kor" in langs:
                preferred.append("kor")
            if "eng" in langs:
                preferred.append("eng")
            if preferred:
                return "+".join(preferred)
            return next(iter(langs), "eng")
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
            if self.engine_name == "glm_ocr":
                return self._read_with_glm_ocr(image)
            elif self.engine_name == "tesseract":
                return self._read_with_tesseract(image)
            elif self.engine_name == "rapidocr":
                return self._read_with_rapidocr(image)
            else:
                return []
        except Exception as e:
            _safe_print(f"[OCR] Text read failed: {e}")
            return []

    def readtext_batch(
        self,
        images: List,
        **kwargs
    ) -> List[List[Tuple[List[List[float]], str, float]]]:
        """
        배치 이미지에서 텍스트 읽기 (GLM-OCR 전용 최적화)

        Args:
            images: List of numpy arrays, file paths, or bytes
            **kwargs: 호환성을 위해 유지 (무시됨)

        Returns:
            List of results for each image
        """
        if self.reader is None:
            return [[] for _ in images]

        # GLM-OCR: 배치 처리 지원
        if self.engine_name == "glm_ocr" and hasattr(self, '_glm_client'):
            try:
                return self._glm_client.recognize_batch(images)
            except Exception as e:
                logger.warning(f"[OCR] Batch read failed, falling back to sequential: {e}")

        # 다른 엔진: 순차 처리
        return [self.readtext(img, **kwargs) for img in images]

    def supports_batch(self) -> bool:
        """Check if current engine supports batch processing"""
        return self.engine_name == "glm_ocr"

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
    global _OCR_CACHED_BACKEND, _OCR_INIT_ATTEMPTED, _OCR_LAST_ERROR

    with _OCR_CACHE_LOCK:
        if _OCR_CACHED_BACKEND is not None:
            return _OCR_CACHED_BACKEND

        # Avoid repeated full init attempts/log spam in the same process.
        if _OCR_INIT_ATTEMPTED:
            if _OCR_LAST_ERROR:
                logger.debug("[OCR] Skipping re-init after previous failure: %s", _OCR_LAST_ERROR)
            return None

        _OCR_INIT_ATTEMPTED = True

    try:
        backend = OCRBackend()
        if backend.reader is not None:
            with _OCR_CACHE_LOCK:
                _OCR_CACHED_BACKEND = backend
                _OCR_LAST_ERROR = None
            return backend
        with _OCR_CACHE_LOCK:
            _OCR_LAST_ERROR = "OCR backend initialized without active reader"
        return None
    except Exception as e:
        with _OCR_CACHE_LOCK:
            _OCR_LAST_ERROR = str(e)
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
        "glm_ocr_available": False,
        "glm_ocr_api_key": False,
        "rapidocr_available": False,
        "tesseract_available": False,
        "tesseract_path": None,
        "recommended_engine": None,
    }

    # GLM-OCR 체크
    if GLM_OCR_AVAILABLE and check_glm_ocr_availability:
        try:
            glm_info = check_glm_ocr_availability()
            info["glm_ocr_available"] = glm_info.get("available", False)
            info["glm_ocr_api_key"] = glm_info.get("api_key_configured", False)
        except Exception:
            pass

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

    # 추천 엔진 (우선순위: GLM-OCR > RapidOCR > Tesseract)
    if info["glm_ocr_available"]:
        info["recommended_engine"] = "glm_ocr"
    elif sys.version_info >= (3, 13):
        info["recommended_engine"] = "tesseract"
    elif info["rapidocr_available"]:
        info["recommended_engine"] = "rapidocr"
    elif info["tesseract_available"]:
        info["recommended_engine"] = "tesseract"
    else:
        info["recommended_engine"] = None

    return info
