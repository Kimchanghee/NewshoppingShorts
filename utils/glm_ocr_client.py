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
    Get API key from environment variable only (secure approach)

    Security: API keys should NEVER be embedded in source code.
    Set the GLM_OCR_API_KEY environment variable to use this client.
    """
    api_key = os.getenv("GLM_OCR_API_KEY")
    if not api_key:
        logger.debug("[GLM-OCR] API key not configured. Set GLM_OCR_API_KEY environment variable.")
    return api_key or ""


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
        Build API request payload

        Args:
            images_b64: List of base64 encoded images

        Returns:
            Request payload dict
        """
        content = []

        # Add images
        for img_b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}"
                }
            })

        # Add prompt for OCR
        content.append({
            "type": "text",
            "text": (
                "Extract all text from the image(s) with bounding boxes. "
                "Return JSON array format: "
                '[{"bbox": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], "text": "detected text", "confidence": 0.95}]. '
                "Only return the JSON array, no other text."
            )
        })

        return {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1
        }

    def _parse_response(self, response_text: str) -> List[Tuple[List[List[float]], str, float]]:
        """
        Parse API response to OCR format

        Args:
            response_text: Raw response text from API

        Returns:
            List of (bbox, text, confidence) tuples
        """
        results = []

        try:
            # Extract JSON from response
            text = response_text.strip()

            # Find JSON array in response
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1

            if start_idx == -1 or end_idx == 0:
                logger.warning("[GLM-OCR] No JSON array found in response")
                return results

            json_str = text[start_idx:end_idx]
            items = json.loads(json_str)

            for item in items:
                bbox = item.get("bbox", [[0, 0], [0, 0], [0, 0], [0, 0]])
                text_content = item.get("text", "")
                confidence = float(item.get("confidence", 0.9))

                if text_content and confidence >= GLMOCRSettings.MIN_CONFIDENCE:
                    results.append((bbox, text_content, confidence))

        except json.JSONDecodeError as e:
            logger.warning(f"[GLM-OCR] JSON parse error: {e}")
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

                # Extract text from OpenAI-compatible response
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    return message.get("content", "")

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
            response = self._call_api(payload)

            if response:
                return self._parse_response(response)

        except Exception as e:
            logger.error(f"[GLM-OCR] Single recognition error: {e}")

        return []

    def recognize_batch(
        self,
        images: List,
        batch_size: int = None
    ) -> List[List[Tuple[List[List[float]], str, float]]]:
        """
        Recognize text in multiple images (batch processing)

        Args:
            images: List of images (numpy arrays, file paths, or bytes)
            batch_size: Batch size (default from settings)

        Returns:
            List of results for each image
        """
        if not self.is_available():
            return [[] for _ in images]

        batch_size = batch_size or GLMOCRSettings.OPTIMAL_BATCH_SIZE
        batch_size = min(batch_size, self._max_batch)

        all_results = []

        # Process in batches
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]

            try:
                # Compress all images in batch
                images_b64 = [self._compress_image(img) for img in batch]

                # Build and send request
                payload = self._build_request(images_b64)
                response = self._call_api(payload)

                if response:
                    # Parse response - expect results per image
                    batch_results = self._parse_batch_response(response, len(batch))
                    all_results.extend(batch_results)
                else:
                    # API failed - return empty results for this batch
                    all_results.extend([[] for _ in batch])

                # Small delay between batches
                if i + batch_size < len(images):
                    time.sleep(GLMOCRSettings.REQUEST_DELAY_MS / 1000.0)

            except Exception as e:
                logger.error(f"[GLM-OCR] Batch recognition error: {e}")
                all_results.extend([[] for _ in batch])

        return all_results

    def _parse_batch_response(
        self,
        response_text: str,
        image_count: int
    ) -> List[List[Tuple[List[List[float]], str, float]]]:
        """
        Parse batch response - handles multiple images in one response

        For batch requests, the model may return results grouped by image
        or as a single flat array. This method handles both cases.

        Args:
            response_text: Raw response text
            image_count: Number of images in the batch

        Returns:
            List of results for each image
        """
        # First try to parse as single response
        all_items = self._parse_response(response_text)

        if not all_items:
            return [[] for _ in range(image_count)]

        # If only one image, return all results for it
        if image_count == 1:
            return [all_items]

        # For multiple images, try to split results
        # Strategy: divide results evenly (simple heuristic)
        # Better approach would be to have the API return image indices
        items_per_image = len(all_items) // image_count if image_count > 0 else 0

        if items_per_image == 0:
            # Very few results - assign all to first image
            results = [[]]
            results[0] = all_items
            results.extend([[] for _ in range(image_count - 1)])
            return results

        # Split evenly
        results = []
        for i in range(image_count):
            start = i * items_per_image
            end = start + items_per_image if i < image_count - 1 else len(all_items)
            results.append(all_items[start:end])

        return results


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
