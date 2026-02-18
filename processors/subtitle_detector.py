"""
Subtitle Detection Processor

This module handles OCR-based Chinese subtitle detection with GPU/NumPy acceleration.
Integrates HybridSubtitleDetector for optimized OCR calls (40% reduction).
"""

import os
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
        self._init_hybrid_detector()

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
                if end_sec - current_start >= 1:
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
            frames_with_chinese = frames_with_chinese_total
            sample_frames_count = total_sample_frames

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
            reliable_regions = self._gpu_aggregate_regions(all_regions)

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
            # 硫붾え由??뺣━: 紐낆떆??媛鍮꾩? 而щ젆??            import gc
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
            if area_ratio > 0.35 or height_pct > 45.0:
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

            # 議곌굔 1: ?ㅼ쨷 ?쒓컙 洹몃９(?꾨젅???먯꽌 異쒗쁽?댁빞 ?먮쭑
            # ???? ?곸긽 ?쒖옉 遺遺?~1珥?? 硫댁젣: ?쒓컙 洹몃９??異⑸텇???볦씠吏 ?딆쑝誘濡?
            is_early_region = region_start_time <= 1.0
            if time_group_count < OCRThresholds.SUBTITLE_MIN_TIME_GROUPS and not is_early_region:
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

                if y_std > OCRThresholds.SUBTITLE_Y_VARIANCE_MAX:
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
                if x_std > OCRThresholds.SUBTITLE_X_VARIANCE_MAX:
                    logger.debug(f"  -> Excluded: X unstable (X std={x_std:.1f}% > {OCRThresholds.SUBTITLE_X_VARIANCE_MAX}%)")
                    continue

            # Multi-feature subtitle scoring for smarter product-text separation.
            score = 0.0
            score += 2.0 if time_group_count >= 3 else (1.0 if time_group_count >= 2 else -1.0)
            score += 1.5 if y_std <= (OCRThresholds.SUBTITLE_Y_VARIANCE_MAX * 0.5) else 0.5
            score += 1.0 if x_std <= (OCRThresholds.SUBTITLE_X_VARIANCE_MAX * 0.5) else 0.0
            if x_std > 0 and x_std <= OCRThresholds.SUBTITLE_X_VARIANCE_MAX:
                score += 0.5
            sample_text = str(entry.get('text', '') or entry.get('sample_text', ''))
            chinese_chars = sum(1 for ch in sample_text if '\u4e00' <= ch <= '\u9fff')
            score += 1.0 if chinese_chars >= 2 else (0.5 if chinese_chars >= 1 else 0.0)
            score += 0.5 if float(entry.get('frequency', 0) or 0) >= 3 else 0.0
            if is_early_region and time_group_count < OCRThresholds.SUBTITLE_MIN_TIME_GROUPS:
                score += 0.5
            if score < OCRThresholds.SUBTITLE_SCORE_THRESHOLD:
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
    def _gpu_process_bbox_batch(self, bboxes, W, H):
        """
        GPU/NumPy accelerated batch processing of bounding boxes.

        Args:
            bboxes: List of bounding boxes (each with 4 points)
            W: Video width
            H: Video height

        Returns:
            List of processed region info (x%, y%, width%, height%)
        """
        if not NUMPY_AVAILABLE or not bboxes:
            return []

        try:
            regions = []
            use_gpu = GPU_ACCEL_AVAILABLE

            for bbox in bboxes:
                if len(bbox) >= 4:
                    try:
                        if use_gpu:
                            try:
                                # GPU 媛??踰꾩쟾
                                coords = xp.array(bbox, dtype=xp.float32)
                                x_coords = coords[:, 0]
                                y_coords = coords[:, 1]

                                x_min = max(0, int(xp.min(x_coords).get()))
                                y_min = max(0, int(xp.min(y_coords).get()))
                                x_max = min(W, int(xp.max(x_coords).get()))
                                y_max = min(H, int(xp.max(y_coords).get()))
                            except Exception:
                                # GPU ?ㅽ뙣 ??NumPy濡??대갚
                                use_gpu = False
                                coords = np.array(bbox, dtype=np.float32)
                                x_coords = coords[:, 0]
                                y_coords = coords[:, 1]

                                x_min = max(0, int(np.min(x_coords)))
                                y_min = max(0, int(np.min(y_coords)))
                                x_max = min(W, int(np.max(x_coords)))
                                y_max = min(H, int(np.max(y_coords)))
                        else:
                            # NumPy 踰꾩쟾
                            coords = np.array(bbox, dtype=np.float32)
                            x_coords = coords[:, 0]
                            y_coords = coords[:, 1]

                            x_min = max(0, int(np.min(x_coords)))
                            y_min = max(0, int(np.min(y_coords)))
                            x_max = min(W, int(np.max(x_coords)))
                            y_max = min(H, int(np.max(y_coords)))

                        width = x_max - x_min
                        height = y_max - y_min

                        # ??理쒖냼 bbox ?ш린 寃利?(constants.py?먯꽌 ?ㅼ젙)
                        if width < OCRThresholds.MIN_BBOX_WIDTH or height < OCRThresholds.MIN_BBOX_HEIGHT:
                            continue
                        if width > W * 0.98 or height > H * 0.5:  # ?믪씠 ?쒗븳 ?꾪솕 (0.4 -> 0.5)
                            continue

                        regions.append({
                            'x': round(100.0 * x_min / W, 1),
                            'y': round(100.0 * y_min / H, 1),
                            'width': max(0.5, round(100.0 * width / W, 1)),
                            'height': max(0.5, round(100.0 * height / H, 1)),
                            'x_min': x_min,
                            'y_min': y_min,
                            'x_max': x_max,
                            'y_max': y_max
                        })
                    except Exception:
                        continue

            return regions
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[GPU Accel] bbox processing error: {e}")
            return []

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

    def _gpu_aggregate_regions(self, all_regions):
        """
        GPU/NumPy accelerated region aggregation with spatial-first clustering.

        ?끸쁾??媛쒖꽑: 怨듦컙-?곗꽑(spatial-first) ?대윭?ㅽ꽣留??끸쁾??        湲곗〈 臾몄젣: ?쒓컙-?곗꽑 洹몃９?????쒓컙??蹂묓빀 ??Y醫뚰몴 誘몄꽭蹂?숈쑝濡?蹂묓빀 ?ㅽ뙣 ???쒓컙 媛?諛쒖깮
        ?닿껐: 紐⑤뱺 ?쒓컙???媛먯?瑜?怨듦컙?곸쑝濡?癒쇱? ?대윭?ㅽ꽣留???媛??대윭?ㅽ꽣???쒓컙 踰붿쐞瑜??곗냽?쇰줈 怨꾩궛

        Phase 1: ?꾩껜 媛먯? 寃곌낵瑜?怨듦컙???좎궗??IoU + ??洹쇱젒???쇰줈 ?대윭?ㅽ꽣留?        Phase 2: 媛?怨듦컙 ?대윭?ㅽ꽣?먯꽌 媛먯? ?쒓컙?ㅼ쓣 ?섏쭛?섏뿬 ?곗냽 ?쒓컙 援ш컙 怨꾩궛
        Phase 3: ?쒓컙 援ш컙蹂?釉붾윭 ?곸뿭 異쒕젰 (?숈씪 ?꾩튂 ?먮쭑???щ씪議뚮떎 ?ъ텧?꾪븯硫?蹂꾨룄 援ш컙)

        Args:
            all_regions: List of all detected regions across all time groups

        Returns:
            List of regions with continuous time ranges per spatial cluster
        """
        if not all_regions or not NUMPY_AVAILABLE:
            return []

        try:
            # ===== Phase 1: 怨듦컙-?곗꽑 ?대윭?ㅽ꽣留?(?꾩껜 ?쒓컙? ?듯빀) =====
            # 紐⑤뱺 媛먯? 寃곌낵瑜?怨듦컙???좎궗?깅쭔?쇰줈 ?대윭?ㅽ꽣留?            # ?대젃寃??섎㈃ Y醫뚰몴 誘몄꽭蹂?숈뿉??媛숈? ?먮쭑?쇰줈 臾띠엫
            spatial_clusters = []

            for region in all_regions:
                added = False
                for cluster in spatial_clusters:
                    # ?대윭?ㅽ꽣?????bbox(泥?硫ㅻ쾭 湲곕컲 以묒븰媛?? 鍮꾧탳?섏뿬 ?쒕━?꾪듃 諛⑹?
                    rep = cluster['representative']
                    iou = self._calculate_iou(region, rep)

                    # Y 以묒떖 洹쇱젒??泥댄겕 (媛숈? ?됱쓽 ?먮쭑)
                    y_center_region = region['y'] + region['height'] / 2.0
                    y_center_cluster = rep['y'] + rep['height'] / 2.0
                    same_row = abs(y_center_region - y_center_cluster) <= max(region['height'], rep['height']) * OCRThresholds.SAME_ROW_MULTIPLIER

                    # ?섑룊 媛?泥댄겕
                    region_right = region['x'] + region['width']
                    rep_right = rep['x'] + rep['width']
                    horizontal_gap = max(0.0, max(region['x'] - rep_right, rep['x'] - region_right))
                    proximity = same_row and horizontal_gap <= OCRThresholds.HORIZONTAL_GAP_THRESHOLD

                    if iou > OCRThresholds.IOU_CLUSTER_THRESHOLD or proximity:
                        cluster['members'].append(region)
                        # union bbox 媛깆떊 (異쒕젰??
                        bbox = cluster['bbox']
                        new_left = min(bbox['x'], region['x'])
                        new_top = min(bbox['y'], region['y'])
                        new_right = max(bbox['x'] + bbox['width'], region['x'] + region['width'])
                        new_bottom = max(bbox['y'] + bbox['height'], region['y'] + region['height'])
                        cluster['bbox'] = {
                            'x': new_left,
                            'y': new_top,
                            'width': new_right - new_left,
                            'height': new_bottom - new_top,
                        }
                        # representative??媛깆떊?섏? ?딆쓬 ??泥댁씤 癒몄? 諛⑹?
                        added = True
                        break

                if not added:
                    init_bbox = {
                        'x': region['x'],
                        'y': region['y'],
                        'width': region['width'],
                        'height': region['height'],
                    }
                    spatial_clusters.append({
                        'bbox': dict(init_bbox),
                        'representative': dict(init_bbox),
                        'members': [region],
                    })

            logger.debug(f"[Spatial-first clustering] {len(all_regions)} detections -> {len(spatial_clusters)} spatial clusters")

            # ===== Phase 2: 媛?怨듦컙 ?대윭?ㅽ꽣?먯꽌 ?곗냽 ?쒓컙 援ш컙 怨꾩궛 =====
            merged_regions = []

            for cluster_idx, cluster in enumerate(spatial_clusters):
                members = cluster['members']
                bbox = cluster['bbox']

                # 紐⑤뱺 媛먯? ?쒓컙 ?섏쭛 諛??뺣젹
                times = sorted(set(round(m.get('time', 0), 2) for m in members))
                if not times:
                    continue

                # ?곗냽 ?쒓컙 援ш컙 遺꾪븷 (媛?씠 ?꾧퀎媛??댁긽?대㈃ 蹂꾨룄 援ш컙)
                # 媛숈? ?꾩튂 ?먮쭑???좉퉸 ?щ씪議뚮떎 ?ъ텧?꾪븯??寃쎌슦瑜?泥섎━
                time_segments = []
                seg_start = times[0]
                seg_end = times[0]

                for t in times[1:]:
                    if t - seg_end <= OCRThresholds.TIME_SEGMENT_GAP:
                        seg_end = t
                    else:
                        time_segments.append((seg_start, seg_end))
                        seg_start = t
                        seg_end = t
                time_segments.append((seg_start, seg_end))

                # ===== Phase 3: ?쒓컙 援ш컙蹂?釉붾윭 ?곸뿭 異쒕젰 =====
                for seg_idx, (seg_start, seg_end) in enumerate(time_segments):
                    # ?쒓컙 踰꾪띁 ?곸슜
                    buffered_start = max(0.0, seg_start - OCRThresholds.TIME_BUFFER_BEFORE)
                    buffered_end = seg_end + OCRThresholds.TIME_BUFFER_AFTER

                    # 怨듦컙 諛붿슫??諛뺤뒪???⑤뵫 異붽?
                    pad = OCRThresholds.SPATIAL_PADDING
                    x = max(0.0, bbox['x'] - pad)
                    y = max(0.0, bbox['y'] - pad)
                    right = min(100.0, bbox['x'] + bbox['width'] + pad)
                    bottom = min(100.0, bbox['y'] + bbox['height'] + pad)

                    sample_text = next((m.get('text', '') for m in members if m.get('text')), '')
                    # ???쒓컙 援ш컙???랁븯??硫ㅻ쾭?ㅼ쓽 Y ?꾩튂 ?섏쭛
                    seg_members = [m for m in members if seg_start <= m.get('time', 0) <= seg_end]
                    y_positions = [float(m.get('y', 0)) for m in seg_members]
                    x_positions = [float(m.get('x', 0)) for m in seg_members]
                    frame_regions = []
                    for member in seg_members:
                        polygon = member.get('polygon')
                        if not polygon:
                            continue
                        frame_regions.append({
                            'time': float(member.get('time', 0)),
                            'frame_index': int(member.get('frame_index', -1)),
                            'polygon': polygon,
                            'text': str(member.get('text', '')),
                            'confidence': float(member.get('confidence', 0.0)),
                        })
                    frame_regions.sort(key=lambda fr: (fr.get('frame_index', -1), fr.get('time', 0.0)))
                    # 異쒗쁽???쒓컙 洹몃９(0.5珥??⑥쐞) ??怨꾩궛
                    time_group_count = len(set(round(m.get('time', 0) * 2) / 2 for m in seg_members))

                    source_name = 'opencv_ocr_gpu' if GPU_ACCEL_AVAILABLE else 'opencv_ocr_numpy'
                    merged_regions.append({
                        'x': x,
                        'y': y,
                        'width': max(1.0, right - x),
                        'height': max(1.0, bottom - y),
                        'frequency': len(seg_members),
                        'language': 'chinese',
                        'source': source_name,
                        'sample_text': sample_text,
                        'start_time': buffered_start,
                        'end_time': buffered_end,
                        'cluster_id': f"spatial_{cluster_idx}_{seg_idx}",
                        'y_positions': y_positions,
                        'x_positions': x_positions,
                        'time_group_count': time_group_count,
                        'frame_regions': frame_regions,
                    })

            # ?쒓컙???뺣젹
            merged_regions.sort(key=lambda r: (r['start_time'], r['y']))

            logger.info(f"[Multi-subtitle merge] {len(all_regions)} detections -> {len(spatial_clusters)} clusters -> {len(merged_regions)} blur regions")
            for i, r in enumerate(merged_regions):
                tg = r.get('time_group_count', 1)
                yp = r.get('y_positions', [])
                y_std_str = ""
                if yp and len(yp) >= 2:
                    try:
                        y_std_val = float(np.std(yp)) if NUMPY_AVAILABLE else 0.0
                        y_std_str = f", Y?몄감={y_std_val:.1f}%"
                    except Exception:
                        pass
                logger.debug(f"  Region #{i+1}: pos=({r['x']:.0f}%, {r['y']:.0f}%), size=({r['width']:.0f}%, {r['height']:.0f}%), time={r['start_time']:.1f}s~{r['end_time']:.1f}s, frames={tg}{y_std_str}, text='{r.get('sample_text', '')[:20]}'")

            return merged_regions
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[GPU Accel] Region aggregation error: {e}")
            return []

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

        batch_size = GLMOCRSettings.OPTIMAL_BATCH_SIZE
        all_regions = []
        frames_with_chinese = 0
        ocr_call_count = 0

        # ?꾨젅???섏쭛 諛?諛곗튂 泥섎━
        frame_data = []  # (frame_pos, frame, scale)

        logger.info(f"[OCR {segment_name}] Batch mode: collecting {len(sample_frames)} frames")

        # 1?④퀎: 紐⑤뱺 ?꾨젅???섏쭛 諛??꾩쿂由?
        for frame_pos in sample_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            if not ret:
                continue

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

            frame_data.append((frame_pos, frame, scale))

        if not frame_data:
            return None

        # 2?④퀎: 諛곗튂 ?⑥쐞濡?OCR ?섑뻾
        total_batches = (len(frame_data) + batch_size - 1) // batch_size
        logger.info(f"[OCR {segment_name}] Processing {len(frame_data)} frames in {total_batches} batches")

        for batch_idx in range(0, len(frame_data), batch_size):
            batch = frame_data[batch_idx:batch_idx + batch_size]
            frames_only = [f[1] for f in batch]

            try:
                # 諛곗튂 OCR ?몄텧
                batch_results = ocr_reader.readtext_batch(frames_only)
                ocr_call_count += 1  # 諛곗튂??1???몄텧濡?移댁슫??
                # 媛??꾨젅?꾨퀎 寃곌낵 泥섎━
                for i, (frame_pos, frame, scale) in enumerate(batch):
                    if i >= len(batch_results):
                        continue

                    results = batch_results[i]
                    time_sec = frame_pos / fps
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
                        if region_info and polygon:
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
                            }
                            all_regions.append(region)

                    if frame_has_chinese:
                        frames_with_chinese += 1

            except Exception as e:
                logger.warning(f"[OCR {segment_name}] Batch {batch_idx // batch_size + 1} error: {e}")
                # 諛곗튂 ?ㅽ뙣 ??媛쒕퀎 泥섎━濡??대갚
                for frame_pos, frame, scale in batch:
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
            start_frame = int(fps * start_sec)
            end_frame = min(int(fps * end_sec), total_frames)

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
            ocr_reader = getattr(self.gui, 'ocr_reader', None)
            use_batch_mode = (
                ocr_reader is not None and
                hasattr(ocr_reader, 'supports_batch') and
                ocr_reader.supports_batch() and
                ocr_reader.engine_name == 'glm_ocr'
            )
            if full_scan_mode:
                use_batch_mode = False

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
            # ?끸쁾??珥덉븞??紐⑤뱶: 留ㅼ슦 蹂댁닔?곸씤 ?꾧퀎媛?+ ?곗냽 泥댄겕 ?끸쁾??            # Use constants for thresholds
            # ?꾧퀎媛??곸닔 ?ъ슜
            ssim_threshold = OCRThresholds.SSIM_THRESHOLD  # 98% (嫄곗쓽 ?쎌? ?숈씪)
            edge_change_threshold = OCRThresholds.EDGE_CHANGE_THRESHOLD  # 0.1% 蹂??媛먯?
            # 1920x540 ROI?먯꽌 0.1% = 1,036 ?쎌? (??湲??蹂寃쎈룄 媛먯?)

            # ?끸쁾??異붽? ?덉쟾?μ튂: ?곗냽 2?꾨젅???댁긽 ?숈씪?댁빞 ?ㅽ궢 ?끸쁾??            # ?먮쭑??諛붾뚮뒗 ?쒓컙(?꾪솚 ?꾨젅?????볦튂吏 ?딄린 ?꾪븿
            min_consecutive_similar = 2

            for i, frame_pos in enumerate(sample_frames):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                ret, frame = cap.read()
                if not ret:
                    continue

                time_sec = frame_pos / fps

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
                            'confidence': prob,
                            'time': time_sec,
                            'frame_index': int(frame_pos),
                            'text': text,
                            'language': 'chinese',
                            'source': source_tag,
                            'roi_type': attempt_name,  # ?대뒓 ROI?먯꽌 媛먯??섏뿀?붿? 湲곕줉
                            'polygon': polygon,
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
                                for bf in boundary_list:
                                    cap2.set(cv2.CAP_PROP_POS_FRAMES, bf)
                                    ret2, frame2 = cap2.read()
                                    if not ret2:
                                        continue
                                    time_sec2 = bf / fps

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
                                        if region_info2 and polygon2:
                                            all_regions.append({
                                                'x': region_info2[0]['x'],
                                                'y': region_info2[0]['y'],
                                                'width': region_info2[0]['width'],
                                                'height': region_info2[0]['height'],
                                                'confidence': prob2,
                                                'time': time_sec2,
                                                'frame_index': int(bf),
                                                'text': text2,
                                                'language': 'chinese',
                                                'source': 'boundary_refine',
                                                'polygon': polygon2,
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

