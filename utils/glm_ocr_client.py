"""
GLM-OCR API Client

Z.ai GLM-OCR API 클라이언트 - 고성능 문서/이미지 OCR
OpenAI-compatible API 사용, 배치 처리 지원

Usage:
    from utils.glm_ocr_client import GLMOCRClient

    client = GLMOCRClient()
    results = client.recognize_single(image)
    batch_results = client.recognize_batch([img1, img2, img3])
"""

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.logging_config import get_logger
from config.constants import GLMOCRSettings

logger = get_logger(__name__)


def _get_api_key() -> str:
    """
    Get API key - env var → SecretsManager fallback.
    Found key is auto-stored in SecretsManager for EXE builds.
    """
    # 1) 환경변수 (.env 또는 시스템)
    api_key = os.getenv("GLM_OCR_API_KEY")
    if api_key:
        # SecretsManager에 저장 (EXE 빌드에서도 작동하도록)
        try:
            from utils.secrets_manager import SecretsManager
            SecretsManager.store_api_key("glm_ocr", api_key)
        except Exception:
            pass
        return api_key

    # 2) SecretsManager 폴백 (EXE 빌드 시 .env 없이도 작동)
    try:
        from utils.secrets_manager import SecretsManager
        stored = SecretsManager.get_api_key("glm_ocr")
        if stored:
            return stored
    except Exception:
        pass

    logger.debug("[GLM-OCR] API key not configured. Set GLM_OCR_API_KEY or store via SecretsManager.")
    return ""


def has_glm_ocr_api_key() -> bool:
    """Return True when GLM-OCR API key is configured (env or SecretsManager)."""
    try:
        return bool(_get_api_key())
    except Exception:
        return False


