from scripts.independent_rapidocr_corner_scan import (
    _map_side_strip_detections,
    _map_top_corner_detections,
)


def test_right_montage_polygon_maps_back_to_top_right_source_corner():
    detections = [
        [
            [[1875, 0], [2159, 82], [2100, 284], [1797, 170]],
            "种草",
            0.99,
        ]
    ]

    mapped = _map_top_corner_detections(
        detections,
        frame_width=1080,
        frame_height=1920,
        crop_width=360,
        crop_height=220,
        scale=3.0,
    )

    assert len(mapped) == 1
    xs = [point[0] for point in mapped[0]["polygon"]]
    ys = [point[1] for point in mapped[0]["polygon"]]
    assert min(xs) >= 959.0
    assert max(xs) == 1079.0
    assert min(ys) == 0.0
    assert max(ys) < 100.0


def test_synthetic_montage_seam_detection_is_rejected():
    detections = [
        [[[1000, 30], [1160, 30], [1160, 100], [1000, 100]], "中文", 0.99]
    ]

    assert _map_top_corner_detections(
        detections,
        frame_width=1080,
        frame_height=1920,
        crop_width=360,
        crop_height=220,
        scale=3.0,
    ) == []


def test_left_side_strip_polygon_preserves_full_height_source_coordinates():
    detections = [
        [
            [[118, 2180], [373, 2173], [373, 2212], [120, 2218]],
            "中国美讯",
            0.74,
        ]
    ]

    mapped = _map_side_strip_detections(
        detections,
        frame_width=1080,
        frame_height=1920,
        crop_width=300,
        scale=1.5,
    )

    assert len(mapped) == 1
    xs = [point[0] for point in mapped[0]["polygon"]]
    ys = [point[1] for point in mapped[0]["polygon"]]
    assert min(xs) < 80.0
    assert max(xs) < 250.0
    assert 1440.0 < min(ys) < 1470.0
    assert max(ys) < 1480.0
