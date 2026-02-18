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
    # ??SSIM ?ㅽ궢 ?꾩쟾 鍮꾪솢?깊솕: ?먮쭑 ?꾪솚???볦튂吏 ?딅룄濡?
    SSIM_THRESHOLD: float = 1.0  # 100% = effectively disabled skip
    MIN_CONSECUTIVE_SIMILAR: int = 999  # ?ъ떎??鍮꾪솢?깊솕
    SSIM_SKIP_ENABLED: bool = False  # SSIM 湲곕컲 ?꾨젅???ㅽ궢 ?쒖꽦???щ?

    # Canny edge detection
    EDGE_CHANGE_THRESHOLD: float = 0.0005  # 0.05% change threshold (??誘쇨컧?섍쾶)
    CANNY_FAST_THRESHOLD: float = 10.0  # Fast threshold for change detection (誘쇨컧?섍쾶)

    # Hybrid detector confirmation
    HYBRID_CONFIRM_THRESHOLD: float = 0.85  # Multi-frame similarity threshold

    # IoU (Intersection over Union) for region merging
    # ??IoU ?꾧퀎媛???땄: 蹂꾨룄 ?먮쭑??蹂묓빀?섏? ?딅룄濡?
    IOU_CLUSTER_THRESHOLD: float = 0.15  # clustering threshold
    IOU_MERGE_THRESHOLD: float = 0.25  # 蹂묓빀??(??땄: 0.4 -> 0.25)
    IOU_OVERLAP_THRESHOLD: float = 0.15  # Minimum overlap to merge regions
    IOU_STRICT_THRESHOLD: float = 0.25  # Strict overlap threshold

    # Area ratio thresholds
    AREA_RATIO_MIN: float = 0.35  # Minimum area ratio for region validation
    AREA_RATIO_MAX: float = 0.50  # Maximum area ratio (利앷?: 0.45 -> 0.50)

    # ROI (Region of Interest) settings
    # ??ROI ?꾩껜 ?붾㈃ ?ㅼ틪: ?곷떒 ?먮쭑??媛먯??섎룄濡?
    ROI_BOTTOM_PERCENT: float = 100.0  # 100% = full-frame OCR
    ROI_MIN_PERCENT: float = 70.0  # 理쒖냼 70% ?ㅼ틪 蹂댁옣

    # Minimum bbox size (pixels)
    MIN_BBOX_WIDTH: int = 15  # 理쒖냼 諛뺤뒪 ?덈퉬 (??땄: 20 -> 15)
    MIN_BBOX_HEIGHT: int = 6  # 理쒖냼 諛뺤뒪 ?믪씠 (??땄: 8 -> 6)

    # Time buffer for blur application (seconds)
    # ??踰꾪띁 ?뺣?: 0.3珥??섑뵆留?媛꾧꺽?먯꽌 ?먮쭑 ?쒖옉/???꾨젅???꾨씫 諛⑹?
    TIME_BUFFER_BEFORE: float = 0.8  # ?먮쭑 ?쒖옉 ??踰꾪띁 (0.5 -> 0.8)
    TIME_BUFFER_AFTER: float = 1.2  # ?먮쭑 醫낅즺 ??踰꾪띁 (0.8 -> 1.2)

    # Spatial clustering (怨듦컙-?곗꽑 ?대윭?ㅽ꽣留?
    SAME_ROW_MULTIPLIER: float = 0.8  # Same row proximity multiplier
    HORIZONTAL_GAP_THRESHOLD: float = 6.0  # Horizontal gap threshold (%)
    TIME_SEGMENT_GAP: float = 2.0  # ?쒓컙 援ш컙 遺꾪븷 媛?珥?
    SPATIAL_PADDING: float = 2.0  # 怨듦컙 諛붿슫??諛뺤뒪 ?⑤뵫(%)

    # Boundary refinement (寃쎄퀎 ?뺣? ?ъ뒪罹?
    BOUNDARY_MAX_FRAMES: int = 500  # 理쒕? 寃쎄퀎 ?ъ뒪罹??꾨젅????
    # Subtitle vs product text discrimination (?먮쭑 vs ?곹뭹 ?띿뒪??援щ텇)
    # ?먮쭑: ?ㅼ쨷 ?꾨젅?꾩뿉???쇱젙???꾩튂??諛섎났 異쒗쁽
    # ?곹뭹 ?띿뒪?? ?곹뭹 ?대룞???곕씪 ?꾩튂 蹂?????먮룞 ?쒖쇅
    SUBTITLE_MIN_TIME_GROUPS: int = 2  # Minimum time groups to accept subtitle
    SUBTITLE_Y_VARIANCE_MAX: float = 8.0  # Maximum vertical variance (%)
    SUBTITLE_X_VARIANCE_MAX: float = 14.0  # Maximum horizontal variance (%)
    SUBTITLE_SCORE_THRESHOLD: float = 2.5  # Minimum subtitle likelihood score

    # Ultra accuracy mode
    FULL_FRAME_SCAN_MODE: bool = True  # Scan every frame for OCR detection
    PRECISION_POLYGON_BLUR: bool = True  # Apply per-frame polygon mask blur

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
    MAX_CHARS_PER_SUBTITLE_LINE: int = 5  # ??以꾨떦 理쒕? 湲????(?꾩뼱?곌린 ?ы븿)

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

    # Local file protocol
    LOCAL_PROTOCOL: str = "local://"
    ALLOWED_VIDEO_EXTENSIONS: Tuple[str, ...] = (
        ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v",
    )


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

