from scripts import independent_rapidocr_audit


def test_audit_configures_utf8_stdout(monkeypatch):
    calls = []

    class _Stdout:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(independent_rapidocr_audit.sys, "stdout", _Stdout())

    independent_rapidocr_audit._configure_utf8_stdout()

    assert calls == [{"encoding": "utf-8", "errors": "replace"}]


def _candidate(frame, text, confidence, chinese_count, box=(10, 10, 30, 30)):
    return {
        "frame_index": frame,
        "text": text,
        "confidence": confidence,
        "chinese_count": chinese_count,
        "box": list(box),
    }


def test_repeated_medium_confidence_single_glyph_is_not_a_residual():
    candidates = [
        _candidate(frame, "人", 0.86, 1) for frame in (10, 11, 12)
    ]

    assert independent_rapidocr_audit._confirmed_residuals(candidates) == []


def test_high_confidence_single_glyph_remains_fail_closed():
    candidate = _candidate(10, "鲜", 0.987, 1)

    assert independent_rapidocr_audit._confirmed_residuals([candidate]) == [candidate]


def test_oversized_isolated_single_glyph_geometry_is_rejected_as_noise():
    candidate = _candidate(10, "二", 0.957, 1, box=(3, 345, 120, 518))
    candidate.update({"frame_width": 720, "frame_height": 1280})

    assert independent_rapidocr_audit._confirmed_residuals([candidate]) == []


def test_corroborated_multi_character_text_remains_a_residual():
    candidates = [
        _candidate(10, "鲜活", 0.62, 2, box=(10, 10, 50, 30)),
        _candidate(11, "鲜活", 0.64, 2, box=(10, 10, 50, 30)),
    ]

    assert independent_rapidocr_audit._confirmed_residuals(candidates) == candidates


def test_square_outlet_slot_hallucination_is_not_a_residual():
    candidates = [
        _candidate(frame, "三二", 0.78, 2, box=(10, 10, 120, 90))
        for frame in (10, 11, 12)
    ]

    assert independent_rapidocr_audit._confirmed_residuals(candidates) == []


def test_only_exact_active_generated_overlay_is_ignored():
    overlays = [{"start_time": 1.0, "end_time": 2.0, "box": [100, 200, 400, 280]}]

    assert independent_rapidocr_audit._covered_by_known_overlay(
        [100, 200, 400, 280], 15, 10.0, overlays
    )
    assert not independent_rapidocr_audit._covered_by_known_overlay(
        [90, 200, 400, 280], 15, 10.0, overlays
    )
    assert not independent_rapidocr_audit._covered_by_known_overlay(
        [100, 200, 400, 280], 25, 10.0, overlays
    )
