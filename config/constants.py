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
    CONFIDENCE_MIN: float = 0.98  # Minimum OCR confidence to accept detection
    TEXT_SIMILARITY: float = 0.001  # Edge change threshold (0.1%)

    # SSIM (Structural Similarity Index) for frame comparison
    SSIM_THRESHOLD: float = 0.98  # 98% similarity to skip frame
    MIN_CONSECUTIVE_SIMILAR: int = 2  # Frames must be similar for N frames to skip

    # Canny edge detection
    EDGE_CHANGE_THRESHOLD: float = 0.001  # 0.1% change threshold
    CANNY_FAST_THRESHOLD: float = 15.0  # Fast threshold for change detection

    # Hybrid detector confirmation
    HYBRID_CONFIRM_THRESHOLD: float = 0.80  # Multi-frame similarity threshold

    # IoU (Intersection over Union) for region merging
    IOU_OVERLAP_THRESHOLD: float = 0.3  # Minimum overlap to merge regions
    IOU_STRICT_THRESHOLD: float = 0.4  # Strict overlap threshold

    # Area ratio thresholds
    AREA_RATIO_MIN: float = 0.35  # Minimum area ratio for region validation
    AREA_RATIO_MAX: float = 0.45  # Maximum area ratio


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
    """Video duration constraints for TikTok/Douyin short videos"""

    MAX_VIDEO_DURATION_SECONDS: int = 39  # Maximum video duration
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
    POSITIONS: Tuple[str, ...] = ("top_left", "top_right", "bottom_left", "bottom_right")
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


# === Convenience accessors ===

def get_sample_interval(is_critical_period: bool, is_ultra_critical: bool = False) -> float:
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
