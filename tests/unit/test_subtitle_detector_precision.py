import math

import cv2
import numpy as np

from config.constants import OCRThresholds
from processors.subtitle_detector import SubtitleDetector


class _DummyGUI:
    def __init__(self):
        self.ocr_reader = None

    def add_log(self, _message):
        pass


class _TimestampCapture:
    def __init__(self, milliseconds):
        self.milliseconds = milliseconds

    def get(self, _property):
        return self.milliseconds


class _ScheduledCapture:
    def __init__(self):
        self.seeks = []
        self.read_count = 0

    def set(self, _property, value):
        self.seeks.append(int(value))

    def read(self):
        self.read_count += 1
        return True, np.zeros((2, 2, 3), dtype=np.uint8)

    def get(self, _property):
        return 0.0


def _region(x, time, frame_index, *, scene_id="scene:0", text="字幕"):
    return {
        "x": float(x),
        "y": 80.0,
        "width": 10.0,
        "height": 5.0,
        "time": float(time),
        "frame_index": int(frame_index),
        "text": text,
        "confidence": 0.95,
        "scene_id": scene_id,
        "polygon": [[x, 80], [x + 10, 80], [x + 10, 85], [x, 85]],
    }


def test_bbox_batch_preserves_input_alignment_and_records_invalid_coordinates():
    detector = SubtitleDetector(_DummyGUI())
    bboxes = [
        [[math.nan, 2], [10, 2], [10, 10], [2, 10]],
        [[20, 20], [80, 20], [80, 40], [20, 40]],
    ]

    processed = detector._gpu_process_bbox_batch(bboxes, W=100, H=100)

    assert len(processed) == len(bboxes)
    assert processed[0] is None
    assert processed[1] is not None
    assert processed[1]["x_min"] == 20
    assert detector.invalid_coordinate_count == 1
    assert detector.review_required is True


def test_glm_client_invalid_coordinate_counter_is_folded_into_diagnostics():
    gui = _DummyGUI()
    gui.ocr_reader = type(
        "Backend", (), {"_glm_client": type("Client", (), {"invalid_coordinate_count": 4})()}
    )()
    detector = SubtitleDetector(gui)
    detector._reset_precision_diagnostics()

    gui.ocr_reader._glm_client.invalid_coordinate_count = 6
    detector._sync_reader_coordinate_diagnostics()

    assert detector.invalid_coordinate_count == 2
    assert detector.review_required is True
    assert "ocr_reader_invalid_coordinates" in detector.review_reasons


def test_glm_request_failure_counter_requires_review():
    gui = _DummyGUI()
    gui.ocr_reader = type(
        "Backend",
        (),
        {
            "_glm_client": type(
                "Client",
                (),
                {"invalid_coordinate_count": 0, "request_failure_count": 2},
            )()
        },
    )()
    detector = SubtitleDetector(gui)
    detector._reset_precision_diagnostics()

    gui.ocr_reader._glm_client.request_failure_count = 3
    detector._sync_reader_coordinate_diagnostics()

    assert detector.review_required is True
    assert "ocr_reader_request_failures" in detector.review_reasons


def test_decoder_timestamp_is_preferred_and_non_monotonic_value_falls_back():
    detector = SubtitleDetector(_DummyGUI())

    assert detector._frame_time_after_read(
        _TimestampCapture(1250.0), frame_index=30, fps=30.0
    ) == 1.25
    recovered = detector._frame_time_after_read(
        _TimestampCapture(1100.0), frame_index=31, fps=30.0, previous_time=1.25
    )
    assert recovered > 1.25
    assert recovered == 31 / 30.0 or recovered == 1.25 + (1 / 30.0)


def test_consecutive_full_scan_frames_seek_only_across_real_gaps():
    detector = SubtitleDetector(_DummyGUI())
    capture = _ScheduledCapture()
    next_expected = None

    for frame_pos in (10, 11, 12, 20, 21):
        ok, _frame, next_expected = detector._read_scheduled_frame(
            capture, frame_pos, next_expected
        )
        assert ok is True

    assert capture.read_count == 5
    assert capture.seeks == [10, 20]


