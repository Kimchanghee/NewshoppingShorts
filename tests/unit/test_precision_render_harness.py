import json

import cv2
import numpy as np

from scripts import render_precision_ocr_validation as harness
from core.video.batch.analysis import _collect_subtitle_diagnostics


class _OneFrameCapture:
    def __init__(self):
        self.read_count = 0

    def isOpened(self):
        return True

    def get(self, property_id):
        if property_id == cv2.CAP_PROP_FPS:
            return 30.0
        if property_id == cv2.CAP_PROP_POS_MSEC:
            return 0.0
        return 0.0

    def read(self):
        if self.read_count:
            return False, None
        self.read_count += 1
        return True, np.zeros((2, 2, 3), dtype=np.uint8)

    def release(self):
        pass


def test_frame_zero_timestamp_is_valid_and_monotonic(monkeypatch):
    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _OneFrameCapture())

    inventory = harness._frame_inventory("unused.mp4")

    assert inventory["ok"] is True
    assert inventory["first_timestamp"] == 0.0
    assert inventory["timestamps_monotonic"] is True
    assert inventory["decoder_timestamps_monotonic"] is True


def test_resume_reuses_only_hash_verified_completed_outputs(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    final = tmp_path / "final.mp4"
    source.write_bytes(b"source")
    final.write_bytes(b"final")
    manifest = {
        "results": [
            {
                "index": 1,
                "source_video": str(source),
                "source_sha256": "verified-hash",
                "final_video": str(final),
                "final_sha256": "verified-hash",
                "code_fingerprint": "current-code",
                "qa_ok": True,
                "independent_residual_ocr": {"ok": True, "scanned_frames": 1},
            },
            {
                "index": 2,
                "source_video": str(source),
                "source_sha256": "verified-hash",
                "final_video": str(tmp_path / "missing.mp4"),
                "final_sha256": "missing",
                "code_fingerprint": "current-code",
                "qa_ok": True,
                "independent_residual_ocr": {"ok": True, "scanned_frames": 1},
            },
        ]
    }
    (tmp_path / "precision_ocr_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    monkeypatch.setattr(harness, "_sha256", lambda _path: "verified-hash")
    monkeypatch.setattr(harness, "_implementation_fingerprint", lambda: "current-code")
    monkeypatch.setattr(
        harness,
        "_frame_inventory",
        lambda _path: {
            "ok": True,
            "timestamps_monotonic": True,
            "decoder_timestamps_monotonic": True,
            "frame_count": 1,
        },
    )

    resumed = harness._load_verified_resume_results(tmp_path)

    assert [item["index"] for item in resumed] == [1]


def test_analysis_diagnostics_include_region_and_cached_detector_failures():
    detector = type(
        "Detector",
        (),
        {
            "review_required": True,
            "invalid_coordinate_count": 2,
            "review_reasons": ["request_failed"],
        },
    )()
    app = type(
        "App",
        (),
        {
            "_cached_subtitle_detector": detector,
            "subtitle_review_required": False,
            "invalid_coordinate_count": 0,
            "ocr_review_reasons": [],
        },
    )()

    result = _collect_subtitle_diagnostics(
        app,
        [{"review_required": True, "invalid_coordinate_count": 3}],
    )

    assert result["subtitle_review_required"] is True
    assert result["invalid_coordinate_count"] == 3
    assert "request_failed" in result["ocr_review_reasons"]


def test_runtime_blur_coverage_requires_every_expected_slot_to_change():
    app = type(
        "App",
        (),
        {
            "_precision_blur_expected_slots": {1, 2, 3},
            "_precision_blur_seen_slots": {0, 1, 2, 3},
            "_precision_blur_active_slots": {1, 2, 3},
            "_precision_blur_slot_deltas": {1: 2.0, 2: 3.0, 3: 1.0},
        },
    )()

    assert harness._collect_runtime_blur_coverage(app)["ok"] is True
    app._precision_blur_slot_deltas[2] = 0.0
    assert harness._collect_runtime_blur_coverage(app)["ok"] is False


def test_page_scale_warning_is_adjudicated_only_by_two_clean_final_audits():
    result = harness._adjudicate_detector_review(
        {
            "review_required": True,
            "review_reasons": ["oversized_ocr_bbox_without_precise_anchor"],
            "invalid_coordinate_count": 0,
        },
        {"ok": True},
        {
            "ok": True,
            "residual_detection_count": 0,
            "request_failure_count": 0,
            "invalid_coordinate_count": 0,
            "undecoded_target_count": 0,
        },
        {
            "ok": True,
            "full_frame_scan": True,
            "scanned_frames": 120,
            "expected_frames": 120,
            "residual_detection_count": 0,
            "error_count": 0,
        },
    )

    assert result["ok"] is True


def test_source_request_failure_is_adjudicated_only_after_clean_final_media():
    result = harness._adjudicate_detector_review(
        {
            "review_required": True,
            "review_reasons": ["ocr_reader_request_failures"],
            "invalid_coordinate_count": 0,
        },
        {"ok": True},
        {
            "ok": True,
            "residual_detection_count": 0,
            "request_failure_count": 0,
            "invalid_coordinate_count": 0,
            "undecoded_target_count": 0,
        },
        {
            "ok": True,
            "full_frame_scan": True,
            "scanned_frames": 120,
            "expected_frames": 120,
            "residual_detection_count": 0,
            "error_count": 0,
        },
    )

    assert result["ok"] is True


def test_review_adjudication_never_clears_ambiguous_or_incomplete_evidence():
    clean_glm = {
        "ok": True,
        "residual_detection_count": 0,
        "request_failure_count": 0,
        "invalid_coordinate_count": 0,
        "undecoded_target_count": 0,
    }
    clean_independent = {
        "ok": True,
        "full_frame_scan": True,
        "scanned_frames": 119,
        "expected_frames": 120,
        "residual_detection_count": 0,
        "error_count": 0,
    }

    ambiguous = harness._adjudicate_detector_review(
        {
            "review_required": True,
            "review_reasons": ["oversized_ocr_bbox_ambiguous_anchor"],
            "invalid_coordinate_count": 0,
        },
        {"ok": True},
        clean_glm,
        {**clean_independent, "scanned_frames": 120},
    )
    incomplete = harness._adjudicate_detector_review(
        {
            "review_required": True,
            "review_reasons": ["oversized_ocr_bbox_without_precise_anchor"],
            "invalid_coordinate_count": 0,
        },
        {"ok": True},
        clean_glm,
        clean_independent,
    )

    assert ambiguous["ok"] is False
    assert incomplete["ok"] is False


class _AuditCapture:
    def __init__(self):
        self.index = 0

    def isOpened(self):
        return True

    def get(self, property_id):
        if property_id == cv2.CAP_PROP_FPS:
            return 10.0
        if property_id == cv2.CAP_PROP_FRAME_COUNT:
            return 4
        return 0.0

    def read(self):
        if self.index >= 4:
            return False, None
        self.index += 1
        return True, np.zeros((20, 20, 3), dtype=np.uint8)

    def release(self):
        pass


def test_post_render_ocr_audit_rejects_readable_chinese(monkeypatch):
    class Reader:
        _glm_client = type(
            "Client", (), {"request_failure_count": 0, "invalid_coordinate_count": 0}
        )()

        def readtext_batch(self, frames):
            return [[([[0, 0]], "残留字幕", 0.9)] for _ in frames]

    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _AuditCapture())

    result = harness._post_render_residual_ocr_audit("unused.mp4", [], Reader())

    assert result["ok"] is False
    assert result["residual_detection_count"] == 1


def test_glm_audit_preserves_private_polygon_for_bounded_repair(monkeypatch):
    polygon = [[2, 3], [12, 3], [12, 13], [2, 13]]

    class Reader:
        _glm_client = type(
            "Client", (), {"request_failure_count": 0, "invalid_coordinate_count": 0}
        )()

        def readtext_batch(self, frames):
            return [[(polygon, "型号", 0.9)] for _ in frames]

    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _AuditCapture())

    result = harness._post_render_residual_ocr_audit("unused.mp4", [], Reader())

    assert result["residuals"][0]["polygon"] == polygon


