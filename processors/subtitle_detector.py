"""
Subtitle Detection Processor

This module handles OCR-based Chinese subtitle detection with GPU/NumPy acceleration.
Integrates HybridSubtitleDetector for optimized OCR calls (40% reduction).
"""

import gc
import json
import os
import subprocess
import sys
import tempfile
import threading
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Iterable

# Logging configuration
# 濡쒓퉭 ?ㅼ젙
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Import constants
from config.constants import OCRThresholds, VideoSettings, GLMOCRSettings

try:
    import cv2
    CV2_AVAILABLE = True
except Exception:
    cv2 = None
    CV2_AVAILABLE = False

# OCR 媛?⑹꽦 ?뚮옒洹?(RapidOCR留?吏??
OCR_AVAILABLE = False

# OCRBackend ?섑띁 ?ъ슜 (RapidOCR ?꾩슜)
try:
    from utils.ocr_backend import OCRBackend
    OCR_BACKEND_AVAILABLE = True
    OCR_AVAILABLE = True
except ImportError:
    OCR_BACKEND_AVAILABLE = False

# ?섏씠釉뚮━??媛먯?湲?(Canny + 硫?고봽?덉엫 理쒖쟻??
HYBRID_DETECTOR_AVAILABLE = False
try:
    from realtime_subtitle_optimization import HybridSubtitleDetector, create_hybrid_detector
    HYBRID_DETECTOR_AVAILABLE = True
except ImportError:
    HybridSubtitleDetector = None
    create_hybrid_detector = None

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except Exception:
    np = None
    NUMPY_AVAILABLE = False

# GPU acceleration support
# Graceful fallback to NumPy if CuPy unavailable (Python 3.14+ or no CUDA)
# CuPy ?ъ슜 遺덇? ??NumPy濡??먮룞 ?꾪솚 (Python 3.14+ ?먮뒗 CUDA ?놁쓬)
GPU_ACCEL_AVAILABLE = False
xp = np  # Default to NumPy

try:
    import cupy as cp
    # Test GPU availability - verify CUDA device accessible
    # GPU 媛?⑹꽦 ?뚯뒪??- CUDA ?붾컮?댁뒪 ?묎렐 媛???щ? ?뺤씤
    device_count = cp.cuda.runtime.getDeviceCount()
    if device_count == 0:
        raise RuntimeError("No CUDA devices available")
    # Test memory allocation
    test_array = cp.zeros(100, dtype=cp.float32)
    _ = cp.sum(test_array)
    xp = cp
    GPU_ACCEL_AVAILABLE = True
    # GPU acceleration enabled with CuPy
except Exception:
    xp = np
    GPU_ACCEL_AVAILABLE = False
    # Silently fallback to CPU (NumPy) mode
from caller import ui_controller

# ?쒖뒪??理쒖쟻??紐⑤뱢
try:
    from utils.system_optimizer import get_system_optimizer
    _system_optimizer = None
    def _get_optimizer(gui):
        global _system_optimizer
        if _system_optimizer is None:
            _system_optimizer = get_system_optimizer(gui)
            # System info printed silently
        return _system_optimizer
except ImportError:
    # system_optimizer not found, using default settings
    def _get_optimizer(gui):
        return None