def test_precision_aggregation_uses_frame_gap_and_per_segment_bbox():
    detector = SubtitleDetector(_DummyGUI())
    regions = [
        _region(10, 1.0, 30),
        _region(12, 1.0 + 2 / 30.0, 32),
        _region(14, 1.3, 39, text="字幕乙"),
    ]

    merged = detector._gpu_aggregate_regions(regions, fps=30.0, total_duration=2.0)

    assert len(merged) == 2
    assert merged[0]["start_time"] == 1.0 - 1 / 30.0
    assert merged[0]["end_time"] == 1.0 + 3 / 30.0
    assert merged[0]["x"] == 8.0
    assert merged[0]["width"] == 16.0
    assert merged[1]["x"] == 12.0
    assert merged[1]["width"] == 14.0


def test_scene_cut_splits_timeline_and_is_kept_in_frame_metadata():
    detector = SubtitleDetector(_DummyGUI())
    regions = [
        _region(20, 2.0, 60, scene_id="segment:0"),
        _region(20, 2.0 + 1 / 30.0, 61, scene_id="segment:1"),
    ]

    merged = detector._gpu_aggregate_regions(regions, fps=30.0)

    assert len(merged) == 2
    assert merged[0]["scene_ids"] == ["segment:0"]
    assert merged[1]["scene_ids"] == ["segment:1"]
    assert merged[0]["frame_regions"][0]["scene_id"] == "segment:0"
    assert merged[1]["frame_regions"][0]["scene_id"] == "segment:1"


def test_high_confidence_chinese_short_moving_observation_is_not_filtered():
    detector = SubtitleDetector(_DummyGUI())
    moving = {
        "x": 10.0,
        "y": 20.0,
        "width": 20.0,
        "height": 6.0,
        "start_time": 5.0,
        "end_time": 5.0,
        "time_group_count": 1,
        "x_positions": [10.0, 80.0],
        "y_positions": [20.0, 70.0],
        "sample_text": "移动字幕",
        "language": "chinese",
        "source": "opencv_ocr_numpy",
        "frequency": 1,
        "max_confidence": 0.95,
        "high_confidence_chinese": True,
    }

    assert detector._filter_chinese_regions([moving]) == [moving]


def test_independent_chinese_single_frame_observation_is_not_filtered():
    detector = SubtitleDetector(_DummyGUI())
    observation = {
        "x": 70.0,
        "y": 85.0,
        "width": 20.0,
        "height": 8.0,
        "start_time": 0.1,
        "end_time": 0.1,
        "time_group_count": 1,
        "x_positions": [70.0],
        "y_positions": [85.0],
        "sample_text": "\u51c0\u51b2\u51b2",
        "language": "chinese",
        "source": "opencv_ocr_numpy",
        "frequency": 1,
        "max_confidence": 0.59,
        "high_confidence_chinese": True,
        "independent_chinese": True,
    }

    assert detector._filter_chinese_regions([observation]) == [observation]


def test_broad_bottom_band_fallback_is_off_and_requests_review():
    detector = SubtitleDetector(_DummyGUI())

    assert OCRThresholds.ENABLE_BROAD_BOTTOM_BAND_FALLBACK is False
    assert detector._fallback_detect_bottom_subtitle_band("missing.mp4") is None
    assert detector.review_required is True
    assert "broad_bottom_band_fallback_disabled" in detector.review_reasons


def test_scene_cut_helper_uses_mad_and_histogram_thresholds():
    detector = SubtitleDetector(_DummyGUI())
    black = np.zeros((90, 160, 3), dtype=np.uint8)
    white = np.full((90, 160, 3), 255, dtype=np.uint8)

    assert detector._is_scene_cut(black, black.copy()) is False
    assert detector._is_scene_cut(black, white) is True


