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
import json
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
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
            raise_on_status=False,
            respect_retry_after_header=True,
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

    def _parse_response(self, response_data: Dict[str, Any]) -> List[Tuple[List[List[float]], str, float]]:
        """
        Parse layout_parsing API response to OCR format

        Args:
            response_data: Parsed JSON response from API

        Returns:
            List of (bbox, text, confidence) tuples
        """
        results = []

        try:
            # layout_parsing response format:
            # {"layout_details": [{"bbox_2d": [x1,y1,x2,y2], "content": "text", "label": "text"}], "md_results": "..."}
            layout_details = response_data.get("layout_details", [])

            # layout_details can be nested list or flat list
            if layout_details and isinstance(layout_details[0], list):
                # Nested: [[{...}, {...}]]
                layout_details = layout_details[0]

            for item in layout_details:
                label = item.get("label", "")
                if label in ("text", "paragraph", "title", "paragraph_title", "table"):
                    text_content = item.get("content", "")
                    # Remove markdown formatting
                    text_content = text_content.replace("## ", "").replace("# ", "").strip()

                    bbox_2d = item.get("bbox_2d", [0, 0, 0, 0])

                    # Convert [x1,y1,x2,y2] to [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                    if len(bbox_2d) >= 4:
                        x1, y1, x2, y2 = bbox_2d[:4]
                        bbox = [
                            [x1, y1],
                            [x2, y1],
                            [x2, y2],
                            [x1, y2]
                        ]
                    else:
                        bbox = [[0, 0], [0, 0], [0, 0], [0, 0]]

                    # layout_parsing doesn't return confidence, use default 0.9
                    confidence = 0.9

                    if text_content and confidence >= GLMOCRSettings.MIN_CONFIDENCE:
                        results.append((bbox, text_content, confidence))

        except Exception as e:
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

        try:
            response = self._session.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=self._timeout
            )

            if response.status_code == 200:
                with self._state_lock:
                    self._consecutive_failures = 0
                data = response.json()
                # layout_parsing returns full response object
                return data

            elif response.status_code == 401:
                logger.error("[GLM-OCR] Invalid API key")
                self._handle_failure()

            elif response.status_code == 429:
                logger.warning("[GLM-OCR] Rate limit exceeded")
                time.sleep(GLMOCRSettings.RATE_LIMIT_WAIT_SECONDS)
                self._handle_failure()

            else:
                logger.warning(f"[GLM-OCR] API error: {response.status_code}")
                self._handle_failure()

        except requests.exceptions.Timeout:
            logger.warning("[GLM-OCR] Request timeout")
            self._handle_failure()

        except requests.exceptions.ConnectionError:
            logger.warning("[GLM-OCR] Connection error")
            self._handle_failure()

        except Exception as e:
            logger.error(f"[GLM-OCR] Unexpected error: {e}")
            self._handle_failure()

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
            img_b64 = self._compress_image(image)
            payload = self._build_request([img_b64])
            response_data = self._call_api(payload)

            if response_data and isinstance(response_data, dict):
                return self._parse_response(response_data)

        except Exception as e:
            logger.error(f"[GLM-OCR] Single recognition error: {e}")

        return []

    def recognize_batch(
        self,
        images: List,
        batch_size: int = None
    ) -> List[List[Tuple[List[List[float]], str, float]]]:
        """
        Recognize text in multiple images (sequential processing)

        Note: layout_parsing API processes one image at a time,
        so we process images sequentially with delays.

        Args:
            images: List of images (numpy arrays, file paths, or bytes)
            batch_size: Ignored (kept for API compatibility)

        Returns:
            List of results for each image
        """
        if not self.is_available():
            return [[] for _ in images]

        all_results = []

        # Process images sequentially (layout_parsing = 1 image per request)
        for i, image in enumerate(images):
            try:
                result = self.recognize_single(image)
                all_results.append(result)

                # Small delay between requests to avoid rate limiting
                if i < len(images) - 1:
                    time.sleep(GLMOCRSettings.REQUEST_DELAY_MS / 1000.0)

            except Exception as e:
                logger.error(f"[GLM-OCR] Batch item {i} error: {e}")
                all_results.append([])

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
