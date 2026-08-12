from pathlib import Path

import numpy as np
from moviepy.editor import VideoClip

from processors.subtitle_processor import SubtitleProcessor


class _DummyGUI:
    pass


def _processor() -> SubtitleProcessor:
    return SubtitleProcessor(_DummyGUI())


def _polygon(x1, y1, x2, y2):
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def test_polygon_timeline_prefers_timestamp_over_capture_frame_index():
    timeline = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {
                        "time": 0.2,
                        "frame_index": 999,
                        "scene_id": 0,
                        "polygon": _polygon(10, 10, 40, 30),
                    }
                ]
            }
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    assert 2 in timeline
    assert 999 not in timeline


def test_polygon_timeline_interpolates_only_inside_same_scene():
    same_scene = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {"time": 0.1, "scene_id": 3, "polygon": _polygon(10, 10, 30, 30)},
                    {"time": 0.3, "scene_id": 3, "polygon": _polygon(30, 10, 50, 30)},
                ]
            }
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )
    assert same_scene[2][0][0][0] == 20

    cut_scene = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {"time": 0.1, "scene_id": 3, "polygon": _polygon(10, 10, 30, 30)},
                    {"time": 0.3, "scene_id": 4, "polygon": _polygon(30, 10, 50, 30)},
                ]
            }
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )
    assert 2 not in cut_scene


def test_polygon_timeline_matches_simultaneous_boxes_one_to_one():
    timeline = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {"time": 0.1, "scene_id": 3, "polygon": _polygon(10, 10, 30, 30)},
                    {"time": 0.1, "scene_id": 3, "polygon": _polygon(100, 10, 120, 30)},
                    {"time": 0.3, "scene_id": 3, "polygon": _polygon(30, 10, 50, 30)},
                    {"time": 0.3, "scene_id": 3, "polygon": _polygon(120, 10, 140, 30)},
                ]
            }
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    interpolated_x = sorted(polygon[0][0] for polygon in timeline[2])
    assert interpolated_x == [20, 110]


def test_polygon_timeline_fills_one_missing_label_when_slot_has_other_boxes():
    timeline = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {
                        "time": 0.1,
                        "scene_id": 3,
                        "text": "发生",
                        "polygon": _polygon(10, 10, 40, 30),
                    },
                    {
                        "time": 0.1,
                        "scene_id": 3,
                        "text": "福气",
                        "polygon": _polygon(100, 10, 130, 30),
                    },
                    {
                        "time": 0.2,
                        "scene_id": 3,
                        "text": "福气",
                        "polygon": _polygon(101, 10, 131, 30),
                    },
                    {
                        "time": 0.3,
                        "scene_id": 3,
                        "text": "发生",
                        "polygon": _polygon(12, 10, 42, 30),
                    },
                    {
                        "time": 0.3,
                        "scene_id": 3,
                        "text": "福气",
                        "polygon": _polygon(102, 10, 132, 30),
                    },
                ]
            }
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    middle_x = sorted(polygon[0][0] for polygon in timeline[2])
    assert 11 in middle_x
    assert 101 in middle_x
    assert min(middle_x) >= 10
    assert max(middle_x) <= 102


def test_polygon_timeline_reconnects_same_text_split_across_regions():
    timeline = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {
                        "time": 0.1,
                        "scene_id": 7,
                        "text": "发生",
                        "polygon": _polygon(40, 30, 90, 65),
                    }
                ]
            },
            {
                "frame_regions": [
                    {
                        "time": 0.2,
                        "scene_id": 7,
                        "text": "福气",
                        "polygon": _polygon(180, 30, 230, 65),
                    }
                ]
            },
            {
                "frame_regions": [
                    {
                        "time": 0.3,
                        "scene_id": 7,
                        "text": "发生",
                        "polygon": _polygon(44, 30, 94, 65),
                    }
                ]
            },
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    assert any(polygon[0][0] == 42 for polygon in timeline[2])


def test_one_frame_polygon_hold_requires_same_scene_presence():
    timeline = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {
                        "time": 0.1,
                        "scene_id": "scene-a",
                        "text": "发生",
                        "polygon": _polygon(10, 10, 40, 30),
                    },
                    {
                        "time": 0.2,
                        "scene_id": "scene-a",
                        "text": "福气",
                        "polygon": _polygon(100, 10, 130, 30),
                    },
                    {
                        "time": 0.3,
                        "scene_id": "scene-b",
                        "text": "新场景",
                        "polygon": _polygon(200, 10, 240, 30),
                    },
                ]
            }
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    assert any(polygon[0][0] == 10 for polygon in timeline[2])
    assert not any(polygon[0][0] == 10 for polygon in timeline[3])