def test_full_frame_precision_keeps_ordered_glm_batch_transport_enabled():
    gui = _DummyGUI()
    gui.ocr_reader = type(
        "GLMBackend",
        (),
        {"engine_name": "glm_ocr", "supports_batch": lambda self: True},
    )()
    detector = SubtitleDetector(gui)

    assert OCRThresholds.FULL_FRAME_SCAN_MODE is True
    assert detector._use_batch_ocr(full_scan_mode=True) is True


def test_sub_second_final_segment_is_not_dropped():
    assert SubtitleDetector._segment_has_frames(10.0, 10.5, 30.0, 315) is True
    assert SubtitleDetector._segment_has_frames(10.5, 10.5, 30.0, 315) is False


def test_fractional_fps_final_physical_frame_is_not_dropped():
    fps = 23.976
    total_frames = 3150
    duration = total_frames / fps

    assert SubtitleDetector._segment_has_frames(
        (total_frames - 1) / fps, duration, fps, total_frames
    ) is True


def test_large_valid_polygon_is_preserved_for_exact_blur():
    detector = SubtitleDetector(_DummyGUI())
    result = detector._gpu_process_bbox_batch(
        [[[0, 0], [99, 0], [99, 60], [0, 60]]], W=100, H=100
    )

    assert result[0] is not None
    assert result[0]["oversized"] is True
    assert detector.review_required is False


def test_independent_shallow_full_width_line_is_not_page_scale_oversized():
    detector = SubtitleDetector(_DummyGUI())
    info = detector._gpu_process_bbox_batch(
        [[[9, 755], [1072, 755], [1072, 881], [9, 881]]], W=1080, H=1920
    )[0]

    assert info["oversized"] is True
    assert detector._independent_box_is_tight_line(info) is True


def test_independent_near_edge_polygon_covers_clipped_glyph_fragment():
    detector = SubtitleDetector(_DummyGUI())

    snapped = detector._snap_polygon_to_near_frame_edges(
        [[23, 9], [182, 9], [182, 56], [23, 56]], W=1080, H=1920
    )

    assert snapped == [[0.0, 0.0], [182.0, 0.0], [182.0, 56.0], [0.0, 56.0]]


def test_near_edge_snapping_does_not_broaden_interior_polygon():
    detector = SubtitleDetector(_DummyGUI())
    polygon = [[100, 100], [300, 100], [300, 160], [100, 160]]

    assert detector._snap_polygon_to_near_frame_edges(
        polygon, W=1080, H=1920
    ) == polygon


def test_batch_mode_streams_bounded_frame_groups():
    class Backend:
        def __init__(self):
            self.batch_sizes = []

        def readtext_batch(self, frames):
            self.batch_sizes.append(len(frames))
            return [[] for _ in frames]

    gui = _DummyGUI()
    gui.ocr_reader = Backend()
    detector = SubtitleDetector(gui)
    capture = _ScheduledCapture()

    result = detector._analyze_segment_batch_streaming(
        capture,
        sample_frames=list(range(25)),
        segment_name="0-1s",
        W=2,
        H=2,
        fps=30.0,
        optimizer=None,
    )

    assert result["total_frames_checked"] == 25
    assert sum(gui.ocr_reader.batch_sizes) == 25
    assert max(gui.ocr_reader.batch_sizes) <= 10


def test_oversized_combined_bbox_is_repaired_from_nearby_precise_text_boxes():
    detector = SubtitleDetector(_DummyGUI())
    regions = [
        _region(5, 1.0, 30, text="热卖中"),
        _region(70, 1.0, 30, text="冲冲冲"),
        {
            **_region(0, 1.1, 33, text="热卖中 冲冲冲"),
            "y": 20.0,
            "width": 100.0,
            "height": 80.0,
            "polygon": [[0, 20], [100, 20], [100, 100], [0, 100]],
            "oversized": True,
        },
    ]

    repaired = detector._repair_oversized_observations(regions, fps=30.0)
    repaired_at_11 = [item for item in repaired if item["time"] == 1.1]

    assert len(repaired_at_11) == 2
    assert sorted(item["x"] for item in repaired_at_11) == [5.0, 70.0]
    assert all(item["repaired_from_oversized"] for item in repaired_at_11)
    assert detector.review_required is False


