"""
Application Constants

This module centralizes all magic numbers and configuration constants.
Extracted from subtitle_detector.py, subtitle_processor.py, and other modules.

Usage:
    from config.constants import (
        OCRThresholds, VideoSettings, MemoryLimits,
        URLProcessing, SessionSettings, VideoDurationLimits,
        RateLimiting, RemoteURLs
    )

    threshold = OCRThresholds.SSIM_THRESHOLD
    height = VideoSettings.DEFAULT_HEIGHT
    max_urls = URLProcessing.MAX_URL_QUEUE_SIZE
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class OCRThresholds:
    """OCR detection and filtering thresholds"""

    # Confidence thresholds
    CONFIDENCE_MIN: float = 0.3  # Minimum OCR confidence (lowered for better detection)
    TEXT_SIMILARITY: float = 0.001  # Edge change threshold (0.1%)

    # SSIM (Structural Similarity Index) for frame comparison
    # ★ SSIM 스킵 완전 비활성화: 자막 전환을 놓치지 않도록
    SSIM_THRESHOLD: float = 1.0  # 100% = 사실상 비활성화 (절대 스킵 안함)
    MIN_CONSECUTIVE_SIMILAR: int = 999  # 사실상 비활성화
    SSIM_SKIP_ENABLED: bool = False  # SSIM 기반 프레임 스킵 활성화 여부

    # Canny edge detection
    EDGE_CHANGE_THRESHOLD: float = 0.0005  # 0.05% change threshold (더 민감하게)
    CANNY_FAST_THRESHOLD: float = 10.0  # Fast threshold for change detection (민감하게)

    # Hybrid detector confirmation
    HYBRID_CONFIRM_THRESHOLD: float = 0.85  # Multi-frame similarity threshold

    # IoU (Intersection over Union) for region merging
    # ★ IoU 임계값 낮춤: 별도 자막이 병합되지 않도록
    IOU_CLUSTER_THRESHOLD: float = 0.15  # 클러스터링용 (낮춤: 0.3 -> 0.15)
    IOU_MERGE_THRESHOLD: float = 0.25  # 병합용 (낮춤: 0.4 -> 0.25)
    IOU_OVERLAP_THRESHOLD: float = 0.15  # Minimum overlap to merge regions
    IOU_STRICT_THRESHOLD: float = 0.25  # Strict overlap threshold

    # Area ratio thresholds
    AREA_RATIO_MIN: float = 0.35  # Minimum area ratio for region validation
    AREA_RATIO_MAX: float = 0.50  # Maximum area ratio (증가: 0.45 -> 0.50)

    # ROI (Region of Interest) settings
    # ★ ROI 전체 화면 스캔: 상단 자막도 감지하도록
    ROI_BOTTOM_PERCENT: float = 100.0  # 100% = 전체 화면 스캔 (기존 50%)
    ROI_MIN_PERCENT: float = 70.0  # 최소 70% 스캔 보장

    # Minimum bbox size (pixels)
    MIN_BBOX_WIDTH: int = 15  # 최소 박스 너비 (낮춤: 20 -> 15)
    MIN_BBOX_HEIGHT: int = 6  # 최소 박스 높이 (낮춤: 8 -> 6)

    # Time buffer for blur application (seconds)
    TIME_BUFFER_BEFORE: float = 0.5  # 자막 시작 전 버퍼
    TIME_BUFFER_AFTER: float = 0.8  # 자막 종료 후 버퍼


@dataclass(frozen=True)
class VideoSettings:
    """Video processing settings"""

    # Resolution
    DEFAULT_HEIGHT: int = 1080  # Default video height
    HD_HEIGHT: int = 720
    SD_HEIGHT: int = 480
    LOW_HEIGHT: int = 360

    # Frame rates
    DEFAULT_FPS: float = 30.0  # Default FPS fallback
    MIN_FPS: int = 25  # Minimum FPS for processing

    # Subtitle positioning
    SUBTITLE_Y_THRESHOLD: float = 0.5  # 50% of frame height (subtitle region)

    # Subtitle text limits
    MAX_CHARS_PER_SUBTITLE_LINE: int = 5  # 한 줄당 최대 글자 수 (띄어쓰기 포함)

    # Sampling intervals (seconds)
    SAMPLE_INTERVAL_DEFAULT: float = 0.3  # Default OCR sample interval
    SAMPLE_INTERVAL_CRITICAL: float = 0.1  # Critical period (0-3s) interval
    CRITICAL_PERIOD_DURATION: float = 3.0  # First 3 seconds

    # Ultra-critical sampling (first few frames)
    ULTRA_CRITICAL_FRAMES: int = 4  # Number of frames at t=0s


@dataclass(frozen=True)
class BlurSettings:
    """Blur processing settings"""

    # Kernel sizes
    BASE_KERNEL: int = 25  # Base blur kernel size
    GAUSSIAN_KERNEL: int = 11  # Gaussian blur kernel size

    # Canny edge detection parameters
    CANNY_THRESHOLD_LOW: int = 100  # Low threshold for edge detection
    CANNY_THRESHOLD_HIGH: int = 200  # High threshold for edge detection


@dataclass(frozen=True)
class MemoryLimits:
    """Memory management limits"""

    # Frame cache
    FRAME_CACHE_MAX: int = 100  # Maximum frames to cache

    # Batch processing
    BATCH_SIZE_GPU: int = 32  # Batch size for GPU processing
    BATCH_SIZE_CPU: int = 8  # Batch size for CPU processing

    # Worker pools
    MAX_WORKERS_DEFAULT: int = 1  # Default max workers for parallel processing
    MAX_WORKERS_HIGH: int = 2  # High performance mode


@dataclass(frozen=True)
class TimeWindows:
    """Time window groupings for subtitle analysis"""

    WINDOW_0_5S: float = 0.5  # 0-0.5 second window
    WINDOW_1_0S: float = 1.0  # 0.5-1.0 second window
    WINDOW_1_5S: float = 1.5  # 1.0-1.5 second window
    WINDOW_5_0S: float = 5.0  # 5 second window


@dataclass(frozen=True)
class RetrySettings:
    """Retry and timeout settings"""

    # OCR initialization retries
    OCR_MAX_RETRIES: int = 3  # Maximum OCR initialization attempts
    OCR_RETRY_DELAY: float = 0.5  # Delay between retries (seconds)

    # Network timeouts
    NETWORK_TIMEOUT_SHORT: int = 60  # 1 minute
    NETWORK_TIMEOUT_MEDIUM: int = 120  # 2 minutes
    NETWORK_TIMEOUT_LONG: int = 300  # 5 minutes

    # API retries
    API_MAX_RETRIES: int = 3  # Maximum API call retries


@dataclass(frozen=True)
class UISettings:
    """UI configuration settings"""

    # Font settings
    FONTSIZE: int = 25  # Default font size
    DAESA_GILI: float = 1.1  # Font size multiplier

    # Voice selection
    MAX_VOICE_SELECTION: int = 10  # Maximum voices user can select

    # Progress update interval
    PROGRESS_UPDATE_INTERVAL: int = 10  # Update UI every N frames


@dataclass(frozen=True)
class URLProcessing:
    """URL processing settings"""

    # Queue limits
    MAX_URL_QUEUE_SIZE: int = 30  # Maximum URLs in queue


@dataclass(frozen=True)
class SessionSettings:
    """Session restore settings"""

    # Retry settings
    SESSION_RESTORE_MAX_RETRIES: int = 3  # Maximum retries for session restore
    SESSION_RESTORE_RETRY_DELAY_MS: int = 500  # Delay between retries in milliseconds


@dataclass(frozen=True)
class VideoDurationLimits:
    """Video duration constraints for Douyin short videos"""

    MAX_VIDEO_DURATION_SECONDS: int = 35  # Maximum video duration
    MIN_VIDEO_DURATION_SECONDS: int = 10  # Minimum video duration


@dataclass(frozen=True)
class RateLimiting:
    """Rate limiting settings"""

    LOGIN_ATTEMPTS_RATE_LIMIT: str = "10/minute"  # Login attempts rate limit


@dataclass(frozen=True)
class RemoteURLs:
    """Remote service URLs"""

    REMOTE_SUPPORT_URL: str = "https://desk.zoho.com/support/showticketsforms/e1d19a0f95c95e42e9b5c14e0b44a30de91dac6cc7b5c6a5ddbbbfff0a03b00d"  # Remote support desk URL


@dataclass(frozen=True)
class PathLimits:
    """File path limitations"""

    MAX_PATH_LENGTH: int = 260  # Windows MAX_PATH
    MAX_FILENAME_LENGTH: int = 255  # Maximum filename length


@dataclass(frozen=True)
class WatermarkSettings:
    """Watermark configuration settings"""

    # Position options
    POSITIONS: Tuple[str, ...] = (
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
    )
    DEFAULT_POSITION: str = "bottom_right"

    # Visual settings
    FONT_SIZE_RATIO: float = 0.025  # Font size as ratio of video height
    MIN_FONT_SIZE: int = 20  # Minimum font size in pixels
    MARGIN_RATIO: float = 0.03  # Margin as ratio of video width

    # Color settings (Gray 50% opacity)
    COLOR_R: int = 128  # Red component
    COLOR_G: int = 128  # Green component
    COLOR_B: int = 128  # Blue component
    OPACITY: int = 128  # Alpha (0-255, 128 = 50%)

    # Text limits
    MAX_CHANNEL_NAME_LENGTH: int = 50  # Maximum channel name length


@dataclass(frozen=True)
class GPUSettings:
    """GPU acceleration settings"""

    # CUDA paths (Windows)
    CUDA_PATHS: Tuple[str, ...] = (
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin",
    )

    # Memory limits
    GPU_MEMORY_FRACTION: float = 0.8  # Use 80% of GPU memory


@dataclass(frozen=True)
class GLMOCRSettings:
    """GLM-OCR API settings (Z.ai)"""

    # API Configuration - layout_parsing endpoint (not chat/completions)
    ENDPOINT: str = "https://open.bigmodel.cn/api/paas/v4/layout_parsing"
    MODEL: str = "glm-ocr"

    # Request settings
    TIMEOUT_SECONDS: int = 30
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 1.0

    # Batch processing
    MAX_BATCH_SIZE: int = 20  # Maximum images per API request
    OPTIMAL_BATCH_SIZE: int = 10  # Default batch size for efficiency

    # Image compression
    TARGET_WIDTH: int = 1280  # Resize larger images
    JPEG_QUALITY: int = 85  # Balance quality/size
    MAX_IMAGE_SIZE_KB: int = 500  # Max size per image

    # Cost optimization
    MIN_CONFIDENCE: float = 0.3  # Filter low-confidence results

    # Fallback settings
    OFFLINE_MODE: bool = False  # Force local OCR
    API_FAILURE_THRESHOLD: int = 3  # Switch to local after N failures

    # Rate limiting
    REQUEST_DELAY_MS: int = 50  # Delay between batch requests (ms)
    RATE_LIMIT_WAIT_SECONDS: float = 1.0  # Wait time when rate limited


# === Convenience accessors ===


def get_sample_interval(
    is_critical_period: bool, is_ultra_critical: bool = False
) -> float:
    """
    Get appropriate sample interval based on video period.

    Args:
        is_critical_period: Whether in critical period (0-3s)
        is_ultra_critical: Whether at t=0s (first few frames)

    Returns:
        Sample interval in seconds
    """
    if is_ultra_critical:
        return 0.0  # Sample every frame at t=0
    elif is_critical_period:
        return VideoSettings.SAMPLE_INTERVAL_CRITICAL
    else:
        return VideoSettings.SAMPLE_INTERVAL_DEFAULT


def get_batch_size(use_gpu: bool) -> int:
    """
    Get appropriate batch size based on hardware.

    Args:
        use_gpu: Whether GPU acceleration is available

    Returns:
        Batch size
    """
    if use_gpu:
        return MemoryLimits.BATCH_SIZE_GPU
    else:
        return MemoryLimits.BATCH_SIZE_CPU


def get_max_workers(high_performance: bool = False) -> int:
    """
    Get appropriate number of worker processes.

    Args:
        high_performance: Whether to use high performance mode

    Returns:
        Maximum number of workers
    """
    if high_performance:
        return MemoryLimits.MAX_WORKERS_HIGH
    else:
        return MemoryLimits.MAX_WORKERS_DEFAULT
