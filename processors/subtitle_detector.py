"""
Subtitle Detection Processor

This module handles OCR-based Chinese subtitle detection with GPU/NumPy acceleration.
Integrates HybridSubtitleDetector for optimized OCR calls (40% reduction).
"""

import os
from typing import Any, Dict, List, Optional, Iterable

# Logging configuration
# 로깅 설정
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Import constants
# 상수 임포트
from config.constants import OCRThresholds, VideoSettings, GLMOCRSettings

try:
    import cv2
    CV2_AVAILABLE = True
except Exception:
    cv2 = None
    CV2_AVAILABLE = False

# OCR 가용성 플래그 (RapidOCR만 지원)
OCR_AVAILABLE = False

# OCRBackend 래퍼 사용 (RapidOCR 전용)
try:
    from utils.ocr_backend import OCRBackend
    OCR_BACKEND_AVAILABLE = True
    OCR_AVAILABLE = True
except ImportError:
    OCR_BACKEND_AVAILABLE = False

# 하이브리드 감지기 (Canny + 멀티프레임 최적화)
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
# CuPy 사용 불가 시 NumPy로 자동 전환 (Python 3.14+ 또는 CUDA 없음)
GPU_ACCEL_AVAILABLE = False
xp = np  # Default to NumPy

try:
    import cupy as cp
    # Test GPU availability - verify CUDA device accessible
    # GPU 가용성 테스트 - CUDA 디바이스 접근 가능 여부 확인
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