def test_oversized_repair_fails_closed_for_ambiguous_duplicate_anchor():
    detector = SubtitleDetector(_DummyGUI())
    first = _region(5, 1.0, 30, text="\u70ed\u5356\u4e2d")
    second = _region(70, 1.0, 30, text="\u70ed\u5356\u4e2d")
    oversized = {
        **_region(0, 1.01, 30, text="\u70ed\u5356\u4e2d"),
        "y": 20.0,
        "width": 100.0,
        "height": 80.0,
        "polygon": [[0, 20], [100, 20], [100, 100], [0, 100]],
        "oversized": True,
    }

    repaired = detector._repair_oversized_observations(
        [first, second, oversized], fps=30.0
    )

    assert not any(item.get("oversized") for item in repaired)
    assert detector.review_required is True
    assert "oversized_ocr_bbox_ambiguous_anchor" in detector.review_reasons


def test_oversized_layout_uses_exact_independent_spatial_anchors():
    detector = SubtitleDetector(_DummyGUI())
    left = {
        **_region(5, 1.0, 30, text="\u70ed\u5356\u4e2d"),
        "source": "rapidocr_independent",
    }
    right = {
        **_region(70, 1.0, 30, text="\u4e2d\u5b89\u63a5"),
        "source": "rapidocr_independent",
    }
    oversized = {
        **_region(0, 1.0, 30, text="\u70ed\u5356\u4e2d\n\u51b2\u51b2\u51b2"),
        "y": 20.0,
        "width": 100.0,
        "height": 80.0,
        "polygon": [[0, 20], [100, 20], [100, 100], [0, 100]],
        "oversized": True,
    }

    repaired = detector._repair_oversized_observations(
        [left, right, oversized], fps=30.0
    )
    repaired_at_time = [
        item for item in repaired if item.get("repaired_from_oversized")
    ]

    assert len(repaired_at_time) == 2
    assert detector.review_required is False


def test_single_line_oversized_layout_uses_exact_independent_spatial_anchor():
    detector = SubtitleDetector(_DummyGUI())
    exact_anchor = {
        **_region(42, 1.0, 30, text="\u79cd\u8349"),
        "source": "rapidocr_independent",
    }
    oversized = {
        **_region(0, 1.0, 30, text="\u4e2d\u56fd\u7f8e\u8303\u8baf"),
        "y": 20.0,
        "width": 100.0,
        "height": 80.0,
        "polygon": [[0, 20], [100, 20], [100, 100], [0, 100]],
        "oversized": True,
    }

    repaired = detector._repair_oversized_observations(
        [exact_anchor, oversized], fps=30.0
    )
    repaired_at_time = [
        item for item in repaired if item.get("repaired_from_oversized")
    ]

    assert len(repaired_at_time) == 1
    assert repaired_at_time[0]["polygon"] == exact_anchor["polygon"]
    assert detector.review_required is False


def test_single_line_layout_never_uses_mismatched_independent_frame():
    detector = SubtitleDetector(_DummyGUI())
    nearby_anchor = {
        **_region(42, 1.0, 30, text="\u79cd\u8349"),
        "source": "rapidocr_independent",
    }
    oversized = {
        **_region(0, 1.0 + (1.0 / 30.0), 31, text="\u4e2d\u56fd\u7f8e\u8303\u8baf"),
        "y": 20.0,
        "width": 100.0,
        "height": 80.0,
        "polygon": [[0, 20], [100, 20], [100, 100], [0, 100]],
        "oversized": True,
    }

    repaired = detector._repair_oversized_observations(
        [nearby_anchor, oversized], fps=30.0
    )

    assert not any(item.get("repaired_from_oversized") for item in repaired)
    assert detector.review_required is True
    assert "oversized_ocr_bbox_without_precise_anchor" in detector.review_reasons


