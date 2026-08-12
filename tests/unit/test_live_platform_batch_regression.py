import pytest

from scripts.live_platform_batch_regression import (
    _meets_relevance_threshold,
    _required_relevance_score,
    _safe_case_slug,
)


def test_live_batch_enforces_requested_relevance_threshold():
    assert _meets_relevance_threshold(1.0, 0.950001)
    assert not _meets_relevance_threshold(0.95, 0.950001)
    assert not _meets_relevance_threshold(0.75, 0.950001)
    assert not _meets_relevance_threshold(None, 0.950001)


@pytest.mark.parametrize(
    "score", [float("nan"), float("inf"), -float("inf"), -0.01, 1.01]
)
def test_live_batch_rejects_invalid_candidate_score(score):
    assert not _meets_relevance_threshold(score, 0.950001)


@pytest.mark.parametrize("required", ["bad", float("nan"), float("inf"), 0.69, 1.01])
def test_live_batch_rejects_invalid_strict_threshold(required):
    with pytest.raises(ValueError, match="required relevance score"):
        _required_relevance_score(required)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("electric_whisk", "electric_whisk"),
        ("../../../../Windows/Temp/pwn", "Windows_Temp_pwn"),
        ("x/../../outside", "x_outside"),
        ("..", "product"),
    ],
)
def test_live_batch_slug_cannot_escape_case_output(raw, expected):
    safe = _safe_case_slug(raw)
    assert safe == expected
    assert "/" not in safe
    assert "\\" not in safe
    assert ".." not in safe
