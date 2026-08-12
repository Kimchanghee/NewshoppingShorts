"""
Subtitle Processing Module

This module handles subtitle processing including blur application and layout management.
"""

from typing import Any, Dict, List, Optional, Iterable

# Logging configuration
from utils.logging_config import get_logger

# Constants for consistent time buffer calculations
from config.constants import OCRThresholds

logger = get_logger(__name__)

try:
    import cv2

    CV2_AVAILABLE = True
except Exception:
    cv2 = None
    CV2_AVAILABLE = False

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except Exception:
    np = None
    NUMPY_AVAILABLE = False

try:
    # moviepy 1.x compatible imports
    from moviepy.editor import VideoClip

    MOVIEPY_AVAILABLE = True
except Exception:
    VideoClip = None
    MOVIEPY_AVAILABLE = False

from caller import ui_controller


class SubtitleProcessor:
    """
    Processes subtitles by applying blur effects and managing layout.

    This processor handles Chinese subtitle removal via blur and Korean
    subtitle layout positioning.
    """

    def __init__(self, gui):
        """
        Initialize the SubtitleProcessor.

        Args:
            gui: Main GUI instance containing video settings and analysis results
        """
        self.gui = gui

    def _get_or_create_detector(self):
        """
        Get cached SubtitleDetector or create new one.

        Caches the detector instance to avoid duplicate instantiation (40% overhead).
        캐시된 SubtitleDetector를 가져오거나 새로 생성합니다.

        Returns:
            SubtitleDetector instance
        """
        if not hasattr(self.gui, "_cached_subtitle_detector"):
            from processors.subtitle_detector import SubtitleDetector

            self.gui._cached_subtitle_detector = SubtitleDetector(self.gui)
        return self.gui._cached_subtitle_detector

    def apply_chinese_subtitle_removal(self, video):
        """
        OCR-based Chinese subtitle blur processing with duplicate execution prevention.

        Detects Chinese subtitles (reusing existing analysis if available) and applies
        blur effect to remove them from the video.

        Args:
            video: MoviePy video clip to process

        Returns:
            Processed video clip with Chinese subtitles blurred
        """
        logger.debug("=" * 60)
        logger.info("[BLUR MAIN] Starting Chinese subtitle blur processing")
        logger.debug("=" * 60)

        self.gui.update_progress_state(
            "subtitle", "processing", 10, "중국어 자막을 분석하고 있습니다."
        )
        self.gui.update_step_progress("subtitle", 10)
        def _get_bool(attr):
            """Extract bool from plain bool or BoolVar-like object."""
            if attr is None:
                return None
            return attr.get() if hasattr(attr, "get") else bool(attr)

        blur_opt = getattr(self.gui, "apply_blur", None)
        blur_val = _get_bool(blur_opt)
        self.gui.latest_blur_metadata = {
            "requested": blur_val is not False,
            "completed": False,
            "applied": False,
            "regions": 0,
            "reason": "",
            "review_required": False,
            "invalid_coordinate_count": 0,
        }
        review_required = False
        invalid_coordinate_count = 0
        review_reasons = []
        logger.debug("[BLUR MAIN] Option status:")
        logger.debug(f"  - add_subtitles: {_get_bool(getattr(self.gui, 'add_subtitles', None))}")
        logger.debug(f"  - apply_blur: {blur_val}")

        if blur_val is not None and not blur_val:
            logger.info("[BLUR MAIN] Blur option disabled - skipping")
            self.gui.latest_blur_metadata.update(
                {
                    "requested": False,
                    "completed": True,
                    "applied": False,
                    "reason": "disabled",
                }
            )
            self.gui.update_progress_state(
                "subtitle", "completed", 100, "블러 단계가 비활성화되어 건너뛰었습니다."
            )
            return video

        try:
            # 이미 분석된 결과가 있으면 재사용
            raw_positions = []
            logger.debug(
                f"[BLUR MAIN] analysis_result exists: {hasattr(self.gui, 'analysis_result')}"
            )
            if hasattr(self.gui, "analysis_result"):
                logger.debug(
                    f"[BLUR MAIN] analysis_result content: {self.gui.analysis_result}"
                )

            if hasattr(self.gui, "analysis_result") and self.gui.analysis_result.get(
                "subtitle_positions"
            ):
                subtitle_positions = list(
                    self.gui.analysis_result.get("subtitle_positions") or []
                )
                raw_positions = list(
                    self.gui.analysis_result.get("raw_subtitle_positions")
                    or subtitle_positions
                )
                review_required = bool(
                    self.gui.analysis_result.get("subtitle_review_required", False)
                )
                review_reasons.extend(
                    self.gui.analysis_result.get("ocr_review_reasons", []) or []
                )
                try:
                    invalid_coordinate_count = int(
                        self.gui.analysis_result.get("invalid_coordinate_count", 0) or 0
                    )
                except (TypeError, ValueError):
                    invalid_coordinate_count = 0
                logger.info(
                    f"[BLUR MAIN] Reusing existing OCR results: {len(subtitle_positions)} regions"
                )
                logger.debug(f"[BLUR MAIN] raw_positions: {len(raw_positions)}")
            else:
                ocr_status = getattr(self.gui, 'ocr_reader', None)
                logger.info(
                    f"[BLUR MAIN] Starting new OCR-based Chinese subtitle detection... (ocr_reader: {type(ocr_status).__name__ if ocr_status else 'None'})"
                )
                # Get cached detector to avoid duplicate instantiation
                # 캐시된 detector를 사용하여 중복 생성 방지 (40% 성능 오버헤드 제거)
                detector = self._get_or_create_detector()
                raw_positions = detector.detect_subtitles_with_opencv() or []
                subtitle_positions = list(raw_positions)
                review_required = bool(getattr(detector, "review_required", False))
                review_reasons.extend(
                    getattr(detector, "review_reasons", []) or []
                )
                try:
                    invalid_coordinate_count = int(
                        getattr(detector, "invalid_coordinate_count", 0) or 0
                    )
                except (TypeError, ValueError):
                    invalid_coordinate_count = 0
                logger.info(
                    f"[BLUR MAIN] OCR detection result: {len(subtitle_positions)} regions"
                )

            detected_positions = raw_positions or subtitle_positions
            review_required = review_required or bool(
                getattr(self.gui, "subtitle_review_required", False)
            )
            review_reasons.extend(
                getattr(self.gui, "ocr_review_reasons", []) or []
            )
            try:
                invalid_coordinate_count = max(
                    invalid_coordinate_count,
                    int(getattr(self.gui, "invalid_coordinate_count", 0) or 0),
                )
            except (TypeError, ValueError):
                review_required = True
            for position in detected_positions:
                if not isinstance(position, dict):
                    review_required = True
                    continue
                review_required = review_required or bool(
                    position.get("review_required", False)
                )
                review_reasons.extend(position.get("review_reasons", []) or [])
                try:
                    invalid_coordinate_count = max(
                        invalid_coordinate_count,
                        int(position.get("invalid_coordinate_count", 0) or 0),
                    )
                except (TypeError, ValueError):
                    review_required = True
            logger.debug(
                f"[BLUR MAIN] Region count before filtering: {len(detected_positions)}"
            )
            for i, pos in enumerate(detected_positions[:10]):  # 처음 10개만 표시
                logger.debug(
                    f"  #{i + 1}: x={pos.get('x')}%, y={pos.get('y')}%, w={pos.get('width')}%, h={pos.get('height')}%, text='{str(pos.get('text', ''))[:20]}...'"
                )
            if len(detected_positions) > 10:
                logger.debug(f"  ... and {len(detected_positions) - 10} more")

            # Reuse cached detector (no duplicate instantiation)
            # 캐시된 detector 재사용 (중복 생성 없음)
            detector = self._get_or_create_detector()
            review_required = review_required or bool(
                getattr(detector, "review_required", False)
            )
            review_reasons.extend(getattr(detector, "review_reasons", []) or [])
            try:
                invalid_coordinate_count = max(
                    invalid_coordinate_count,
                    int(getattr(detector, "invalid_coordinate_count", 0) or 0),
                )
            except (TypeError, ValueError):
                pass
            chinese_positions = detector._filter_chinese_regions(detected_positions)

            logger.info(
                f"[BLUR MAIN] Region count after filtering: {len(chinese_positions)}"
            )

            if not chinese_positions:
                logger.info("[BLUR MAIN] No Chinese subtitles detected - skipping blur")
                logger.debug("[BLUR MAIN] Possible reasons:")
                logger.debug("  1. Video has no Chinese subtitles")
                logger.debug(
                    "  2. Subtitle position is in upper half (y < 50%) and filtered out"
                )
                logger.debug("  3. OCR did not detect text")
                self.gui.latest_blur_metadata.update(
                    {
                        "completed": True,
                        "applied": False,
                        "regions": 0,
                        "reason": (
                            "review_required_no_reliable_regions"
                            if review_required or invalid_coordinate_count
                            else "no_chinese_regions_detected"
                        ),
                        "review_required": bool(
                            review_required or invalid_coordinate_count
                        ),
                        "invalid_coordinate_count": invalid_coordinate_count,
                        "review_reasons": list(
                            dict.fromkeys(str(value) for value in review_reasons if value)
                        ),
                    }
                )
                self.gui.update_progress_state(
                    "subtitle",
                    "completed",
                    100,
                    "중국어 자막이 보이지 않네요. 화면을 깨끗하게 유지합니다.",
                )
                self.gui.update_step_progress("subtitle", 100)
                return video

            self._update_korean_subtitle_layout(chinese_positions)

            logger.info(
                f"[BLUR MAIN] Processing blur for {len(chinese_positions)} regions"
            )
            for i, pos in enumerate(chinese_positions):
                logger.debug(
                    f"  #{i + 1}: x={pos.get('x')}%, y={pos.get('y')}%, w={pos.get('width')}%, h={pos.get('height')}%"
                )
                logger.debug(
                    f"       time={pos.get('start_time', 0):.1f}s~{pos.get('end_time', 'end')}, text='{str(pos.get('text', ''))[:30]}...'"
                )

            self.gui.update_progress_state(
                "subtitle",
                "processing",
                60,
                f"중국어 자막 {len(chinese_positions)}개 발견! 블러 처리 중입니다.",
            )
            self.gui.update_step_progress("subtitle", 60)

            w, h = video.size
            blurred_video = self.apply_opencv_blur_enhanced_v2(
                video, chinese_positions, w, h
            )

            logger.info("[BLUR MAIN] Blur processing completed")
            logger.debug("=" * 60)
            self.gui.latest_blur_metadata.update(
                {
                    "completed": True,
                    "applied": True,
                    "regions": len(chinese_positions),
                    "reason": "",
                    "review_required": bool(
                        review_required or invalid_coordinate_count
                    ),
                    "invalid_coordinate_count": invalid_coordinate_count,
                    "review_reasons": list(
                        dict.fromkeys(str(value) for value in review_reasons if value)
                    ),
                    "coverage_stats": getattr(
                        self.gui, "_precision_blur_stats", {}
                    ),
                }
            )
            self.gui.update_progress_state(
                "subtitle",
                "completed",
                100,
                f"중국어 자막 {len(chinese_positions)}개 구역 블러 완료!",
            )
            self.gui.update_step_progress("subtitle", 100)
            return blurred_video

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[BLUR MAIN] Error occurred: {str(e)}")
            logger.exception("Chinese subtitle processing failed")
            self.gui.latest_blur_metadata.update(
                {
                    "completed": False,
                    "applied": False,
                    "reason": f"error: {e}",
                }
            )
            self.gui.update_progress_state(
                "subtitle", "error", 0, "중국어 자막 처리 중 오류가 발생했어요."
            )
            return video

    def apply_opencv_blur_enhanced(self, video, subtitle_positions, w, h):
        """
        Apply natural blur with feathered mask to detected subtitle regions.
        Only applies blur during time ranges when Chinese subtitles are detected.

        Args:
            video: MoviePy video clip
            subtitle_positions: List of subtitle region positions (with time info)
            w: Video width
            h: Video height

        Returns:
            Video clip with blurred subtitle regions
        """
        import cv2
        import numpy as np

        # moviepy 1.x compatible imports
        from moviepy.editor import VideoClip

        logger.debug("*" * 60)
        logger.info("[BLUR APPLY] Starting blur application")
        logger.debug("*" * 60)
        logger.debug(f"[BLUR APPLY] Video size: {w}x{h}")
        logger.debug(f"[BLUR APPLY] Video duration: {video.duration:.2f}s")
        logger.debug(f"[BLUR APPLY] Input region count: {len(subtitle_positions)}")

        # 영상 해상도에 비례한 최소 패딩 계산 (1080p 기준)
        base_height = 1080
        base_min_pad = 5
        min_pad = max(2, int(base_min_pad * (h / base_height)))
        logger.debug(f"[BLUR APPLY] Min padding: {min_pad}px")
        extra_side_pad = int(w * 0.07)  # 좌우로 추가 확장할 7% 영역

        # 퍼센트 좌표 → 픽셀 박스 (중국어 글자 크기에 맞게 조정) + 시간 정보 포함
        boxes_with_time = []
        logger.debug("[Multi-subtitle blur] Detailed info per subtitle region:")
        for idx, pos in enumerate(subtitle_positions):
            x1 = int(w * pos["x"] / 100)
            y1 = int(h * pos["y"] / 100)
            x2 = int(w * (pos["x"] + pos["width"]) / 100)
            y2 = int(h * (pos["y"] + pos["height"]) / 100)

            # 중국어 글자 크기에 맞춘 패딩 (가로/세로 균형있게)
            box_width = x2 - x1
            box_height = y2 - y1

            # 글자 크기 기준으로 패딩 계산 (박스 크기의 5%, 해상도 비례)
            pad_x = max(min_pad, int(box_width * 0.05))
            pad_y = max(min_pad, int(box_height * 0.08))

            # 시간 범위 가져오기 (없으면 전체 영상에 적용)
            start_time = pos.get("start_time", 0)
            end_time = pos.get("end_time", video.duration)

            # ★★★ 100% 감지 모드: 일관된 시간 버퍼 적용 (constants.py에서 설정) ★★★
            # TIME_BUFFER_BEFORE: 자막 시작 전 버퍼 (0.5초)
            # TIME_BUFFER_AFTER: 자막 종료 후 버퍼 (0.8초)
            if start_time == 0:
                # 영상 시작 즉시 블러 적용
                start_time = 0
            else:
                start_time = max(0, start_time - OCRThresholds.TIME_BUFFER_BEFORE)
            end_time = min(video.duration, end_time + OCRThresholds.TIME_BUFFER_AFTER)

            final_box = [
                max(0, x1 - pad_x - extra_side_pad),  # 좌측 패딩 + 추가 확장
                max(0, y1 - pad_y // 2),  # 위쪽 패딩
                min(w - 1, x2 + pad_x + extra_side_pad),  # 우측 패딩 + 추가 확장
                min(h - 1, y2 + pad_y),  # 아래쪽 패딩 (조금 더)
            ]

            # ★★★ 자막별 상세 로그 ★★★
            blur_width = final_box[2] - final_box[0]
            blur_height = final_box[3] - final_box[1]
            logger.debug(f"  Subtitle #{idx + 1}:")
            logger.debug(
                f"    Position: ({final_box[0]}px, {final_box[1]}px) from top-left"
            )
            logger.debug(
                f"    Size: {blur_width}px x {blur_height}px ({pos['width']:.1f}% x {pos['height']:.1f}%)"
            )
            logger.debug(
                f"    Time: {start_time:.2f}s ~ {end_time:.2f}s (total {end_time - start_time:.2f}s)"
            )
            logger.debug(f"    Text: '{pos.get('sample_text', '')[:30]}'")

            boxes_with_time.append(
                {
                    "box": final_box,
                    "start_time": start_time,
                    "end_time": end_time,
                    "text": pos.get("text", "")[:30],  # 디버그용
                }
            )

            logger.debug(f"[BLUR APPLY] Region #{idx + 1} transform:")
            logger.debug(
                f"  - Original(%): x={pos['x']}%, y={pos['y']}%, w={pos['width']}%, h={pos['height']}%"
            )
            logger.debug(f"  - Original(px): ({x1}, {y1}) ~ ({x2}, {y2})")
            logger.debug(f"  - Padding: pad_x={pad_x}px, pad_y={pad_y}px")
            logger.debug(
                f"  - Final(px): ({final_box[0]}, {final_box[1]}) ~ ({final_box[2]}, {final_box[3]})"
            )
            logger.debug(f"  - Time range: {start_time:.2f}s ~ {end_time:.2f}s")
            logger.debug(f"  - Text: '{pos.get('text', '')[:30]}...'")

        logger.info(
            f"[BLUR APPLY] {len(boxes_with_time)} regions ready for time-based blur processing"
        )
        for i, bt in enumerate(boxes_with_time):
            logger.debug(
                f"  Region {i + 1}: {bt['start_time']:.1f}s - {bt['end_time']:.1f}s, box={bt['box']}"
            )

        # 영상 해상도에 비례한 블러 커널 크기 계산 (1080p 기준)
        base_kernel = 35
        min_kernel = max(15, int(base_kernel * (h / base_height)))

        # 영상 해상도에 비례한 페더 마스크 블러 크기 계산 (1080p 기준)
        base_feather = 21
        feather_size = int(base_feather * (h / base_height))
        feather_size = (
            feather_size + 1 if feather_size % 2 == 0 else feather_size
        )  # 홀수 유지
        feather_size = max(11, min(feather_size, 51))  # 최소 11, 최대 51

        def _auto_kernel(a, b):
            k = max(min_kernel, ((a + b) // 2) // 12)
            return k + 1 if k % 2 == 0 else k

        # 디버그용: 마지막 로그 시간 추적
        last_log_time = [-1.0]  # mutable to allow closure modification
        blur_apply_count = [0]  # 블러 적용 횟수 추적

        def _feather_blur(get_frame, t):
            frame = get_frame(t).copy()

            # 매 5초마다 상세 로그 출력
            should_log = (int(t) % 5 == 0) and (int(t) != last_log_time[0])
            if should_log:
                last_log_time[0] = int(t)

            active_boxes = []
            # 현재 시간(t)에 활성화된 블러 박스만 적용
            for bt in boxes_with_time:
                # 시간 범위 체크 - 해당 시간대에만 블러 적용
                if bt["start_time"] <= t <= bt["end_time"]:
                    active_boxes.append(bt)
                    X1, Y1, X2, Y2 = bt["box"]
                    roi = frame[Y1:Y2, X1:X2]
                    if roi.size == 0:
                        if should_log:
                            logger.debug(
                                f"[BLUR FRAME] t={t:.2f}s - ROI empty, skipping"
                            )
                        continue
                    k = _auto_kernel(X2 - X1, Y2 - Y1)
                    blurred = cv2.GaussianBlur(roi, (k, k), 0)

                    # 페더 마스크 (영상 해상도에 비례한 크기)
                    mask = np.zeros((Y2 - Y1, X2 - X1), np.uint8)
                    cv2.rectangle(mask, (0, 0), (X2 - X1 - 1, Y2 - Y1 - 1), 255, -1)
                    mask = cv2.GaussianBlur(mask, (feather_size, feather_size), 0)
                    m3 = np.dstack([mask, mask, mask]).astype(np.float32) / 255.0

                    frame[Y1:Y2, X1:X2] = (
                        blurred.astype(np.float32) * m3
                        + roi.astype(np.float32) * (1 - m3)
                    ).astype(np.uint8)
                    blur_apply_count[0] += 1

            # 매 5초마다 상세 로그 출력
            if should_log:
                if active_boxes:
                    logger.debug(
                        f"[Multi-blur] t={t:.2f}s - Blurring {len(active_boxes)} subtitle regions:"
                    )
                    for i, bt in enumerate(active_boxes):
                        X1, Y1, X2, Y2 = bt["box"]
                        blur_w = X2 - X1
                        blur_h = Y2 - Y1
                        logger.debug(
                            f"  Subtitle {i + 1}: pos=({X1}px, {Y1}px), size={blur_w}px x {blur_h}px, time={bt['start_time']:.1f}~{bt['end_time']:.1f}s"
                        )
                else:
                    logger.debug(
                        f"[Multi-blur] t={t:.2f}s - No active blur regions (all outside time range)"
                    )

            return frame

        clip = VideoClip(
            lambda t: _feather_blur(video.get_frame, t), duration=video.duration
        )
        if video.audio:
            clip = clip.set_audio(video.audio)
        if hasattr(video, "fps"):
            clip.fps = video.fps
        return clip

    def _merge_spatial_boxes(
        self, boxes: List[List[int]], frame_width: int
    ) -> List[List[int]]:
        """Merge neighboring boxes on the same subtitle row to remove gaps."""
        if not boxes:
            return []

        gap_px = max(12, int(frame_width * 0.04))
        ordered = sorted([list(b) for b in boxes], key=lambda b: (b[1], b[0]))
        merged: List[List[int]] = []

        for box in ordered:
            if not merged:
                merged.append(box)
                continue

            last = merged[-1]
            last_h = max(1, last[3] - last[1])
            box_h = max(1, box[3] - box[1])
            last_center_y = (last[1] + last[3]) / 2.0
            box_center_y = (box[1] + box[3]) / 2.0
            same_row = abs(last_center_y - box_center_y) <= max(last_h, box_h) * 0.9
            gap = max(0, max(box[0] - last[2], last[0] - box[2]))

            if same_row and gap <= gap_px:
                last[0] = min(last[0], box[0])
                last[1] = min(last[1], box[1])
                last[2] = max(last[2], box[2])
                last[3] = max(last[3], box[3])
            else:
                merged.append(box)

        return merged

    def _normalize_polygon_points(
        self, polygon: Any, frame_w: int, frame_h: int
    ) -> List[List[int]]:
        """Normalize polygon points into in-frame integer coordinates."""
        if not isinstance(polygon, list):
            return []
        normalized: List[List[int]] = []
        for point in polygon:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                px = int(round(float(point[0])))
                py = int(round(float(point[1])))
            except (TypeError, ValueError):
                continue
            px = max(0, min(frame_w - 1, px))
            py = max(0, min(frame_h - 1, py))
            normalized.append([px, py])
        if len(normalized) < 3:
            return []
        return normalized

    @staticmethod
    def _match_polygons_for_interpolation(left_polygons, right_polygons):
        """One-to-one nearest matching for simultaneous text boxes."""
        def metrics(polygon):
            xs = [point[0] for point in polygon]
            ys = [point[1] for point in polygon]
            return (
                (min(xs) + max(xs)) / 2.0,
                (min(ys) + max(ys)) / 2.0,
                max(xs) - min(xs),
                max(ys) - min(ys),
            )

        candidates = []
        for left_index, left in enumerate(left_polygons):
            if len(left) < 3:
                continue
            lx, ly, lw, lh = metrics(left)
            for right_index, right in enumerate(right_polygons):
                if len(left) != len(right) or len(right) < 3:
                    continue
                rx, ry, rw, rh = metrics(right)
                distance = ((lx - rx) ** 2 + (ly - ry) ** 2) ** 0.5
                max_distance = max(20.0, max(lw, lh, rw, rh) * 2.5)
                if distance <= max_distance:
                    candidates.append((distance, left_index, right_index))

        matches = []
        used_left = set()
        used_right = set()
        for _distance, left_index, right_index in sorted(candidates):
            if left_index in used_left or right_index in used_right:
                continue
            used_left.add(left_index)
            used_right.add(right_index)
            matches.append((left_polygons[left_index], right_polygons[right_index]))
        return matches

    def _linked_stable_overlay_bounds(
        self, subtitle_positions, fps: float, frame_w: int, frame_h: int
    ) -> Dict[int, tuple]:
        """Deprecated: unrelated overlays must never share temporal bounds."""
        return {}

    def _build_polygon_timeline(
        self,
        subtitle_positions: List[Dict[str, Any]],
        fps: float,
        frame_w: int,
        frame_h: int,
        video_duration: float,
    ) -> Dict[int, List[List[List[int]]]]:
        """Build a time-first polygon map with tightly bounded gap filling.

        ``frame_index`` from the capture backend is diagnostic only.  Rendering
        is keyed from the decoder timestamp saved in ``frame_regions`` so a
        different MoviePy FPS cannot silently shift the mask.  Missing slots
        are interpolated only when they are bounded by observations from the
        same region and scene; event-edge extrapolation is limited to one slot.
        """
        timeline: Dict[int, List[List[List[int]]]] = {}
        if fps <= 0:
            return timeline

        max_frame = max(0, int(video_duration * fps) + 1)
        expansion_frames = max(
            0,
            int(
                round(
                    fps
                    * float(
                        getattr(OCRThresholds, "PRECISION_EVENT_EDGE_SECONDS", 0.4)
                    )
                )
            ),
        )
        max_internal_gap_frames = 2
        persistent_gap_frames = max(
            max_internal_gap_frames,
            int(
                round(
                    fps
                    * float(
                        getattr(
                            OCRThresholds,
                            "PRECISION_PERSISTENT_TRACK_GAP_SECONDS",
                            1.0,
                        )
                    )
                )
            ),
        )

        global_exact_groups: Dict[tuple, List[Dict[str, Any]]] = {}
        global_scene_observations: Dict[str, List[Dict[str, Any]]] = {}

        for pos_index, pos in enumerate(subtitle_positions):
            frame_regions = pos.get("frame_regions")
            if isinstance(frame_regions, list) and frame_regions:
                observations: List[Dict[str, Any]] = []
                for fr in frame_regions:
                    polygon = self._normalize_polygon_points(
                        fr.get("polygon"), frame_w=frame_w, frame_h=frame_h
                    )
                    if not polygon:
                        continue

                    # Timestamp is canonical.  Old caches without a timestamp
                    # retain a frame-index fallback for backward compatibility.
                    try:
                        time_value = float(fr.get("time"))
                    except (TypeError, ValueError):
                        time_value = -1.0
                    if time_value >= 0.0:
                        slot = int(round(time_value * fps))
                    else:
                        try:
                            slot = int(fr.get("frame_index", -1))
                        except (TypeError, ValueError):
                            slot = -1
                    if slot < 0 or slot > max_frame:
                        continue
                    # Scene IDs may include the detector segment name. Preserve
                    # the value instead of coercing every string ID to zero.
                    scene_id = str(fr.get("scene_id", "scene:0") or "scene:0")
                    observations.append(
                        {
                            "slot": slot,
                            "scene_id": scene_id,
                            "polygon": polygon,
                            "text": str(fr.get("text", "") or "").strip(),
                            "source": str(fr.get("source", "") or ""),
                        }
                    )

                observations.sort(key=lambda item: (item["slot"], item["scene_id"]))
                grouped: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
                exact_slots = set()
                for item in observations:
                    normalized_text = "".join(item["text"].split()).casefold()
                    if normalized_text:
                        global_exact_groups.setdefault(
                            (item["scene_id"], normalized_text), []
                        ).append(item)
                    global_scene_observations.setdefault(item["scene_id"], []).append(
                        item
                    )
                    exact_slots.add(item["slot"])
                    timeline.setdefault(item["slot"], []).append(item["polygon"])
                    grouped.setdefault(item["scene_id"], {}).setdefault(
                        item["slot"], []
                    ).append(item)

                # Build one-to-one polygon tracks inside each scene before
                # interpolation. A scene slot can contain many OCR boxes. The
                # former slot-level algorithm treated that slot as complete if
                # *any* box existed, so a label observed on frames 6 and 8 was
                # not filled on frame 7 when an unrelated label happened to be
                # present there. Tracking each polygon independently preserves
                # simultaneous labels and fills only the missing object.
                def polygon_metrics(polygon):
                    xs = [point[0] for point in polygon]
                    ys = [point[1] for point in polygon]
                    width = max(1.0, float(max(xs) - min(xs)))
                    height = max(1.0, float(max(ys) - min(ys)))
                    return (
                        (min(xs) + max(xs)) / 2.0,
                        (min(ys) + max(ys)) / 2.0,
                        width,
                        height,
                    )

                for _scene_id, scene_slots in grouped.items():
                    tracks: List[List[Dict[str, Any]]] = []
                    for slot in sorted(scene_slots):
                        assigned_tracks = set()
                        for item in scene_slots[slot]:
                            ix, iy, iw, ih = polygon_metrics(item["polygon"])
                            item_text = "".join(item["text"].split()).casefold()
                            candidates = []
                            for track_index, track in enumerate(tracks):
                                if track_index in assigned_tracks:
                                    continue
                                previous = track[-1]
                                slot_gap = int(slot) - int(previous["slot"])
                                if slot_gap <= 0:
                                    continue
                                previous_text = "".join(
                                    previous["text"].split()
                                ).casefold()
                                same_text = bool(
                                    item_text
                                    and previous_text
                                    and item_text == previous_text
                                )
                                allowed_missing = (
                                    persistent_gap_frames
                                    if same_text
                                    else max_internal_gap_frames
                                )
                                if slot_gap - 1 > allowed_missing:
                                    continue
                                px, py, pw, ph = polygon_metrics(
                                    previous["polygon"]
                                )
                                width_ratio = max(iw, pw) / max(1.0, min(iw, pw))
                                height_ratio = max(ih, ph) / max(1.0, min(ih, ph))
                                if width_ratio > 2.5 or height_ratio > 2.5:
                                    continue
                                distance = ((ix - px) ** 2 + (iy - py) ** 2) ** 0.5
                                max_distance = (
                                    max(20.0, max(iw, ih, pw, ph) * 2.5)
                                    if same_text
                                    else max(12.0, max(iw, ih, pw, ph) * 1.25)
                                )
                                if distance > max_distance:
                                    continue
                                candidates.append(
                                    (
                                        0 if same_text else 1,
                                        distance / max(1.0, max(iw, ih, pw, ph)),
                                        slot_gap,
                                        track_index,
                                    )
                                )
                            if candidates:
                                track_index = min(candidates)[-1]
                                tracks[track_index].append(item)
                                assigned_tracks.add(track_index)
                            else:
                                tracks.append([item])
                                assigned_tracks.add(len(tracks) - 1)

                    for track in tracks:
                        for left, right in zip(track, track[1:]):
                            missing = int(right["slot"]) - int(left["slot"]) - 1
                            if missing < 1:
                                continue
                            left_text = "".join(left["text"].split()).casefold()
                            right_text = "".join(right["text"].split()).casefold()
                            same_text = bool(
                                left_text and right_text and left_text == right_text
                            )
                            allowed_gap = (
                                persistent_gap_frames
                                if same_text
                                else max_internal_gap_frames
                            )
                            if missing > allowed_gap:
                                continue
                            left_polygon = left["polygon"]
                            right_polygon = right["polygon"]
                            if len(left_polygon) != len(right_polygon):
                                continue
                            for offset in range(1, missing + 1):
                                ratio = offset / float(missing + 1)
                                polygon = [
                                    [
                                        int(round(lp[0] + (rp[0] - lp[0]) * ratio)),
                                        int(round(lp[1] + (rp[1] - lp[1]) * ratio)),
                                    ]
                                    for lp, rp in zip(left_polygon, right_polygon)
                                ]
                                timeline.setdefault(
                                    int(left["slot"]) + offset, []
                                ).append(polygon)

                # Protect only the outer event edges. Expanding every scene
                # edge would bridge a hard cut between adjacent scenes.
                if exact_slots and expansion_frames > 0:
                    first_slot = min(exact_slots)
                    last_slot = max(exact_slots)
                    for edge_slot, direction in (
                        (first_slot, -expansion_frames),
                        (last_slot, expansion_frames),
                    ):
                        edge_polygons = [
                            item["polygon"]
                            for item in observations
                            if item["slot"] == edge_slot
                        ]
                        step = -1 if direction < 0 else 1
                        for offset in range(1, abs(direction) + 1):
                            slot = edge_slot + (step * offset)
                            if slot < 0 or slot > max_frame or slot in exact_slots:
                                continue
                            timeline.setdefault(slot, []).extend(edge_polygons)
                continue

            # Fallback: rectangular mask by time range when polygon history is unavailable.
            try:
                x = float(pos.get("x", 0.0))
                y = float(pos.get("y", 0.0))
                width = float(pos.get("width", 0.0))
                height = float(pos.get("height", 0.0))
            except (TypeError, ValueError):
                continue
            x1 = max(0, min(frame_w - 1, int(round(frame_w * x / 100.0))))
            y1 = max(0, min(frame_h - 1, int(round(frame_h * y / 100.0))))
            x2 = max(0, min(frame_w - 1, int(round(frame_w * (x + width) / 100.0))))
            y2 = max(0, min(frame_h - 1, int(round(frame_h * (y + height) / 100.0))))
            if x2 <= x1 or y2 <= y1:
                continue
            rect_poly = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            try:
                start_time = float(pos.get("start_time", 0.0))
            except (TypeError, ValueError):
                start_time = 0.0
            try:
                end_time = float(pos.get("end_time", video_duration))
            except (TypeError, ValueError):
                end_time = video_duration
            start_idx = max(0, int(round(start_time * fps)))
            end_idx = min(max_frame, int(round(end_time * fps)))
            for idx in range(start_idx, end_idx + 1):
                timeline.setdefault(idx, []).append(rect_poly)

        # A dense decorative Chinese panel is a single physical text-bearing
        # surface even when OCR recognizes only changing subsets of its words.
        # Build a bounded per-frame envelope for high-density independent OCR
        # groups, excluding isolated subtitles and wide title lines.  The
        # envelope is tracked like any other same-text polygon below, so it
        # follows camera motion and remains scene/time bounded.
        dense_marker = "__dense_chinese_layout__"
        dense_vertical_gap = max(24.0, float(frame_h) * 0.10)
        # Expand each observed word inside a dense panel instead of blurring
        # one large panel rectangle. This covers nearby clipped glyphs while
        # preserving foreground products and empty gaps between labels.
        # Keep this deliberately tight.  A decorative panel can sit directly
        # behind the advertised product, so percentage-wide padding causes
        # neighbouring word masks to coalesce and obscure the foreground.
        # The renderer adds its own small mask dilation afterwards; this pad
        # only covers glyph antialiasing and modest OCR box jitter.
        dense_word_pad_x = max(6, int(round(float(frame_w) * 0.012)))
        dense_word_pad_y = max(8, int(round(float(frame_h) * 0.012)))
        for scene_id, scene_items in list(global_scene_observations.items()):
            by_slot: Dict[int, List[Dict[str, Any]]] = {}
            for item in scene_items:
                if not str(item.get("source", "") or "").startswith("rapidocr_"):
                    continue
                polygon = item["polygon"]
                xs = [point[0] for point in polygon]
                ys = [point[1] for point in polygon]
                width = max(xs) - min(xs)
                height = max(ys) - min(ys)
                if (
                    width <= 0
                    or height <= 0
                    or width > frame_w * 0.65
                    or height > frame_h * 0.30
                ):
                    continue
                enriched = dict(item)
                enriched["box"] = [min(xs), min(ys), max(xs), max(ys)]
                by_slot.setdefault(int(item["slot"]), []).append(enriched)

            for slot, slot_items in by_slot.items():
                # Approximate duplicate removal prevents the base and enlarged
                # OCR passes from inflating density for one physical word.
                unique_items = []
                seen_boxes = set()
                for item in sorted(slot_items, key=lambda value: value["box"][1]):
                    box = item["box"]
                    key = tuple(int(round(value / 8.0)) for value in box)
                    if key in seen_boxes:
                        continue
                    seen_boxes.add(key)
                    unique_items.append(item)

                vertical_groups: List[List[Dict[str, Any]]] = []
                for item in unique_items:
                    if (
                        not vertical_groups
                        or item["box"][1]
                        > max(member["box"][3] for member in vertical_groups[-1])
                        + dense_vertical_gap
                    ):
                        vertical_groups.append([item])
                    else:
                        vertical_groups[-1].append(item)

                for group in vertical_groups:
                    texts = {
                        "".join(member["text"].split()).casefold()
                        for member in group
                        if "".join(member["text"].split())
                    }
                    if len(group) < 6 or len(texts) < 4:
                        continue
                    x1 = min(member["box"][0] for member in group)
                    y1 = min(member["box"][1] for member in group)
                    x2 = max(member["box"][2] for member in group)
                    y2 = max(member["box"][3] for member in group)
                    bbox_area = max(1.0, (x2 - x1) * (y2 - y1))
                    observed_area = sum(
                        max(0.0, member["box"][2] - member["box"][0])
                        * max(0.0, member["box"][3] - member["box"][1])
                        for member in group
                    )
                    if (
                        observed_area / bbox_area < 0.12
                        or (x2 - x1) > frame_w * 0.95
                        or (y2 - y1) > frame_h * 0.60
                    ):
                        continue
                    for member in group:
                        box = member["box"]
                        mx1 = max(0, int(round(box[0])) - dense_word_pad_x)
                        my1 = max(0, int(round(box[1])) - dense_word_pad_y)
                        mx2 = min(
                            frame_w - 1,
                            int(round(box[2])) + dense_word_pad_x,
                        )
                        my2 = min(
                            frame_h - 1,
                            int(round(box[3])) + dense_word_pad_y,
                        )
                        if mx2 <= mx1 or my2 <= my1:
                            continue
                        dense_item = {
                            "slot": int(slot),
                            "scene_id": scene_id,
                            "polygon": [
                                [mx1, my1],
                                [mx2, my1],
                                [mx2, my2],
                                [mx1, my2],
                            ],
                            "text": dense_marker,
                            "source": "rapidocr_dense_layout",
                        }
                        timeline.setdefault(int(slot), []).append(
                            dense_item["polygon"]
                        )
                        global_exact_groups.setdefault(
                            (scene_id, dense_marker), []
                        ).append(dense_item)
                        global_scene_observations[scene_id].append(dense_item)

        # Dense layouts can make the detector's spatial aggregation absorb
        # neighboring labels into different region objects over time.  Join
        # exact same-text observations once more across all regions, while
        # keeping simultaneous copies one-to-one by spatial proximity.  This
        # restores short OCR dropouts without creating a row-wide envelope.
        for (_scene_id, _normalized_text), items in global_exact_groups.items():
            if len(items) < 2:
                continue
            tracks: List[List[Dict[str, Any]]] = []
            for item in sorted(items, key=lambda value: int(value["slot"])):
                polygon = item["polygon"]
                xs = [point[0] for point in polygon]
                ys = [point[1] for point in polygon]
                ix = (min(xs) + max(xs)) / 2.0
                iy = (min(ys) + max(ys)) / 2.0
                iw = max(1.0, float(max(xs) - min(xs)))
                ih = max(1.0, float(max(ys) - min(ys)))
                candidates = []
                for track_index, track in enumerate(tracks):
                    previous = track[-1]
                    slot_gap = int(item["slot"]) - int(previous["slot"])
                    if slot_gap <= 0 or slot_gap - 1 > persistent_gap_frames:
                        continue
                    previous_polygon = previous["polygon"]
                    pxs = [point[0] for point in previous_polygon]
                    pys = [point[1] for point in previous_polygon]
                    px = (min(pxs) + max(pxs)) / 2.0
                    py = (min(pys) + max(pys)) / 2.0
                    pw = max(1.0, float(max(pxs) - min(pxs)))
                    ph = max(1.0, float(max(pys) - min(pys)))
                    width_ratio = max(iw, pw) / max(1.0, min(iw, pw))
                    height_ratio = max(ih, ph) / max(1.0, min(ih, ph))
                    if width_ratio > 2.5 or height_ratio > 2.5:
                        continue
                    distance = ((ix - px) ** 2 + (iy - py) ** 2) ** 0.5
                    per_frame_motion = max(
                        8.0, max(iw, ih, pw, ph) * 0.35
                    )
                    max_distance = per_frame_motion * max(1, slot_gap)
                    if distance > max_distance:
                        continue
                    candidates.append(
                        (
                            distance / max(1.0, max(iw, ih, pw, ph)),
                            slot_gap,
                            track_index,
                        )
                    )
                if candidates:
                    tracks[min(candidates)[-1]].append(item)
                else:
                    tracks.append([item])

            for track in tracks:
                for left, right in zip(track, track[1:]):
                    missing = int(right["slot"]) - int(left["slot"]) - 1
                    if missing < 1 or missing > persistent_gap_frames:
                        continue
                    left_polygon = left["polygon"]
                    right_polygon = right["polygon"]
                    if len(left_polygon) != len(right_polygon):
                        continue
                    for offset in range(1, missing + 1):
                        ratio = offset / float(missing + 1)
                        interpolated = [
                            [
                                int(round(lp[0] + (rp[0] - lp[0]) * ratio)),
                                int(round(lp[1] + (rp[1] - lp[1]) * ratio)),
                            ]
                            for lp, rp in zip(left_polygon, right_polygon)
                        ]
                        timeline.setdefault(int(left["slot"]) + offset, []).append(
                            interpolated
                        )

        # One physical frame of scene-bounded hold covers OCR onset/offset
        # jitter without recreating the old 0.4-second temporal overreach. A
        # target slot must already contain an observation from the same scene,
        # so the hold can never cross a hard cut into an unrelated scene.
        hold_frames = max(
            0, int(getattr(OCRThresholds, "PRECISION_BUFFER_FRAMES", 1))
        )
        if hold_frames > 0:
            for _scene_id, items in global_scene_observations.items():
                scene_slots = {int(item["slot"]) for item in items}
                for item in items:
                    source_slot = int(item["slot"])
                    for offset in range(1, hold_frames + 1):
                        for target_slot in (source_slot - offset, source_slot + offset):
                            if target_slot in scene_slots:
                                timeline.setdefault(target_slot, []).append(
                                    item["polygon"]
                                )

        # Deduplicate polygons per frame.
        for idx, polygons in list(timeline.items()):
            seen = set()
            unique: List[List[List[int]]] = []
            for polygon in polygons:
                key = tuple((pt[0], pt[1]) for pt in polygon)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(polygon)
            timeline[idx] = unique
        return timeline

    def _build_time_aware_blur_boxes(
        self,
        subtitle_positions: List[Dict[str, Any]],
        w: int,
        h: int,
        video_duration: float,
        *,
        exclude_polygon_regions: bool = False,
    ) -> List[Dict[str, Any]]:
        """Build bounded timed boxes without cross-time row envelopes."""
        base_height = 1080
        base_min_pad = 5
        min_pad = max(2, int(base_min_pad * (h / base_height)))
        extra_side_pad = max(4, int(w * 0.006))
        row_merge_threshold = max(14, int(h * 0.03))
        horizontal_merge_gap = max(12, int(w * 0.025))

        prepared: List[Dict[str, Any]] = []
        for pos in subtitle_positions:
            if exclude_polygon_regions and pos.get("frame_regions"):
                # Polygon-backed tracks are represented by their exact or
                # bounded interpolated samples.  Their accumulated rectangle
                # would over-blur motion paths and must not be added as well.
                continue
            try:
                x = float(pos.get("x", 0))
                y = float(pos.get("y", 0))
                width = float(pos.get("width", 0))
                height = float(pos.get("height", 0))
            except (TypeError, ValueError):
                continue

            x1 = int(w * x / 100.0)
            y1 = int(h * y / 100.0)
            x2 = int(w * (x + width) / 100.0)
            y2 = int(h * (y + height) / 100.0)
            if x2 <= x1 or y2 <= y1:
                continue

            box_width = x2 - x1
            box_height = y2 - y1
            pad_x = max(min_pad, int(box_width * 0.12))
            pad_y = max(min_pad, int(box_height * 0.15))
            side_pad = max(extra_side_pad, int(box_width * 0.12))

            start_time = pos.get("start_time", 0)
            end_time = pos.get("end_time", video_duration)
            try:
                start_time = float(start_time)
            except (TypeError, ValueError):
                start_time = 0.0
            try:
                end_time = float(end_time)
            except (TypeError, ValueError):
                end_time = video_duration

            # 시간 버퍼는 subtitle_detector에서 이미 적용됨 - 여기서는 범위만 클램프
            start_time = max(0.0, start_time)
            end_time = min(video_duration, end_time)
            if end_time < start_time:
                end_time = start_time

            final_box = [
                max(0, x1 - pad_x - side_pad),
                max(0, y1 - pad_y // 2),
                min(w - 1, x2 + pad_x + side_pad),
                min(h - 1, y2 + pad_y),
            ]
            if final_box[2] <= final_box[0] or final_box[3] <= final_box[1]:
                continue

            prepared.append(
                {
                    "box": final_box,
                    "start_time": start_time,
                    "end_time": end_time,
                    "text": str(pos.get("text", "") or pos.get("sample_text", ""))[:30],
                }
            )

        if not prepared:
            return []

        prepared.sort(
            key=lambda e: (
                (e["box"][1] + e["box"][3]) / 2.0,
                e["start_time"],
            )
        )

        merged: List[Dict[str, Any]] = []
        for entry in prepared:
            box = entry["box"]
            center_y = (box[1] + box[3]) / 2.0
            was_merged = False

            for existing in merged:
                ex_box = existing["box"]
                ex_center_y = (ex_box[1] + ex_box[3]) / 2.0
                same_row = abs(ex_center_y - center_y) <= row_merge_threshold
                overlaps_in_time = (
                    entry["start_time"] <= existing["end_time"]
                    and entry["end_time"] >= existing["start_time"]
                )
                horizontal_gap = max(
                    0,
                    max(box[0] - ex_box[2], ex_box[0] - box[2]),
                )

                if same_row and overlaps_in_time and horizontal_gap <= horizontal_merge_gap:
                    ex_box[0] = min(ex_box[0], box[0])
                    ex_box[1] = min(ex_box[1], box[1])
                    ex_box[2] = max(ex_box[2], box[2])
                    ex_box[3] = max(ex_box[3], box[3])
                    existing["start_time"] = min(existing["start_time"], entry["start_time"])
                    existing["end_time"] = max(existing["end_time"], entry["end_time"])
                    if len(entry["text"]) > len(existing["text"]):
                        existing["text"] = entry["text"]
                    was_merged = True
                    break

            if not was_merged:
                merged.append(
                    {
                        "box": list(box),
                        "start_time": entry["start_time"],
                        "end_time": entry["end_time"],
                        "text": entry["text"],
                    }
                )

        merged.sort(key=lambda e: (e["start_time"], e["box"][1], e["box"][0]))
        return merged

    def apply_opencv_blur_enhanced_v2(self, video, subtitle_positions, w, h):
        """Blur pipeline with temporal stabilization + merged mask blending."""
        import cv2
        import numpy as np
        from moviepy.editor import VideoClip

        fps = float(getattr(video, "fps", 0.0) or 0.0)
        if fps <= 0:
            fps = 30.0

        polygon_timeline: Dict[int, List[List[List[int]]]] = {}
        if getattr(OCRThresholds, "PRECISION_POLYGON_BLUR", False):
            polygon_timeline = self._build_polygon_timeline(
                subtitle_positions=subtitle_positions,
                fps=fps,
                frame_w=w,
                frame_h=h,
                video_duration=float(video.duration),
            )
            if polygon_timeline:
                logger.info(
                    f"[BLUR APPLY V2] Precision polygon timeline: {len(polygon_timeline)} frame slots"
                )

        boxes_with_time = self._build_time_aware_blur_boxes(
            subtitle_positions=subtitle_positions,
            w=w,
            h=h,
            video_duration=float(video.duration),
            exclude_polygon_regions=bool(polygon_timeline),
        )
        logger.info(f"[BLUR APPLY V2] Stabilized region count: {len(boxes_with_time)}")
        if not boxes_with_time and not polygon_timeline:
            return video

        coverage_stats = {
            "expected_polygon_slots": len(polygon_timeline),
            "rendered_unique_slots": 0,
            "active_unique_slots": 0,
            "changed_unique_slots": 0,
            "minimum_mask_delta": None,
            "maximum_mask_delta": None,
        }
        seen_slots = set()
        active_slots = set()
        changed_slots = set()
        slot_deltas: Dict[int, float] = {}
        self.gui._precision_blur_stats = coverage_stats
        self.gui._precision_blur_expected_slots = set(polygon_timeline)
        self.gui._precision_blur_seen_slots = seen_slots
        self.gui._precision_blur_active_slots = active_slots
        self.gui._precision_blur_slot_deltas = slot_deltas

        base_height = 1080
        base_kernel = 25
        min_kernel = max(15, int(base_kernel * (h / base_height)))
        base_feather = 21
        feather_size = int(base_feather * (h / base_height))
        feather_size = feather_size + 1 if feather_size % 2 == 0 else feather_size
        feather_size = max(11, min(feather_size, 51))

        def _auto_kernel(a: int, b: int) -> int:
            k = max(min_kernel, min(151, max(a, b) // 4))
            return k + 1 if k % 2 == 0 else k

        last_log_time = [-1.0]

        def _feather_blur(get_frame, t):
            frame = get_frame(t).copy()
            should_log = (int(t) % 5 == 0) and (int(t) != last_log_time[0])
            if should_log:
                last_log_time[0] = int(t)

            frame_index = int(round(t * fps))
            if frame_index not in seen_slots:
                seen_slots.add(frame_index)
                coverage_stats["rendered_unique_slots"] = len(seen_slots)
            frame_polygons = polygon_timeline.get(frame_index, []) if polygon_timeline else []
            valid_polygons = []
            for polygon in frame_polygons:
                normalized = self._normalize_polygon_points(
                    polygon, frame_w=w, frame_h=h
                )
                if normalized:
                    valid_polygons.append(normalized)

            mask_polygons = []
            for polygon in valid_polygons:
                mask_polygon = polygon
                polygon_xs = [point[0] for point in polygon]
                polygon_ys = [point[1] for point in polygon]
                polygon_height = max(polygon_ys) - min(polygon_ys)
                # Bottom subtitle OCR can recognize adjacent glyph groups as
                # separate boxes and intermittently lose a short side group.
                # Add horizontal row padding only for shallow lower-third
                # polygons; dense panels and arbitrary product regions keep
                # their own exact geometry.
                if (
                    min(polygon_ys) >= h * 0.70
                    and polygon_height <= h * 0.15
                ):
                    row_pad_x = max(12, int(round(w * 0.06)))
                    row_pad_y = max(4, int(round(h * 0.012)))
                    px1 = max(0, min(polygon_xs) - row_pad_x)
                    py1 = max(0, min(polygon_ys) - row_pad_y)
                    px2 = min(w - 1, max(polygon_xs) + row_pad_x)
                    py2 = min(h - 1, max(polygon_ys) + row_pad_y)
                    mask_polygon = [
                        [px1, py1],
                        [px2, py1],
                        [px2, py2],
                        [px1, py2],
                    ]
                mask_polygons.append(mask_polygon)

            frame_duration = 1.0 / fps
            active = [
                bt
                for bt in boxes_with_time
                if bt["start_time"] - (frame_duration * 0.5)
                <= t
                < bt["end_time"] + frame_duration
            ]
            merged_boxes = self._merge_spatial_boxes(
                [entry["box"] for entry in active], frame_width=w
            )

            if not valid_polygons and not merged_boxes:
                return frame

            bounds = [list(box) for box in merged_boxes]
            for polygon in mask_polygons:
                xs = [p[0] for p in polygon]
                ys = [p[1] for p in polygon]
                bounds.append([min(xs), min(ys), max(xs) + 1, max(ys) + 1])

            global_x1 = max(0, min(box[0] for box in bounds) - 2)
            global_y1 = max(0, min(box[1] for box in bounds) - 2)
            global_x2 = min(w, max(box[2] for box in bounds) + 3)
            global_y2 = min(h, max(box[3] for box in bounds) + 3)
            if global_x2 <= global_x1 or global_y2 <= global_y1:
                return frame

            roi = frame[global_y1:global_y2, global_x1:global_x2]
            if roi.size == 0:
                return frame
            original_roi = roi.copy()

            roi_mask = np.zeros((global_y2 - global_y1, global_x2 - global_x1), np.uint8)
            for mask_polygon in mask_polygons:
                shifted = np.array(
                    [[p[0] - global_x1, p[1] - global_y1] for p in mask_polygon],
                    dtype=np.int32,
                ).reshape((-1, 1, 2))
                cv2.fillPoly(roi_mask, [shifted], 255)
            for box in merged_boxes:
                x1, y1, x2, y2 = box
                rx1 = max(0, x1 - global_x1)
                ry1 = max(0, y1 - global_y1)
                rx2 = min(global_x2 - global_x1, x2 - global_x1)
                ry2 = min(global_y2 - global_y1, y2 - global_y1)
                if rx2 > rx1 and ry2 > ry1:
                    cv2.rectangle(roi_mask, (rx1, ry1), (rx2 - 1, ry2 - 1), 255, -1)

            # Expand glyph edges and shadows but never close distant masks into
            # one large rectangle.
            # OCR polygons are often tight to the visible glyph body. Leave
            # enough room for a one-frame camera move, outlines, and shadows
            # while keeping disconnected labels as separate components.
            edge_kernel = max(5, int(min(w, h) * 0.012))
            if edge_kernel % 2 == 0:
                edge_kernel += 1
            edge_struct = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (edge_kernel, edge_kernel)
            )
            roi_mask = cv2.dilate(roi_mask, edge_struct, iterations=1)

            # Blur each disconnected subtitle component independently. This is
            # both stronger and faster than blurring the empty space between a
            # top caption and a bottom badge in one full-height ROI.
            output_roi = original_roi.copy()
            component_count, labels, component_stats, _centroids = (
                cv2.connectedComponentsWithStats((roi_mask > 0).astype(np.uint8), 8)
            )
            component_pad = max(4, feather_size)
            for component_id in range(1, component_count):
                cx, cy, cw, ch, area = component_stats[component_id]
                if area <= 0 or cw <= 0 or ch <= 0:
                    continue
                sx1 = max(0, int(cx) - component_pad)
                sy1 = max(0, int(cy) - component_pad)
                sx2 = min(roi.shape[1], int(cx + cw) + component_pad)
                sy2 = min(roi.shape[0], int(cy + ch) + component_pad)
                component_roi = original_roi[sy1:sy2, sx1:sx2]
                component_mask = (
                    (labels[sy1:sy2, sx1:sx2] == component_id).astype(np.uint8)
                    * 255
                )
                blur_kernel = _auto_kernel(cw, ch)
                blurred_component = cv2.GaussianBlur(
                    component_roi, (blur_kernel, blur_kernel), 0
                )
                blurred_component = cv2.GaussianBlur(
                    blurred_component, (blur_kernel, blur_kernel), 0
                )
                feathered = cv2.GaussianBlur(
                    component_mask, (feather_size, feather_size), 0
                )
                component_alpha = np.dstack(
                    [feathered, feathered, feathered]
                ).astype(np.float32) / 255.0
                output_roi[sy1:sy2, sx1:sx2] = (
                    blurred_component.astype(np.float32) * component_alpha
                    + output_roi[sy1:sy2, sx1:sx2].astype(np.float32)
                    * (1 - component_alpha)
                ).astype(np.uint8)

            frame[global_y1:global_y2, global_x1:global_x2] = output_roi

            if frame_index not in active_slots:
                active_slots.add(frame_index)
                coverage_stats["active_unique_slots"] = len(active_slots)
                changed_roi = frame[global_y1:global_y2, global_x1:global_x2]
                core_mask = roi_mask >= 128
                if np.any(core_mask):
                    delta = float(
                        np.abs(
                            changed_roi.astype(np.float32)
                            - original_roi.astype(np.float32)
                        )[core_mask].mean()
                    )
                else:
                    delta = 0.0
                slot_deltas[frame_index] = delta
                if delta > 0.5:
                    changed_slots.add(frame_index)
                    coverage_stats["changed_unique_slots"] = len(changed_slots)
                current_min = coverage_stats["minimum_mask_delta"]
                current_max = coverage_stats["maximum_mask_delta"]
                coverage_stats["minimum_mask_delta"] = (
                    delta if current_min is None else min(float(current_min), delta)
                )
                coverage_stats["maximum_mask_delta"] = (
                    delta if current_max is None else max(float(current_max), delta)
                )

            if should_log:
                logger.debug(
                    f"[BLUR APPLY V2] t={t:.2f}s polygons={len(valid_polygons)} "
                    f"boxes={len(merged_boxes)} "
                    f"roi={global_x2 - global_x1}x{global_y2 - global_y1}"
                )
            return frame

        clip = VideoClip(lambda t: _feather_blur(video.get_frame, t), duration=video.duration)
        if video.audio:
            clip = clip.set_audio(video.audio)
        if hasattr(video, "fps"):
            clip.fps = video.fps
        return clip

    def prepare_centered_subtitle_layout(
        self, subtitle_positions: Optional[Iterable[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Prepare centered Korean subtitle layout based on Chinese subtitle positions.

        Args:
            subtitle_positions: List of detected Chinese subtitle positions

        Returns:
            List containing single centered subtitle region configuration
        """
        region = self._compute_centered_subtitle_region(subtitle_positions)
        if not region:
            self.gui.center_subtitle_region = None
            self.gui.korean_subtitle_override = None
            self.gui.korean_subtitle_mode = "default"
            return []

        previous = getattr(self.gui, "center_subtitle_region", None)
        previous_signature = None
        if isinstance(previous, dict):
            previous_signature = (
                previous.get("x"),
                previous.get("y"),
                previous.get("width"),
                previous.get("height"),
            )
        new_signature = (region["x"], region["y"], region["width"], region["height"])

        self.gui.center_subtitle_region = region
        self.gui.korean_subtitle_override = {
            "x": region["x"],
            "y": region["y"],
            "width": region["width"],
            "height": region["height"],
        }
        self.gui.korean_subtitle_mode = "overlay"

        if previous_signature != new_signature:
            self.gui.add_log(
                "[자막 배치] 중앙 정렬 영역 적용 "
                f"(x={region['x']}%, y={region['y']}%, w={region['width']}%, h={region['height']}%)"
            )

        return [region]

    def _compute_centered_subtitle_region(
        self, positions: Optional[Iterable[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """
        Compute centered subtitle region from detected positions.

        Args:
            positions: List of detected subtitle positions

        Returns:
            Dictionary with centered region coordinates (x, y, width, height in %)
            or None if computation fails
        """
        if not positions:
            return None

        positions = list(positions)
        if not positions:
            return None

        def _safe_float(value: Any) -> Optional[float]:
            try:
                if value is None:
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        def _median_or_default(
            values: List[float], default: float, minimum: float, maximum: float
        ) -> float:
            valid = sorted(v for v in values if v is not None and v > 0)
            if not valid:
                return default
            mid = len(valid) // 2
            if len(valid) % 2 == 1:
                median_value = valid[mid]
            else:
                median_value = (valid[mid - 1] + valid[mid]) / 2.0
            return max(minimum, min(maximum, median_value))

        width_candidates = [_safe_float(pos.get("width")) for pos in positions]
        height_candidates = [_safe_float(pos.get("height")) for pos in positions]

        width_pct = _median_or_default(
            width_candidates, default=60.0, minimum=30.0, maximum=90.0
        )
        height_pct = _median_or_default(
            height_candidates, default=18.0, minimum=10.0, maximum=35.0
        )

        center_x_pct = 50.0
        center_y_pct = 65.0
        x_pct = max(0.0, min(100.0 - width_pct, center_x_pct - (width_pct / 2.0)))
        y_pct = max(0.0, min(100.0 - height_pct, center_y_pct - (height_pct / 2.0)))

        base = {
            "x": round(x_pct, 2),
            "y": round(y_pct, 2),
            "width": round(width_pct, 2),
            "height": round(height_pct, 2),
            "language": "chinese",
            "source": "center_alignment",
            "frequency": len(positions) if positions else 0,
        }

        if positions:
            exemplar = positions[0]
            sample = exemplar.get("sample_text") or exemplar.get("text")
            if sample:
                base["sample_text"] = sample
            lang = exemplar.get("language")
            if lang:
                base["language"] = lang

        return base

    def _update_korean_subtitle_layout(self, subtitle_positions):
        """
        Update Korean subtitle layout strategy based on Chinese subtitle positions.
        Places Korean subtitles directly over blurred Chinese subtitle areas.

        Args:
            subtitle_positions: List of Chinese subtitle regions
        """
        self.gui.korean_subtitle_override = None
        self.gui.korean_subtitle_mode = "default"

        if not subtitle_positions:
            logger.debug(
                "[Korean subtitle] No Chinese subtitle position - keeping default position"
            )
            return

        try:
            # 중국어 자막 위치의 평균 계산
            if not subtitle_positions:
                logger.debug("[Korean subtitle] Chinese subtitle positions empty")
                return
            centered = self.prepare_centered_subtitle_layout(subtitle_positions)
            if centered:
                return

            # 모든 중국어 자막 영역의 평균 위치 계산
            total_x = 0
            total_y = 0
            total_width = 0
            total_height = 0
            count = len(subtitle_positions)

            for pos in subtitle_positions:
                total_x += pos.get("x", 0)
                total_y += pos.get("y", 0)
                total_width += pos.get("width", 0)
                total_height += pos.get("height", 0)

            avg_x = total_x / count
            avg_y = total_y / count
            avg_width = total_width / count
            avg_height = total_height / count

            # 한글 자막을 중국어 자막 위치에 정확히 배치
            self.gui.korean_subtitle_override = {
                "x": avg_x,
                "y": avg_y,
                "width": avg_width,
                "height": avg_height,
            }
            self.gui.korean_subtitle_mode = "overlay"

            logger.debug(
                f"[Korean subtitle] Overlay on Chinese subtitle position: x={avg_x:.1f}%, y={avg_y:.1f}%, w={avg_width:.1f}%, h={avg_height:.1f}%"
            )

        except Exception as e:
            logger.error(f"[Korean subtitle] Error during position calculation: {e}")
            logger.exception("Korean subtitle layout calculation failed")
