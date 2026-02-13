from processors.subtitle_detector import SubtitleDetector
from processors.subtitle_processor import SubtitleProcessor


class _DummyGUI:
    def __init__(self):
        self.ocr_reader = None

    def add_log(self, _msg):
        pass


def _right_edge(region):
    return float(region["x"]) + float(region["width"])


def test_detector_aggregate_uses_union_envelope_for_cluster():
    detector = SubtitleDetector(_DummyGUI())

    # Same subtitle line, overlapping boxes in the same time group.
    # The merged region should preserve the full union range.
    regions = [
        {"x": 10.0, "y": 78.0, "width": 40.0, "height": 8.0, "time": 1.0, "text": "字幕A"},
        {"x": 20.0, "y": 78.0, "width": 40.0, "height": 8.0, "time": 1.1, "text": "字幕B"},
    ]

    merged = detector._gpu_aggregate_regions(regions)
    assert merged

    # Union right edge from inputs is 60. New logic should not shrink below that.
    assert max(_right_edge(r) for r in merged) >= 60.0


def test_detector_aggregate_merges_adjacent_same_row_regions():
    detector = SubtitleDetector(_DummyGUI())

    # Two neighboring boxes in the same row/time should become one blur target.
    regions = [
        {"x": 12.0, "y": 80.0, "width": 18.0, "height": 7.0, "time": 2.0, "text": "前半"},
        {"x": 33.0, "y": 80.5, "width": 18.0, "height": 7.0, "time": 2.1, "text": "后半"},
    ]

    merged = detector._gpu_aggregate_regions(regions)
    assert merged
    assert len(merged) == 1
    assert _right_edge(merged[0]) >= 50.0


def test_processor_merge_spatial_boxes_fills_middle_gap():
    processor = SubtitleProcessor(_DummyGUI())

    boxes = [
        [120, 810, 320, 900],
        [340, 812, 520, 898],  # small gap; should merge
    ]
    merged = processor._merge_spatial_boxes(boxes, frame_width=1080)

    assert len(merged) == 1
    assert merged[0][0] == 120
    assert merged[0][2] == 520


def test_processor_time_aware_boxes_merge_over_time():
    processor = SubtitleProcessor(_DummyGUI())

    positions = [
        {"x": 20.0, "y": 80.0, "width": 14.0, "height": 6.0, "start_time": 1.0, "end_time": 1.8},
        {"x": 44.0, "y": 80.0, "width": 15.0, "height": 6.0, "start_time": 2.0, "end_time": 2.8},
    ]

    boxes = processor._build_time_aware_blur_boxes(
        subtitle_positions=positions,
        w=1080,
        h=1920,
        video_duration=8.0,
    )

    assert boxes
    assert len(boxes) == 1
    x1, _, x2, _ = boxes[0]["box"]
    assert x2 - x1 > 300