# 시스템 최적화 모듈
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
        """하이브리드 감지기 초기화 (옵션)"""
        if not HYBRID_DETECTOR_AVAILABLE:
            # Hybrid detector not available - fallback to basic mode silently
            return

        ocr_reader = getattr(self.gui, "ocr_reader", None)
        if not ocr_reader:
            # OCR reader not ready - wait for initialization silently
            return

        try:
            # 시스템 최적화 파라미터 가져오기
            optimizer = _get_optimizer(self.gui)
            if optimizer:
                ocr_params = optimizer.get_optimized_ocr_params()
                min_interval = ocr_params.get('sample_interval', 0.3)
            else:
                min_interval = 0.3

            self.hybrid_detector = create_hybrid_detector(
                ocr_reader,
                min_interval=min_interval,
                fast_threshold=15.0,  # Canny 변화 감지 임계값
                confirm_threshold=0.80  # 멀티프레임 유사도 임계값
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

        # OCR reader 가용성 확인
        ocr_reader = getattr(self.gui, "ocr_reader", None)
        if not ocr_reader:
            logger.warning("[OCR 감지] ocr_reader가 None - OCR 없이 하단 자막 밴드 폴백 감지를 시도합니다.")
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

            # 먼저 비디오 정보 확인 (try/finally로 리소스 해제 보장)
            # Ensure VideoCapture is released even if exception occurs
            cap = cv2.VideoCapture(video_path)
            try:
                if not cap.isOpened():
                    # Cannot open video file
                    return None

                W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                # FPS 폴백: 메타데이터가 없거나 유효하지 않으면 30fps로 가정
                # None, NaN, 0, 음수 모두 처리
                import math
                fps = cap.get(cv2.CAP_PROP_FPS)
                if not fps or not math.isfinite(fps) or fps <= 0:
                    fps = 30.0
                    logger.warning(f"[OCR] FPS metadata missing, using default {fps}fps")

                # 프레임 수 폴백: NaN이면 0으로 처리
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

            # 전체 영상을 10초 단위로 분할하여 모든 구간 검사
            segments = []
            segment_duration = 10  # 10초 단위

            # 0초부터 영상 끝까지 10초 단위로 구간 생성
            current_start = 0
            segment_idx = 1
            while current_start < total_duration:
                end_sec = min(current_start + segment_duration, total_duration)
                # 최소 1초 이상인 구간만 추가
                if end_sec - current_start >= 1:
                    segments.append({
                        'name': f'{int(current_start)}-{int(end_sec)}초',
                        'start_sec': current_start,
                        'end_sec': end_sec
                    })
                current_start += segment_duration
                segment_idx += 1

            if not segments:
                # No segments to analyze (video shorter than 1 second)
                return None

            # Parallel segment analysis starting (silently)

            # 병렬로 각 구간 처리
            all_regions_combined = []
            frames_with_chinese_total = 0
            total_sample_frames = 0            # 시스템 최적화 설정 사용
            optimizer = _get_optimizer(self.gui)
            if optimizer:
                ocr_params = optimizer.get_optimized_ocr_params()
                max_workers = ocr_params['max_workers']
                logger.info(f"[OCR Parallel] System optimized: {max_workers} workers")
            else:
                # 기본값
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

            # 병렬 처리 결과 사용
            all_regions = all_regions_combined
            frames_with_chinese = frames_with_chinese_total
            sample_frames_count = total_sample_frames

            # 결과 분석
            if not all_regions:
                # No Chinese subtitles detected in any segment
                fallback = self._fallback_detect_bottom_subtitle_band(video_path, W=W, H=H, fps=fps, total_frames=total_frames)
                return fallback or None

            # Chinese subtitles detected (processing silently)

            # ★★★ 개선: 감지 비율 임계치 1%로 하향 (초민감 모드) ★★★
            # 단 1개 프레임이라도 중국어가 감지되면 블러 처리
            detection_rate = frames_with_chinese / sample_frames_count if sample_frames_count > 0 else 0

            # 최소 1개 프레임에서 중국어가 감지되었으면 블러 적용
            if frames_with_chinese == 0:
                logger.info("[OCR Parallel] No Chinese detected in any frame - trying fallback band detection")
                fallback = self._fallback_detect_bottom_subtitle_band(video_path, W=W, H=H, fps=fps, total_frames=total_frames)
                return fallback or None
            elif detection_rate < 0.01:
                # 1% 미만이어도 감지된 프레임이 있으면 경고만 출력하고 진행
                logger.warning(f"[OCR Parallel] Very low Chinese detection rate: {detection_rate*100:.2f}% ({frames_with_chinese} frames)")
                logger.info("[OCR Parallel] Subtitles may only appear in some segments - proceeding with blur")
            else:
                logger.info(f"[OCR Parallel] Chinese detection rate: {detection_rate*100:.1f}% - proceeding with blur")

            # ===== GPU/NumPy 가속: 빈도 기반 필터링 =====
            accel_name = "GPU Accel" if GPU_ACCEL_AVAILABLE else "NumPy Accel"
            logger.debug(f"[{accel_name}] Region aggregation starting - {len(all_regions)} regions")
            reliable_regions = self._gpu_aggregate_regions(all_regions)

            if not reliable_regions:
                logger.debug(f'[OCR {accel_name}] No trusted subtitle region found - using fallback with spatial clustering')
                # ★★★ 개선: Fallback 시에도 IoU 기반 클러스터링으로 분리된 박스 유지 ★★★
                if all_regions:
                    # 모든 영역을 IoU 기반으로 클러스터링
                    clusters = []
                    for region in all_regions:
                        added_to_cluster = False
                        for cluster in clusters:
                            representative = cluster[0]
                            iou = self._calculate_iou(region, representative)
                            # ★ IoU 임계값 낮춤: 별도 자막이 병합되지 않도록 (0.3 -> 0.15)
                            if iou > OCRThresholds.IOU_CLUSTER_THRESHOLD:
                                cluster.append(region)
                                added_to_cluster = True
                                break
                        if not added_to_cluster:
                            clusters.append([region])

                    logger.debug(f'[Fallback] {len(all_regions)} regions -> {len(clusters)} clusters created')

                    # 각 클러스터마다 별도의 fallback 영역 생성
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
                        fallback_region = {
                            'x': min_x,
                            'y': min_y,
                            'width': max(5, max_x - min_x),
                            'height': max(5, max_y - min_y),
                            'frequency': len(cluster),
                            'language': 'unknown',
                            'source': source_name,
                            'sample_text': next((r.get('text') for r in cluster if r.get('text')), ''),
                            'fallback_cluster': cluster_idx
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
            # 메모리 정리: 명시적 가비지 컬렉션
            import gc
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
        OCR 없이도 하단 자막 밴드를 감지하는 폴백.

        목표:
        - 사용자 PC에 OCR 엔진이 없거나(OCR 초기화 실패 포함),
          OCR이 중국어를 잘 못 읽는 상황에서도 "블러가 아예 안 되는" 상황을 방지.

        방식:
        - 영상에서 몇 프레임을 샘플링
        - 하단 ROI(기본 72%~95%)의 엣지 밀도를 계산
        - 텍스트/자막처럼 고주파(엣지)가 지속적으로 나타나면 하단 밴드를 블러 대상으로 반환
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
            "cn", "han", "중국", "중문"
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
                reason = f"언어 태그 '{lang}'가 중국어"
                filtered.append(entry)
            elif text and any('\u4e00' <= ch <= '\u9fff' for ch in text):
                chinese_in_text = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
                reason = f"텍스트에 중국어 {chinese_in_text}자 포함"
                filtered.append(entry)
            elif sample and any('\u4e00' <= ch <= '\u9fff' for ch in sample):
                chinese_in_sample = sum(1 for ch in sample if '\u4e00' <= ch <= '\u9fff')
                reason = f"샘플텍스트에 중국어 {chinese_in_sample}자 포함"
                filtered.append(entry)
            elif source in {'rapidocr', 'rapidocr_gpu', 'opencv_ocr', 'opencv_ocr_gpu', 'opencv_ocr_numpy'} and not lang:
                reason = f"OCR 소스 '{source}'에서 감지"
                filtered.append(entry)
            elif source.startswith("fallback_region"):
                reason = "OCR 폴백 자막 밴드"
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
                self.gui.add_log(f"[블러] 의심스러운 큰 영역을 제외합니다: "
                             f"w={width_pct:.1f}%, h={height_pct:.1f}% (source={entry.get('source')})")
                continue

            # === 모든 중국어 텍스트 블러 처리 ===
            # 위치 관계없이 중국어가 감지되면 블러 적용
            logger.debug(f"  -> Chinese text blur target: y={y_pct:.1f}%")

            # ★★★ Fallback 영역 조건 완화: OCR이 위치는 맞췄지만 텍스트 인식 실패 시에도 블러 적용 ★★★
            # source 타입 안전성 확보
            source = str(entry.get('source') or '')
            # fallback_region이라도 OCR 소스에서 감지된 것이면 블러 적용
            # (sample_text에 중국어가 없어도 위치 정보가 있으면 적용)
            if source.startswith('fallback_region'):
                sample_text = str(entry.get('sample_text', '') or '')
                has_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in sample_text)
                # 중국어가 있거나, 텍스트가 비어있어도 위치 정보가 유효하면 통과
                # (OCR이 위치는 맞췄지만 텍스트 인식에 실패한 경우도 블러 적용)
                if not has_chinese and sample_text.strip():
                    # 중국어가 아닌 다른 텍스트가 있으면 제외 (영어 등)
                    logger.debug(f"  -> Excluded: Fallback region with non-Chinese text: '{sample_text[:20]}'")
                    continue
                # sample_text가 비어있으면 통과 (위치 정보만 있는 경우)
                logger.debug(f"  -> Fallback region accepted: sample_text='{sample_text[:20] if sample_text else '(empty)'}'")

            logger.debug("  -> Final pass OK")
            safe_filtered.append(entry)

        logger.debug("=" * 60)
        logger.info(f"[BLUR FILTER] Final blur targets: {len(safe_filtered)} regions")
        for i, entry in enumerate(safe_filtered):
            logger.debug(f"  #{i+1}: x={entry.get('x')}%, y={entry.get('y')}%, w={entry.get('width')}%, h={entry.get('height')}%, text='{str(entry.get('text', ''))[:30]}...'")
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

    # ========== GPU/NumPy 가속 유틸리티 함수 ==========

    def _gpu_check_chinese_chars(self, texts):
        """
        GPU/NumPy accelerated Chinese character counting.

        Args:
            texts: List of text strings

        Returns:
            List of Chinese character counts for each text
        """
        if not NUMPY_AVAILABLE:
            # NumPy 없으면 일반 방식
            return [sum(1 for c in text if '\u4e00' <= c <= '\u9fff') for text in texts]

        try:
            # 각 텍스트의 중국어 문자 개수 계산
            counts = []
            for text in texts:
                # 유니코드 포인트로 변환 후 범위 체크
                if GPU_ACCEL_AVAILABLE:
                    try:
                        # GPU 가속 버전
                        unicode_points = xp.array([ord(c) for c in text], dtype=xp.int32)
                        is_chinese = (unicode_points >= 0x4e00) & (unicode_points <= 0x9fff)
                        count = int(xp.sum(is_chinese))
                    except (RuntimeError, AttributeError):
                        # CuPy 실행 중 오류 발생 시 NumPy로 폴백
                        unicode_points = np.array([ord(c) for c in text], dtype=np.int32)
                        is_chinese = (unicode_points >= 0x4e00) & (unicode_points <= 0x9fff)
                        count = int(np.sum(is_chinese))
                else:
                    # NumPy 버전
                    unicode_points = np.array([ord(c) for c in text], dtype=np.int32)
                    is_chinese = (unicode_points >= 0x4e00) & (unicode_points <= 0x9fff)
                    count = int(np.sum(is_chinese))
                counts.append(count)
            return counts
        except Exception as e:
            ui_controller.write_error_log(e)
            # 오류 시 일반 방식으로 폴백
            return [sum(1 for c in text if '\u4e00' <= c <= '\u9fff') for text in texts]

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
                                # GPU 가속 버전
                                coords = xp.array(bbox, dtype=xp.float32)
                                x_coords = coords[:, 0]
                                y_coords = coords[:, 1]

                                x_min = max(0, int(xp.min(x_coords).get()))
                                y_min = max(0, int(xp.min(y_coords).get()))
                                x_max = min(W, int(xp.max(x_coords).get()))
                                y_max = min(H, int(xp.max(y_coords).get()))
                            except Exception:
                                # GPU 실패 시 NumPy로 폴백
                                use_gpu = False
                                coords = np.array(bbox, dtype=np.float32)
                                x_coords = coords[:, 0]
                                y_coords = coords[:, 1]

                                x_min = max(0, int(np.min(x_coords)))
                                y_min = max(0, int(np.min(y_coords)))
                                x_max = min(W, int(np.max(x_coords)))
                                y_max = min(H, int(np.max(y_coords)))
                        else:
                            # NumPy 버전
                            coords = np.array(bbox, dtype=np.float32)
                            x_coords = coords[:, 0]
                            y_coords = coords[:, 1]

                            x_min = max(0, int(np.min(x_coords)))
                            y_min = max(0, int(np.min(y_coords)))
                            x_max = min(W, int(np.max(x_coords)))
                            y_max = min(H, int(np.max(y_coords)))

                        width = x_max - x_min
                        height = y_max - y_min

                        # ★ 최소 bbox 크기 검증 (constants.py에서 설정)
                        if width < OCRThresholds.MIN_BBOX_WIDTH or height < OCRThresholds.MIN_BBOX_HEIGHT:
                            continue
                        if width > W * 0.98 or height > H * 0.5:  # 높이 제한 완화 (0.4 -> 0.5)
                            continue

                        regions.append({
                            'x': int(100 * x_min / W),
                            'y': int(100 * y_min / H),
                            'width': int(100 * width / W),
                            # Use the video height to compute the percentage height of the box
                            'height': int(100 * height / H),
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
        GPU/NumPy accelerated region frequency calculation and aggregation.
        ★ 개선: IoU 기반 클러스터링으로 공간적으로 분리된 자막을 개별 추적 ★

        Args:
            all_regions: List of all detected regions

        Returns:
            List of regions with precise time ranges (each subtitle appearance as separate entry)
        """
        if not all_regions or not NUMPY_AVAILABLE:
            return []

        try:
            # ★ 핵심 변경 1: 시간별로 먼저 그룹화 (0.5초 단위) ★
            time_groups = {}

            for region in all_regions:
                time_sec = region.get('time', 0)
                time_key = round(time_sec * 2) / 2  # 0, 0.5, 1.0, 1.5, ...

                if time_key not in time_groups:
                    time_groups[time_key] = []
                time_groups[time_key].append(region)

            logger.debug(f"[Multi-subtitle detection] {len(time_groups)} time groups created")

            # ★ 핵심 변경 2: 각 시간대에서 IoU 기반 클러스터링으로 공간 분리 ★
            reliable_regions = []

            for time_key, regions in time_groups.items():
                # IoU 기반 클러스터링: 같은 시간대에 공간적으로 분리된 자막들 분리
                clusters = []

                for region in regions:
                    added_to_cluster = False

                    # 기존 클러스터 중 IoU가 높은 곳에 추가
                    for cluster in clusters:
                        # 클러스터 대표와 IoU 계산
                        representative = cluster[0]
                        iou = self._calculate_iou(region, representative)

                        # ★ IoU 임계값 낮춤: 별도 자막이 병합되지 않도록 (0.3 -> 0.15)
                        if iou > OCRThresholds.IOU_CLUSTER_THRESHOLD:
                            cluster.append(region)
                            added_to_cluster = True
                            break

                    # 새로운 클러스터 생성 (공간적으로 분리된 자막)
                    if not added_to_cluster:
                        clusters.append([region])

                logger.debug(f"  Time {time_key:.1f}s: {len(regions)} boxes -> {len(clusters)} subtitle regions")

                # 각 클러스터(개별 자막)마다 하나의 블러 영역 생성
                for cluster_idx, cluster in enumerate(clusters):
                    try:
                        if GPU_ACCEL_AVAILABLE:
                            x_values = xp.array([r['x'] for r in cluster], dtype=xp.float32)
                            y_values = xp.array([r['y'] for r in cluster], dtype=xp.float32)
                            width_values = xp.array([r['width'] for r in cluster], dtype=xp.float32)
                            height_values = xp.array([r['height'] for r in cluster], dtype=xp.float32)
                            avg_x = int(xp.mean(x_values).get())
                            avg_y = int(xp.mean(y_values).get())
                            avg_width = int(xp.mean(width_values).get())
                            avg_height = int(xp.mean(height_values).get())
                        else:
                            x_values = np.array([r['x'] for r in cluster], dtype=np.float32)
                            y_values = np.array([r['y'] for r in cluster], dtype=np.float32)
                            width_values = np.array([r['width'] for r in cluster], dtype=np.float32)
                            height_values = np.array([r['height'] for r in cluster], dtype=np.float32)
                            avg_x = int(np.mean(x_values))
                            avg_y = int(np.mean(y_values))
                            avg_width = int(np.mean(width_values))
                            avg_height = int(np.mean(height_values))
                    except Exception:
                        avg_x = int(sum(r['x'] for r in cluster) / len(cluster))
                        avg_y = int(sum(r['y'] for r in cluster) / len(cluster))
                        avg_width = int(sum(r['width'] for r in cluster) / len(cluster))
                        avg_height = int(sum(r['height'] for r in cluster) / len(cluster))

                    sample_text = next((r.get('text', '') for r in cluster if r.get('text')), '')

                    # ★★★ 100% 감지 모드: 일관된 시간 버퍼 적용 (constants.py에서 설정) ★★★
                    if time_key <= OCRThresholds.TIME_BUFFER_BEFORE:
                        start_time = 0
                    else:
                        start_time = max(0, time_key - OCRThresholds.TIME_BUFFER_BEFORE)
                    end_time = time_key + OCRThresholds.TIME_BUFFER_AFTER

                    source_name = 'opencv_ocr_gpu' if GPU_ACCEL_AVAILABLE else 'opencv_ocr_numpy'
                    reliable_regions.append({
                        'x': max(0, avg_x - 2),
                        'y': max(0, avg_y - 2),
                        'width': min(100, avg_width + 4),
                        'height': min(100, avg_height + 4),
                        'frequency': len(cluster),
                        'language': 'chinese',
                        'source': source_name,
                        'sample_text': sample_text,
                        'start_time': start_time,
                        'end_time': end_time,
                        'cluster_id': f"{time_key}_{cluster_idx}"
                    })

            # ★★★ 연속된 시간대의 "동일 트랙" 영역만 병합 (IoU 기반으로 공간 유사성 확인) ★★★
            # 시간순 정렬
            reliable_regions.sort(key=lambda r: (r['y'], r['start_time']))

            merged_regions = []
            for region in reliable_regions:
                merged = False
                for existing in merged_regions:
                    # IoU 계산 (공간적 유사성)
                    iou = self._calculate_iou(existing, region)

                    # ★ 같은 트랙 조건: IoU 임계값 낮춤 (0.4 -> 0.25)
                    # 공간적으로 분리된 자막은 IoU가 낮아 병합되지 않음
                    if (iou > OCRThresholds.IOU_MERGE_THRESHOLD and existing['end_time'] >= region['start_time'] - 1.0):
                        # 시간 범위 확장 (공간은 평균으로 갱신)
                        total_freq = existing['frequency'] + region['frequency']
                        existing['x'] = int((existing['x'] * existing['frequency'] + region['x'] * region['frequency']) / total_freq)
                        existing['y'] = int((existing['y'] * existing['frequency'] + region['y'] * region['frequency']) / total_freq)
                        existing['width'] = int((existing['width'] * existing['frequency'] + region['width'] * region['frequency']) / total_freq)
                        existing['height'] = int((existing['height'] * existing['frequency'] + region['height'] * region['frequency']) / total_freq)
                        existing['start_time'] = min(existing['start_time'], region['start_time'])
                        existing['end_time'] = max(existing['end_time'], region['end_time'])
                        existing['frequency'] = total_freq
                        merged = True
                        break

                if not merged:
                    merged_regions.append(region.copy())

            logger.info(f"[Multi-subtitle merge] {len(reliable_regions)} -> {len(merged_regions)} independent subtitle regions")
            for i, r in enumerate(merged_regions):
                logger.debug(f"  Subtitle #{i+1}: pos=({r['x']:.0f}%, {r['y']:.0f}%), size=({r['width']:.0f}%, {r['height']:.0f}%), time={r['start_time']:.1f}s~{r['end_time']:.1f}s, text='{r.get('sample_text', '')[:20]}'")

            return merged_regions
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[GPU Accel] Region aggregation error: {e}")
            return []

    def _detect_text_edge_changes(self, frame1, frame2):
        """
        Canny Edge Detection으로 텍스트 영역 변화 감지

        SSIM으로 놓칠 수 있는 미세한 자막 변화를 감지합니다.
        배경은 같지만 텍스트만 바뀐 경우를 포착합니다.

        Args:
            frame1: 첫 번째 프레임 (BGR)
            frame2: 두 번째 프레임 (BGR)

        Returns:
            변화율 (0.0~1.0, 높을수록 변화 많음)
        """
        try:
            import cv2
            import numpy as np

            # Grayscale 변환
            if len(frame1.shape) == 3:
                gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            else:
                gray1 = frame1

            if len(frame2.shape) == 3:
                gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            else:
                gray2 = frame2

            # 크기 맞추기
            if gray1.shape != gray2.shape:
                gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))

            # Canny Edge Detection (텍스트 윤곽선 감지)
            edges1 = cv2.Canny(gray1, 100, 200)
            edges2 = cv2.Canny(gray2, 100, 200)

            # XOR 연산으로 차이 계산
            diff = cv2.bitwise_xor(edges1, edges2)

            # 변화율 계산 (전체 픽셀 대비 변화된 픽셀 비율)
            total_pixels = diff.size
            changed_pixels = np.count_nonzero(diff)
            change_rate = changed_pixels / total_pixels

            return float(change_rate)

        except Exception as e:
            logger.debug(f"[Edge detection] Error: {e}")
            return 1.0  # 오류 시 변화 있다고 판단 (안전)

    def _calculate_ssim(self, frame1, frame2):
        """
        SSIM (Structural Similarity Index)으로 프레임 유사도 계산

        웹 조사 결과 기반:
        - 95% 유사도 이상이면 스킵 (더 엄격하게, 자막 변화 놓치지 않기 위함)
        - PSNR보다 인간 시각에 가까운 측정

        Args:
            frame1: 첫 번째 프레임 (BGR)
            frame2: 두 번째 프레임 (BGR)

        Returns:
            SSIM 값 (0.0~1.0, 높을수록 유사)
        """
        try:
            import cv2
            import numpy as np

            # Grayscale 변환 (SSIM은 단일 채널에서 계산)
            if len(frame1.shape) == 3:
                gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            else:
                gray1 = frame1

            if len(frame2.shape) == 3:
                gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            else:
                gray2 = frame2

            # 크기가 다르면 리사이즈
            if gray1.shape != gray2.shape:
                gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))

            # SSIM 계산 (scikit-image 대신 OpenCV 방식 사용)
            # C1, C2는 안정성을 위한 상수
            C1 = (0.01 * 255) ** 2
            C2 = (0.03 * 255) ** 2

            # 평균
            mu1 = cv2.GaussianBlur(gray1.astype(float), (11, 11), 1.5)
            mu2 = cv2.GaussianBlur(gray2.astype(float), (11, 11), 1.5)

            mu1_sq = mu1 ** 2
            mu2_sq = mu2 ** 2
            mu1_mu2 = mu1 * mu2

            # 분산 및 공분산
            sigma1_sq = cv2.GaussianBlur(gray1.astype(float) ** 2, (11, 11), 1.5) - mu1_sq
            sigma2_sq = cv2.GaussianBlur(gray2.astype(float) ** 2, (11, 11), 1.5) - mu2_sq
            sigma12 = cv2.GaussianBlur(gray1.astype(float) * gray2.astype(float), (11, 11), 1.5) - mu1_mu2

            # SSIM 공식
            ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))

            # 평균 SSIM
            return float(np.mean(ssim_map))

        except Exception as e:
            logger.debug(f"[SSIM] Calculation error: {e}")
            return 0.0  # 오류 시 유사하지 않다고 판단

    def _preprocess_frame_for_ocr(self, frame, use_gpu=False):
        """
        프레임 전처리로 OCR 정확도 향상

        웹 조사 결과 기반:
        - Bilateral filter로 엣지 보존하면서 노이즈 제거
        - Gaussian blur로 추가 노이즈 제거
        - Adaptive threshold로 텍스트 강조
        - GPU 가속 지원 (cv2.UMat)

        Args:
            frame: 원본 프레임 (BGR)
            use_gpu: GPU 가속 사용 여부

        Returns:
            전처리된 프레임
        """
        try:
            import cv2

            # GPU 가속 옵션 (cv2.UMat 사용)
            if use_gpu and CV2_AVAILABLE:
                try:
                    # UMat로 변환 (OpenCL GPU 가속)
                    frame_umat = cv2.UMat(frame)

                    # 1. Bilateral filter: 엣지 보존하면서 노이즈 제거
                    filtered = cv2.bilateralFilter(frame_umat, d=9, sigmaColor=75, sigmaSpace=75)

                    # 2. Gaussian blur: 남은 노이즈 제거
                    blurred = cv2.GaussianBlur(filtered, (3, 3), 0)

                    # 3. Grayscale 변환
                    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)

                    # 4. Adaptive threshold: 텍스트 강조
                    thresh = cv2.adaptiveThreshold(
                        gray, 255,
                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY,
                        blockSize=11,
                        C=2
                    )

                    # 5. BGR로 다시 변환 (OCR 입력용)
                    result = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

                    # UMat을 numpy로 변환
                    return result.get()

                except Exception as gpu_error:
                    # GPU 실패 시 CPU로 폴백
                    logger.debug(f"[OCR preprocessing] GPU processing failed, switching to CPU: {gpu_error}")
                    use_gpu = False

            # CPU 버전
            # 1. Bilateral filter: 엣지 보존하면서 노이즈 제거
            filtered = cv2.bilateralFilter(frame, d=9, sigmaColor=75, sigmaSpace=75)

            # 2. Gaussian blur: 남은 노이즈 제거
            blurred = cv2.GaussianBlur(filtered, (3, 3), 0)

            # 3. Grayscale 변환
            gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)

            # 4. Adaptive threshold: 텍스트 강조
            thresh = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=11,
                C=2
            )

            # 5. BGR로 다시 변환 (OCR 입력용)
            result = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

            return result
        except Exception as e:
            # 전처리 실패 시 원본 반환
            logger.debug(f"[OCR preprocessing] Error: {e}")
            return frame

    def _analyze_segment_batch_mode(
        self, cap, sample_frames, segment_name, W, H, fps, optimizer
    ):
        """
        GLM-OCR 배치 모드로 세그먼트 분석 (최적화된 API 호출)

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

        # 프레임 수집 및 배치 처리
        frame_data = []  # (frame_pos, frame, scale)

        logger.info(f"[OCR {segment_name}] Batch mode: collecting {len(sample_frames)} frames")

        # 1단계: 모든 프레임 수집 및 전처리
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

        # 2단계: 배치 단위로 OCR 수행
        total_batches = (len(frame_data) + batch_size - 1) // batch_size
        logger.info(f"[OCR {segment_name}] Processing {len(frame_data)} frames in {total_batches} batches")

        for batch_idx in range(0, len(frame_data), batch_size):
            batch = frame_data[batch_idx:batch_idx + batch_size]
            frames_only = [f[1] for f in batch]

            try:
                # 배치 OCR 호출
                batch_results = ocr_reader.readtext_batch(frames_only)
                ocr_call_count += 1  # 배치는 1회 호출로 카운트

                # 각 프레임별 결과 처리
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

                        # 중국어 문자 확인
                        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
                        if chinese_chars < 1:
                            continue

                        frame_has_chinese = True

                        # Bbox 스케일 조정
                        try:
                            if scale != 1.0:
                                adjusted_bbox = [(x / scale, y / scale) for x, y in bbox]
                            else:
                                adjusted_bbox = bbox
                        except Exception:
                            adjusted_bbox = bbox

                        # Region 정보 생성
                        region_info = self._gpu_process_bbox_batch([adjusted_bbox], W, H)
                        if region_info:
                            region = {
                                'x': region_info[0]['x'],
                                'y': region_info[0]['y'],
                                'width': region_info[0]['width'],
                                'height': region_info[0]['height'],
                                'confidence': prob,
                                'time': time_sec,
                                'text': text,
                                'language': 'chinese',
                                'source': 'glm_ocr_batch',
                            }
                            all_regions.append(region)

                    if frame_has_chinese:
                        frames_with_chinese += 1

            except Exception as e:
                logger.warning(f"[OCR {segment_name}] Batch {batch_idx // batch_size + 1} error: {e}")
                # 배치 실패 시 개별 처리로 폴백
                for frame_pos, frame, scale in batch:
                    try:
                        results = ocr_reader.readtext(frame)
                        ocr_call_count += 1
                        # 결과 처리 (간소화)
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
        전처리를 사용한 재시도 로직으로 OCR 수행.

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
        # 안전 검사: OCR reader가 여전히 사용 가능한지 확인
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

        # 1차 시도: 원본 프레임
        try:
            results = ocr_reader.readtext(target_frame)
            ocr_call_count += 1

            # 결과가 없거나 중국어가 감지되지 않으면 전처리 시도
            if not has_chinese(results):
                # 2차 시도: 전처리 프레임 (GPU 가속 시도)
                try:
                    use_gpu = GPU_ACCEL_AVAILABLE
                    preprocessed_frame = self._preprocess_frame_for_ocr(target_frame, use_gpu=use_gpu)
                    preprocessed_results = ocr_reader.readtext(preprocessed_frame)
                    ocr_call_count += 1

                    # 전처리 결과가 더 나으면 교체
                    if has_chinese(preprocessed_results):
                        results = preprocessed_results
                        if frame_idx % 50 == 0:  # 로그 스팸 방지
                            logger.debug(f"[OCR {segment_name}] Frame {frame_idx + 1} ({attempt_name}) Chinese detection improved with preprocessing")
                except Exception:
                    pass  # 전처리 실패 시 원본 결과 유지

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.debug(f"[OCR {segment_name}] Frame {frame_idx + 1} ({attempt_name}) first attempt failed: {str(e)}")

            # 재시도: 전처리 후 다시 시도 (GPU 가속)
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
        cap = None  # ★ try/finally를 위해 미리 선언
        try:
            import cv2
            import numpy as np

            # Check OCR reader availability
            # OCR reader 가용성 확인
            if not hasattr(self.gui, 'ocr_reader') or self.gui.ocr_reader is None:
                logger.warning(f"[OCR {segment_name}] OCR reader not initialized, skipping segment")
                return None

            logger.debug(f"[OCR {segment_name}] Analysis starting...")

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.warning(f"[OCR {segment_name}] Could not open video file")
                return None

            # 프레임 범위 계산
            start_frame = int(fps * start_sec)
            end_frame = min(int(fps * end_sec), total_frames)

            # 시스템 최적화에 따른 샘플링 간격
            optimizer = _get_optimizer(self.gui)
            if optimizer:
                ocr_params = optimizer.get_optimized_ocr_params()
                sample_interval_sec = ocr_params['sample_interval']
            else:
                sample_interval_sec = 0.3  # 기본값

            # 하이브리드 감지기 확인 및 초기화
            use_hybrid = False
            hybrid_detector = None

            if HYBRID_DETECTOR_AVAILABLE and self.hybrid_detector is None:
                # 지연 초기화 시도
                self._init_hybrid_detector()

            if self.hybrid_detector is not None:
                use_hybrid = True
                hybrid_detector = self.hybrid_detector
                hybrid_detector.reset()  # 세그먼트별 통계 초기화
                logger.debug(f"[OCR {segment_name}] Hybrid detection mode activated")
            else:
                logger.debug(f"[OCR {segment_name}] Default sampling mode ({sample_interval_sec}s interval)")

            # GLM-OCR 배치 모드 확인
            ocr_reader = getattr(self.gui, 'ocr_reader', None)
            use_batch_mode = (
                ocr_reader is not None and
                hasattr(ocr_reader, 'supports_batch') and
                ocr_reader.supports_batch() and
                ocr_reader.engine_name == 'glm_ocr'
            )
            if use_batch_mode:
                logger.info(f"[OCR {segment_name}] GLM-OCR batch mode enabled")

            # ★★★ 개선: 0~3초 구간 집중 샘플링 (0.1초 간격) ★★★
            # 영상 시작부 자막을 확실히 포착하기 위한 전략
            sample_frames = []

            # ★ 0초 주변 초정밀 샘플링: 0, 0.05, 0.1, 0.15초 프레임 강제 포함 ★
            if start_sec == 0:
                ultra_critical_times = [0.0, 0.05, 0.1, 0.15]
                for t in ultra_critical_times:
                    frame_num = int(fps * t)
                    if frame_num < total_frames and frame_num not in sample_frames:
                        sample_frames.append(frame_num)
                logger.debug(f"[OCR {segment_name}] Ultra-precise sampling near 0s: {len(sample_frames)} frames ({ultra_critical_times}s)")

            # 0~3초 구간: 0.1초 간격 (10 FPS) - 초기 자막 확실히 포착
            critical_start_duration = 3.0
            critical_end_frame = min(int(fps * critical_start_duration), end_frame)

            if start_sec < critical_start_duration:
                # 이 구간은 0~3초를 포함하는 구간
                critical_interval = max(1, int(fps * 0.1))  # 0.1초 간격
                critical_start = start_frame
                critical_end = min(critical_end_frame, end_frame)

                for frame_num in range(critical_start, critical_end, critical_interval):
                    if frame_num < total_frames and frame_num not in sample_frames:
                        sample_frames.append(frame_num)

                logger.debug(f"[OCR {segment_name}] 0-3s intensive sampling: {len([f for f in sample_frames if f < critical_end_frame])} frames (0.1s interval)")

            # 3초 이후: 동적 샘플링 (자막 감지 여부에 따라 간격 조정)
            if end_frame > critical_end_frame:
                if use_hybrid:
                    # 하이브리드: 더 촘촘한 프레임 스캔 (0.1초 간격)
                    base_interval = max(1, int(fps * 0.1))
                else:
                    base_interval = max(1, int(fps * sample_interval_sec))

                # ★★★ 동적 샘플링: 자막 없는 구간은 간격 2배로 확대 ★★★
                # (실제 감지 여부는 OCR 후에 알 수 있으므로, 일단 기본 간격 사용)
                scan_interval = base_interval

                regular_start = max(critical_end_frame, start_frame)
                for frame_num in range(regular_start, end_frame, scan_interval):
                    if frame_num < total_frames and frame_num not in sample_frames:
                        sample_frames.append(frame_num)

            # 시간순 정렬
            sample_frames.sort()

            if not sample_frames:
                cap.release()
                return None

            logger.debug(f"[OCR {segment_name}] {len(sample_frames)} frames scheduled for scan")

            # ★★★ GLM-OCR 배치 처리 모드 ★★★
            if use_batch_mode:
                result = self._analyze_segment_batch_mode(
                    cap, sample_frames, segment_name, W, H, fps, optimizer
                )
                cap.release()
                return result

            all_regions = []
            frames_with_chinese = 0
            position_history = []
            ocr_call_count = 0  # 실제 OCR 호출 횟수 추적
            ssim_skip_count = 0  # SSIM으로 스킵한 프레임 수
            edge_detected_count = 0  # Edge detection으로 변화 감지한 횟수
            prev_frame_roi = None  # 이전 프레임 (SSIM 비교용)
            consecutive_similar_count = 0  # 연속 유사 프레임 카운터

            # ★★★ 초안전 모드: 매우 보수적인 임계값 + 연속 체크 ★★★
            # Use constants for thresholds
            # 임계값 상수 사용
            ssim_threshold = OCRThresholds.SSIM_THRESHOLD  # 98% (거의 픽셀 동일)
            edge_change_threshold = OCRThresholds.EDGE_CHANGE_THRESHOLD  # 0.1% 변화 감지
            # 1920x540 ROI에서 0.1% = 1,036 픽셀 (한 글자 변경도 감지)

            # ★★★ 추가 안전장치: 연속 2프레임 이상 동일해야 스킵 ★★★
            # 자막이 바뀌는 순간(전환 프레임)을 놓치지 않기 위함
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
                    if optimizer:
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

                # ★★★ 100% 감지 모드: 전체 화면 스캔 ★★★
                # 상단/중앙/하단 어디에 있는 자막도 놓치지 않도록 전체 화면 스캔
                attempts = []
                roi_frame = None
                try:
                    h_resized, w_resized = frame.shape[:2]
                    # 전체 화면을 ROI로 사용 (100%)
                    roi_percent = OCRThresholds.ROI_BOTTOM_PERCENT / 100.0  # 100% 전체 화면
                    roi_percent = max(OCRThresholds.ROI_MIN_PERCENT / 100.0, roi_percent)  # 최소 70%
                    roi_start = int(h_resized * (1 - roi_percent))
                    if roi_start < h_resized - 8:
                        roi_frame = frame[roi_start:, :]
                        attempts.append(("roi_full", roi_frame, roi_start))
                except Exception:
                    pass
                # 항상 전체 프레임도 시도 (fallback)
                attempts.append(("full", frame, 0))

                # ★★★ 100% 감지 모드: SSIM 스킵 완전 비활성화 ★★★
                # 모든 프레임을 OCR 검사하여 자막 전환을 절대 놓치지 않음
                skip_by_ssim = False  # 항상 False (스킵 안함)

                # SSIM 스킵 비활성화 (constants.py에서 설정)
                if not OCRThresholds.SSIM_SKIP_ENABLED:
                    # 모든 프레임 검사 - 스킵 없음
                    pass
                else:
                    # SSIM 스킵이 활성화된 경우 (기본값 False이므로 실행 안됨)
                    # 이 코드는 향후 성능 최적화 시 사용 가능
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

                # SSIM으로 스킵된 프레임은 OCR하지 않음 (현재는 항상 False)
                if skip_by_ssim:
                    continue

                # ROI 프레임 저장 (다음 비교용 - SSIM 활성화 시 사용)
                if roi_frame is not None:
                    prev_frame_roi = roi_frame.copy()

                frame_has_chinese = False
                current_frame_regions = []

                for attempt_name, target_frame, y_offset in attempts:
                    results = None

                    # 하이브리드 감지기 사용
                    if use_hybrid and hybrid_detector:
                        ocr_results, meta = hybrid_detector.process(target_frame, time_sec)

                        if meta['processed']:
                            # OCR이 실제로 호출됨
                            ocr_call_count += 1
                            results = ocr_results
                        elif not meta['fast_detected']:
                            # 변화 없음 - 스킵
                            continue
                        else:
                            # 변화 감지됐지만 OCR 스킵 (시간 제한)
                            continue
                    else:
                        # OCR 재시도 로직을 별도 메서드로 위임
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

                        # ★★★ 개선: 신뢰도 임계값 0.5 → 0.3 (초기 감지 단계) ★★★
                        # 중국어 자막은 복잡한 문자가 많아 신뢰도가 낮을 수 있음
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

                        frame_has_chinese = True
                        region = {
                            'x': region_info['x'],
                            'y': region_info['y'],
                            'width': region_info['width'],
                            'height': region_info['height'],
                            'confidence': prob,
                            'time': time_sec,
                            'text': text,
                            'language': 'chinese',
                            'source': source_tag,
                            'roi_type': attempt_name  # 어느 ROI에서 감지되었는지 기록
                        }

                        current_frame_regions.append(region)
                        all_regions.append(region)

                    # ★★★ 개선: ROI에서 발견되더라도 다른 ROI들도 계속 스캔 ★★★
                    # 하단 ROI에서 발견되더라도 상단/중앙에 다른 자막이 있을 수 있음
                    # break 제거로 모든 ROI 스캔 보장

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
            # 프레임 캐시 정리 (메모리 누수 방지)
            if 'prev_frame_roi' in locals():
                del prev_frame_roi
            if 'roi_frame' in locals():
                del roi_frame

            # ★★★ 성능 통계 출력 ★★★
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

            # 하이브리드 감지기 통계 출력
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
            # ★★★ 리소스 누수 방지: 예외 발생 시에도 VideoCapture 해제 ★★★
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