def test_residual_repair_tracks_stay_spatially_separate():
    residuals = [
        {"time": 1.0, "polygon": [[10, 10], [30, 10], [30, 20], [10, 20]]},
        {"time": 1.5, "polygon": [[20, 12], [40, 12], [40, 22], [20, 22]]},
        {"time": 1.5, "polygon": [[250, 120], [280, 120], [280, 140], [250, 140]]},
    ]

    positions = harness._build_residual_repair_positions(
        residuals, fps=10.0, frame_width=320, frame_height=180
    )

    assert len(positions) == 2
    assert sorted(len(item["frame_regions"]) for item in positions) == [1, 2]


def test_glm_audit_ignores_only_recorded_korean_overlay(monkeypatch):
    class Reader:
        _glm_client = type(
            "Client", (), {"request_failure_count": 0, "invalid_coordinate_count": 0}
        )()

        def readtext_batch(self, frames):
            return [
                [([[0, 0], [20, 0], [20, 20], [0, 20]], "買", 0.99)]
                for _ in frames
            ]

    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _AuditCapture())
    overlays = [{"start_time": 0.0, "end_time": 1.0, "box": [0, 0, 20, 20]}]

    result = harness._post_render_residual_ocr_audit(
        "unused.mp4", [], Reader(), overlay_records=overlays
    )

    assert result["ok"] is True
    assert result["residual_detection_count"] == 0
    assert result["ignored_known_overlay_count"] == 1