class GLMOCRClient:
    """
    GLM-OCR API Client

    Features:
    - 연결 풀링 및 재시도 로직
    - 배치 이미지 처리 (최대 20개/요청)
    - 자동 이미지 압축
    - 오프라인 폴백 지원
    - 스레드 안전한 상태 관리
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize GLM-OCR client

        Args:
            api_key: Optional API key (uses environment variable if not provided)
        """
        self._api_key = api_key or _get_api_key()
        self._session = self._create_session()
        self._consecutive_failures = 0
        self._offline_mode = False
        self._state_lock = threading.Lock()  # Thread safety for state mutations
        self.invalid_coordinate_count = 0
        self.request_failure_count = 0
        self._rate_limit_until = 0.0

        # 설정
        self._endpoint = GLMOCRSettings.ENDPOINT
        self._model = GLMOCRSettings.MODEL
        self._timeout = GLMOCRSettings.TIMEOUT_SECONDS
        self._max_batch = GLMOCRSettings.MAX_BATCH_SIZE

        logger.info("[GLM-OCR] Client initialized")

    def _create_session(self) -> requests.Session:
        """Create HTTP session with connection pooling and retry"""
        session = requests.Session()
        session.verify = True

        retry_strategy = Retry(
            total=GLMOCRSettings.MAX_RETRIES,
            backoff_factor=GLMOCRSettings.BACKOFF_FACTOR,
            # 429 is handled by the application-level shared cooldown below.
            # Retrying it in urllib3 as well multiplied one logical request into
            # as many as 20 POSTs and bypassed the cross-worker cooldown.
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST"],
            raise_on_status=False,
            # 429 is owned exclusively by the application-level shared
            # cooldown below. urllib3 otherwise retries a 429 carrying a
            # Retry-After header even when absent from status_forcelist.
            respect_retry_after_header=False,
        )

        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _compress_image(self, image, target_width: int = None) -> str:
        """
        Compress and encode image to base64

        Args:
            image: numpy array, file path, or bytes
            target_width: Target width for resizing (default from settings)

        Returns:
            Base64 encoded JPEG string
        """
        import cv2
        import numpy as np

        target_width = target_width or GLMOCRSettings.TARGET_WIDTH
        quality = GLMOCRSettings.JPEG_QUALITY

        # Convert to numpy array if needed
        if isinstance(image, str):
            # File path
            frame = cv2.imread(image)
        elif isinstance(image, bytes):
            # Bytes
            nparr = np.frombuffer(image, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif hasattr(image, '__array__'):
            # Numpy array or similar
            frame = np.asarray(image)
        else:
            frame = image

        if frame is None:
            raise ValueError("Failed to load image")

        h, w = frame.shape[:2]

        # Resize if too wide
        if w > target_width:
            scale = target_width / w
            new_h = int(h * scale)
            frame = cv2.resize(frame, (target_width, new_h), interpolation=cv2.INTER_AREA)

        # Encode as JPEG
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        _, buffer = cv2.imencode('.jpg', frame, encode_params)

        return base64.b64encode(buffer).decode('utf-8')

    @staticmethod
    def _get_source_size(image) -> Tuple[int, int]:
        """Return the original image size as ``(width, height)`` before compression."""
        import cv2
        import numpy as np

        if isinstance(image, str):
            frame = cv2.imread(image)
        elif isinstance(image, bytes):
            nparr = np.frombuffer(image, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif hasattr(image, '__array__'):
            frame = np.asarray(image)
        else:
            frame = image

        if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
            raise ValueError("Failed to load image")

        height, width = frame.shape[:2]
        if width <= 0 or height <= 0:
            raise ValueError("Image dimensions must be positive")
        return int(width), int(height)

    def _record_invalid_coordinate(self) -> None:
        """Increment the malformed-coordinate diagnostic counter safely."""
        with self._state_lock:
            self.invalid_coordinate_count += 1

    def _record_request_failure(self) -> None:
        """Record an exhausted OCR request so precision QA can fail closed."""
        with self._state_lock:
            self.request_failure_count += 1

    def _set_rate_limit_cooldown(self, seconds: float) -> None:
        with self._state_lock:
            self._rate_limit_until = max(
                self._rate_limit_until, time.monotonic() + max(0.0, float(seconds))
            )

    def _wait_for_rate_limit_slot(self) -> None:
        with self._state_lock:
            remaining = self._rate_limit_until - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _get_uploaded_size(source_size: Tuple[int, int]) -> Tuple[int, int]:
        """Return the JPEG dimensions sent to GLM for a source image."""
        width, height = source_size
        target_width = int(GLMOCRSettings.TARGET_WIDTH)
        if width > target_width:
            scale = target_width / float(width)
            return target_width, max(1, int(height * scale))
        return int(width), int(height)

    def _bbox_to_pixel_polygon(
        self,
        bbox_2d: Any,
        source_size: Optional[Tuple[int, int]],
        response_size: Optional[Tuple[int, int]] = None,
    ) -> Optional[List[List[float]]]:
        """Validate GLM coordinates and map them to source-image pixels.

        GLM deployments have returned both documented normalized coordinates
        and uploaded-image pixel coordinates. Accept both explicit spaces and
        reject ambiguous malformed values instead of silently clamping them.
        """
        if not isinstance(bbox_2d, (list, tuple)) or len(bbox_2d) < 4:
            self._record_invalid_coordinate()
            return None

        coordinates = bbox_2d[:4]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in coordinates):
            self._record_invalid_coordinate()
            return None

        x1, y1, x2, y2 = (float(value) for value in coordinates)
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)) or x2 <= x1 or y2 <= y1:
            self._record_invalid_coordinate()
            return None

        if source_size is None:
            self._record_invalid_coordinate()
            return None
        width, height = source_size
        if (
            isinstance(width, bool)
            or isinstance(height, bool)
            or not isinstance(width, (int, float))
            or not isinstance(height, (int, float))
            or not math.isfinite(float(width))
            or not math.isfinite(float(height))
            or width <= 0
            or height <= 0
        ):
            self._record_invalid_coordinate()
            return None

        if all(0.0 <= value <= 1.0 for value in (x1, y1, x2, y2)):
            px1, px2 = x1 * float(width), x2 * float(width)
            py1, py2 = y1 * float(height), y2 * float(height)
        else:
            # A value just outside 0..1 mixed with normalized-looking values is
            # far more likely to be a corrupt normalized box than a sub-pixel
            # pixel-space box. Real GLM pixel coordinates are integral/larger.
            if max(x1, y1, x2, y2) <= 2.0 and min(x1, y1, x2, y2) < 1.0:
                self._record_invalid_coordinate()
                return None
            response_width, response_height = response_size or source_size
            if (
                not all(value >= 0.0 for value in (x1, y1, x2, y2))
                or x2 > float(response_width)
                or y2 > float(response_height)
            ):
                self._record_invalid_coordinate()
                return None
            scale_x = float(width) / float(response_width)
            scale_y = float(height) / float(response_height)
            px1, px2 = x1 * scale_x, x2 * scale_x
            py1, py2 = y1 * scale_y, y2 * scale_y
        return [
            [px1, py1],
            [px2, py1],
            [px2, py2],
            [px1, py2],
        ]

    def _build_request(self, images_b64: List[str]) -> Dict[str, Any]:
        """
        Build API request payload for layout_parsing endpoint

        Args:
            images_b64: List of base64 encoded images

        Returns:
            Request payload dict
        """
        # layout_parsing API uses 'file' parameter with base64 data URI
        # For single image (batch not directly supported, process sequentially)
        img_b64 = images_b64[0] if images_b64 else ""

        return {
            "model": self._model,
            "file": f"data:image/jpeg;base64,{img_b64}"
        }

    def _parse_response(
        self,
        response_data: Dict[str, Any],
        source_size: Optional[Tuple[int, int]] = None,
        response_size: Optional[Tuple[int, int]] = None,
    ) -> List[Tuple[List[List[float]], str, float]]:
        """
        Parse layout_parsing API response to OCR format

        Args:
            response_data: Parsed JSON response from API
            source_size: Original input image size as ``(width, height)``. GLM
                returns normalized ``bbox_2d`` coordinates, so production
                callers pass this even when the uploaded JPEG was resized.

        Returns:
            List of (bbox, text, confidence) tuples
        """
        results = []

        try:
            if not isinstance(response_data, dict) or "layout_details" not in response_data:
                self._record_request_failure()
                logger.warning("[GLM-OCR] Response missing layout_details")
                return results
            # layout_parsing response format:
            # {"layout_details": [{"bbox_2d": [x1,y1,x2,y2], "content": "text", "label": "text"}], "md_results": "..."}
            layout_details = response_data.get("layout_details", [])
            if not isinstance(layout_details, list):
                self._record_request_failure()
                logger.warning("[GLM-OCR] layout_details is not a list")
                return results

            # layout_details can be nested list or flat list
            if layout_details and isinstance(layout_details[0], list):
                # Nested: [[{...}, {...}]]
                layout_details = layout_details[0]

            for item in layout_details:
                if not isinstance(item, dict):
                    self._record_request_failure()
                    logger.warning("[GLM-OCR] Ignoring malformed layout item")
                    continue
                label = item.get("label", "")
                if label in ("text", "paragraph", "title", "paragraph_title", "table"):
                    text_content = item.get("content", "")
                    # Remove markdown formatting
                    text_content = text_content.replace("## ", "").replace("# ", "").strip()

                    bbox = self._bbox_to_pixel_polygon(
                        item.get("bbox_2d"), source_size, response_size=response_size
                    )
                    if bbox is None:
                        continue

                    # layout_parsing doesn't return confidence, use default 0.9
                    confidence = 0.9

                    if text_content and confidence >= GLMOCRSettings.MIN_CONFIDENCE:
                        results.append((bbox, text_content, confidence))

        except Exception as e:
            self._record_request_failure()
            logger.warning(f"[GLM-OCR] Response parse error: {e}")

        return results

    def _call_api(self, payload: Dict[str, Any]) -> Optional[str]:
        """
        Make API call with error handling

        Args:
            payload: Request payload

        Returns:
            Response text or None on failure
        """
        if not self._api_key:
            logger.error("[GLM-OCR] API key not configured")
            return None

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        rate_limit_retries = max(0, int(getattr(GLMOCRSettings, "RATE_LIMIT_RETRIES", 4)))
        for rate_attempt in range(rate_limit_retries + 1):
            self._wait_for_rate_limit_slot()
            try:
                response = self._session.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                )

                if response.status_code == 200:
                    with self._state_lock:
                        self._consecutive_failures = 0
                    return response.json()

                if response.status_code == 429:
                    retry_after = 0.0
                    try:
                        retry_after = float(response.headers.get("Retry-After") or 0.0)
                    except (TypeError, ValueError):
                        retry_after = 0.0
                    cooldown = max(
                        float(GLMOCRSettings.RATE_LIMIT_WAIT_SECONDS), retry_after
                    )
                    self._set_rate_limit_cooldown(cooldown)
                    logger.warning(
                        "[GLM-OCR] Rate limit exceeded; cooldown %.1fs (%d/%d)",
                        cooldown,
                        rate_attempt + 1,
                        rate_limit_retries + 1,
                    )
                    if rate_attempt < rate_limit_retries:
                        continue
                    self._record_request_failure()
                    return None

                if response.status_code == 401:
                    logger.error("[GLM-OCR] Invalid API key")
                else:
                    logger.warning(f"[GLM-OCR] API error: {response.status_code}")
                self._handle_failure()
                self._record_request_failure()
                return None

            except requests.exceptions.Timeout:
                logger.warning("[GLM-OCR] Request timeout")
                self._handle_failure()
                self._record_request_failure()
                return None
            except requests.exceptions.ConnectionError:
                logger.warning("[GLM-OCR] Connection error")
                self._handle_failure()
                self._record_request_failure()
                return None
            except Exception as e:
                logger.error(f"[GLM-OCR] Unexpected error: {e}")
                self._handle_failure()
                self._record_request_failure()
                return None

        return None

    def _handle_failure(self):
        """Track consecutive failures and trigger offline mode (thread-safe)"""
        with self._state_lock:
            self._consecutive_failures += 1

            if self._consecutive_failures >= GLMOCRSettings.API_FAILURE_THRESHOLD:
                self._offline_mode = True
                logger.error(
                    f"[GLM-OCR] {self._consecutive_failures} consecutive failures. "
                    "Switching to offline mode."
                )

    def is_available(self) -> bool:
        """Check if GLM-OCR API is available (thread-safe)"""
        if GLMOCRSettings.OFFLINE_MODE:
            return False
        with self._state_lock:
            if self._offline_mode:
                return False
        if not self._api_key:
            return False
        return True

    def reset_offline_mode(self):
        """Reset offline mode (e.g., after network recovery) - thread-safe"""
        with self._state_lock:
            self._offline_mode = False
            self._consecutive_failures = 0
        logger.info("[GLM-OCR] Offline mode reset")

    def close(self):
        """Explicitly close the HTTP session"""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass

    def __del__(self):
        """Cleanup resources on garbage collection"""
        self.close()

    def recognize_single(self, image) -> List[Tuple[List[List[float]], str, float]]:
        """
        Recognize text in a single image

        Args:
            image: numpy array, file path, or bytes

        Returns:
            List of (bbox, text, confidence) tuples
        """
        if not self.is_available():
            return []

        try:
            source_size = self._get_source_size(image)
            response_size = self._get_uploaded_size(source_size)
            img_b64 = self._compress_image(image)
            payload = self._build_request([img_b64])
            response_data = self._call_api(payload)

            if response_data and isinstance(response_data, dict):
                return self._parse_response(
                    response_data,
                    source_size=source_size,
                    response_size=response_size,
                )

        except Exception as e:
            logger.error(f"[GLM-OCR] Single recognition error: {e}")

        return []

    def recognize_batch(
        self,
        images: List,
        batch_size: int = None
    ) -> List[List[Tuple[List[List[float]], str, float]]]:
        """
        Recognize text in multiple images with bounded request concurrency.

        The layout_parsing endpoint accepts one image per request. Requests are
        independent, so a small worker pool avoids serial network latency while
        preserving the exact input/result ordering expected by callers.

        Args:
            images: List of images (numpy arrays, file paths, or bytes)
            batch_size: Ignored (kept for API compatibility)

        Returns:
            List of results for each image
        """
        if not self.is_available():
            return [[] for _ in images]

        if not images:
            return []

        concurrency = max(
            1,
            min(int(getattr(GLMOCRSettings, "BATCH_CONCURRENCY", 4)), len(images)),
        )
        all_results: List[List[Tuple[List[List[float]], str, float]]] = [
            [] for _ in images
        ]

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(self.recognize_single, image): index
                for index, image in enumerate(images)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    all_results[index] = future.result()
                except Exception as e:
                    logger.error(f"[GLM-OCR] Batch item {index} error: {e}")
                    all_results[index] = []

        return all_results

    def _parse_batch_response(
        self,
        response_data: Dict[str, Any],
        image_count: int
    ) -> List[List[Tuple[List[List[float]], str, float]]]:
        """
        Parse batch response - handles multiple images in one response

        Note: layout_parsing API processes one image at a time,
        so batch is processed sequentially.

        Args:
            response_data: Parsed JSON response
            image_count: Number of images in the batch

        Returns:
            List of results for each image
        """
        # layout_parsing processes one image at a time
        all_items = self._parse_response(response_data)

        if not all_items:
            return [[] for _ in range(image_count)]

        # For single image batch, return all results
        if image_count == 1:
            return [all_items]

        # For multiple images (shouldn't happen with layout_parsing)
        return [all_items] + [[] for _ in range(image_count - 1)]


# Singleton instance with thread-safe initialization
_glm_client: Optional[GLMOCRClient] = None
_client_lock = threading.Lock()


def get_glm_ocr_client() -> GLMOCRClient:
    """Get or create GLM-OCR client singleton (thread-safe)"""
    global _glm_client
    if _glm_client is None:
        with _client_lock:
            # Double-check locking pattern
            if _glm_client is None:
                _glm_client = GLMOCRClient()
    return _glm_client


def check_glm_ocr_availability() -> Dict[str, Any]:
    """
    Check GLM-OCR API availability

    Returns:
        Dict with availability info (sanitized, no sensitive data)
    """
    client = get_glm_ocr_client()

    return {
        "available": client.is_available(),
        "api_key_configured": bool(client._api_key),  # Only boolean, not the key itself
        "model": client._model
    }