def test_static_visual_track_extends_only_over_visible_connected_frames(tmp_path):
    video_path = tmp_path / "visual_track.avi"
    width, height, fps, total_frames = 160, 90, 10.0, 12
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height)
    )
    assert writer.isOpened()
    for frame_index in range(total_frames):
        frame = np.full((height, width, 3), 25, dtype=np.uint8)
        if 2 <= frame_index <= 10:
            cv2.rectangle(frame, (38, 28), (122, 58), (245, 245, 245), 2)
            for offset in range(45, 116, 12):
                cv2.line(frame, (offset, 34), (offset, 52), (255, 255, 255), 3)
        writer.write(frame)
    writer.release()

    exact_frames = (4, 6, 8)
    independent_texts = ["\u51b2\u51b2", "\u4e2d\u5b89\u63a5", "\u51c0\u51b2\u51b2"]
    observations = [
        {
            "x": 23.75,
            "y": 31.1,
            "width": 52.5,
            "height": 33.3,
            "time": frame_index / fps,
            "frame_index": frame_index,
            "text": independent_texts[index],
            "confidence": 0.99,
            "scene_id": "scene:0",
            "source": "rapidocr_independent",
            "polygon": [[38, 28], [122, 28], [122, 58], [38, 58]],
        }
        for index, frame_index in enumerate(exact_frames)
    ]
    detector = SubtitleDetector(_DummyGUI())

    augmented = detector._augment_static_visual_tracks(
        str(video_path), observations, fps, total_frames, width, height
    )
    inferred_frames = {
        item["frame_index"]
        for item in augmented
        if str(item.get("source", "")).endswith("visual_inferred")
    }

    assert set(range(2, 11)) - set(exact_frames) <= inferred_frames
    assert not ({0, 1, 11} & inferred_frames)


def test_distant_same_box_independent_labels_form_separate_tracks(tmp_path):
    video_path = tmp_path / "distant_same_box.avi"
    width, height, fps, total_frames = 160, 90, 10.0, 24
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height)
    )
    assert writer.isOpened()
    for _frame_index in range(total_frames):
        frame = np.full((height, width, 3), 25, dtype=np.uint8)
        cv2.rectangle(frame, (45, 28), (115, 58), (240, 240, 240), 2)
        cv2.putText(frame, "TAG", (58, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        writer.write(frame)
    writer.release()

    observations = []
    for text, frames in (("热卖", (1, 2, 3)), ("如意", (20, 21, 22))):
        for frame_index in frames:
            observations.append(
                {
                    "x": 28.1,
                    "y": 31.1,
                    "width": 43.8,
                    "height": 33.3,
                    "time": frame_index / fps,
                    "frame_index": frame_index,
                    "text": text,
                    "confidence": 0.99,
                    "scene_id": "rapidocr:0",
                    "source": "rapidocr_independent",
                    "polygon": [[45, 28], [115, 28], [115, 58], [45, 58]],
                }
            )

    detector = SubtitleDetector(_DummyGUI())
    detector._augment_static_visual_tracks(
        str(video_path), observations, fps, total_frames, width, height
    )

    tracked_texts = [set(item["texts"]) for item in detector.visual_track_diagnostics]
    assert {"热卖"} in tracked_texts
    assert {"如意"} in tracked_texts
    assert {"热卖", "如意"} not in tracked_texts


def test_visual_edge_hysteresis_is_similarity_bounded():
    flags = [False, False, False, False, True, True, False, False]
    scores = [0.20, 0.54, 0.61, 0.66, 0.90, 0.88, 0.62, 0.40]

    extended = SubtitleDetector._extend_visual_match_edges(
        flags, scores, max_frames=3, threshold=0.55
    )

    assert extended == [False, False, True, True, True, True, True, False]


def test_visual_template_collection_never_uses_frame_seek(tmp_path, monkeypatch):
    video_path = tmp_path / "sequential_templates.avi"
    width, height, fps, total_frames = 120, 80, 10.0, 8
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height)
    )
    assert writer.isOpened()
    for frame_index in range(total_frames):
        frame = np.full((height, width, 3), 20, dtype=np.uint8)
        cv2.rectangle(frame, (35, 25), (90, 55), (180 + frame_index, 240, 240), 2)
        writer.write(frame)
    writer.release()

    real_capture = cv2.VideoCapture

    class NoSeekCapture:
        def __init__(self, path):
            self._capture = real_capture(path)

        def __getattr__(self, name):
            return getattr(self._capture, name)

        def set(self, *_args, **_kwargs):
            raise AssertionError("VFR-unsafe frame seek was used")

    monkeypatch.setattr(cv2, "VideoCapture", NoSeekCapture)
    observations = [
        {
            "x": 29.2,
            "y": 31.2,
            "width": 45.8,
            "height": 37.5,
            "time": frame_index / fps,
            "frame_index": frame_index,
            "text": "如意",
            "confidence": 0.99,
            "scene_id": "rapidocr:0",
            "source": "rapidocr_independent",
            "polygon": [[35, 25], [90, 25], [90, 55], [35, 55]],
        }
        for frame_index in (2, 4, 6)
    ]

    detector = SubtitleDetector(_DummyGUI())
    augmented = detector._augment_static_visual_tracks(
        str(video_path), observations, fps, total_frames, width, height
    )

    assert len(augmented) >= len(observations)


