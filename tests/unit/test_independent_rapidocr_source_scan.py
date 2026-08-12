from __future__ import annotations

import numpy as np
import json

from scripts.independent_rapidocr_source_scan import (
    _is_scene_cut,
    _merge_frame_detections,
    _normalized_detections,
)
from scripts import independent_rapidocr_source_scan as source_scan


def _detection(text, confidence, box):
    x1, y1, x2, y2 = box
    return [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]], text, confidence]


def test_upscaled_detection_maps_back_to_source_coordinates():
    result = _normalized_detections(
        [_detection("鲜牛奶", 0.99, [900, 600, 1050, 750])], scale=1.5
    )

    assert result[0]["polygon"] == [
        [600.0, 400.0],
        [700.0, 400.0],
        [700.0, 500.0],
        [600.0, 500.0],
    ]


def test_multiscale_merge_keeps_separate_rows_and_deduplicates_overlap():
    primary = _normalized_detections(
        [_detection("鲜活", 0.98, [600, 320, 700, 400])]
    )
    scaled = _normalized_detections(
        [
            _detection("鲜活", 0.99, [900, 480, 1050, 600]),
            _detection("牛奶", 0.99, [900, 615, 1050, 735]),
        ],
        scale=1.5,
    )

    merged = _merge_frame_detections(primary, scaled)

    assert [item["text"] for item in merged] == ["鲜活", "牛奶"]


def test_scene_cut_detector_rejects_identical_frames_and_accepts_hard_cut():
    black = np.zeros((128, 72, 3), dtype=np.uint8)
    white = np.full((128, 72, 3), 255, dtype=np.uint8)

    assert _is_scene_cut(black, black.copy()) is False
    assert _is_scene_cut(black, white) is True


def test_verified_source_scan_cache_round_trip(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    result = tmp_path / "result.json"
    restored = tmp_path / "restored.json"
    payload = {"ok": True, "scanned_frames": 3, "expected_frames": 3, "regions": []}
    result.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(source_scan, "_source_cache_path", lambda _video: cache)

    source_scan._store_cached_scan("unused.mp4", str(result), payload)

    assert source_scan._restore_cached_scan("unused.mp4", str(restored)) is True
    assert json.loads(restored.read_text(encoding="utf-8")) == payload


def test_incomplete_source_scan_cache_is_rejected(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps({"ok": True, "scanned_frames": 2, "expected_frames": 3}),
        encoding="utf-8",
    )
    monkeypatch.setattr(source_scan, "_source_cache_path", lambda _video: cache)

    assert source_scan._restore_cached_scan("unused.mp4", str(tmp_path / "out.json")) is False