def test_dense_independent_chinese_layout_expands_words_not_whole_panel():
    frame_regions = []
    for index, text in enumerate(("发生", "福气", "招财", "进宝", "平安", "好运")):
        x1 = 20 + (index % 3) * 70
        y1 = 20 + (index // 3) * 45
        frame_regions.append(
            {
                "time": 0.2,
                "scene_id": "panel-scene",
                "text": text,
                "source": "rapidocr_independent",
                "polygon": _polygon(x1, y1, x1 + 45, y1 + 28),
            }
        )

    timeline = _processor()._build_polygon_timeline(
        [{"frame_regions": frame_regions}],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    bounds = [
        (
            min(point[0] for point in polygon),
            min(point[1] for point in polygon),
            max(point[0] for point in polygon),
            max(point[1] for point in polygon),
        )
        for polygon in timeline[2]
    ]
    assert any(x1 <= 14 and y1 <= 12 and x2 >= 71 and y2 >= 56 for x1, y1, x2, y2 in bounds)
    assert not any((x2 - x1) > 110 for x1, _y1, x2, _y2 in bounds)


def test_sparse_independent_labels_do_not_create_panel_envelope():
    frame_regions = [
        {
            "time": 0.2,
            "scene_id": "sparse-scene",
            "text": text,
            "source": "rapidocr_independent",
            "polygon": _polygon(20 + index * 50, 20, 50 + index * 50, 45),
        }
        for index, text in enumerate(("发生", "福气", "招财", "进宝", "平安"))
    ]

    timeline = _processor()._build_polygon_timeline(
        [{"frame_regions": frame_regions}],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    assert len(timeline[2]) == 5


def test_polygon_timeline_fills_longer_same_text_ocr_dropout_only():
    same_text = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {
                        "time": 0.1,
                        "scene_id": 3,
                        "text": "热卖中",
                        "polygon": _polygon(10, 10, 30, 30),
                    },
                    {
                        "time": 0.8,
                        "scene_id": 3,
                        "text": "热卖中",
                        "polygon": _polygon(10, 10, 30, 30),
                    },
                ]
            }
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )
    changed_text = _processor()._build_polygon_timeline(
        [
            {
                "frame_regions": [
                    {
                        "time": 0.1,
                        "scene_id": 3,
                        "text": "字幕甲",
                        "polygon": _polygon(10, 10, 30, 30),
                    },
                    {
                        "time": 0.8,
                        "scene_id": 3,
                        "text": "字幕乙",
                        "polygon": _polygon(10, 10, 30, 30),
                    },
                ]
            }
        ],
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    assert all(slot in same_text for slot in range(1, 9))
    assert 5 not in changed_text


def test_static_simultaneous_labels_keep_independent_event_bounds():
    long_track = [
        {
            "time": slot / 10.0,
            "scene_id": 1,
            "text": "主字幕",
            "polygon": _polygon(20, 20, 80, 45),
        }
        for slot in range(2, 9)
    ]
    short_badge = [
        {
            "time": slot / 10.0,
            "scene_id": 1,
            "text": "热卖中",
            "polygon": _polygon(220, 130, 290, 165),
        }
        for slot in range(4, 7)
    ]
    positions = [
        {"frame_regions": long_track},
        {"frame_regions": short_badge},
    ]

    bounds = _processor()._linked_stable_overlay_bounds(
        positions, fps=10.0, frame_w=320, frame_h=180
    )
    timeline = _processor()._build_polygon_timeline(
        positions,
        fps=10.0,
        frame_w=320,
        frame_h=180,
        video_duration=1.0,
    )

    assert bounds == {}
    assert not any(polygon[0][0] == 220 for polygon in timeline[2])
    assert not any(polygon[0][0] == 220 for polygon in timeline[8])
    assert any(polygon[0][0] == 220 for polygon in timeline[4])


def test_time_boxes_do_not_form_cross_time_row_envelope():
    boxes = _processor()._build_time_aware_blur_boxes(
        [
            {"x": 10, "y": 75, "width": 10, "height": 6, "start_time": 1.0, "end_time": 1.2},
            {"x": 70, "y": 75, "width": 10, "height": 6, "start_time": 2.0, "end_time": 2.2},
        ],
        w=1080,
        h=1920,
        video_duration=4.0,
    )

    assert len(boxes) == 2
    assert all(entry["box"][2] - entry["box"][0] < 300 for entry in boxes)


def test_polygon_and_separate_box_are_blurred_in_same_frame_without_gap_fill():
    yy, xx = np.indices((180, 320))
    pattern = (((xx + yy) % 2) * 255).astype(np.uint8)
    frame = np.dstack([pattern, pattern, pattern])
    clip = VideoClip(lambda _t: frame.copy(), duration=0.5)
    clip.fps = 10

    positions = [
        {
            "x": 6.0,
            "y": 11.0,
            "width": 13.0,
            "height": 14.0,
            "start_time": 0.2,
            "end_time": 0.2,
            "frame_regions": [
                {"time": 0.2, "scene_id": 0, "polygon": _polygon(20, 20, 60, 45)}
            ],
        },
        {
            "x": 70.0,
            "y": 65.0,
            "width": 15.0,
            "height": 12.0,
            "start_time": 0.15,
            "end_time": 0.25,
        },
    ]

    output = _processor().apply_opencv_blur_enhanced_v2(
        clip, positions, w=320, h=180
    )
    changed = np.abs(output.get_frame(0.2).astype(np.int16) - frame.astype(np.int16))

    assert changed[25:40, 25:55].mean() > 20
    assert changed[120:145, 230:270].mean() > 20
    assert changed[75:100, 120:180].max() == 0


def test_lower_third_fragment_gets_bounded_horizontal_row_padding():
    yy, xx = np.indices((180, 320))
    pattern = (((xx + yy) % 2) * 255).astype(np.uint8)
    frame = np.dstack([pattern, pattern, pattern])
    clip = VideoClip(lambda _t: frame.copy(), duration=0.3)
    clip.fps = 10
    positions = [
        {
            "frame_regions": [
                {
                    "time": 0.1,
                    "scene_id": 0,
                    "text": "祁和",
                    "polygon": _polygon(150, 145, 200, 165),
                }
            ]
        }
    ]

    output = _processor().apply_opencv_blur_enhanced_v2(
        clip, positions, w=320, h=180
    )
    changed = np.abs(output.get_frame(0.1).astype(np.int16) - frame.astype(np.int16))

    assert changed[150:160, 138:148].mean() > 10
    assert changed[150:160, 80:100].max() == 0


def test_production_render_paths_blur_before_spatial_transforms():
    root = Path(__file__).resolve().parents[2]
    batch_source = (root / "core/video/batch/processor.py").read_text(encoding="utf-8")
    ordinary_source = (root / "core/video/CreateFinalVideo.py").read_text(encoding="utf-8")

    batch_start = batch_source.index("def _create_final_video_for_batch")
    batch_section = batch_source[batch_start:]
    blur_index = batch_section.index("app.apply_chinese_subtitle_removal(video)")
    assert blur_index < batch_section.index("video.crop(")
    assert blur_index < batch_section.index("video.resize(")
    assert blur_index < batch_section.index("video.fx(vfx.mirror_x)")

    ordinary_blur = ordinary_source.index("app.apply_chinese_subtitle_removal(video)")
    ordinary_mirror = ordinary_source.index("video.fx(vfx.mirror_x)")
    assert ordinary_blur < ordinary_mirror


def test_processor_preserves_cached_region_review_diagnostics():
    class Detector:
        review_required = False
        invalid_coordinate_count = 0

        def _filter_chinese_regions(self, positions):
            return list(positions)

    class GUI:
        apply_blur = True
        subtitle_review_required = False
        invalid_coordinate_count = 0
        _cached_subtitle_detector = Detector()
        analysis_result = {
            "subtitle_positions": [
                {
                    "x": 10,
                    "y": 10,
                    "width": 20,
                    "height": 10,
                    "start_time": 0,
                    "end_time": 0.2,
                    "language": "chinese",
                    "sample_text": "字幕",
                    "review_required": True,
                    "invalid_coordinate_count": 3,
                }
            ]
        }

        def update_progress_state(self, *_args):
            pass

        def update_step_progress(self, *_args):
            pass

        def add_log(self, *_args):
            pass

    frame = np.zeros((180, 320, 3), dtype=np.uint8)
    clip = VideoClip(lambda _t: frame.copy(), duration=0.3)
    clip.fps = 10
    gui = GUI()

    SubtitleProcessor(gui).apply_chinese_subtitle_removal(clip)

    assert gui.latest_blur_metadata["review_required"] is True
    assert gui.latest_blur_metadata["invalid_coordinate_count"] == 3