class SubtitleDetector:
    """
    Detects Chinese subtitles in video using OCR with GPU/NumPy acceleration.

    This processor analyzes video frames to locate Chinese subtitle regions
    using RapidOCR with optional GPU acceleration via CuPy.

    Integrates HybridSubtitleDetector for optimized OCR calls:
    - Canny edge-based fast change detection
    - Multi-frame consistency verification
    - Expected 40% reduction in OCR calls
    """

    def __init__(self, gui):
        """
        Initialize the SubtitleDetector.

        Args:
            gui: Main GUI instance containing video file paths and OCR reader
        """
        self.gui = gui
        self.hybrid_detector = None
        self._diagnostics_lock = threading.Lock()
        self.invalid_coordinate_count = 0
        self.review_required = False
        self.review_reasons: List[str] = []
        self._ocr_invalid_coordinate_synced = 0
        self._ocr_request_failure_synced = 0
        self.unresolved_oversized_observations: List[Dict[str, Any]] = []
        self.visual_track_diagnostics: List[Dict[str, Any]] = []
        self._init_hybrid_detector()

    def _reader_invalid_coordinate_count(self) -> int:
        reader = getattr(self.gui, "ocr_reader", None)
        candidates = [reader, getattr(reader, "_glm_client", None)]
        counts = []
        for candidate in candidates:
            try:
                counts.append(max(0, int(getattr(candidate, "invalid_coordinate_count", 0) or 0)))
            except Exception:
                continue
        return max(counts, default=0)

    def _sync_reader_coordinate_diagnostics(self) -> None:
        current = self._reader_invalid_coordinate_count()
        reader = getattr(self.gui, "ocr_reader", None)
        candidates = [reader, getattr(reader, "_glm_client", None)]
        request_failures = 0
        for candidate in candidates:
            try:
                request_failures = max(
                    request_failures,
                    max(0, int(getattr(candidate, "request_failure_count", 0) or 0)),
                )
            except Exception:
                continue
        with self._diagnostics_lock:
            delta = max(0, current - self._ocr_invalid_coordinate_synced)
            self._ocr_invalid_coordinate_synced = max(self._ocr_invalid_coordinate_synced, current)
            request_delta = max(0, request_failures - self._ocr_request_failure_synced)
            self._ocr_request_failure_synced = max(
                self._ocr_request_failure_synced, request_failures
            )
        if delta:
            self._mark_review_required(
                "ocr_reader_invalid_coordinates", invalid_coordinates=delta
            )
        if request_delta:
            self._mark_review_required("ocr_reader_request_failures")

    def _reset_precision_diagnostics(self) -> None:
        """Reset per-video precision diagnostics exposed to the UI/tests."""
        with self._diagnostics_lock:
            self.invalid_coordinate_count = 0
            self.review_required = False
            self.review_reasons = []
            self.unresolved_oversized_observations = []
            self.visual_track_diagnostics = []
            self._ocr_invalid_coordinate_synced = self._reader_invalid_coordinate_count()
            reader = getattr(self.gui, "ocr_reader", None)
            self._ocr_request_failure_synced = max(
                int(getattr(reader, "request_failure_count", 0) or 0),
                int(
                    getattr(
                        getattr(reader, "_glm_client", None),
                        "request_failure_count",
                        0,
                    )
                    or 0
                ),
            )
        try:
            self.gui.ocr_invalid_coordinate_count = 0
            self.gui.ocr_review_required = False
            self.gui.ocr_review_reasons = []
        except Exception:
            pass

    def _mark_review_required(self, reason: str, *, invalid_coordinates: int = 0) -> None:
        """Accumulate non-fatal precision problems without losing valid detections."""
        with self._diagnostics_lock:
            if invalid_coordinates > 0:
                self.invalid_coordinate_count += int(invalid_coordinates)
            self.review_required = True
            if reason and reason not in self.review_reasons:
                self.review_reasons.append(reason)
            invalid_coordinate_count = self.invalid_coordinate_count
            review_reasons = list(self.review_reasons)
        try:
            self.gui.ocr_invalid_coordinate_count = invalid_coordinate_count
            self.gui.ocr_review_required = True
            self.gui.ocr_review_reasons = review_reasons
        except Exception:
            pass

    def _init_hybrid_detector(self):
        """?섏씠釉뚮━??媛먯?湲?珥덇린??(?듭뀡)"""
        if not HYBRID_DETECTOR_AVAILABLE:
            # Hybrid detector not available - fallback to basic mode silently
            return

        ocr_reader = getattr(self.gui, "ocr_reader", None)
        if not ocr_reader:
            # OCR reader not ready - wait for initialization silently
            return

        try:
            # ?쒖뒪??理쒖쟻???뚮씪誘명꽣 媛?몄삤湲?
            optimizer = _get_optimizer(self.gui)
            if optimizer:
                ocr_params = optimizer.get_optimized_ocr_params()
                min_interval = ocr_params.get('sample_interval', 0.3)
            else:
                min_interval = 0.3

            self.hybrid_detector = create_hybrid_detector(
                ocr_reader,
                min_interval=min_interval,
                fast_threshold=15.0,  # Canny edge change threshold
                confirm_threshold=0.80,  # Multi-frame similarity threshold
            )

            # Hybrid detector initialized successfully (silently)
        except Exception as e:
            # Hybrid detector initialization failed - fallback to basic mode silently
            self.hybrid_detector = None

    def _use_batch_ocr(self, *, full_scan_mode: bool) -> bool:
        """Use ordered batch transport whenever the active OCR backend supports it.

        Full-frame precision controls *which* frames are scanned, not whether
        independent GLM requests must be serialized. Keeping these decisions
        separate preserves exhaustive coverage without avoidable network delay.
        """
        ocr_reader = getattr(self.gui, "ocr_reader", None)
        return bool(
            ocr_reader is not None
            and hasattr(ocr_reader, "supports_batch")
            and ocr_reader.supports_batch()
            and getattr(ocr_reader, "engine_name", None) == "glm_ocr"
        )

    @staticmethod
    def _segment_has_frames(
        start_sec: float, end_sec: float, fps: float, total_frames: int
    ) -> bool:
        """Return whether a segment contains any physical source frame."""
        if fps <= 0 or total_frames <= 0 or end_sec <= start_sec:
            return False
        # Segment boundaries are derived with the same rounding rule on both
        # sides.  Truncation can turn ``fps * (total_frames / fps)`` into
        # ``total_frames - 1`` at fractional frame rates and lose the tail.
        start_frame = min(total_frames, max(0, int(round(fps * start_sec))))
        end_frame = min(total_frames, max(0, int(round(fps * end_sec))))
        return start_frame < end_frame

    def detect_subtitles_with_opencv(self):
        """
        OCR-based Chinese subtitle detection with GPU/NumPy acceleration.

        Analyzes video frames at ~0.3-second intervals across 10-second segments
        processed in parallel for faster and more reliable detection.
        Uses GPU acceleration when available via CuPy.

        Returns:
            List of detected subtitle regions with position, confidence, and metadata,
            or None if no Chinese subtitles found
        """
        
        self._reset_precision_diagnostics()
        video_path = getattr(self.gui, 'local_file_path', '') if getattr(self.gui, 'video_source', 'none') == 'local' else getattr(self.gui, '_temp_downloaded_file', None)

        # OCR reader 媛?⑹꽦 ?뺤씤
        ocr_reader = getattr(self.gui, "ocr_reader", None)
        if not ocr_reader:
            logger.warning("[OCR 媛먯?] ocr_reader媛 None - OCR ?놁씠 ?섎떒 ?먮쭑 諛대뱶 ?대갚 媛먯?瑜??쒕룄?⑸땲??")
            fallback = self._fallback_detect_bottom_subtitle_band(video_path)
            return fallback or None

        # Video path determined silently

        # GPU/NumPy acceleration status (silently configured)
        # if GPU_ACCEL_AVAILABLE: using CuPy
        # elif NUMPY_AVAILABLE: using NumPy
        # else: using basic mode

        try:
            import cv2
            import numpy as np
            from concurrent.futures import ThreadPoolExecutor, as_completed

            video_path = getattr(self.gui, 'local_file_path', '') if getattr(self.gui, 'video_source', 'none') == "local" else getattr(self.gui, '_temp_downloaded_file', None)
            if not video_path or not os.path.exists(video_path):
                # Video file not found
                return None

            # 癒쇱? 鍮꾨뵒???뺣낫 ?뺤씤 (try/finally濡?由ъ냼???댁젣 蹂댁옣)
            # Ensure VideoCapture is released even if exception occurs
            cap = cv2.VideoCapture(video_path)
            try:
                if not cap.isOpened():
                    # Cannot open video file
                    return None

                W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                # FPS ?대갚: 硫뷀??곗씠?곌? ?녾굅???좏슚?섏? ?딆쑝硫?30fps濡?媛??                # None, NaN, 0, ?뚯닔 紐⑤몢 泥섎━
                import math
                fps = cap.get(cv2.CAP_PROP_FPS)
                if not fps or not math.isfinite(fps) or fps <= 0:
                    fps = 30.0
                    logger.warning(f"[OCR] FPS metadata missing, using default {fps}fps")

                # ?꾨젅?????대갚: NaN?대㈃ 0?쇰줈 泥섎━
                frame_count_raw = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if not frame_count_raw or not math.isfinite(frame_count_raw) or frame_count_raw < 0:
                    total_frames = 0
                    logger.warning("[OCR] Frame count metadata missing, initialized to 0")
                else:
                    total_frames = int(frame_count_raw)

                total_duration = total_frames / fps if total_frames > 0 else 0

                logger.info(f"[OCR] Video analysis: {W}x{H}, {fps}fps, {total_frames} frames ({total_duration:.1f}s)")
            finally:
                cap.release()

            # ?꾩껜 ?곸긽??10珥??⑥쐞濡?遺꾪븷?섏뿬 紐⑤뱺 援ш컙 寃??
            segments = []
            segment_duration = 10  # 10珥??⑥쐞

            # 0珥덈????곸긽 ?앷퉴吏 10珥??⑥쐞濡?援ш컙 ?앹꽦
            current_start = 0
            segment_idx = 1
            while current_start < total_duration:
                end_sec = min(current_start + segment_duration, total_duration)
                # 理쒖냼 1珥??댁긽??援ш컙留?異붽?
                if self._segment_has_frames(current_start, end_sec, fps, total_frames):
                    segments.append({
                        'name': f"{int(current_start)}-{int(end_sec)}s",
                        'start_sec': current_start,
                        'end_sec': end_sec
                    })
                current_start += segment_duration
                segment_idx += 1

            if not segments:
                # No segments to analyze (video shorter than 1 second)
                return None

            # Parallel segment analysis starting (silently)

            # 蹂묐젹濡?媛?援ш컙 泥섎━
            all_regions_combined = []
            frames_with_chinese_total = 0
            total_sample_frames = 0            # ?쒖뒪??理쒖쟻???ㅼ젙 ?ъ슜
            full_scan_mode = bool(getattr(OCRThresholds, "FULL_FRAME_SCAN_MODE", False))
            optimizer = _get_optimizer(self.gui)
            if full_scan_mode:
                max_workers = 1
                logger.info("[OCR Parallel] Ultra-accuracy mode: sequential segment scan")
            elif optimizer:
                ocr_params = optimizer.get_optimized_ocr_params()
                max_workers = ocr_params['max_workers']
                logger.info(f"[OCR Parallel] System optimized: {max_workers} workers")
            else:
                # 湲곕낯媛?
                max_workers = min(3, len(segments)) if len(segments) > 0 else 1
                logger.info(f"[OCR Parallel] Default config: {max_workers} workers")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_segment = {
                    executor.submit(
                        self._analyze_video_segment,
                        video_path, seg['name'], seg['start_sec'], seg['end_sec'],
                        W, H, fps, total_frames
                    ): seg for seg in segments
                }

                for future in as_completed(future_to_segment):
                    segment = future_to_segment[future]
                    try:
                        result = future.result()
                        if result:
                            all_regions_combined.extend(result['regions'])
                            frames_with_chinese_total += result['frames_with_chinese']
                            total_sample_frames += result['total_frames_checked']
                            logger.debug(f"[OCR Parallel] {segment['name']} done: {result['frames_with_chinese']}/{result['total_frames_checked']} frames with Chinese")
                    except Exception as e:
                        logger.error(f"[OCR Parallel] {segment['name']} processing error: {e}")
                        ui_controller.write_error_log(e)

            # 蹂묐젹 泥섎━ 寃곌낵 ?ъ슜
            all_regions = all_regions_combined
            if full_scan_mode:
                all_regions.extend(
                    self._scan_with_independent_local_ocr(
                        video_path,
                        fps=fps,
                        total_frames=total_frames,
                        W=W,
                        H=H,
                    )
                )
                all_regions.extend(
                    self._scan_with_independent_corner_ocr(
                        video_path,
                        fps=fps,
                        total_frames=total_frames,
                        W=W,
                        H=H,
                    )
                )
                if all_regions:
                    all_regions = self._augment_static_visual_tracks(
                        video_path,
                        all_regions,
                        fps=fps,
                        total_frames=total_frames,
                        W=W,
                        H=H,
                    )
            frames_with_chinese = frames_with_chinese_total
            sample_frames_count = total_sample_frames
            self._sync_reader_coordinate_diagnostics()

            # 寃곌낵 遺꾩꽍
            if not all_regions:
                # No Chinese subtitles detected in any segment
                fallback = self._fallback_detect_bottom_subtitle_band(video_path, W=W, H=H, fps=fps, total_frames=total_frames)
                return fallback or None

            # Chinese subtitles detected (processing silently)

            # ?끸쁾??媛쒖꽑: 媛먯? 鍮꾩쑉 ?꾧퀎移?1%濡??섑뼢 (珥덈?媛?紐⑤뱶) ?끸쁾??            # ??1媛??꾨젅?꾩씠?쇰룄 以묎뎅?닿? 媛먯??섎㈃ 釉붾윭 泥섎━
            detection_rate = frames_with_chinese / sample_frames_count if sample_frames_count > 0 else 0

            # 理쒖냼 1媛??꾨젅?꾩뿉??以묎뎅?닿? 媛먯??섏뿀?쇰㈃ 釉붾윭 ?곸슜
            if frames_with_chinese == 0:
                logger.info("[OCR Parallel] No Chinese detected in any frame - trying fallback band detection")
                fallback = self._fallback_detect_bottom_subtitle_band(video_path, W=W, H=H, fps=fps, total_frames=total_frames)
                return fallback or None
            elif detection_rate < 0.01:
                # 1% 誘몃쭔?댁뼱??媛먯????꾨젅?꾩씠 ?덉쑝硫?寃쎄퀬留?異쒕젰?섍퀬 吏꾪뻾
                logger.warning(f"[OCR Parallel] Very low Chinese detection rate: {detection_rate*100:.2f}% ({frames_with_chinese} frames)")
                logger.info("[OCR Parallel] Subtitles may only appear in some segments - proceeding with blur")
            else:
                logger.info(f"[OCR Parallel] Chinese detection rate: {detection_rate*100:.1f}% - proceeding with blur")

            # ===== GPU/NumPy 媛?? 鍮덈룄 湲곕컲 ?꾪꽣留?=====
            accel_name = "GPU Accel" if GPU_ACCEL_AVAILABLE else "NumPy Accel"
            logger.debug(f"[{accel_name}] Region aggregation starting - {len(all_regions)} regions")
            reliable_regions = self._gpu_aggregate_regions(
                all_regions, fps=fps, total_duration=total_duration
            )

            if not reliable_regions:
                logger.debug(f'[OCR {accel_name}] No trusted subtitle region found - using fallback with spatial clustering')
                # Fallback: create clusters directly from raw regions.
                if all_regions:
                    clusters = []
                    for region in all_regions:
                        added_to_cluster = False
                        for cluster in clusters:
                            representative = cluster[0]
                            iou = self._calculate_iou(region, representative)
                            # ??IoU ?꾧퀎媛???땄: 蹂꾨룄 ?먮쭑??蹂묓빀?섏? ?딅룄濡?(0.3 -> 0.15)
                            if iou > OCRThresholds.IOU_CLUSTER_THRESHOLD:
                                cluster.append(region)
                                added_to_cluster = True
                                break
                        if not added_to_cluster:
                            clusters.append([region])

                    logger.debug(f'[Fallback] {len(all_regions)} regions -> {len(clusters)} clusters created')

                    # 媛??대윭?ㅽ꽣留덈떎 蹂꾨룄??fallback ?곸뿭 ?앹꽦
                    for cluster_idx, cluster in enumerate(clusters):
                        if NUMPY_AVAILABLE:
                            try:
                                if GPU_ACCEL_AVAILABLE:
                                    xs = xp.array([r['x'] for r in cluster])
                                    ys = xp.array([r['y'] for r in cluster])
                                    widths = xp.array([r['width'] for r in cluster])
                                    heights = xp.array([r['height'] for r in cluster])
                                    min_x = max(0, int(xp.min(xs).get()) - 2)
                                    min_y = max(0, int(xp.min(ys).get()) - 2)
                                    max_x = min(100, int(xp.max(xs + widths).get()) + 2)
                                    max_y = min(100, int(xp.max(ys + heights).get()) + 2)
                                else:
                                    xs = np.array([r['x'] for r in cluster])
                                    ys = np.array([r['y'] for r in cluster])
                                    widths = np.array([r['width'] for r in cluster])
                                    heights = np.array([r['height'] for r in cluster])
                                    min_x = max(0, int(np.min(xs)) - 2)
                                    min_y = max(0, int(np.min(ys)) - 2)
                                    max_x = min(100, int(np.max(xs + widths)) + 2)
                                    max_y = min(100, int(np.max(ys + heights)) + 2)
                            except Exception:
                                xs = [r['x'] for r in cluster]
                                ys = [r['y'] for r in cluster]
                                widths = [r['width'] for r in cluster]
                                heights = [r['height'] for r in cluster]
                                min_x = max(0, min(xs) - 2)
                                min_y = max(0, min(ys) - 2)
                                max_x = min(100, max(x + w for x, w in zip(xs, widths)) + 2)
                                max_y = min(100, max(y + h for y, h in zip(ys, heights)) + 2)
                        else:
                            xs = [r['x'] for r in cluster]
                            ys = [r['y'] for r in cluster]
                            widths = [r['width'] for r in cluster]
                            heights = [r['height'] for r in cluster]
                            min_x = max(0, min(xs) - 2)
                            min_y = max(0, min(ys) - 2)
                            max_x = min(100, max(x + w for x, w in zip(xs, widths)) + 2)
                            max_y = min(100, max(y + h for y, h in zip(ys, heights)) + 2)

                        source_name = 'fallback_region_gpu' if GPU_ACCEL_AVAILABLE else 'fallback_region_numpy'
                        # ??Fallback ?곸뿭?먮룄 ?쒓컙 踰붿쐞 異붽? (?꾩껜 ?곸긽 而ㅻ쾭)
                        cluster_times = sorted(set(r.get('time', 0) for r in cluster))
                        fb_start = max(0.0, min(cluster_times) - OCRThresholds.TIME_BUFFER_BEFORE) if cluster_times else 0.0
                        fb_end = min(total_duration, max(cluster_times) + OCRThresholds.TIME_BUFFER_AFTER) if cluster_times else total_duration
                        fallback_region = {
                            'x': min_x,
                            'y': min_y,
                            'width': max(5, max_x - min_x),
                            'height': max(5, max_y - min_y),
                            'frequency': len(cluster),
                            'language': 'unknown',
                            'source': source_name,
                            'sample_text': next((r.get('text') for r in cluster if r.get('text')), ''),
                            'fallback_cluster': cluster_idx,
                            'start_time': fb_start,
                            'end_time': fb_end,
                            'y_positions': [float(r.get('y', 0)) for r in cluster],
                            'x_positions': [float(r.get('x', 0)) for r in cluster],
                            'time_group_count': len(set(round(r.get('time', 0) * 2) / 2 for r in cluster)),
                            'invalid_coordinate_count': self.invalid_coordinate_count,
                            'review_required': self.review_required,
                            'review_reasons': list(self.review_reasons),
                            'frame_regions': [
                                {
                                    'time': float(r.get('time', 0)),
                                    'frame_index': int(r.get('frame_index', -1)),
                                    'polygon': r.get('polygon'),
                                    'text': str(r.get('text', '')),
                                    'confidence': float(r.get('confidence', 0.0)),
                                }
                                for r in cluster
                                if r.get('polygon')
                            ],
                        }
                        reliable_regions.append(fallback_region)
                        logger.debug(f"  Fallback region #{cluster_idx+1}: pos=({min_x:.0f}%, {min_y:.0f}%), size=({max_x-min_x:.0f}%, {max_y-min_y:.0f}%)")

            logger.info(f"[OCR] Finalized {len(reliable_regions)} Chinese subtitle region(s)")
            for i, region in enumerate(reliable_regions, 1):
                logger.debug(f"  Region {i}: X={region['x']}%, Y={region['y']}%, Size={region['width']}%x{region['height']}% (count: {region['frequency']})")

            return reliable_regions

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[OCR Error] {str(e)}")
            logger.exception("OCR detection failed")
            return None
        finally:
            # Clean up memory: force garbage collection
            gc.collect()
            # Memory cleanup completed silently

    def _fallback_detect_bottom_subtitle_band(
        self,
        video_path: Optional[str],
        *,
        W: Optional[int] = None,
        H: Optional[int] = None,
        fps: Optional[float] = None,
        total_frames: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        OCR ?놁씠???섎떒 ?먮쭑 諛대뱶瑜?媛먯??섎뒗 ?대갚.

        紐⑺몴:
        - ?ъ슜??PC??OCR ?붿쭊???녾굅??OCR 珥덇린???ㅽ뙣 ?ы븿),
          OCR??以묎뎅?대? ??紐??쎈뒗 ?곹솴?먯꽌??"釉붾윭媛 ?꾩삁 ???섎뒗" ?곹솴??諛⑹?.

        諛⑹떇:
        - ?곸긽?먯꽌 紐??꾨젅?꾩쓣 ?섑뵆留?        - ?섎떒 ROI(湲곕낯 72%~95%)???ｌ? 諛?꾨? 怨꾩궛
        - ?띿뒪???먮쭑泥섎읆 怨좎＜???ｌ?)媛 吏?띿쟻?쇰줈 ?섑??섎㈃ ?섎떒 諛대뱶瑜?釉붾윭 ??곸쑝濡?諛섑솚
        """
        if not bool(getattr(OCRThresholds, "ENABLE_BROAD_BOTTOM_BAND_FALLBACK", False)):
            self._mark_review_required("broad_bottom_band_fallback_disabled")
            logger.warning(
                "[Fallback] Broad bottom-band blur is disabled for precision mode; manual review is required."
            )
            return None

        self._mark_review_required("broad_bottom_band_fallback_used")
        if not video_path or not isinstance(video_path, str) or not os.path.exists(video_path):
            return None
        if not CV2_AVAILABLE:
            return None

        try:
            import cv2
            import numpy as np
            import math

            cap = cv2.VideoCapture(video_path)
            try:
                if not cap.isOpened():
                    return None

                if W is None:
                    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                if H is None:
                    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                if fps is None:
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    if not fps or not math.isfinite(fps) or fps <= 0:
                        fps = 30.0

                if total_frames is None:
                    fc = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    total_frames = int(fc) if fc and math.isfinite(fc) and fc > 0 else 0

                duration = (total_frames / fps) if (total_frames and fps) else 0.0

                if not W or not H or total_frames <= 0:
                    return None

                sample_n = 8
                idxs = np.linspace(0, max(total_frames - 1, 0), num=sample_n, dtype=int).tolist()
                y1 = int(H * 0.72)
                y2 = int(H * 0.95)
                if y2 <= y1:
                    return None

                edge_ratios = []
                for fi in idxs:
                    try:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
                        ok, frame = cap.read()
                        if not ok or frame is None:
                            continue
                        roi = frame[y1:y2, :]
                        if roi.size == 0:
                            continue
                        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        if gray.shape[1] > 640:
                            scale = 640.0 / float(gray.shape[1])
                            gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                        edges = cv2.Canny(gray, 50, 150)
                        ratio = float(np.count_nonzero(edges)) / float(edges.size)
                        edge_ratios.append(ratio)
                    except Exception:
                        continue

                if len(edge_ratios) < 3:
                    return None

                avg = sum(edge_ratios) / len(edge_ratios)
                # Empirical threshold: subtitles tend to produce sustained edge density.
                if avg < 0.012:
                    return None

                logger.info(
                    f"[Fallback] Bottom-band subtitle edges detected (avg_edge_ratio={avg:.4f}); applying band blur fallback."
                )

                region = {
                    "x": 0.0,
                    "y": 72.0,
                    "width": 100.0,
                    "height": 23.0,
                    "start_time": 0.0,
                    "end_time": float(duration) if duration and duration > 0 else None,
                    "text": "",
                    "sample_text": "",
                    "language": "",
                    "confidence": 0.25,
                    "source": "fallback_region_edges",
                    "review_required": True,
                    "review_reasons": list(self.review_reasons),
                }
                return [region]
            finally:
                cap.release()
        except Exception:
            return None

    def _filter_chinese_regions(self, subtitle_positions: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Filter subtitle positions to only include Chinese text regions.

        Args:
            subtitle_positions: List of detected subtitle regions

        Returns:
            Filtered list containing only Chinese subtitle regions
        """
        logger.debug("=" * 60)
        logger.debug("[BLUR FILTER] Starting Chinese subtitle filtering")
        logger.debug("=" * 60)

        filtered: List[Dict[str, Any]] = []
        if not subtitle_positions:
            logger.debug("[BLUR FILTER] No input regions - returning empty list")
            return filtered

        subtitle_positions_list = list(subtitle_positions)
        logger.debug(f"[BLUR FILTER] Input region count: {len(subtitle_positions_list)}")

        chinese_tokens = {
            "chinese", "zh", "zh-cn", "zh-tw", "zh-hans", "zh-hant",
            "cn", "han", "以묎뎅", "以묐Ц"
        }

        for idx, entry in enumerate(subtitle_positions_list):
            if not isinstance(entry, dict):
                logger.debug(f"[BLUR FILTER] #{idx+1}: Not a dict - excluded")
                continue

            lang = str(entry.get('language', '') or '').strip().lower()
            text = str(entry.get('text', '') or '').strip()
            sample = str(entry.get('sample_text', '') or '').strip()
            source = str(entry.get('source', '') or '').strip().lower()

            reason = None
            if lang and any(token in lang for token in chinese_tokens):
                reason = f"language tag matched: {lang}"
                filtered.append(entry)
            elif text and any('\u4e00' <= ch <= '\u9fff' for ch in text):
                chinese_in_text = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
                reason = f"chinese chars in text: {chinese_in_text}"
                filtered.append(entry)
            elif sample and any('\u4e00' <= ch <= '\u9fff' for ch in sample):
                chinese_in_sample = sum(1 for ch in sample if '\u4e00' <= ch <= '\u9fff')
                reason = f"chinese chars in sample: {chinese_in_sample}"
                filtered.append(entry)
            elif source in {'rapidocr', 'rapidocr_gpu', 'opencv_ocr', 'opencv_ocr_gpu', 'opencv_ocr_numpy'} and not lang:
                reason = f"OCR source without language: {source}"
                filtered.append(entry)
            elif source.startswith("fallback_region"):
                reason = "fallback subtitle band source"
                filtered.append(entry)
            else:
                logger.debug(f"[BLUR FILTER] #{idx+1}: Not Chinese - excluded (lang={lang}, text='{text[:30]}...', source={source})")
                continue

            logger.debug(f"[BLUR FILTER] #{idx+1}: Identified as Chinese ({reason})")

        logger.debug(f"[BLUR FILTER] First filter passed: {len(filtered)} regions")

        safe_filtered: List[Dict[str, Any]] = []
        for idx, entry in enumerate(filtered):
            try:
                x_pct = float(entry.get('x') or 0)
                y_pct = float(entry.get('y') or 0)
                width_pct = float(entry.get('width') or 0)
                height_pct = float(entry.get('height') or 0)
            except (TypeError, ValueError):
                x_pct = y_pct = width_pct = height_pct = 0.0

            text_preview = str(entry.get('text', '') or '')[:20]
            logger.debug(f"[BLUR FILTER] Validation #{idx+1}: '{text_preview}...'")
            logger.debug(f"  Position: x={x_pct:.1f}%, y={y_pct:.1f}%")
            logger.debug(f"  Size: w={width_pct:.1f}%, h={height_pct:.1f}%")

            area_ratio = (width_pct / 100.0) * (height_pct / 100.0)
            exact_polygon_chinese = bool(entry.get("frame_regions")) and bool(
                any("\u4e00" <= char <= "\u9fff" for char in f"{text}{sample}")
                or "chinese" in lang
                or lang.startswith("zh")
            )
            if (area_ratio > 0.35 or height_pct > 45.0) and not exact_polygon_chinese:
                self._mark_review_required(
                    "oversized_region_without_exact_chinese_polygon"
                )
                logger.debug(f"  -> Excluded: Region too large (area={area_ratio*100:.1f}%, height={height_pct:.1f}%)")
                self.gui.add_log(f"[釉붾윭] ?섏떖?ㅻ윭?????곸뿭???쒖쇅?⑸땲?? "
                             f"w={width_pct:.1f}%, h={height_pct:.1f}% (source={entry.get('source')})")
                continue

            # ?끸쁾???먮쭑 vs ?곹뭹 ?띿뒪??援щ텇 (?ㅼ쨷 ?꾨젅??+ ?꾩튂 ?덉젙??
            source = str(entry.get('source') or '')

            # Fallback ?곸뿭? 蹂꾨룄 泥섎━ (OCR ?대갚)
            if source.startswith('fallback_region'):
                sample_text = str(entry.get('sample_text', '') or '')
                has_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in sample_text)
                if not has_chinese and sample_text.strip():
                    logger.debug(f"  -> Excluded: Fallback region with non-Chinese text: '{sample_text[:20]}'")
                    continue
                logger.debug(f"  -> Fallback region accepted: sample_text='{sample_text[:20] if sample_text else '(empty)'}'")
                logger.debug("  -> Final pass OK (fallback)")
                safe_filtered.append(entry)
                continue

            # --- ?먮쭑 ?먮퀎: ?ㅼ쨷 ?꾨젅??異쒗쁽 + ?꾩튂 ?쇱젙 ---
            time_group_count = entry.get('time_group_count', 1)
            y_positions = entry.get('y_positions', [])
            region_start_time = entry.get('start_time', 999)
            sample_text = str(entry.get('text', '') or entry.get('sample_text', ''))
            explicit_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in sample_text)
            max_confidence = float(
                entry.get('max_confidence', entry.get('confidence', 0.0)) or 0.0
            )
            high_confidence_chinese = bool(entry.get('high_confidence_chinese')) or (
                explicit_chinese
                and max_confidence >= OCRThresholds.HIGH_CONFIDENCE_CHINESE
            )

            # 議곌굔 1: ?ㅼ쨷 ?쒓컙 洹몃９(?꾨젅???먯꽌 異쒗쁽?댁빞 ?먮쭑
            # ???? ?곸긽 ?쒖옉 遺遺?~1珥?? 硫댁젣: ?쒓컙 洹몃９??異⑸텇???볦씠吏 ?딆쑝誘濡?
            is_early_region = region_start_time <= 1.0
            if (
                time_group_count < OCRThresholds.SUBTITLE_MIN_TIME_GROUPS
                and not is_early_region
                and not high_confidence_chinese
            ):
                logger.debug(f"  -> Excluded: ?⑥씪 ?꾨젅??異쒗쁽 (time_groups={time_group_count} < {OCRThresholds.SUBTITLE_MIN_TIME_GROUPS}) ???곹뭹 ?띿뒪?몃줈 ?먯젙")
                self.gui.add_log(f"[釉붾윭] ?곹뭹 ?띿뒪???쒖쇅: ?⑥씪 ?꾨젅??異쒗쁽 ('{str(entry.get('text', '') or str(entry.get('sample_text', '')))[:15]}...')")
                continue
            if is_early_region and time_group_count < OCRThresholds.SUBTITLE_MIN_TIME_GROUPS:
                logger.debug(f"  -> ?곸긽 ?쒖옉 援ш컙 硫댁젣: start_time={region_start_time:.1f}s, time_groups={time_group_count} (MIN_TIME_GROUPS 議곌굔 硫댁젣)")

            # 議곌굔 2: Y醫뚰몴 ?꾩튂媛 ?쇱젙?댁빞 ?먮쭑 (?곹뭹? ?吏곸씠誘濡??꾩튂 遺덉븞??
            y_std = 0.0
            if y_positions and len(y_positions) >= 2:
                try:
                    y_std = float(np.std(y_positions)) if NUMPY_AVAILABLE else (
                        (sum((y - sum(y_positions) / len(y_positions)) ** 2 for y in y_positions) / len(y_positions)) ** 0.5
                    )
                except Exception:
                    y_std = 0.0

                if y_std > OCRThresholds.SUBTITLE_Y_VARIANCE_MAX and not high_confidence_chinese:
                    logger.debug(
                        f"  -> Excluded: unstable Y (std={y_std:.1f}% > {OCRThresholds.SUBTITLE_Y_VARIANCE_MAX}%)"
                    )
                    self.gui.add_log(
                        f"[블러] 상품 텍스트 제외: Y 변동 큼 (std={y_std:.1f}%, '{str(entry.get('text', '') or str(entry.get('sample_text', '')))[:15]}...')"
                    )
                    continue
                logger.debug(
                    f"  -> Y stability OK: std={y_std:.1f}% (limit={OCRThresholds.SUBTITLE_Y_VARIANCE_MAX}%)"
                )

            x_positions = entry.get('x_positions', [])
            x_std = 0.0
            if x_positions and len(x_positions) >= 2:
                try:
                    x_std = float(np.std(x_positions)) if NUMPY_AVAILABLE else (
                        (sum((x - sum(x_positions) / len(x_positions)) ** 2 for x in x_positions) / len(x_positions)) ** 0.5
                    )
                except Exception:
                    x_std = 0.0
                if x_std > OCRThresholds.SUBTITLE_X_VARIANCE_MAX and not high_confidence_chinese:
                    logger.debug(f"  -> Excluded: X unstable (X std={x_std:.1f}% > {OCRThresholds.SUBTITLE_X_VARIANCE_MAX}%)")
                    continue

            # Multi-feature subtitle scoring for smarter product-text separation.
            score = 0.0
            score += 2.0 if time_group_count >= 3 else (1.0 if time_group_count >= 2 else -1.0)
            score += 1.5 if y_std <= (OCRThresholds.SUBTITLE_Y_VARIANCE_MAX * 0.5) else 0.5
            score += 1.0 if x_std <= (OCRThresholds.SUBTITLE_X_VARIANCE_MAX * 0.5) else 0.0
            if x_std > 0 and x_std <= OCRThresholds.SUBTITLE_X_VARIANCE_MAX:
                score += 0.5
            chinese_chars = sum(1 for ch in sample_text if '\u4e00' <= ch <= '\u9fff')
            score += 1.0 if chinese_chars >= 2 else (0.5 if chinese_chars >= 1 else 0.0)
            score += 0.5 if float(entry.get('frequency', 0) or 0) >= 3 else 0.0
            if is_early_region and time_group_count < OCRThresholds.SUBTITLE_MIN_TIME_GROUPS:
                score += 0.5
            if score < OCRThresholds.SUBTITLE_SCORE_THRESHOLD and not high_confidence_chinese:
                logger.debug(f"  -> Excluded: low subtitle score ({score:.2f} < {OCRThresholds.SUBTITLE_SCORE_THRESHOLD})")
                continue

            logger.debug(f"  -> ?먮쭑?쇰줈 ?먯젙: {time_group_count}媛??꾨젅??異쒗쁽, ?꾩튂 ?덉젙, score={score:.2f}")
            logger.debug("  -> Final pass OK")
            safe_filtered.append(entry)

        logger.debug("=" * 60)
        logger.info(f"[BLUR FILTER] Final blur targets: {len(safe_filtered)} regions (filtered from {len(filtered)} Chinese regions)")
        for i, entry in enumerate(safe_filtered):
            tg = entry.get('time_group_count', '?')
            yp = entry.get('y_positions', [])
            y_std_str = ""
            if yp and len(yp) >= 2:
                try:
                    y_std_val = float(np.std(yp)) if NUMPY_AVAILABLE else 0.0
                    y_std_str = f", Y?몄감={y_std_val:.1f}%"
                except Exception:
                    pass
            logger.debug(f"  #{i+1}: x={entry.get('x')}%, y={entry.get('y')}%, w={entry.get('width')}%, h={entry.get('height')}%, frames={tg}{y_std_str}, text='{str(entry.get('text', '') or entry.get('sample_text', ''))[:30]}...'")
        if len(filtered) > len(safe_filtered):
            excluded = len(filtered) - len(safe_filtered)
            logger.info(f"[BLUR FILTER] {excluded} regions excluded as product text (?⑥씪?꾨젅???꾩튂遺덉븞??")
        logger.debug("=" * 60)

        return safe_filtered

    def _update_korean_subtitle_layout(self, subtitle_positions):
        """
        Update Korean subtitle layout strategy based on Chinese subtitle positions.

        Args:
            subtitle_positions: List of Chinese subtitle regions
        """
        self.gui.korean_subtitle_override = None
        self.gui.korean_subtitle_mode = 'default'

        if not subtitle_positions:
            logger.debug('[Korean subtitle] No Chinese subtitle position - keeping default position.')
            return

        try:
            centered = []
            if hasattr(self.gui, 'prepare_centered_subtitle_layout'):
                centered = self.gui.prepare_centered_subtitle_layout(subtitle_positions)
            else:
                centered = list(subtitle_positions or [])

            if centered:
                return

            logger.debug('[Korean subtitle] Could not calculate centered region. Keeping default position.')
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[Korean subtitle] Error during centered layout: {e}")

    # ========== GPU/NumPy 媛???좏떥由ы떚 ?⑥닔 ==========

    def _gpu_check_chinese_chars(self, texts):
        """
        GPU/NumPy accelerated Chinese character counting.

        Args:
            texts: List of text strings

        Returns:
            List of Chinese character counts for each text
        """
        if not NUMPY_AVAILABLE:
            # NumPy ?놁쑝硫??쇰컲 諛⑹떇
            return [sum(1 for c in text if '\u4e00' <= c <= '\u9fff') for text in texts]

        try:
            # 媛??띿뒪?몄쓽 以묎뎅??臾몄옄 媛쒖닔 怨꾩궛
            counts = []
            for text in texts:
                # ?좊땲肄붾뱶 ?ъ씤?몃줈 蹂????踰붿쐞 泥댄겕
                if GPU_ACCEL_AVAILABLE:
                    try:
                        # GPU 媛??踰꾩쟾
                        unicode_points = xp.array([ord(c) for c in text], dtype=xp.int32)
                        is_chinese = (unicode_points >= 0x4e00) & (unicode_points <= 0x9fff)
                        count = int(xp.sum(is_chinese))
                    except (RuntimeError, AttributeError):
                        # CuPy ?ㅽ뻾 以??ㅻ쪟 諛쒖깮 ??NumPy濡??대갚
                        unicode_points = np.array([ord(c) for c in text], dtype=np.int32)
                        is_chinese = (unicode_points >= 0x4e00) & (unicode_points <= 0x9fff)
                        count = int(np.sum(is_chinese))
                else:
                    # NumPy 踰꾩쟾
                    unicode_points = np.array([ord(c) for c in text], dtype=np.int32)
                    is_chinese = (unicode_points >= 0x4e00) & (unicode_points <= 0x9fff)
                    count = int(np.sum(is_chinese))
                counts.append(count)
            return counts
        except Exception as e:
            ui_controller.write_error_log(e)
            # ?ㅻ쪟 ???쇰컲 諛⑹떇?쇰줈 ?대갚
            return [sum(1 for c in text if '\u4e00' <= c <= '\u9fff') for text in texts]

    def _normalize_polygon(self, bbox, W, H):
        """Normalize OCR polygon points into clamped pixel coordinates."""
        if not bbox:
            return []
        polygon = []
        for point in bbox:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                px = float(point[0])
                py = float(point[1])
            except (TypeError, ValueError):
                continue
            px = max(0.0, min(float(W - 1), px))
            py = max(0.0, min(float(H - 1), py))
            polygon.append([round(px, 2), round(py, 2)])
        if len(polygon) < 3:
            return []
        return polygon

    @staticmethod
    def _snap_polygon_to_near_frame_edges(polygon, W, H):
        """Include glyph fragments clipped by a nearby physical frame edge.

        OCR boxes commonly begin a few pixels inside the image when the first
        glyph of a watermark/subtitle is itself clipped by the video boundary.
        Expanding only a small, bounded near-edge box to that same edge avoids
        leaving the readable fragment behind without broadening interior masks.
        """
        if not polygon or not W or not H:
            return polygon or []
        try:
            xs = [float(point[0]) for point in polygon]
            ys = [float(point[1]) for point in polygon]
        except (TypeError, ValueError, IndexError):
            return polygon
        edge_x = max(4, min(32, int(round(float(W) * 0.025))))
        edge_y = max(4, min(32, int(round(float(H) * 0.025))))
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        snapped_x1 = 0.0 if x1 <= edge_x else x1
        snapped_y1 = 0.0 if y1 <= edge_y else y1
        snapped_x2 = float(W - 1) if x2 >= (W - 1 - edge_x) else x2
        snapped_y2 = float(H - 1) if y2 >= (H - 1 - edge_y) else y2
        if (snapped_x1, snapped_y1, snapped_x2, snapped_y2) == (x1, y1, x2, y2):
            return polygon
        return [
            [round(snapped_x1, 2), round(snapped_y1, 2)],
            [round(snapped_x2, 2), round(snapped_y1, 2)],
            [round(snapped_x2, 2), round(snapped_y2, 2)],
            [round(snapped_x1, 2), round(snapped_y2, 2)],
        ]

    @staticmethod
    def _independent_box_is_tight_line(info):
        """Trust a precise all-frame OCR polygon for a shallow full-width line."""
        if not isinstance(info, dict):
            return False
        return bool(float(info.get("height", 100.0) or 100.0) <= 15.0)

    def _gpu_process_bbox_batch(self, bboxes, W, H):
        """Return one processed result per input bbox, preserving alignment."""
        if not bboxes:
            return []

        regions: List[Optional[Dict[str, Any]]] = [None] * len(bboxes)
        if not NUMPY_AVAILABLE or not W or not H:
            self._mark_review_required(
                "bbox_processing_unavailable", invalid_coordinates=len(bboxes)
            )
            return regions

        use_gpu = GPU_ACCEL_AVAILABLE
        for index, bbox in enumerate(bboxes):
            invalid_reason = "invalid_bbox_coordinates"
            try:
                if bbox is None or len(bbox) < 4:
                    raise ValueError("bbox requires at least four points")

                if use_gpu:
                    try:
                        coords = xp.asarray(bbox, dtype=xp.float32)
                        if coords.ndim != 2 or coords.shape[1] < 2:
                            raise ValueError("bbox must contain xy points")
                        if not bool(xp.all(xp.isfinite(coords)).get()):
                            raise ValueError("bbox contains non-finite values")
                        x_min_f = float(xp.min(coords[:, 0]).get())
                        y_min_f = float(xp.min(coords[:, 1]).get())
                        x_max_f = float(xp.max(coords[:, 0]).get())
                        y_max_f = float(xp.max(coords[:, 1]).get())
                    except Exception:
                        use_gpu = False
                        coords = np.asarray(bbox, dtype=np.float32)
                        if coords.ndim != 2 or coords.shape[1] < 2 or not np.all(np.isfinite(coords)):
                            raise ValueError("bbox contains invalid coordinates")
                        x_min_f = float(np.min(coords[:, 0]))
                        y_min_f = float(np.min(coords[:, 1]))
                        x_max_f = float(np.max(coords[:, 0]))
                        y_max_f = float(np.max(coords[:, 1]))
                else:
                    coords = np.asarray(bbox, dtype=np.float32)
                    if coords.ndim != 2 or coords.shape[1] < 2 or not np.all(np.isfinite(coords)):
                        raise ValueError("bbox contains invalid coordinates")
                    x_min_f = float(np.min(coords[:, 0]))
                    y_min_f = float(np.min(coords[:, 1]))
                    x_max_f = float(np.max(coords[:, 0]))
                    y_max_f = float(np.max(coords[:, 1]))

                x_min = max(0, min(int(W), int(np.floor(x_min_f))))
                y_min = max(0, min(int(H), int(np.floor(y_min_f))))
                x_max = max(0, min(int(W), int(np.ceil(x_max_f))))
                y_max = max(0, min(int(H), int(np.ceil(y_max_f))))
                width = x_max - x_min
                height = y_max - y_min

                if width < OCRThresholds.MIN_BBOX_WIDTH or height < OCRThresholds.MIN_BBOX_HEIGHT:
                    invalid_reason = "bbox_below_minimum_size"
                    raise ValueError(invalid_reason)
                # Large multi-line banners are valid OCR targets.  Their exact
                # polygon is safer than silently dropping the text and claiming
                # a successful render; downstream filtering still rejects broad
                # heuristic fallback bands that have no per-frame polygon.
                oversized = bool(width > W * 0.98 or height > H * 0.5)

                regions[index] = {
                    'x': round(100.0 * x_min / W, 1),
                    'y': round(100.0 * y_min / H, 1),
                    'width': max(0.5, round(100.0 * width / W, 1)),
                    'height': max(0.5, round(100.0 * height / H, 1)),
                    'x_min': x_min,
                    'y_min': y_min,
                    'x_max': x_max,
                    'y_max': y_max,
                    'oversized': oversized,
                }
            except Exception:
                if invalid_reason in {
                    "bbox_below_minimum_size",
                }:
                    # A valid coordinate can still be intentionally rejected by
                    # the subtitle-size safety policy.  Do not misreport that as
                    # a malformed OCR contract or fail a precision render.
                    logger.debug("[BBox] Rejected by size policy: %s", invalid_reason)
                else:
                    self._mark_review_required(invalid_reason, invalid_coordinates=1)

        return regions

    def _calculate_iou(self, box1, box2):
        """Calculate IoU (Intersection over Union) between two boxes."""
        x1_min, y1_min = box1['x'], box1['y']
        x1_max, y1_max = x1_min + box1['width'], y1_min + box1['height']
        x2_min, y2_min = box2['x'], box2['y']
        x2_max, y2_max = x2_min + box2['width'], y2_min + box2['height']

        # Intersection
        inter_xmin = max(x1_min, x2_min)
        inter_ymin = max(y1_min, y2_min)
        inter_xmax = min(x1_max, x2_max)
        inter_ymax = min(y1_max, y2_max)

        if inter_xmin >= inter_xmax or inter_ymin >= inter_ymax:
            return 0.0

        inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
        box1_area = box1['width'] * box1['height']
        box2_area = box2['width'] * box2['height']
        union_area = box1_area + box2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    def _repair_oversized_observations(self, all_regions, fps):
        """Replace imprecise page-scale GLM boxes with nearby text-matched boxes."""
        regions = [item for item in (all_regions or []) if isinstance(item, dict)]
        normal = [item for item in regions if not item.get("oversized")]
        if not normal:
            if any(item.get("oversized") for item in regions):
                self._mark_review_required("oversized_ocr_bbox_without_precise_anchor")
            return regions

        max_time_delta = max(1.0, 6.0 / max(float(fps or 30.0), 1.0))
        repaired = []
        for region in regions:
            if not region.get("oversized"):
                repaired.append(region)
                continue

            oversized_text = "".join(
                char
                for char in str(region.get("text", "") or "")
                if "\u4e00" <= char <= "\u9fff" or char.isalnum()
            )
            oversized_parts = [
                "".join(
                    char
                    for char in line
                    if "\u4e00" <= char <= "\u9fff" or char.isalnum()
                )
                for line in str(region.get("text", "") or "").splitlines()
            ]
            oversized_parts = [part for part in oversized_parts if len(part) >= 2]
            region_time = float(region.get("time", 0.0) or 0.0)
            scene_id = region.get("scene_id")
            candidates = []
            for candidate in normal:
                time_delta = abs(float(candidate.get("time", 0.0) or 0.0) - region_time)
                if time_delta > max_time_delta:
                    continue
                same_physical_frame = bool(
                    int(candidate.get("frame_index", -2))
                    == int(region.get("frame_index", -1))
                )
                if candidate.get("scene_id") != scene_id and not same_physical_frame:
                    continue
                candidate_text = "".join(
                    char
                    for char in str(candidate.get("text", "") or "")
                    if "\u4e00" <= char <= "\u9fff" or char.isalnum()
                )
                if len(candidate_text) < 2 or not oversized_text:
                    continue
                matcher = SequenceMatcher(None, oversized_text, candidate_text)
                longest = matcher.find_longest_match(
                    0, len(oversized_text), 0, len(candidate_text)
                ).size
                is_substring = candidate_text in oversized_text
                sequence_ratio = matcher.ratio()
                independent_anchor = str(candidate.get("source", "") or "").startswith(
                    "rapidocr_"
                )
                candidate_center_x = float(candidate.get("x", 0.0)) + float(
                    candidate.get("width", 0.0)
                ) / 2.0
                candidate_center_y = float(candidate.get("y", 0.0)) + float(
                    candidate.get("height", 0.0)
                ) / 2.0
                inside_oversized = bool(
                    float(region.get("x", 0.0)) <= candidate_center_x
                    <= float(region.get("x", 0.0)) + float(region.get("width", 0.0))
                    and float(region.get("y", 0.0)) <= candidate_center_y
                    <= float(region.get("y", 0.0)) + float(region.get("height", 0.0))
                )
                layout_only_anchor = bool(
                    independent_anchor and same_physical_frame and inside_oversized
                )
                if not is_substring and not layout_only_anchor and (
                    longest < 2
                    or (sequence_ratio < 0.55 and not independent_anchor)
                ):
                    continue
                candidates.append(
                    (
                        time_delta,
                        candidate,
                        candidate_text,
                        matcher,
                        is_substring,
                        layout_only_anchor,
                    )
                )

            # An oversized layout belongs to one source frame.  Mixing anchors
            # from the whole +/-1 second window can replicate unrelated labels
            # that merely share a common character.  Keep only the closest
            # timestamp group (one decoder frame of tolerance).
            if candidates:
                closest_delta = min(item[0] for item in candidates)
                same_frame_tolerance = 1.5 / max(float(fps or 30.0), 1.0)
                candidates = [
                    item
                    for item in candidates
                    if item[0] <= closest_delta + same_frame_tolerance
                ]

            anchors = []
            anchor_texts = []
            anchor_layout_flags = []
            covered_indices = set()
            ambiguous = False
            for (
                _time_delta,
                candidate,
                candidate_text,
                matcher,
                is_substring,
                layout_only_anchor,
            ) in sorted(
                candidates, key=lambda item: item[0]
            ):
                same_anchor = any(
                    self._calculate_iou(candidate, existing) > 0.2
                    for existing in anchors
                )
                if same_anchor:
                    continue
                if candidate_text in anchor_texts:
                    # The same phrase at multiple disjoint locations is
                    # ambiguous unless the combined OCR text itself contains
                    # multiple copies in the same order.
                    if oversized_text.count(candidate_text) <= anchor_texts.count(
                        candidate_text
                    ):
                        ambiguous = True
                        continue
                anchors.append(candidate)
                anchor_texts.append(candidate_text)
                anchor_layout_flags.append(layout_only_anchor)
                if is_substring:
                    search_from = 0
                    while True:
                        start = oversized_text.find(candidate_text, search_from)
                        if start < 0:
                            break
                        covered_indices.update(
                            range(start, min(len(oversized_text), start + len(candidate_text)))
                        )
                        search_from = start + 1
                else:
                    for block in matcher.get_matching_blocks():
                        if block.size >= 2:
                            covered_indices.update(
                                range(block.a, min(len(oversized_text), block.a + block.size))
                            )

            coverage = (
                len(covered_indices) / len(oversized_text)
                if oversized_text
                else 0.0
            )
            if (
                len(oversized_parts) >= 1
                and sum(1 for value in anchor_layout_flags if value)
                >= len(oversized_parts)
            ):
                # A second engine confirmed at least the same number of
                # spatially distinct Chinese layout items on the exact
                # physical frame.  This applies to a single line as well as a
                # multi-line document box: stylized text can be recognized
                # differently by the two engines while the independent pixel
                # polygon remains a precise layout anchor.  The exact-frame
                # requirement above prevents borrowing unrelated text from a
                # nearby frame or across a scene cut.
                coverage = 1.0
            if anchors and coverage >= 0.75 and not ambiguous:
                for anchor in anchors:
                    clone = dict(anchor)
                    clone.update(
                        {
                            "time": region_time,
                            "frame_index": int(region.get("frame_index", -1)),
                            "scene_id": scene_id,
                            "source": "oversized_bbox_repaired",
                            "oversized": False,
                            "repaired_from_oversized": True,
                            "independent_chinese": bool(
                                str(anchor.get("source", "") or "").startswith(
                                    "rapidocr_"
                                )
                            ),
                        }
                    )
                    repaired.append(clone)
            else:
                reason = (
                    "oversized_ocr_bbox_ambiguous_anchor"
                    if ambiguous
                    else "oversized_ocr_bbox_without_precise_anchor"
                )
                self._mark_review_required(reason)
                self.unresolved_oversized_observations.append(
                    {
                        "time": region_time,
                        "frame_index": int(region.get("frame_index", -1)),
                        "scene_id": scene_id,
                        "text": str(region.get("text", "") or "")[:200],
                        "candidate_count": len(candidates),
                        "coverage": round(float(coverage), 4),
                        "ambiguous": bool(ambiguous),
                    }
                )
                # Never render the unresolved page-scale polygon.  It is kept
                # out of the automatic blur path and the diagnostic forces a
                # manual/retry decision instead of obscuring most of the frame.
        return repaired

    @staticmethod
    def _normalized_track_text(value: Any) -> str:
        return "".join(
            char
            for char in str(value or "")
            if "\u4e00" <= char <= "\u9fff" or char.isalnum()
        ).casefold()

    @staticmethod
    def _visual_track_signature(crop):
        """Return a normalized high-pass signature for a tight OCR crop."""
        if crop is None or not getattr(crop, "size", 0):
            return None
        try:
            gray = (
                cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                if len(crop.shape) == 3
                else crop
            ).astype(np.float32)
            gray = cv2.resize(gray, (128, 48), interpolation=cv2.INTER_AREA)
            high_pass = gray - cv2.GaussianBlur(gray, (0, 0), 2.0)
            high_pass -= float(high_pass.mean())
            norm = float(np.linalg.norm(high_pass))
            if not np.isfinite(norm) or norm < 1e-5:
                return None
            return high_pass / norm
        except Exception:
            return None

    @staticmethod
    def _fill_short_visual_gaps(flags: List[bool], max_gap: int) -> List[bool]:
        """Fill only short false runs that are bounded by visual matches."""
        filled = list(flags)
        index = 0
        while index < len(filled):
            if filled[index]:
                index += 1
                continue
            start = index
            while index < len(filled) and not filled[index]:
                index += 1
            if (
                start > 0
                and index < len(filled)
                and (index - start) <= max(0, int(max_gap))
            ):
                for gap_index in range(start, index):
                    filled[gap_index] = True
        return filled

    @staticmethod
    def _extend_visual_match_edges(
        flags: List[bool], scores: List[float], max_frames: int, threshold: float
    ) -> List[bool]:
        """Extend strong visual components only over adjacent weaker matches.

        Tiny moving labels often fade or slide into view for a few frames
        before OCR becomes readable.  A bounded hysteresis edge follows the
        actual pixel similarity while avoiding a blind temporal buffer.
        Scene isolation is applied by the caller before this helper runs.
        """
        extended = list(flags)
        limit = max(0, int(max_frames))
        original = list(flags)
        index = 0
        while index < len(original):
            if not original[index]:
                index += 1
                continue
            start = index
            while index < len(original) and original[index]:
                index += 1
            end = index
            for distance in range(1, limit + 1):
                left = start - distance
                if left < 0 or float(scores[left]) < float(threshold):
                    break
                extended[left] = True
            for distance in range(limit):
                right = end + distance
                if right >= len(original) or float(scores[right]) < float(threshold):
                    break
                extended[right] = True
        return extended

    @staticmethod
    def _stable_compact_track_envelope(track, frame_width, frame_height):
        """Return a padded full-label envelope for a stable local OCR track."""
        if not track or frame_width <= 0 or frame_height <= 0:
            return None
        if not any(
            str(item.get("region", {}).get("source", "") or "")
            == "rapidocr_independent"
            for item in track
        ):
            return None
        boxes = [item.get("box") for item in track if item.get("box")]
        if not boxes:
            return None
        centers_x = [(box[0] + box[2]) / 2.0 for box in boxes]
        centers_y = [(box[1] + box[3]) / 2.0 for box in boxes]
        x1 = int(max(0, round(min(box[0] for box in boxes) - 3)))
        y1 = int(max(0, round(min(box[1] for box in boxes) - 3)))
        x2 = int(min(frame_width - 1, round(max(box[2] for box in boxes) + 3)))
        y2 = int(min(frame_height - 1, round(max(box[3] for box in boxes) + 3)))
        if (
            x2 <= x1
            or y2 <= y1
            or (x2 - x1) > frame_width * 0.25
            or (y2 - y1) > frame_height * 0.18
            or (max(centers_x) - min(centers_x))
            > max(12.0, (x2 - x1) * 0.75)
            or (max(centers_y) - min(centers_y))
            > max(10.0, (y2 - y1) * 0.75)
        ):
            return None
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    def _augment_static_visual_tracks(
        self, video_path, all_regions, fps, total_frames, W, H
    ):
        """Fill OCR misses only where a stable subtitle is visibly present.

        GLM can miss an animated badge on alternating animation phases even
        during exhaustive scanning.  This pass builds high-pass templates from
        exact OCR observations, then adds a polygon only on source frames whose
        tight crop matches that template bank.  Long unbounded time extension
        is deliberately forbidden: every inferred frame belongs to a connected
        visual-match component containing at least one exact OCR observation.
        """
        regions = [item for item in (all_regions or []) if isinstance(item, dict)]
        if (
            not CV2_AVAILABLE
            or not NUMPY_AVAILABLE
            or not video_path
            or not os.path.exists(video_path)
            or not fps
            or fps <= 0
            or total_frames <= 0
        ):
            return regions

        candidates = []
        for region in regions:
            if region.get("oversized") or not region.get("polygon"):
                continue
            text = self._normalized_track_text(region.get("text"))
            if not text or not any("\u4e00" <= char <= "\u9fff" for char in text):
                continue
            try:
                frame_index = int(region.get("frame_index", -1))
                polygon = self._normalize_polygon(region.get("polygon"), W, H)
            except Exception:
                continue
            if frame_index < 0 or frame_index >= total_frames or not polygon:
                continue
            xs = [point[0] for point in polygon]
            ys = [point[1] for point in polygon]
            candidates.append(
                {
                    "region": region,
                    "text": text,
                    "frame_index": frame_index,
                    "box": [min(xs), min(ys), max(xs), max(ys)],
                }
            )
        if len(candidates) < 3:
            return regions

        def box_iou(left, right):
            x1 = max(left[0], right[0])
            y1 = max(left[1], right[1])
            x2 = min(left[2], right[2])
            y2 = min(left[3], right[3])
            intersection = max(0, x2 - x1) * max(0, y2 - y1)
            left_area = max(1, (left[2] - left[0]) * (left[3] - left[1]))
            right_area = max(1, (right[2] - right[0]) * (right[3] - right[1]))
            return intersection / float(left_area + right_area - intersection)

        tracks = []
        for candidate in sorted(candidates, key=lambda item: item["frame_index"]):
            assigned = False
            for track in tracks:
                track_match = False
                # Animated stickers can alternate between boxes that do not
                # overlap on consecutive frames.  Compare against the track's
                # recent template bank, not only its immediately previous box.
                for representative in reversed(track[-48:]):
                    matcher = SequenceMatcher(
                        None, candidate["text"], representative["text"]
                    )
                    text_related = bool(
                        candidate["text"] in representative["text"]
                        or representative["text"] in candidate["text"]
                        or matcher.ratio() >= 0.65
                    )
                    candidate_box = candidate["box"]
                    representative_box = representative["box"]
                    candidate_width = max(1, candidate_box[2] - candidate_box[0])
                    candidate_height = max(1, candidate_box[3] - candidate_box[1])
                    representative_width = max(
                        1, representative_box[2] - representative_box[0]
                    )
                    representative_height = max(
                        1, representative_box[3] - representative_box[1]
                    )
                    center_close = bool(
                        abs(
                            (candidate_box[0] + candidate_box[2]) / 2.0
                            - (representative_box[0] + representative_box[2]) / 2.0
                        )
                        <= max(candidate_width, representative_width) * 1.25
                        and abs(
                            (candidate_box[1] + candidate_box[3]) / 2.0
                            - (representative_box[1] + representative_box[3]) / 2.0
                        )
                        <= max(candidate_height, representative_height) * 1.25
                    )
                    spatially_related = bool(
                        box_iou(candidate_box, representative_box) >= 0.15
                        or center_close
                    )
                    both_independent = bool(
                        str(candidate["region"].get("source", "") or "").startswith(
                            "rapidocr_"
                        )
                        and str(
                            representative["region"].get("source", "") or ""
                        ).startswith("rapidocr_")
                    )
                    width_ratio = max(candidate_width, representative_width) / max(
                        1.0, min(candidate_width, representative_width)
                    )
                    height_ratio = max(candidate_height, representative_height) / max(
                        1.0, min(candidate_height, representative_height)
                    )
                    independent_center_close = bool(
                        abs(
                            (candidate_box[0] + candidate_box[2]) / 2.0
                            - (representative_box[0] + representative_box[2]) / 2.0
                        )
                        <= max(16.0, min(candidate_width, representative_width) * 0.85)
                        and abs(
                            (candidate_box[1] + candidate_box[3]) / 2.0
                            - (representative_box[1] + representative_box[3]) / 2.0
                        )
                        <= max(10.0, min(candidate_height, representative_height) * 0.85)
                        and width_ratio <= 2.5
                        and height_ratio <= 2.5
                    )
                    independent_visual_match = bool(
                        width_ratio <= 2.5
                        and height_ratio <= 2.5
                        and (
                            box_iou(candidate_box, representative_box) >= 0.20
                            or independent_center_close
                        )
                    )
                    frame_gap = int(candidate["frame_index"]) - int(
                        representative["frame_index"]
                    )
                    # Independent OCR can vary one glyph between adjacent
                    # frames (e.g. 如意/如惠), but a merely similar box much
                    # later in the same long scene is not the same track.
                    # The old spatial-only rule merged unrelated labels into
                    # an oversized envelope, disabling visual onset recovery.
                    independent_text_continuity = bool(
                        text_related
                        or (
                            0 <= frame_gap <= 6
                            and box_iou(candidate_box, representative_box) >= 0.50
                        )
                    )
                    independent_temporal_continuity = bool(
                        0 <= frame_gap <= max(6, int(round(float(fps))))
                    )
                    if (
                        both_independent
                        and candidate["region"].get("scene_id")
                        == representative["region"].get("scene_id")
                        and independent_visual_match
                        and independent_text_continuity
                        and independent_temporal_continuity
                    ) or (
                        not both_independent
                        and spatially_related
                        and text_related
                    ):
                        track_match = True
                        break
                if track_match:
                    track.append(candidate)
                    assigned = True
                    break
            if not assigned:
                tracks.append([candidate])

        inferred = []
        self.visual_track_diagnostics = []
        for track in tracks:
            exact_frames = sorted({item["frame_index"] for item in track})
            if len(exact_frames) < 3:
                continue
            independent_track = any(
                str(item["region"].get("source", "") or "").startswith("rapidocr_")
                for item in track
            )
            centers_x = [(item["box"][0] + item["box"][2]) / 2.0 for item in track]
            centers_y = [(item["box"][1] + item["box"][3]) / 2.0 for item in track]
            x1 = int(max(0, round(min(item["box"][0] for item in track) - 3)))
            y1 = int(max(0, round(min(item["box"][1] for item in track) - 3)))
            x2 = int(min(W - 1, round(max(item["box"][2] for item in track) + 3)))
            y2 = int(min(H - 1, round(max(item["box"][3] for item in track) + 3)))
            if x2 <= x1 or y2 <= y1:
                continue
            if (x2 - x1) > W * 0.85 or (y2 - y1) > H * 0.40:
                continue
            envelope_polygon = self._stable_compact_track_envelope(track, W, H)
            stable_compact_envelope = bool(envelope_polygon)

            # Preserve temporal and animation diversity without unbounded
            # memory/API cost.
            seed_frames = exact_frames
            if len(seed_frames) > 24:
                sample_indices = np.linspace(0, len(seed_frames) - 1, 24, dtype=int)
                seed_frames = [seed_frames[int(index)] for index in sample_indices]
            templates = []
            cap = cv2.VideoCapture(video_path)
            try:
                # Frame-index seeking is not exact on VFR media: OpenCV may
                # seek by the stream's average FPS and return a neighboring
                # decoded frame.  OCR observations and rendering both use the
                # sequential decode order, so collect templates in that same
                # order to keep the visual onset aligned frame-for-frame.
                seed_frame_set = set(int(value) for value in seed_frames)
                last_seed_frame = max(seed_frame_set, default=-1)
                seed_items_by_frame = {
                    seed_frame: min(
                        track,
                        key=lambda item: abs(item["frame_index"] - seed_frame),
                    )
                    for seed_frame in seed_frame_set
                }
                sequential_index = 0
                while sequential_index <= last_seed_frame:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    if sequential_index not in seed_frame_set:
                        sequential_index += 1
                        continue
                    signature = self._visual_track_signature(frame[y1:y2, x1:x2])
                    if signature is not None:
                        seed_item = seed_items_by_frame[sequential_index]
                        seed_polygon = self._normalize_polygon(
                            seed_item["region"].get("polygon"), W, H
                        )
                        if seed_polygon:
                            templates.append((signature, seed_polygon))
                    sequential_index += 1
            finally:
                cap.release()
            if not templates:
                continue

            scores = []
            matched_polygons = []
            frame_times = []
            visual_scene_ids = []
            visual_scene_counter = 0
            previous_scene_frame = None
            cap = cv2.VideoCapture(video_path)
            previous_time = None
            try:
                for frame_index in range(total_frames):
                    ok, frame = cap.read()
                    if not ok:
                        scores.append(float("-inf"))
                        matched_polygons.append(None)
                        frame_times.append(frame_index / float(fps))
                        visual_scene_ids.append(visual_scene_counter)
                        continue
                    if self._is_scene_cut(previous_scene_frame, frame):
                        visual_scene_counter += 1
                    previous_scene_frame = frame
                    visual_scene_ids.append(visual_scene_counter)
                    frame_time = self._frame_time_after_read(
                        cap, frame_index, fps, previous_time=previous_time
                    )
                    previous_time = frame_time
                    signature = self._visual_track_signature(frame[y1:y2, x1:x2])
                    if signature is None:
                        score = float("-inf")
                        matched_polygon = None
                    else:
                        scored_templates = [
                            (float(np.sum(signature * template[0])), template[1])
                            for template in templates
                        ]
                        score, matched_polygon = max(
                            scored_templates, key=lambda item: item[0]
                        )
                    scores.append(score)
                    matched_polygons.append(matched_polygon)
                    frame_times.append(frame_time)
            finally:
                cap.release()

            matched = [score >= 0.68 for score in scores]
            for frame_index in exact_frames:
                if 0 <= frame_index < len(matched):
                    matched[frame_index] = True
            # Fill only inside a visual scene.  A matching logo-like crop on
            # both sides of a hard cut must never bridge the scene boundary.
            scene_start = 0
            while scene_start < len(matched):
                scene_end = scene_start + 1
                while (
                    scene_end < len(matched)
                    and visual_scene_ids[scene_end]
                    == visual_scene_ids[scene_start]
                ):
                    scene_end += 1
                scene_flags = self._fill_short_visual_gaps(
                    matched[scene_start:scene_end],
                    max_gap=max(2, int(round(float(fps) * 0.12))),
                )
                scene_flags = self._extend_visual_match_edges(
                    scene_flags,
                    scores[scene_start:scene_end],
                    max_frames=max(1, int(round(float(fps) * 0.10))),
                    threshold=0.55,
                )
                matched[scene_start:scene_end] = scene_flags
                scene_start = scene_end

            exact_set = set(exact_frames)
            keep = [False] * len(matched)
            index = 0
            while index < len(matched):
                if not matched[index]:
                    index += 1
                    continue
                start = index
                scene_id = visual_scene_ids[index]
                while (
                    index < len(matched)
                    and matched[index]
                    and visual_scene_ids[index] == scene_id
                ):
                    index += 1
                if any(frame in exact_set for frame in range(start, index)):
                    for frame in range(start, index):
                        keep[frame] = True

            self.visual_track_diagnostics.append(
                {
                    "texts": sorted({item["text"] for item in track})[:12],
                    "exact_count": len(exact_frames),
                    "first_exact": exact_frames[0],
                    "last_exact": exact_frames[-1],
                    "box": [x1, y1, x2, y2],
                    "template_count": len(templates),
                    "matched_count": sum(1 for value in matched if value),
                    "kept_count": sum(1 for value in keep if value),
                    "inferred_count": sum(
                        1
                        for frame_index, value in enumerate(keep)
                        if value and frame_index not in exact_set
                    ),
                    "score_min": round(
                        min((score for score in scores if np.isfinite(score)), default=-1.0),
                        4,
                    ),
                    "score_max": round(
                        max((score for score in scores if np.isfinite(score)), default=-1.0),
                        4,
                    ),
                    "stable_compact_envelope": stable_compact_envelope,
                }
            )

            exact_scene_by_frame = {
                item["frame_index"]: item["region"].get("scene_id") for item in track
            }
            representative_region = max(
                track,
                key=lambda item: float(item["region"].get("confidence", 0.0) or 0.0),
            )["region"]
            for frame_index, should_keep in enumerate(keep):
                if not should_keep or frame_index in exact_set:
                    continue
                nearest_exact = min(exact_frames, key=lambda value: abs(value - frame_index))
                scene_id = exact_scene_by_frame.get(nearest_exact)
                polygon = matched_polygons[frame_index]
                if stable_compact_envelope:
                    polygon = envelope_polygon
                if not polygon:
                    continue
                polygon_xs = [point[0] for point in polygon]
                polygon_ys = [point[1] for point in polygon]
                polygon_x1, polygon_x2 = min(polygon_xs), max(polygon_xs)
                polygon_y1, polygon_y2 = min(polygon_ys), max(polygon_ys)
                inferred.append(
                    {
                        "x": round(100.0 * polygon_x1 / W, 4),
                        "y": round(100.0 * polygon_y1 / H, 4),
                        "width": round(100.0 * (polygon_x2 - polygon_x1) / W, 4),
                        "height": round(100.0 * (polygon_y2 - polygon_y1) / H, 4),
                        "oversized": False,
                        "confidence": float(
                            representative_region.get("confidence", 1.0) or 1.0
                        ),
                        "time": float(frame_times[frame_index]),
                        "frame_index": frame_index,
                        "text": str(representative_region.get("text", "") or ""),
                        "language": "chinese",
                        "source": (
                            "rapidocr_visual_inferred"
                            if independent_track
                            else "visual_track_inferred"
                        ),
                        "polygon": polygon,
                        "scene_id": scene_id,
                        "visual_match_score": float(scores[frame_index]),
                    }
                )

        if inferred:
            logger.info(
                "[OCR visual tracking] Added %d frame-backed observations across %d tracks",
                len(inferred),
                len(tracks),
            )
        return regions + inferred

    def _scan_with_independent_local_ocr(
        self, video_path: str, fps: float, total_frames: int, W: int, H: int
    ) -> List[Dict[str, Any]]:
        """Run all-frame RapidOCR in an isolated process and normalize boxes."""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts",
            "independent_rapidocr_source_scan.py",
        )
        if not os.path.isfile(script_path):
            self._mark_review_required("independent_source_ocr_script_missing")
            return []
        result_path = None
        try:
            handle = tempfile.NamedTemporaryFile(
                prefix="precision_source_ocr_", suffix=".json", delete=False
            )
            result_path = handle.name
            handle.close()
            command = [sys.executable, script_path, video_path, result_path]
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            if process.stdout is not None:
                for line in process.stdout:
                    if line.strip():
                        logger.info(line.rstrip())
            return_code = process.wait()
            try:
                with open(result_path, "r", encoding="utf-8") as result_file:
                    payload = json.load(result_file)
            except Exception:
                payload = None
            if (
                return_code != 0
                or not isinstance(payload, dict)
                or not payload.get("ok")
                or int(payload.get("scanned_frames", -1)) != int(total_frames)
            ):
                self._mark_review_required("independent_source_ocr_failed")
                return []

            normalized = []
            for item in payload.get("regions") or []:
                polygon = item.get("polygon") if isinstance(item, dict) else None
                normalized_polygon = self._normalize_polygon(polygon, W, H)
                normalized_polygon = self._snap_polygon_to_near_frame_edges(
                    normalized_polygon, W, H
                )
                processed = self._gpu_process_bbox_batch([normalized_polygon], W, H)
                if not processed or processed[0] is None or not normalized_polygon:
                    continue
                info = processed[0]
                # A high-confidence independent OCR line can legitimately span
                # almost the entire frame width.  Width alone previously marked
                # these shallow banners as page-scale failures and dropped the
                # exact polygon (case: 98.4% wide, 6.5% high Chinese caption).
                oversized = bool(info.get("oversized", False))
                if oversized and self._independent_box_is_tight_line(info):
                    oversized = False
                normalized.append(
                    {
                        "x": info["x"],
                        "y": info["y"],
                        "width": info["width"],
                        "height": info["height"],
                        "oversized": oversized,
                        "confidence": float(item.get("confidence", 0.0) or 0.0),
                        "time": float(item.get("time", 0.0) or 0.0),
                        "frame_index": int(item.get("frame_index", -1)),
                        "text": str(item.get("text", "") or ""),
                        "language": "chinese",
                        "source": "rapidocr_independent",
                        "polygon": normalized_polygon,
                        "scene_id": str(item.get("scene_id", "rapidocr:0") or "rapidocr:0"),
                    }
                )
            logger.info(
                "[OCR independent source] Added %d exact observations",
                len(normalized),
            )
            return normalized
        except Exception as exc:
            logger.warning("[OCR independent source] Failed: %s", type(exc).__name__)
            self._mark_review_required("independent_source_ocr_failed")
            return []
        finally:
            if result_path:
                try:
                    os.unlink(result_path)
                except OSError:
                    pass

    def _scan_with_independent_corner_ocr(
        self, video_path: str, fps: float, total_frames: int, W: int, H: int
    ) -> List[Dict[str, Any]]:
        """Run a cached 3x top-corner OCR pass for small rotated labels."""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts",
            "independent_rapidocr_corner_scan.py",
        )
        if not os.path.isfile(script_path):
            self._mark_review_required("independent_corner_ocr_script_missing")
            return []
        result_path = None
        try:
            handle = tempfile.NamedTemporaryFile(
                prefix="precision_corner_ocr_", suffix=".json", delete=False
            )
            result_path = handle.name
            handle.close()
            command = [sys.executable, script_path, video_path, result_path]
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            if process.stdout is not None:
                for line in process.stdout:
                    if line.strip():
                        logger.info(line.rstrip())
            return_code = process.wait()
            try:
                with open(result_path, "r", encoding="utf-8") as result_file:
                    payload = json.load(result_file)
            except Exception:
                payload = None
            if (
                return_code != 0
                or not isinstance(payload, dict)
                or not payload.get("ok")
                or int(payload.get("scanned_frames", -1)) != int(total_frames)
            ):
                self._mark_review_required("independent_corner_ocr_failed")
                return []
            normalized = []
            for item in payload.get("regions") or []:
                polygon = item.get("polygon") if isinstance(item, dict) else None
                normalized_polygon = self._normalize_polygon(polygon, W, H)
                normalized_polygon = self._snap_polygon_to_near_frame_edges(
                    normalized_polygon, W, H
                )
                processed = self._gpu_process_bbox_batch([normalized_polygon], W, H)
                if not processed or processed[0] is None or not normalized_polygon:
                    continue
                info = processed[0]
                normalized.append(
                    {
                        "x": info["x"],
                        "y": info["y"],
                        "width": info["width"],
                        "height": info["height"],
                        "oversized": False,
                        "confidence": float(item.get("confidence", 0.0) or 0.0),
                        "time": float(item.get("time", 0.0) or 0.0),
                        "frame_index": int(item.get("frame_index", -1)),
                        "text": str(item.get("text", "") or ""),
                        "language": "chinese",
                        "source": "rapidocr_corner",
                        "polygon": normalized_polygon,
                        "scene_id": str(
                            item.get("scene_id", "rapidocr:0") or "rapidocr:0"
                        ),
                    }
                )
            logger.info("[OCR independent corner] Added %d observations", len(normalized))
            return normalized
        except Exception as exc:
            logger.warning("[OCR independent corner] Failed: %s", type(exc).__name__)
            self._mark_review_required("independent_corner_ocr_failed")
            return []
        finally:
            if result_path:
                try:
                    os.unlink(result_path)
                except OSError:
                    pass

    def _gpu_aggregate_regions(self, all_regions, fps=None, total_duration=None):
        """Aggregate detections with frame-scale timing and scene boundaries."""
        if not all_regions or not NUMPY_AVAILABLE:
            return []

        import math

        precision_timing = bool(fps and math.isfinite(float(fps)) and float(fps) > 0)
        safe_fps = float(fps) if precision_timing else 30.0
        if precision_timing:
            max_gap = max(1, int(OCRThresholds.PRECISION_MAX_GAP_FRAMES)) / safe_fps
            buffer_before = max(0, int(OCRThresholds.PRECISION_BUFFER_FRAMES)) / safe_fps
            buffer_after = buffer_before
            persistent_gap = max(
                max_gap,
                float(OCRThresholds.PRECISION_PERSISTENT_TRACK_GAP_SECONDS),
            )
        else:
            # Compatibility for direct callers that do not provide video FPS.
            max_gap = float(OCRThresholds.TIME_SEGMENT_GAP)
            buffer_before = float(OCRThresholds.TIME_BUFFER_BEFORE)
            buffer_after = float(OCRThresholds.TIME_BUFFER_AFTER)
            persistent_gap = max_gap

        try:
            spatial_clusters = []
            ordered_regions = sorted(
                self._repair_oversized_observations(all_regions, safe_fps),
                key=lambda item: (float(item.get('time', 0.0)), int(item.get('frame_index', -1))),
            )
            for region in ordered_regions:
                added = False
                region_text = str(region.get('text', '') or '').strip()
                for cluster in spatial_clusters:
                    representative = cluster['representative']
                    iou = self._calculate_iou(region, representative)
                    y_center_region = region['y'] + region['height'] / 2.0
                    y_center_cluster = representative['y'] + representative['height'] / 2.0
                    same_row = abs(y_center_region - y_center_cluster) <= max(
                        region['height'], representative['height']
                    ) * OCRThresholds.SAME_ROW_MULTIPLIER
                    region_right = region['x'] + region['width']
                    representative_right = representative['x'] + representative['width']
                    horizontal_gap = max(
                        0.0,
                        max(region['x'] - representative_right, representative['x'] - region_right),
                    )
                    proximity = same_row and horizontal_gap <= OCRThresholds.HORIZONTAL_GAP_THRESHOLD
                    last_member = cluster['members'][-1]
                    same_scene = region.get('scene_id') == last_member.get('scene_id')
                    close_in_time = (
                        float(region.get('time', 0.0)) - float(last_member.get('time', 0.0))
                    ) <= (max_gap + 1e-6)
                    persistent_close = (
                        float(region.get('time', 0.0)) - float(last_member.get('time', 0.0))
                    ) <= (persistent_gap + 1e-6)
                    same_moving_text = bool(
                        region_text
                        and region_text == str(last_member.get('text', '') or '').strip()
                        and same_scene
                        and persistent_close
                    )
                    same_track_window = same_scene and close_in_time
                    same_size_class = bool(region.get('oversized', False)) == bool(
                        last_member.get('oversized', False)
                    )
                    if same_size_class and (
                        (
                            same_track_window
                            and (
                                iou > OCRThresholds.IOU_CLUSTER_THRESHOLD
                                or proximity
                            )
                        )
                        or same_moving_text
                    ):
                        cluster['members'].append(region)
                        # The latest observation is a better motion-track anchor.
                        cluster['representative'] = {
                            'x': region['x'],
                            'y': region['y'],
                            'width': region['width'],
                            'height': region['height'],
                        }
                        added = True
                        break
                if not added:
                    bbox = {
                        'x': region['x'],
                        'y': region['y'],
                        'width': region['width'],
                        'height': region['height'],
                    }
                    spatial_clusters.append({
                        'representative': dict(bbox),
                        'members': [region],
                    })

            merged_regions = []
            for cluster_index, cluster in enumerate(spatial_clusters):
                members = sorted(
                    cluster['members'],
                    key=lambda item: (float(item.get('time', 0.0)), int(item.get('frame_index', -1))),
                )
                segments = []
                current = []
                for member in members:
                    if current:
                        previous = current[-1]
                        time_gap = float(member.get('time', 0.0)) - float(previous.get('time', 0.0))
                        scene_changed = member.get('scene_id') != previous.get('scene_id')
                        same_text = bool(
                            str(member.get('text', '') or '').strip()
                            and str(member.get('text', '') or '').strip()
                            == str(previous.get('text', '') or '').strip()
                        )
                        persistent_text_gap = same_text and time_gap <= (
                            persistent_gap + 1e-6
                        )
                        if (
                            (time_gap > (max_gap + 1e-6) and not persistent_text_gap)
                            or scene_changed
                        ):
                            segments.append(current)
                            current = []
                    current.append(member)
                if current:
                    segments.append(current)

                for segment_index, seg_members in enumerate(segments):
                    seg_start = min(float(item.get('time', 0.0)) for item in seg_members)
                    seg_end = max(float(item.get('time', 0.0)) for item in seg_members)
                    buffered_start = max(0.0, seg_start - buffer_before)
                    buffered_end = seg_end + buffer_after
                    if total_duration is not None and float(total_duration) > 0:
                        buffered_end = min(float(total_duration), buffered_end)

                    # Recompute the box from this time segment only.  Using the
                    # all-time cluster union caused long moving-caption trails.
                    left = min(float(item['x']) for item in seg_members)
                    top = min(float(item['y']) for item in seg_members)
                    right = max(float(item['x']) + float(item['width']) for item in seg_members)
                    bottom = max(float(item['y']) + float(item['height']) for item in seg_members)
                    pad = OCRThresholds.SPATIAL_PADDING
                    x = max(0.0, left - pad)
                    y = max(0.0, top - pad)
                    right = min(100.0, right + pad)
                    bottom = min(100.0, bottom + pad)

                    confidences = [float(item.get('confidence', 0.0) or 0.0) for item in seg_members]
                    sample_text = next(
                        (str(item.get('text', '')) for item in seg_members if item.get('text')),
                        '',
                    )
                    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in sample_text)
                    has_independent_chinese = any(
                        (
                            str(item.get('source', '') or '').startswith('rapidocr_')
                            or bool(item.get('independent_chinese'))
                        )
                        and any(
                            '\u4e00' <= char <= '\u9fff'
                            for char in str(item.get('text', '') or '')
                        )
                        for item in seg_members
                    )
                    max_confidence = max(confidences) if confidences else 0.0
                    scene_ids = []
                    frame_regions = []
                    for member in seg_members:
                        scene_id = member.get('scene_id')
                        if scene_id not in scene_ids:
                            scene_ids.append(scene_id)
                        polygon = member.get('polygon')
                        if polygon:
                            frame_regions.append({
                                'time': float(member.get('time', 0.0)),
                                'frame_index': int(member.get('frame_index', -1)),
                                'polygon': polygon,
                                'text': str(member.get('text', '')),
                                'confidence': float(member.get('confidence', 0.0) or 0.0),
                                'scene_id': scene_id,
                                'source': str(member.get('source', '') or ''),
                                'visual_match_score': member.get('visual_match_score'),
                            })
                    frame_regions.sort(
                        key=lambda item: (item.get('time', 0.0), item.get('frame_index', -1))
                    )
                    distinct_frames = {
                        int(item.get('frame_index', -1))
                        for item in seg_members
                        if int(item.get('frame_index', -1)) >= 0
                    }
                    time_group_count = len(distinct_frames) or len(
                        {round(float(item.get('time', 0.0)), 6) for item in seg_members}
                    )
                    merged_regions.append({
                        'x': x,
                        'y': y,
                        'width': max(1.0, right - x),
                        'height': max(1.0, bottom - y),
                        'frequency': len(seg_members),
                        'language': 'chinese',
                        'source': 'opencv_ocr_gpu' if GPU_ACCEL_AVAILABLE else 'opencv_ocr_numpy',
                        'sample_text': sample_text,
                        'start_time': buffered_start,
                        'end_time': buffered_end,
                        'cluster_id': f"spatial_{cluster_index}_{segment_index}",
                        'y_positions': [float(item.get('y', 0.0)) for item in seg_members],
                        'x_positions': [float(item.get('x', 0.0)) for item in seg_members],
                        'time_group_count': time_group_count,
                        'frame_regions': frame_regions,
                        'scene_id': scene_ids[0] if len(scene_ids) == 1 else None,
                        'scene_ids': scene_ids,
                        'max_confidence': max_confidence,
                        'mean_confidence': float(sum(confidences) / len(confidences)) if confidences else 0.0,
                        'high_confidence_chinese': bool(
                            has_chinese
                            and (
                                max_confidence >= OCRThresholds.HIGH_CONFIDENCE_CHINESE
                                or has_independent_chinese
                            )
                        ),
                        'independent_chinese': has_independent_chinese,
                        'oversized_observation_count': sum(
                            1 for item in seg_members if item.get('oversized')
                        ),
                        'invalid_coordinate_count': self.invalid_coordinate_count,
                        'review_required': self.review_required,
                        'review_reasons': list(self.review_reasons),
                    })

            merged_regions.sort(key=lambda item: (item['start_time'], item['y']))
            logger.info(
                f"[Precision merge] {len(all_regions)} detections -> "
                f"{len(spatial_clusters)} tracks -> {len(merged_regions)} blur regions"
            )
            return merged_regions
        except Exception as exc:
            ui_controller.write_error_log(exc)
            logger.error(f"[Precision merge] Region aggregation error: {exc}")
            return []

    def _frame_time_after_read(self, cap, frame_index, fps, previous_time=None):
        """Prefer the decoder timestamp after ``read`` and enforce monotonicity."""
        import math

        safe_fps = float(fps) if fps and math.isfinite(float(fps)) and float(fps) > 0 else 30.0
        fallback = max(0.0, float(frame_index) / safe_fps)
        reported = None
        try:
            msec = float(cap.get(cv2.CAP_PROP_POS_MSEC))
            if math.isfinite(msec) and msec >= 0:
                reported = msec / 1000.0
                if int(frame_index) > 0 and reported <= 0.0:
                    reported = None
        except Exception:
            reported = None

        candidate = reported if reported is not None else fallback
        if previous_time is not None and candidate <= float(previous_time):
            candidate = max(fallback, float(previous_time) + (1.0 / safe_fps))
        return candidate

    @staticmethod
    def _read_scheduled_frame(cap, frame_pos: int, next_expected_frame: Optional[int]):
        """Read consecutive scheduled frames without redundant decoder seeks."""
        if next_expected_frame != int(frame_pos):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_pos))
        ok, frame = cap.read()
        return ok, frame, (int(frame_pos) + 1 if ok else None)

    def _is_scene_cut(self, previous_frame, current_frame):
        """Deterministic low-cost cut detector for interpolation boundaries."""
        if previous_frame is None or current_frame is None or not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return False
        try:
            def _gray160(frame):
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
                height, width = gray.shape[:2]
                if width != 160:
                    target_h = max(1, int(round(height * (160.0 / max(1, width)))))
                    gray = cv2.resize(gray, (160, target_h), interpolation=cv2.INTER_AREA)
                return gray

            gray_a = _gray160(previous_frame)
            gray_b = _gray160(current_frame)
            if gray_a.shape != gray_b.shape:
                gray_b = cv2.resize(gray_b, (gray_a.shape[1], gray_a.shape[0]), interpolation=cv2.INTER_AREA)
            mad = float(np.mean(np.abs(gray_a.astype(np.float32) - gray_b.astype(np.float32)))) / 255.0
            hist_a = cv2.calcHist([gray_a], [0], None, [32], [0, 256])
            hist_b = cv2.calcHist([gray_b], [0], None, [32], [0, 256])
            cv2.normalize(hist_a, hist_a)
            cv2.normalize(hist_b, hist_b)
            correlation = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))
            return mad >= 0.28 and correlation < 0.55
        except Exception:
            return False

    def _detect_text_edge_changes(self, frame1, frame2):
        """
        Canny Edge Detection?쇰줈 ?띿뒪???곸뿭 蹂??媛먯?

        SSIM?쇰줈 ?볦튌 ???덈뒗 誘몄꽭???먮쭑 蹂?붾? 媛먯??⑸땲??
        諛곌꼍? 媛숈?留??띿뒪?몃쭔 諛붾?寃쎌슦瑜??ъ갑?⑸땲??

        Args:
            frame1: 泥?踰덉㎏ ?꾨젅??(BGR)
            frame2: ??踰덉㎏ ?꾨젅??(BGR)

        Returns:
            蹂?붿쑉 (0.0~1.0, ?믪쓣?섎줉 蹂??留롮쓬)
        """
        try:
            import cv2
            import numpy as np

            # Grayscale 蹂??
            if len(frame1.shape) == 3:
                gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            else:
                gray1 = frame1

            if len(frame2.shape) == 3:
                gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            else:
                gray2 = frame2

            # ?ш린 留욎텛湲?
            if gray1.shape != gray2.shape:
                gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))

            # Canny Edge Detection (?띿뒪???ㅺ낸??媛먯?)
            edges1 = cv2.Canny(gray1, 100, 200)
            edges2 = cv2.Canny(gray2, 100, 200)

            # XOR ?곗궛?쇰줈 李⑥씠 怨꾩궛
            diff = cv2.bitwise_xor(edges1, edges2)

            # 蹂?붿쑉 怨꾩궛 (?꾩껜 ?쎌? ?鍮?蹂?붾맂 ?쎌? 鍮꾩쑉)
            total_pixels = diff.size
            changed_pixels = np.count_nonzero(diff)
            change_rate = changed_pixels / total_pixels

            return float(change_rate)

        except Exception as e:
            logger.debug(f"[Edge detection] Error: {e}")
            return 1.0  # ?ㅻ쪟 ??蹂???덈떎怨??먮떒 (?덉쟾)

    def _calculate_ssim(self, frame1, frame2):
        """
        SSIM (Structural Similarity Index)?쇰줈 ?꾨젅???좎궗??怨꾩궛

        ??議곗궗 寃곌낵 湲곕컲:
        - 95% ?좎궗???댁긽?대㈃ ?ㅽ궢 (???꾧꺽?섍쾶, ?먮쭑 蹂???볦튂吏 ?딄린 ?꾪븿)
        - PSNR蹂대떎 ?멸컙 ?쒓컖??媛源뚯슫 痢≪젙

        Args:
            frame1: 泥?踰덉㎏ ?꾨젅??(BGR)
            frame2: ??踰덉㎏ ?꾨젅??(BGR)

        Returns:
            SSIM 媛?(0.0~1.0, ?믪쓣?섎줉 ?좎궗)
        """
        try:
            import cv2
            import numpy as np

            # Grayscale 蹂??(SSIM? ?⑥씪 梨꾨꼸?먯꽌 怨꾩궛)
            if len(frame1.shape) == 3:
                gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            else:
                gray1 = frame1

            if len(frame2.shape) == 3:
                gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            else:
                gray2 = frame2

            # ?ш린媛 ?ㅻⅤ硫?由ъ궗?댁쫰
            if gray1.shape != gray2.shape:
                gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))

            # SSIM 怨꾩궛 (scikit-image ???OpenCV 諛⑹떇 ?ъ슜)
            # C1, C2???덉젙?깆쓣 ?꾪븳 ?곸닔
            C1 = (0.01 * 255) ** 2
            C2 = (0.03 * 255) ** 2

            # ?됯퇏
            mu1 = cv2.GaussianBlur(gray1.astype(float), (11, 11), 1.5)
            mu2 = cv2.GaussianBlur(gray2.astype(float), (11, 11), 1.5)

            mu1_sq = mu1 ** 2
            mu2_sq = mu2 ** 2
            mu1_mu2 = mu1 * mu2

            # 遺꾩궛 諛?怨듬텇??
            sigma1_sq = cv2.GaussianBlur(gray1.astype(float) ** 2, (11, 11), 1.5) - mu1_sq
            sigma2_sq = cv2.GaussianBlur(gray2.astype(float) ** 2, (11, 11), 1.5) - mu2_sq
            sigma12 = cv2.GaussianBlur(gray1.astype(float) * gray2.astype(float), (11, 11), 1.5) - mu1_mu2

            # SSIM 怨듭떇
            ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))

            # ?됯퇏 SSIM
            return float(np.mean(ssim_map))

        except Exception as e:
            logger.debug(f"[SSIM] Calculation error: {e}")
            return 0.0  # ?ㅻ쪟 ???좎궗?섏? ?딅떎怨??먮떒

    def _preprocess_frame_for_ocr(self, frame, use_gpu=False):
        """
        ?꾨젅???꾩쿂由щ줈 OCR ?뺥솗???μ긽

        ??議곗궗 寃곌낵 湲곕컲:
        - Bilateral filter濡??ｌ? 蹂댁〈?섎㈃???몄씠利??쒓굅
        - Gaussian blur濡?異붽? ?몄씠利??쒓굅
        - Adaptive threshold濡??띿뒪??媛뺤“
        - GPU 媛??吏??(cv2.UMat)

        Args:
            frame: ?먮낯 ?꾨젅??(BGR)
            use_gpu: GPU 媛???ъ슜 ?щ?

        Returns:
            ?꾩쿂由щ맂 ?꾨젅??        """
        try:
            import cv2

            # GPU 媛???듭뀡 (cv2.UMat ?ъ슜)
            if use_gpu and CV2_AVAILABLE:
                try:
                    # UMat濡?蹂??(OpenCL GPU 媛??
                    frame_umat = cv2.UMat(frame)

                    # 1. Bilateral filter: ?ｌ? 蹂댁〈?섎㈃???몄씠利??쒓굅
                    filtered = cv2.bilateralFilter(frame_umat, d=9, sigmaColor=75, sigmaSpace=75)

                    # 2. Gaussian blur: ?⑥? ?몄씠利??쒓굅
                    blurred = cv2.GaussianBlur(filtered, (3, 3), 0)

                    # 3. Grayscale 蹂??
                    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)

                    # 4. Adaptive threshold: ?띿뒪??媛뺤“
                    thresh = cv2.adaptiveThreshold(
                        gray, 255,
                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY,
                        blockSize=11,
                        C=2
                    )

                    # 5. BGR濡??ㅼ떆 蹂??(OCR ?낅젰??
                    result = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

                    # UMat??numpy濡?蹂??
                    return result.get()

                except Exception as gpu_error:
                    # GPU ?ㅽ뙣 ??CPU濡??대갚
                    logger.debug(f"[OCR preprocessing] GPU processing failed, switching to CPU: {gpu_error}")
                    use_gpu = False

            # CPU 踰꾩쟾
            # 1. Bilateral filter: ?ｌ? 蹂댁〈?섎㈃???몄씠利??쒓굅
            filtered = cv2.bilateralFilter(frame, d=9, sigmaColor=75, sigmaSpace=75)

            # 2. Gaussian blur: ?⑥? ?몄씠利??쒓굅
            blurred = cv2.GaussianBlur(filtered, (3, 3), 0)

            # 3. Grayscale 蹂??
            gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)

            # 4. Adaptive threshold: ?띿뒪??媛뺤“
            thresh = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=11,
                C=2
            )

            # 5. BGR濡??ㅼ떆 蹂??(OCR ?낅젰??
            result = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

            return result
        except Exception as e:
            # ?꾩쿂由??ㅽ뙣 ???먮낯 諛섑솚
            logger.debug(f"[OCR preprocessing] Error: {e}")
            return frame

    def _analyze_segment_batch_streaming(
        self, cap, sample_frames, segment_name, W, H, fps, optimizer
    ):
        """Read, OCR, and release one bounded frame batch at a time."""
        import cv2

        ocr_reader = getattr(self.gui, "ocr_reader", None)
        if ocr_reader is None:
            return None

        batch_size = max(1, int(GLMOCRSettings.OPTIMAL_BATCH_SIZE))
        all_regions: List[Dict[str, Any]] = []
        frames_with_chinese = 0
        frames_checked = 0
        ocr_call_count = 0
        batch_number = 0

        def append_results(batch, batch_results) -> int:
            nonlocal frames_with_chinese
            accepted = 0
            if not isinstance(batch_results, (list, tuple)):
                self._mark_review_required("ocr_batch_result_malformed")
                batch_results = []
            if len(batch_results) != len(batch):
                self._mark_review_required("ocr_batch_result_alignment")

            for index, (frame_pos, time_sec, _frame, scale, scene_id) in enumerate(batch):
                results = batch_results[index] if index < len(batch_results) else []
                frame_has_chinese = False
                for result in results or []:
                    if not isinstance(result, (list, tuple)) or len(result) < 2:
                        continue
                    bbox, text = result[0], str(result[1] or "")
                    try:
                        prob = float(result[2]) if len(result) >= 3 else 1.0
                    except (TypeError, ValueError):
                        continue
                    if prob < OCRThresholds.CONFIDENCE_MIN:
                        continue
                    if not any("\u4e00" <= char <= "\u9fff" for char in text):
                        continue

                    try:
                        adjusted_bbox = (
                            [(x / scale, y / scale) for x, y in bbox]
                            if scale != 1.0
                            else bbox
                        )
                    except Exception:
                        adjusted_bbox = bbox
                    region_info = self._gpu_process_bbox_batch([adjusted_bbox], W, H)
                    polygon = self._normalize_polygon(adjusted_bbox, W, H)
                    if not region_info or region_info[0] is None or not polygon:
                        continue
                    info = region_info[0]
                    all_regions.append(
                        {
                            "x": info["x"],
                            "y": info["y"],
                            "width": info["width"],
                            "height": info["height"],
                            "oversized": bool(info.get("oversized", False)),
                            "confidence": prob,
                            "time": time_sec,
                            "frame_index": int(frame_pos),
                            "text": text,
                            "language": "chinese",
                            "source": "glm_ocr_batch",
                            "polygon": polygon,
                            "scene_id": scene_id,
                        }
                    )
                    frame_has_chinese = True
                if frame_has_chinese:
                    frames_with_chinese += 1
                    accepted += 1
            return accepted

        def flush(batch) -> None:
            nonlocal ocr_call_count, batch_number
            if not batch:
                return
            batch_number += 1
            frames_only = [item[2] for item in batch]
            try:
                batch_results = ocr_reader.readtext_batch(frames_only)
                ocr_call_count += 1
                append_results(batch, batch_results)
            except Exception as exc:
                logger.warning(
                    "[OCR %s] Batch %d error: %s", segment_name, batch_number, exc
                )
                self._mark_review_required("ocr_batch_exception")
                for item in batch:
                    try:
                        results = ocr_reader.readtext(item[2])
                        ocr_call_count += 1
                        append_results([item], [results])
                    except Exception:
                        self._mark_review_required("ocr_single_frame_fallback_failed")

        logger.info(
            "[OCR %s] Streaming batch mode: %d scheduled frames, batch=%d",
            segment_name,
            len(sample_frames),
            batch_size,
        )
        previous_time = None
        previous_scene_frame = None
        scene_counter = 0
        next_expected_frame = None
        pending = []

        for frame_pos in sample_frames:
            ret, frame, next_expected_frame = self._read_scheduled_frame(
                cap, frame_pos, next_expected_frame
            )
            if not ret:
                self._mark_review_required("scheduled_frame_decode_failed")
                continue
            time_sec = self._frame_time_after_read(
                cap, frame_pos, fps, previous_time=previous_time
            )
            previous_time = time_sec
            if self._is_scene_cut(previous_scene_frame, frame):
                scene_counter += 1
            scene_id = f"{segment_name}:{scene_counter}"
            previous_scene_frame = frame.copy()

            scale = 1.0
            try:
                height, width = frame.shape[:2]
                if optimizer:
                    params = optimizer.get_optimized_ocr_params()
                    target_width = int(params.get("downscale_target", 1440))
                else:
                    target_width = 1440 if width > 1920 else width
                if width > target_width:
                    scale = target_width / float(width)
                    frame = cv2.resize(
                        frame,
                        (target_width, max(1, int(height * scale))),
                        interpolation=cv2.INTER_AREA,
                    )
            except Exception:
                scale = 1.0

            pending.append((frame_pos, time_sec, frame, scale, scene_id))
            frames_checked += 1
            if len(pending) >= batch_size:
                flush(pending)
                pending.clear()
        flush(pending)

        logger.info(
            "[OCR %s] Streaming complete: %d/%d frames with Chinese, %d OCR calls",
            segment_name,
            frames_with_chinese,
            frames_checked,
            ocr_call_count,
        )
        if frames_checked == 0:
            return None
        return {
            "regions": all_regions,
            "frames_with_chinese": frames_with_chinese,
            "total_frames_checked": frames_checked,
            "ocr_calls": ocr_call_count,
        }

    def _analyze_segment_batch_mode(
        self, cap, sample_frames, segment_name, W, H, fps, optimizer
    ):
        """
        GLM-OCR 諛곗튂 紐⑤뱶濡??멸렇癒쇳듃 遺꾩꽍 (理쒖쟻?붾맂 API ?몄텧)

        Args:
            cap: VideoCapture object
            sample_frames: List of frame positions to analyze
            segment_name: Segment name for logging
            W, H: Video dimensions
            fps: Video FPS
            optimizer: System optimizer instance

        Returns:
            Dictionary with analysis results
        """
        import cv2
        import numpy as np

        ocr_reader = getattr(self.gui, 'ocr_reader', None)
        if ocr_reader is None:
            return None

        return self._analyze_segment_batch_streaming(
            cap, sample_frames, segment_name, W, H, fps, optimizer
        )

        batch_size = GLMOCRSettings.OPTIMAL_BATCH_SIZE
        all_regions = []
        frames_with_chinese = 0
        ocr_call_count = 0

        # ?꾨젅???섏쭛 諛?諛곗튂 泥섎━
        frame_data = []  # (frame_pos, time_sec, frame, scale, scene_id)
        previous_time = None
        previous_scene_frame = None
        scene_counter = 0

        logger.info(f"[OCR {segment_name}] Batch mode: collecting {len(sample_frames)} frames")

        # 1?④퀎: 紐⑤뱺 ?꾨젅???섏쭛 諛??꾩쿂由?
        next_expected_frame = None
        for frame_pos in sample_frames:
            ret, frame, next_expected_frame = self._read_scheduled_frame(
                cap, frame_pos, next_expected_frame
            )
            if not ret:
                continue

            time_sec = self._frame_time_after_read(
                cap, frame_pos, fps, previous_time=previous_time
            )
            previous_time = time_sec
            if self._is_scene_cut(previous_scene_frame, frame):
                scene_counter += 1
            scene_id = f"{segment_name}:{scene_counter}"
            previous_scene_frame = frame.copy()

            # Downscale frame
            scale = 1.0
            try:
                h, w = frame.shape[:2]
                if optimizer:
                    ocr_params = optimizer.get_optimized_ocr_params()
                    target_w = ocr_params.get('downscale_target', 1440)
                else:
                    target_w = 1440 if w > 1920 else w

                if w > target_w:
                    scale = target_w / float(w)
                    new_h = max(1, int(h * scale))
                    frame = cv2.resize(frame, (target_w, new_h), interpolation=cv2.INTER_AREA)
            except Exception:
                scale = 1.0

            frame_data.append((frame_pos, time_sec, frame, scale, scene_id))

        if not frame_data:
            return None

        # 2?④퀎: 諛곗튂 ?⑥쐞濡?OCR ?섑뻾
        total_batches = (len(frame_data) + batch_size - 1) // batch_size
        logger.info(f"[OCR {segment_name}] Processing {len(frame_data)} frames in {total_batches} batches")

        for batch_idx in range(0, len(frame_data), batch_size):
            batch = frame_data[batch_idx:batch_idx + batch_size]
            frames_only = [f[2] for f in batch]

            try:
                # 諛곗튂 OCR ?몄텧
                batch_results = ocr_reader.readtext_batch(frames_only)
                ocr_call_count += 1  # 諛곗튂??1???몄텧濡?移댁슫??
                # 媛??꾨젅?꾨퀎 寃곌낵 泥섎━
                for i, (frame_pos, time_sec, frame, scale, scene_id) in enumerate(batch):
                    if i >= len(batch_results):
                        continue

                    results = batch_results[i]
                    frame_has_chinese = False

                    for result in results:
                        if len(result) == 3:
                            bbox, text, prob = result
                        elif len(result) == 2:
                            bbox, text = result
                            prob = 1.0
                        else:
                            continue

                        if prob < OCRThresholds.CONFIDENCE_MIN:
                            continue

                        # 以묎뎅??臾몄옄 ?뺤씤
                        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
                        if chinese_chars < 1:
                            continue

                        frame_has_chinese = True

                        # Bbox ?ㅼ???議곗젙
                        try:
                            if scale != 1.0:
                                adjusted_bbox = [(x / scale, y / scale) for x, y in bbox]
                            else:
                                adjusted_bbox = bbox
                        except Exception:
                            adjusted_bbox = bbox

                        # Region ?뺣낫 ?앹꽦
                        region_info = self._gpu_process_bbox_batch([adjusted_bbox], W, H)
                        polygon = self._normalize_polygon(adjusted_bbox, W, H)
                        if region_info and region_info[0] is not None and polygon:
                            region = {
                                'x': region_info[0]['x'],
                                'y': region_info[0]['y'],
                                'width': region_info[0]['width'],
                                'height': region_info[0]['height'],
                                'confidence': prob,
                                'time': time_sec,
                                'frame_index': int(frame_pos),
                                'text': text,
                                'language': 'chinese',
                                'source': 'glm_ocr_batch',
                                'polygon': polygon,
                                'scene_id': scene_id,
                            }
                            all_regions.append(region)

                    if frame_has_chinese:
                        frames_with_chinese += 1

            except Exception as e:
                logger.warning(f"[OCR {segment_name}] Batch {batch_idx // batch_size + 1} error: {e}")
                # 諛곗튂 ?ㅽ뙣 ??媛쒕퀎 泥섎━濡??대갚
                for frame_pos, time_sec, frame, scale, scene_id in batch:
                    try:
                        results = ocr_reader.readtext(frame)
                        ocr_call_count += 1
                        # 寃곌낵 泥섎━ (媛꾩냼??
                        for result in results:
                            if len(result) >= 2:
                                text = result[1]
                                if any('\u4e00' <= c <= '\u9fff' for c in text):
                                    frames_with_chinese += 1
                                    break
                    except Exception:
                        pass

        logger.info(
            f"[OCR {segment_name}] Batch complete: "
            f"{frames_with_chinese}/{len(frame_data)} frames with Chinese, "
            f"{ocr_call_count} API calls"
        )

        return {
            'regions': all_regions,
            'frames_with_chinese': frames_with_chinese,
            'total_frames_checked': len(frame_data),
            'ocr_calls': ocr_call_count
        }

    def _perform_ocr_with_retry(self, target_frame, segment_name, frame_idx, attempt_name):
        """
        Perform OCR with retry logic using preprocessing.
        ?꾩쿂由щ? ?ъ슜???ъ떆??濡쒖쭅?쇰줈 OCR ?섑뻾.

        Attempts:
        1. Original frame OCR
        2. If no Chinese detected, try preprocessed frame
        3. If first attempt fails, retry with preprocessing

        Args:
            target_frame: Frame to analyze (BGR numpy array)
            segment_name: Segment name for logging
            frame_idx: Frame index for logging
            attempt_name: Attempt type name for logging

        Returns:
            Tuple of (results, ocr_call_count) where:
            - results: List of OCR results or None if failed
            - ocr_call_count: Number of OCR calls made
        """
        results = None
        ocr_call_count = 0

        # Safety check: Verify OCR reader is still available
        # ?덉쟾 寃?? OCR reader媛 ?ъ쟾???ъ슜 媛?ν븳吏 ?뺤씤
        ocr_reader = getattr(self.gui, 'ocr_reader', None)
        if ocr_reader is None:
            logger.warning(f"[OCR {segment_name}] OCR reader became unavailable during processing")
            return None, 0

        def has_chinese(ocr_results):
            """Check if OCR results contain Chinese characters."""
            if not ocr_results:
                return False
            return any(
                any('\u4e00' <= c <= '\u9fff' for c in str(r[1]) if len(r) >= 2)
                for r in ocr_results
            )

        # 1李??쒕룄: ?먮낯 ?꾨젅??
        try:
            results = ocr_reader.readtext(target_frame)
            ocr_call_count += 1

            # 寃곌낵媛 ?녾굅??以묎뎅?닿? 媛먯??섏? ?딆쑝硫??꾩쿂由??쒕룄
            if not has_chinese(results):
                # 2李??쒕룄: ?꾩쿂由??꾨젅??(GPU 媛???쒕룄)
                try:
                    use_gpu = GPU_ACCEL_AVAILABLE
                    preprocessed_frame = self._preprocess_frame_for_ocr(target_frame, use_gpu=use_gpu)
                    preprocessed_results = ocr_reader.readtext(preprocessed_frame)
                    ocr_call_count += 1

                    # ?꾩쿂由?寃곌낵媛 ???섏쑝硫?援먯껜
                    if has_chinese(preprocessed_results):
                        results = preprocessed_results
                        if frame_idx % 50 == 0:  # 濡쒓렇 ?ㅽ뙵 諛⑹?
                            logger.debug(f"[OCR {segment_name}] Frame {frame_idx + 1} ({attempt_name}) Chinese detection improved with preprocessing")
                except Exception:
                    pass  # ?꾩쿂由??ㅽ뙣 ???먮낯 寃곌낵 ?좎?

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.debug(f"[OCR {segment_name}] Frame {frame_idx + 1} ({attempt_name}) first attempt failed: {str(e)}")

            # ?ъ떆?? ?꾩쿂由????ㅼ떆 ?쒕룄 (GPU 媛??
            try:
                logger.debug(f"[OCR {segment_name}] Frame {frame_idx + 1} ({attempt_name}) retrying with preprocessing...")
                use_gpu = GPU_ACCEL_AVAILABLE
                preprocessed_frame = self._preprocess_frame_for_ocr(target_frame, use_gpu=use_gpu)
                results = ocr_reader.readtext(preprocessed_frame)
                ocr_call_count += 1
                logger.debug(f"[OCR {segment_name}] Frame {frame_idx + 1} ({attempt_name}) retry successful!")
            except Exception as retry_error:
                ui_controller.write_error_log(retry_error)
                logger.debug(f"[OCR {segment_name}] Frame {frame_idx + 1} ({attempt_name}) retry failed: {str(retry_error)}")
                return None, ocr_call_count

        return results, ocr_call_count

    def _analyze_video_segment(self, video_path, segment_name, start_sec, end_sec, W, H, fps, total_frames):
        """
        Analyze a specific time segment of the video for Chinese subtitles.

        Uses HybridSubtitleDetector when available for optimized OCR calls:
        - Canny edge-based fast change detection
        - Multi-frame consistency verification
        - Expected 40% reduction in OCR calls

        Args:
            video_path: Path to video file
            segment_name: Name of segment (for logging)
            start_sec: Start time in seconds
            end_sec: End time in seconds
            W: Video width
            H: Video height
            fps: Video FPS
            total_frames: Total frame count

        Returns:
            Dictionary with analysis results or None
        """
        cap = None  # ??try/finally瑜??꾪빐 誘몃━ ?좎뼵
        try:
            import cv2
            import numpy as np

            # Check OCR reader availability
            # OCR reader 媛?⑹꽦 ?뺤씤
            if not hasattr(self.gui, 'ocr_reader') or self.gui.ocr_reader is None:
                logger.warning(f"[OCR {segment_name}] OCR reader not initialized, skipping segment")
                return None

            logger.debug(f"[OCR {segment_name}] Analysis starting...")

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.warning(f"[OCR {segment_name}] Could not open video file")
                return None

            # ?꾨젅??踰붿쐞 怨꾩궛
            start_frame = min(total_frames, max(0, int(round(fps * start_sec))))
            end_frame = min(total_frames, max(0, int(round(fps * end_sec))))

            # ?쒖뒪??理쒖쟻???뚮씪誘명꽣 媛?몄삤湲?
            optimizer = _get_optimizer(self.gui)

            full_scan_mode = bool(getattr(OCRThresholds, "FULL_FRAME_SCAN_MODE", False))

            # ?섏씠釉뚮━??媛먯?湲??뺤씤 諛?珥덇린??
            use_hybrid = False
            hybrid_detector = None

            if HYBRID_DETECTOR_AVAILABLE and self.hybrid_detector is None:
                # 吏??珥덇린???쒕룄
                self._init_hybrid_detector()

            if self.hybrid_detector is not None and not full_scan_mode:
                use_hybrid = True
                hybrid_detector = self.hybrid_detector
                hybrid_detector.reset()  # ?멸렇癒쇳듃蹂??듦퀎 珥덇린??
                logger.debug(f"[OCR {segment_name}] Hybrid detection mode activated")
            else:
                logger.debug(f"[OCR {segment_name}] Default sampling mode")

            # GLM-OCR 諛곗튂 紐⑤뱶 ?뺤씤
            use_batch_mode = self._use_batch_ocr(full_scan_mode=full_scan_mode)

            if use_batch_mode:
                logger.info(f"[OCR {segment_name}] GLM-OCR batch mode enabled")

            sample_frames = []
            if full_scan_mode:
                sample_frames = list(range(start_frame, end_frame))
                logger.info(
                    f"[OCR {segment_name}] Ultra-accuracy mode: scanning every frame ({len(sample_frames)} frames)"
                )
            else:
                # ?끸쁾??媛쒖꽑: 0~3珥?援ш컙 吏묒쨷 ?섑뵆留?(0.1珥?媛꾧꺽) ?끸쁾??            # ?곸긽 ?쒖옉遺 ?먮쭑???뺤떎???ъ갑?섍린 ?꾪븳 ?꾨왂
                # ??0珥?二쇰? 珥덉젙諛 ?섑뵆留? 0, 0.05, 0.1, 0.15珥??꾨젅??媛뺤젣 ?ы븿
                if start_sec == 0:
                    ultra_critical_times = [0.0, 0.05, 0.1, 0.15]
                    for t in ultra_critical_times:
                        frame_num = int(fps * t)
                        if frame_num < total_frames and frame_num not in sample_frames:
                            sample_frames.append(frame_num)
                    logger.debug(f"[OCR {segment_name}] Ultra-precise sampling near 0s: {len(sample_frames)} frames ({ultra_critical_times}s)")

                # 0~3珥?援ш컙: 0.1珥?媛꾧꺽 (10 FPS) - 珥덇린 ?먮쭑 ?뺤떎???ъ갑
                critical_start_duration = 3.0
                critical_end_frame = min(int(fps * critical_start_duration), end_frame)

                if start_sec < critical_start_duration:
                    # ??援ш컙? 0~3珥덈? ?ы븿?섎뒗 援ш컙
                    critical_interval = max(1, int(fps * 0.1))  # 0.1珥?媛꾧꺽
                    critical_start = start_frame
                    critical_end = min(critical_end_frame, end_frame)

                    for frame_num in range(critical_start, critical_end, critical_interval):
                        if frame_num < total_frames and frame_num not in sample_frames:
                            sample_frames.append(frame_num)

                    logger.debug(f"[OCR {segment_name}] 0-3s intensive sampling: {len([f for f in sample_frames if f < critical_end_frame])} frames (0.1s interval)")

                # 3珥??댄썑: 珥섏킌???섑뵆留?(0.15珥?媛꾧꺽)
                # ?끸쁾??媛쒖꽑: 0.3珥???0.15珥덈줈 異뺤냼?섏뿬 吏㏃? ?먮쭑 ?꾨씫 諛⑹?
                if end_frame > critical_end_frame:
                    if use_hybrid:
                        # ?섏씠釉뚮━?? ??珥섏킌???꾨젅???ㅼ틪 (0.1珥?媛꾧꺽)
                        base_interval = max(1, int(fps * 0.1))
                    else:
                        # ??湲곕낯 媛꾧꺽 0.15珥? 0.3珥덉뿉???덈컲?쇰줈 以꾩뿬 ?먮쭑 ?꾪솚 ?ъ갑瑜??μ긽
                        base_interval = max(1, int(fps * 0.15))

                    scan_interval = base_interval

                    regular_start = max(critical_end_frame, start_frame)
                    for frame_num in range(regular_start, end_frame, scan_interval):
                        if frame_num < total_frames and frame_num not in sample_frames:
                            sample_frames.append(frame_num)

                # ?쒓컙???뺣젹
                sample_frames.sort()

            if not sample_frames:
                cap.release()
                return None

            logger.debug(f"[OCR {segment_name}] {len(sample_frames)} frames scheduled for scan")

            # ?끸쁾??GLM-OCR 諛곗튂 泥섎━ 紐⑤뱶 ?끸쁾??
            if use_batch_mode:
                result = self._analyze_segment_batch_mode(
                    cap, sample_frames, segment_name, W, H, fps, optimizer
                )
                cap.release()
                return result

            all_regions = []
            frames_with_chinese = 0
            position_history = []
            ocr_call_count = 0  # ?ㅼ젣 OCR ?몄텧 ?잛닔 異붿쟻
            ssim_skip_count = 0  # SSIM?쇰줈 ?ㅽ궢???꾨젅????            
            edge_detected_count = 0  # Edge detection?쇰줈 蹂??媛먯????잛닔
            prev_frame_roi = None  # ?댁쟾 ?꾨젅??(SSIM 鍮꾧탳??
            consecutive_similar_count = 0  # ?곗냽 ?좎궗 ?꾨젅??移댁슫??
            previous_time = None
            previous_scene_frame = None
            scene_counter = 0
            # ?끸쁾??珥덉븞??紐⑤뱶: 留ㅼ슦 蹂댁닔?곸씤 ?꾧퀎媛?+ ?곗냽 泥댄겕 ?끸쁾??            # Use constants for thresholds
            # ?꾧퀎媛??곸닔 ?ъ슜
            ssim_threshold = OCRThresholds.SSIM_THRESHOLD  # 98% (嫄곗쓽 ?쎌? ?숈씪)
            edge_change_threshold = OCRThresholds.EDGE_CHANGE_THRESHOLD  # 0.1% 蹂??媛먯?
            # 1920x540 ROI?먯꽌 0.1% = 1,036 ?쎌? (??湲??蹂寃쎈룄 媛먯?)

            # ?끸쁾??異붽? ?덉쟾?μ튂: ?곗냽 2?꾨젅???댁긽 ?숈씪?댁빞 ?ㅽ궢 ?끸쁾??            # ?먮쭑??諛붾뚮뒗 ?쒓컙(?꾪솚 ?꾨젅?????볦튂吏 ?딄린 ?꾪븿
            min_consecutive_similar = 2

            next_expected_frame = None
            for i, frame_pos in enumerate(sample_frames):
                ret, frame, next_expected_frame = self._read_scheduled_frame(
                    cap, frame_pos, next_expected_frame
                )
                if not ret:
                    continue

                time_sec = self._frame_time_after_read(
                    cap, frame_pos, fps, previous_time=previous_time
                )
                previous_time = time_sec
                if self._is_scene_cut(previous_scene_frame, frame):
                    scene_counter += 1
                scene_id = f"{segment_name}:{scene_counter}"
                previous_scene_frame = frame.copy()

                # Downscale frame for faster OCR
                scale = 1.0
                try:
                    h, w = frame.shape[:2]
                    if full_scan_mode:
                        target_w = w
                    elif optimizer:
                        ocr_params = optimizer.get_optimized_ocr_params()
                        target_w = ocr_params['downscale_target'] if w > ocr_params['downscale_target'] else w
                    else:
                        target_w = 1440 if w > 1920 else w
                    if w > target_w:
                        scale = target_w / float(w)
                        new_h = max(1, int(h * scale))
                        frame = cv2.resize(frame, (target_w, new_h), interpolation=cv2.INTER_AREA)
                except Exception:
                    scale = 1.0

                # ?끸쁾??100% 媛먯? 紐⑤뱶: ?꾩껜 ?붾㈃ ?ㅼ틪 ?끸쁾??                # ?곷떒/以묒븰/?섎떒 ?대뵒???덈뒗 ?먮쭑???볦튂吏 ?딅룄濡??꾩껜 ?붾㈃ ?ㅼ틪
                attempts = []
                roi_frame = None
                try:
                    h_resized, w_resized = frame.shape[:2]
                    # ?꾩껜 ?붾㈃??ROI濡??ъ슜 (100%)
                    roi_percent = OCRThresholds.ROI_BOTTOM_PERCENT / 100.0  # 100% ?꾩껜 ?붾㈃
                    roi_percent = max(OCRThresholds.ROI_MIN_PERCENT / 100.0, roi_percent)  # 理쒖냼 70%
                    roi_start = int(h_resized * (1 - roi_percent))
                    if 0 < roi_start < h_resized - 8:
                        roi_frame = frame[roi_start:, :]
                        attempts.append(("roi_full", roi_frame, roi_start))
                except Exception:
                    pass
                # ??긽 ?꾩껜 ?꾨젅?꾨룄 ?쒕룄 (fallback)
                attempts.append(("full", frame, 0))

                # ?끸쁾??100% 媛먯? 紐⑤뱶: SSIM ?ㅽ궢 ?꾩쟾 鍮꾪솢?깊솕 ?끸쁾??                # 紐⑤뱺 ?꾨젅?꾩쓣 OCR 寃?ы븯???먮쭑 ?꾪솚???덈? ?볦튂吏 ?딆쓬
                skip_by_ssim = False  # ??긽 False (?ㅽ궢 ?덊븿)

                # SSIM ?ㅽ궢 鍮꾪솢?깊솕 (constants.py?먯꽌 ?ㅼ젙)
                if not OCRThresholds.SSIM_SKIP_ENABLED:
                    # 紐⑤뱺 ?꾨젅??寃??- ?ㅽ궢 ?놁쓬
                    pass
                else:
                    # SSIM ?ㅽ궢???쒖꽦?붾맂 寃쎌슦 (湲곕낯媛?False?대?濡??ㅽ뻾 ?덈맖)
                    # ??肄붾뱶???ν썑 ?깅뒫 理쒖쟻?????ъ슜 媛??
                    if prev_frame_roi is not None and roi_frame is not None:
                        try:
                            ssim_score = self._calculate_ssim(prev_frame_roi, roi_frame)
                            edge_change = self._detect_text_edge_changes(prev_frame_roi, roi_frame)
                            is_similar = (ssim_score >= ssim_threshold and edge_change < edge_change_threshold)

                            if is_similar:
                                consecutive_similar_count += 1
                                if consecutive_similar_count >= min_consecutive_similar:
                                    skip_by_ssim = True
                                    ssim_skip_count += 1
                            else:
                                consecutive_similar_count = 0
                                if edge_change >= edge_change_threshold:
                                    edge_detected_count += 1
                        except Exception:
                            consecutive_similar_count = 0

                # SSIM?쇰줈 ?ㅽ궢???꾨젅?꾩? OCR?섏? ?딆쓬 (?꾩옱????긽 False)
                if skip_by_ssim:
                    continue

                # ROI ?꾨젅?????(?ㅼ쓬 鍮꾧탳??- SSIM ?쒖꽦?????ъ슜)
                if roi_frame is not None:
                    prev_frame_roi = roi_frame.copy()

                frame_has_chinese = False
                current_frame_regions = []

                for attempt_name, target_frame, y_offset in attempts:
                    results = None

                    # ?섏씠釉뚮━??媛먯?湲??ъ슜
                    if use_hybrid and hybrid_detector:
                        ocr_results, meta = hybrid_detector.process(target_frame, time_sec)

                        if meta['processed']:
                            # OCR???ㅼ젣濡??몄텧??                            ocr_call_count += 1
                            results = ocr_results
                        elif not meta['fast_detected']:
                            # 蹂???놁쓬 - ?ㅽ궢
                            continue
                        else:
                            # 蹂??媛먯??먯?留?OCR ?ㅽ궢 (?쒓컙 ?쒗븳)
                            continue
                    else:
                        # OCR ?ъ떆??濡쒖쭅??蹂꾨룄 硫붿꽌?쒕줈 ?꾩엫
                        # Delegate OCR retry logic to separate method
                        results, calls_made = self._perform_ocr_with_retry(
                            target_frame, segment_name, i, attempt_name
                        )
                        ocr_call_count += calls_made
                        if results is None:
                            continue

                    if results is None:
                        continue

                    texts = []
                    bboxes = []
                    probs = []

                    for result in results:
                        if len(result) == 3:
                            bbox, text, prob = result
                        elif len(result) == 2:
                            bbox, text = result
                            prob = 1.0
                        else:
                            continue

                        # ?끸쁾??媛쒖꽑: ?좊ː???꾧퀎媛?0.5 ??0.3 (珥덇린 媛먯? ?④퀎) ?끸쁾??                        # 以묎뎅???먮쭑? 蹂듭옟??臾몄옄媛 留롮븘 ?좊ː?꾧? ??쓣 ???덉쓬
                        if prob < 0.3:
                            continue

                        try:
                            adjusted_bbox = []
                            for x, y in bbox:
                                y_adj = y + y_offset
                                if scale != 1.0:
                                    adjusted_bbox.append((x / scale, y_adj / scale))
                                else:
                                    adjusted_bbox.append((x, y_adj))
                            bbox = adjusted_bbox
                        except Exception:
                            pass

                        texts.append(text)
                        bboxes.append(bbox)
                        probs.append(prob)

                    if not texts:
                        continue

                    chinese_char_counts = self._gpu_check_chinese_chars(texts)
                    processed_regions = self._gpu_process_bbox_batch(bboxes, W, H)

                    source_tag = 'rapidocr_hybrid' if use_hybrid else ('rapidocr_gpu' if GPU_ACCEL_AVAILABLE else 'rapidocr')

                    for idx, (text, prob, chinese_chars) in enumerate(zip(texts, probs, chinese_char_counts)):
                        region_info = processed_regions[idx] if idx < len(processed_regions) else None
                        if not region_info:
                            continue
                        if chinese_chars < 1:
                            continue
                        polygon = self._normalize_polygon(
                            bboxes[idx] if idx < len(bboxes) else None, W, H
                        )
                        if not polygon:
                            continue

                        frame_has_chinese = True
                        region = {
                            'x': region_info['x'],
                            'y': region_info['y'],
                            'width': region_info['width'],
                            'height': region_info['height'],
                            'oversized': bool(region_info.get('oversized', False)),
                            'confidence': prob,
                            'time': time_sec,
                            'frame_index': int(frame_pos),
                            'text': text,
                            'language': 'chinese',
                            'source': source_tag,
                            'roi_type': attempt_name,  # ?대뒓 ROI?먯꽌 媛먯??섏뿀?붿? 湲곕줉
                            'polygon': polygon,
                            'scene_id': scene_id,
                        }

                        current_frame_regions.append(region)
                        all_regions.append(region)

                    # ?끸쁾??媛쒖꽑: ROI?먯꽌 諛쒓껄?섎뜑?쇰룄 ?ㅻⅨ ROI?ㅻ룄 怨꾩냽 ?ㅼ틪 ?끸쁾??                    # ?섎떒 ROI?먯꽌 諛쒓껄?섎뜑?쇰룄 ?곷떒/以묒븰???ㅻⅨ ?먮쭑???덉쓣 ???덉쓬
                    # break ?쒓굅濡?紐⑤뱺 ROI ?ㅼ틪 蹂댁옣

                if frame_has_chinese:
                    frames_with_chinese += 1

                if current_frame_regions:
                    current_positions = set()
                    for region in current_frame_regions:
                        key = (
                            round(region['x'] / 10) * 10,
                            round(region['y'] / 10) * 10,
                            round(region['width'] / 10) * 10,
                            round(region['height'] / 10) * 10
                        )
                        current_positions.add(key)
                    position_history.append(current_positions)

            # Clear frame cache to prevent memory leak
            # ?꾨젅??罹먯떆 ?뺣━ (硫붾え由??꾩닔 諛⑹?)
            if 'prev_frame_roi' in locals():
                del prev_frame_roi
            if 'roi_frame' in locals():
                del roi_frame

            # ?끸쁾??Phase 2: ?먮쭑 寃쎄퀎 ?뺣? ?ъ뒪罹?(Boundary Refinement) ?끸쁾??            # 媛먯????먮쭑???쒖옉/??寃쎄퀎 洹쇱쿂瑜?0.05珥?媛꾧꺽?쇰줈 ?ъ뒪罹뷀븯??            # ?뺥솗???먮쭑 ?쒖옉/???쒓컙???뚯븙
            if all_regions and frames_with_chinese > 0 and not full_scan_mode:
                # ?멸렇癒쇳듃 寃쎄퀎留??ㅼ틪: ?곗냽 媛먯???泥?留덉?留??쒓컙 + 媛?寃쎄퀎
                detected_times = sorted(set(r.get('time', 0) for r in all_regions))
                if detected_times:
                    # 寃쎄퀎 ?쒓컙留?異붿텧 (?꾩껜 ?쒓컙 ????멸렇癒쇳듃 寃쎄퀎留?
                    edge_times = set()
                    edge_times.add(detected_times[0])
                    edge_times.add(detected_times[-1])
                    for i in range(1, len(detected_times)):
                        if detected_times[i] - detected_times[i - 1] > OCRThresholds.TIME_SEGMENT_GAP:
                            edge_times.add(detected_times[i - 1])
                            edge_times.add(detected_times[i])

                    boundary_frames = set()
                    refine_interval = max(1, int(fps * 0.05))  # 0.05珥?媛꾧꺽

                    for det_time in edge_times:
                        det_frame = int(det_time * fps)
                        # 媛먯? ?쒖옉 吏곸쟾 援ш컙 (1珥???~ 媛먯? ?쒖젏)
                        scan_before_start = max(start_frame, det_frame - int(fps * 1.0))
                        for f in range(scan_before_start, det_frame, refine_interval):
                            if f not in sample_frames and f < total_frames:
                                boundary_frames.add(f)
                        # 媛먯? 醫낅즺 吏곹썑 援ш컙 (媛먯? ?쒖젏 ~ 1珥???
                        scan_after_end = min(end_frame, det_frame + int(fps * 1.0))
                        for f in range(det_frame, scan_after_end, refine_interval):
                            if f not in sample_frames and f < total_frames:
                                boundary_frames.add(f)

                    # 以묐났 ?쒓굅: ?대? ?ㅼ틪???꾨젅???쒖쇅
                    scanned_set = set(sample_frames)
                    boundary_frames -= scanned_set

                    # ?꾨젅?????쒗븳 (?깅뒫 蹂댄샇)
                    if len(boundary_frames) > OCRThresholds.BOUNDARY_MAX_FRAMES:
                        boundary_frames = set(sorted(boundary_frames)[:OCRThresholds.BOUNDARY_MAX_FRAMES])

                    if boundary_frames:
                        boundary_list = sorted(boundary_frames)
                        logger.info(f"[OCR {segment_name}] Boundary refinement: scanning {len(boundary_list)} extra frames near {len(edge_times)} edge transitions")

                        cap2 = cv2.VideoCapture(video_path)
                        try:
                            if cap2.isOpened():
                                boundary_previous_time = None
                                boundary_previous_frame = None
                                boundary_scene_counter = 0
                                for bf in boundary_list:
                                    cap2.set(cv2.CAP_PROP_POS_FRAMES, bf)
                                    ret2, frame2 = cap2.read()
                                    if not ret2:
                                        continue
                                    time_sec2 = self._frame_time_after_read(
                                        cap2, bf, fps, previous_time=boundary_previous_time
                                    )
                                    boundary_previous_time = time_sec2
                                    if self._is_scene_cut(boundary_previous_frame, frame2):
                                        boundary_scene_counter += 1
                                    boundary_scene_id = (
                                        f"{segment_name}:boundary:{boundary_scene_counter}"
                                    )
                                    boundary_previous_frame = frame2.copy()

                                    # ?ㅼ슫?ㅼ???(硫붿씤 ?ㅼ틪怨??숈씪???듯떚留덉씠? ?ㅼ젙 ?ъ슜)
                                    scale2 = 1.0
                                    try:
                                        h2, w2 = frame2.shape[:2]
                                        if optimizer:
                                            ocr_params_br = optimizer.get_optimized_ocr_params()
                                            target_w2 = ocr_params_br['downscale_target'] if w2 > ocr_params_br['downscale_target'] else w2
                                        else:
                                            target_w2 = 1440 if w2 > 1920 else w2
                                        if w2 > target_w2:
                                            scale2 = target_w2 / float(w2)
                                            new_h2 = max(1, int(h2 * scale2))
                                            frame2 = cv2.resize(frame2, (target_w2, new_h2), interpolation=cv2.INTER_AREA)
                                    except Exception:
                                        scale2 = 1.0

                                    results2, calls2 = self._perform_ocr_with_retry(
                                        frame2, segment_name, bf, "boundary"
                                    )
                                    ocr_call_count += calls2

                                    if not results2:
                                        continue

                                    for result in results2:
                                        if len(result) == 3:
                                            bbox2, text2, prob2 = result
                                        elif len(result) == 2:
                                            bbox2, text2 = result
                                            prob2 = 1.0
                                        else:
                                            continue
                                        if prob2 < 0.3:
                                            continue
                                        chinese_chars2 = sum(1 for c in text2 if '\u4e00' <= c <= '\u9fff')
                                        if chinese_chars2 < 1:
                                            continue

                                        # bbox ?ㅼ???議곗젙
                                        try:
                                            if scale2 != 1.0:
                                                bbox2 = [(x / scale2, y / scale2) for x, y in bbox2]
                                        except Exception:
                                            pass

                                        region_info2 = self._gpu_process_bbox_batch([bbox2], W, H)
                                        polygon2 = self._normalize_polygon(bbox2, W, H)
                                        if region_info2 and region_info2[0] is not None and polygon2:
                                            all_regions.append({
                                                'x': region_info2[0]['x'],
                                                'y': region_info2[0]['y'],
                                                'width': region_info2[0]['width'],
                                                'height': region_info2[0]['height'],
                                                'oversized': bool(region_info2[0].get('oversized', False)),
                                                'confidence': prob2,
                                                'time': time_sec2,
                                                'frame_index': int(bf),
                                                'text': text2,
                                                'language': 'chinese',
                                                'source': 'boundary_refine',
                                                'polygon': polygon2,
                                                'scene_id': boundary_scene_id,
                                            })
                                            frames_with_chinese += 1
                        finally:
                            cap2.release()

                        logger.info(f"[OCR {segment_name}] Boundary refinement complete: {len(all_regions)} total regions (added from boundary scan)")

            # ?끸쁾???깅뒫 ?듦퀎 異쒕젰 ?끸쁾??
            total_scanned = len(sample_frames)
            actual_processed = total_scanned - ssim_skip_count
            efficiency_gain = (ssim_skip_count / max(1, total_scanned)) * 100

            logger.info(f"[OCR {segment_name}] ===== Performance Stats =====")
            logger.info(f"  Scan targets: {total_scanned} frames")
            logger.info(f"  SSIM skip: {ssim_skip_count} ({efficiency_gain:.1f}% reduction)")
            logger.info(f"  Edge detection: {edge_detected_count} (OCR despite high SSIM)")
            logger.info(f"  Actual processed: {actual_processed} frames")
            logger.info(f"  OCR calls: {ocr_call_count}")
            logger.debug(f"  [100% Detection mode]:")
            logger.debug(f"    - SSIM skip: DISABLED (all frames scanned)")
            logger.debug(f"    - ROI: Full screen (100%)")

            # ?섏씠釉뚮━??媛먯?湲??듦퀎 異쒕젰
            if use_hybrid and hybrid_detector:
                stats = hybrid_detector.stats
                logger.info(f"[OCR {segment_name}] Hybrid stats:")
                logger.info(f"  - Scan frames: {stats['total_frames']}")
                logger.info(f"  - OCR calls: {stats['processed_frames']} ({stats['processed_frames']/max(1,stats['total_frames'])*100:.1f}%)")
                logger.info(f"  - Fast detected: {stats['fast_detected']}")
                logger.info(f"  - Skipped(fast): {stats['skipped_by_fast']}")
                logger.info(f"  - Skipped(confirm): {stats['skipped_by_confirm']}")

            logger.info(f"[OCR {segment_name}] ==========================")

            return {
                'regions': all_regions,
                'frames_with_chinese': frames_with_chinese,
                'total_frames_checked': len(sample_frames),
                'ocr_calls': ocr_call_count
            }

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[OCR {segment_name}] Error: {e}")
            logger.exception("OCR segment analysis failed")
            return None
        finally:
            # ?끸쁾??由ъ냼???꾩닔 諛⑹?: ?덉쇅 諛쒖깮 ?쒖뿉??VideoCapture ?댁젣 ?끸쁾??
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