def test_independent_full_frame_audit_rejects_first_readable_chinese(monkeypatch):
    class IndependentEngine:
        def __init__(self):
            self.calls = 0

        def __call__(self, _frame):
            self.calls += 1
            if self.calls == 3:
                return (
                    [
                        (
                            [[0, 0], [10, 0], [10, 10], [0, 10]],
                            "\u70ed\u5356\u4e2d",
                            0.98,
                        )
                    ],
                    None,
                )
            return ([], None)

    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _AuditCapture())

    result = harness._post_render_independent_full_frame_audit(
        "unused.mp4", engine=IndependentEngine()
    )

    assert result["ok"] is False
    assert result["full_frame_scan"] is True
    assert result["scanned_frames"] == 4
    assert result["residual_detection_count"] == 1


def test_independent_audit_ignores_low_confidence_single_glyph_noise(monkeypatch):
    class IndependentEngine:
        def __call__(self, _frame):
            return (
                [
                    (
                        [[0, 0], [10, 0], [10, 10], [0, 10]],
                        "\u798f",
                        0.59,
                    )
                ],
                None,
            )

    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _AuditCapture())

    result = harness._post_render_independent_full_frame_audit(
        "unused.mp4", engine=IndependentEngine()
    )

    assert result["ok"] is True
    assert result["scanned_frames"] == 4
    assert result["residual_detection_count"] == 0


def test_independent_audit_rejects_corroborated_adjacent_residual(monkeypatch):
    class IndependentEngine:
        def __init__(self):
            self.calls = 0

        def __call__(self, _frame):
            self.calls += 1
            if self.calls in {2, 3}:
                return (
                    [
                        (
                            [[2, 2], [12, 2], [12, 12], [2, 12]],
                            "\u51b2\u51b2",
                            0.70,
                        )
                    ],
                    None,
                )
            return ([], None)

    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _AuditCapture())

    result = harness._post_render_independent_full_frame_audit(
        "unused.mp4", engine=IndependentEngine()
    )

    assert result["ok"] is False
    assert result["scanned_frames"] == 4
    assert result["residual_detection_count"] == 2


def test_independent_audit_ignores_only_recorded_korean_overlay(monkeypatch):
    class IndependentEngine:
        def __call__(self, _frame):
            return (
                [
                    (
                        [[2, 2], [12, 2], [12, 12], [2, 12]],
                        "\u54c1\u53f7",
                        0.98,
                    )
                ],
                None,
            )

    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _AuditCapture())
    overlays = [{"start_time": 0.0, "end_time": 1.0, "box": [2, 2, 12, 12]}]

    result = harness._post_render_independent_full_frame_audit(
        "unused.mp4", engine=IndependentEngine(), overlay_records=overlays
    )

    assert result["ok"] is True
    assert result["residual_detection_count"] == 0
    assert result["ignored_known_overlay_count"] == 4


def test_sanitized_summary_omits_urls_paths_and_tts_metadata(tmp_path):
    path = harness._write_sanitized_qa_summary(
        [
            {
                "index": 1,
                "slug": "case",
                "affiliate_url": "https://secret.example",
                "source_video": "C:/private/source.mp4",
                "render_integrity": {"tts": {"file_path": "C:/private/voice.wav"}},
                "final_sha256": "abc",
                "final_inventory": {"frame_count": 10},
                "video_probe": {"width": 1080, "height": 1920, "has_audio": True},
                "blur": {"regions": 2},
                "blur_coverage": {"coverage_ratio": 1.0},
                "residual_ocr": {"sampled_frames": 3, "residual_detection_count": 0},
                "qa_ok": True,
            }
        ],
        tmp_path,
    )

    text = path.read_text(encoding="utf-8")
    assert "https://" not in text
    assert "C:/" not in text
    assert "tts" not in text.lower()


def test_sourcing_summary_rejects_video_paths_outside_its_directory(tmp_path):
    outside = tmp_path.parent / "outside.mp4"
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "ok": True,
                        "media": {"decode_ok": True},
                        "video_path": str(outside),
                    }
                ]
                * 5
            }
        ),
        encoding="utf-8",
    )

    try:
        harness._load_cases(summary)
    except ValueError as exc:
        assert "got 0" in str(exc)
    else:
        raise AssertionError("out-of-root source path was accepted")