def test_sparse_small_label_is_not_absorbed_by_nearby_large_overlay(tmp_path):
    video_path = tmp_path / "separate_visual_tracks.avi"
    width, height, fps, total_frames = 200, 140, 10.0, 12
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height)
    )
    assert writer.isOpened()
    for _frame_index in range(total_frames):
        frame = np.full((height, width, 3), 20, dtype=np.uint8)
        cv2.rectangle(frame, (30, 25), (175, 65), (240, 240, 240), 2)
        cv2.putText(frame, "OVERLAY", (38, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.rectangle(frame, (135, 72), (180, 110), (235, 235, 235), 2)
        cv2.putText(frame, "MILK", (138, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
        writer.write(frame)
    writer.release()

    observations = []
    for frame_index in range(total_frames):
        observations.append(
            {
                "x": 15.0,
                "y": 17.9,
                "width": 72.5,
                "height": 28.6,
                "time": frame_index / fps,
                "frame_index": frame_index,
                "text": "打发过程不剪辑鲜活",
                "confidence": 0.99,
                "scene_id": "scene:0",
                "source": "rapidocr_independent",
                "polygon": [[30, 25], [175, 25], [175, 65], [30, 65]],
            }
        )
    for index, frame_index in enumerate((2, 6, 10)):
        observations.append(
            {
                "x": 67.5,
                "y": 51.4,
                "width": 22.5,
                "height": 27.1,
                "time": frame_index / fps,
                "frame_index": frame_index,
                "text": ("鲜活", "鲜奶", "鲜活")[index],
                "confidence": 0.99,
                "scene_id": "scene:0",
                "source": "rapidocr_independent",
                "polygon": [[135, 72], [180, 72], [180, 110], [135, 110]],
            }
        )

    detector = SubtitleDetector(_DummyGUI())
    augmented = detector._augment_static_visual_tracks(
        str(video_path), observations, fps, total_frames, width, height
    )
    small_label_frames = {
        item["frame_index"]
        for item in augmented
        if item.get("source") == "rapidocr_visual_inferred"
        and min(point[1] for point in item["polygon"]) >= 70
    }

    assert set(range(total_frames)) - {2, 6, 10} <= small_label_frames


def test_adjacent_independent_text_rows_keep_separate_visual_tracks(tmp_path):
    video_path = tmp_path / "adjacent_rows.avi"
    width, height, fps, total_frames = 180, 120, 10.0, 12
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height)
    )
    assert writer.isOpened()
    for _frame_index in range(total_frames):
        frame = np.full((height, width, 3), 18, dtype=np.uint8)
        cv2.rectangle(frame, (78, 28), (138, 52), (245, 245, 245), 2)
        cv2.rectangle(frame, (78, 58), (138, 82), (245, 245, 245), 2)
        cv2.putText(frame, "TOP", (84, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
        cv2.putText(frame, "MILK", (82, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1)
        writer.write(frame)
    writer.release()

    observations = []
    for frame_index in (2, 6, 10):
        for row_index, (text, top, bottom) in enumerate(
            (("鲜活", 28, 52), ("牛奶", 58, 82))
        ):
            observations.append(
                {
                    "x": 43.3,
                    "y": top * 100.0 / height,
                    "width": 33.3,
                    "height": (bottom - top) * 100.0 / height,
                    "time": frame_index / fps,
                    "frame_index": frame_index,
                    "text": text if frame_index != 6 else ("住活", "土奶")[row_index],
                    "confidence": 0.99,
                    "scene_id": "scene:0",
                    "source": "rapidocr_independent",
                    "polygon": [[78, top], [138, top], [138, bottom], [78, bottom]],
                }
            )

    detector = SubtitleDetector(_DummyGUI())
    augmented = detector._augment_static_visual_tracks(
        str(video_path), observations, fps, total_frames, width, height
    )
    inferred_upper = {
        item["frame_index"]
        for item in augmented
        if item.get("source") == "rapidocr_visual_inferred"
        and max(point[1] for point in item["polygon"]) <= 52
    }
    inferred_lower = {
        item["frame_index"]
        for item in augmented
        if item.get("source") == "rapidocr_visual_inferred"
        and min(point[1] for point in item["polygon"]) >= 58
    }
    expected = set(range(total_frames)) - {2, 6, 10}

    assert expected <= inferred_upper
    assert expected <= inferred_lower


def test_visual_track_never_crosses_a_hard_scene_cut(tmp_path):
    video_path = tmp_path / "visual_scene_cut.avi"
    width, height, fps, total_frames = 160, 90, 10.0, 12
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height)
    )
    assert writer.isOpened()
    for frame_index in range(total_frames):
        background = 10 if frame_index < 6 else 245
        frame = np.full((height, width, 3), background, dtype=np.uint8)
        cv2.rectangle(frame, (45, 28), (115, 58), (120, 120, 120), -1)
        cv2.putText(frame, "TEXT", (52, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        writer.write(frame)
    writer.release()

    observations = [
        {
            "x": 28.1,
            "y": 31.1,
            "width": 43.8,
            "height": 33.3,
            "time": frame_index / fps,
            "frame_index": frame_index,
            "text": "字幕",
            "confidence": 0.99,
            "scene_id": "rapidocr:0",
            "source": "rapidocr_independent",
            "polygon": [[45, 28], [115, 28], [115, 58], [45, 58]],
        }
        for frame_index in (2, 3, 4)
    ]

    detector = SubtitleDetector(_DummyGUI())
    augmented = detector._augment_static_visual_tracks(
        str(video_path), observations, fps, total_frames, width, height
    )
    inferred_frames = {
        item["frame_index"]
        for item in augmented
        if item.get("source") == "rapidocr_visual_inferred"
    }

    assert not (set(range(6, total_frames)) & inferred_frames)


def test_stable_compact_track_uses_observed_envelope_for_partial_glyph_boxes(tmp_path):
    boxes = ((78, 30, 120, 68), (95, 30, 138, 68), (80, 30, 136, 68))
    detector = SubtitleDetector(_DummyGUI())
    track = [
        {
            "box": list(box),
            "region": {"source": "rapidocr_independent"},
        }
        for box in boxes
    ]

    polygon = detector._stable_compact_track_envelope(track, 300, 300)
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]

    assert min(xs) <= 78
    assert max(xs) >= 138
    assert min(ys) <= 30
    assert max(ys) >= 68


def test_persistent_same_text_track_survives_one_second_ocr_dropout():
    detector = SubtitleDetector(_DummyGUI())
    regions = [
        _region(10, 1.0, 30, text="热卖中"),
        _region(10, 1.8, 54, text="热卖中"),
    ]

    merged = detector._gpu_aggregate_regions(regions, fps=30.0, total_duration=3.0)

    assert len(merged) == 1
    assert len(merged[0]["frame_regions"]) == 2
