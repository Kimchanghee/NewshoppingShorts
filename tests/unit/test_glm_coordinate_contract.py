"""Coordinate-contract regression tests for the GLM OCR client."""

import base64
import time

import cv2
import numpy as np
import pytest

from utils.glm_ocr_client import GLMOCRClient


def _response(*boxes):
    return {
        "layout_details": [
            {
                "label": "text",
                "content": f"text-{index}",
                "bbox_2d": box,
            }
            for index, box in enumerate(boxes)
        ]
    }


def test_normalized_bbox_maps_to_original_image_pixels():
    client = GLMOCRClient(api_key="test-key")

    results = client._parse_response(
        _response([0.1, 0.7, 0.9, 0.8]),
        source_size=(1080, 1920),
    )

    assert results == [
        (
            [
                [108.0, 1344.0],
                [972.0, 1344.0],
                [972.0, 1536.0],
                [108.0, 1536.0],
            ],
            "text-0",
            0.9,
        )
    ]
    assert isinstance(results[0], tuple)
    assert client.invalid_coordinate_count == 0


def test_missing_source_size_fails_closed():
    client = GLMOCRClient(api_key="test-key")

    assert client._parse_response(_response([0.1, 0.2, 0.4, 0.3])) == []
    assert client.invalid_coordinate_count == 1


def test_live_pixel_bbox_is_kept_in_original_source_space():
    client = GLMOCRClient(api_key="test-key")

    results = client._parse_response(
        _response([23, 221, 270, 256]),
        source_size=(720, 1280),
        response_size=(720, 1280),
    )

    assert results[0][0] == [
        [23.0, 221.0],
        [270.0, 221.0],
        [270.0, 256.0],
        [23.0, 256.0],
    ]
    assert client.invalid_coordinate_count == 0


def test_uploaded_pixel_bbox_scales_back_to_pre_resize_source():
    client = GLMOCRClient(api_key="test-key")

    results = client._parse_response(
        _response([100, 100, 900, 400]),
        source_size=(2000, 1000),
        response_size=(1000, 500),
    )

    assert results[0][0] == [
        [200.0, 200.0],
        [1800.0, 200.0],
        [1800.0, 800.0],
        [200.0, 800.0],
    ]


def test_recognize_single_keeps_original_coordinates_after_internal_resize(monkeypatch):
    client = GLMOCRClient(api_key="test-key")
    original = np.zeros((1920, 2160, 3), dtype=np.uint8)
    observed = {}

    monkeypatch.setattr(client, "is_available", lambda: True)

    def fake_call_api(payload):
        encoded = payload["file"].split(",", 1)[1]
        compressed = cv2.imdecode(
            np.frombuffer(base64.b64decode(encoded), dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        observed["compressed_size"] = (compressed.shape[1], compressed.shape[0])
        return _response([0.1, 0.25, 0.9, 0.75])

    monkeypatch.setattr(client, "_call_api", fake_call_api)

    results = client.recognize_single(original)

    assert observed["compressed_size"] == (1280, 1137)
    assert results[0][0] == [
        [216.0, 480.0],
        [1944.0, 480.0],
        [1944.0, 1440.0],
        [216.0, 1440.0],
    ]


@pytest.mark.parametrize(
    "invalid_box",
    [
        None,
        [0.1, 0.2, 0.3],
        [float("nan"), 0.2, 0.8, 0.9],
        [0.1, float("inf"), 0.8, 0.9],
        [-0.01, 0.2, 0.8, 0.9],
        [0.1, 0.2, 1.01, 0.9],
        [0.8, 0.2, 0.1, 0.9],
        [0.1, 0.9, 0.8, 0.2],
        [0.1, 0.2, 0.1, 0.9],
        [0.1, 0.2, 0.8, 0.2],
        [True, 0.2, 0.8, 0.9],
        ["0.1", 0.2, 0.8, 0.9],
    ],
)
def test_malformed_non_finite_and_out_of_range_boxes_are_excluded(invalid_box):
    client = GLMOCRClient(api_key="test-key")

    results = client._parse_response(
        _response(invalid_box, [0.1, 0.2, 0.8, 0.9]),
        source_size=(1000, 500),
    )

    assert [text for _, text, _ in results] == ["text-1"]
    assert client.invalid_coordinate_count == 1


def test_invalid_coordinate_count_accumulates_across_responses():
    client = GLMOCRClient(api_key="test-key")

    client._parse_response(_response([1.2, 0.2, 0.8, 0.9]), source_size=(10, 10))
    client._parse_response(
        _response([0.1, 0.2, 0.8], [0.1, 0.2, 0.8, 0.9]),
        source_size=(10, 10),
    )

    assert client.invalid_coordinate_count == 2


def test_batch_concurrency_preserves_input_order_and_isolates_failures(monkeypatch):
    client = GLMOCRClient(api_key="test-key")
    monkeypatch.setattr(client, "is_available", lambda: True)

    def recognize(value):
        time.sleep((4 - value) * 0.005)
        if value == 2:
            raise RuntimeError("one frame failed")
        return [([[value, 0]], f"text-{value}", 0.9)]

    monkeypatch.setattr(client, "recognize_single", recognize)

    results = client.recognize_batch([0, 1, 2, 3])

    assert [items[0][1] if items else None for items in results] == [
        "text-0",
        "text-1",
        None,
        "text-3",
    ]


class _APIResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_http_adapter_does_not_duplicate_application_429_retries():
    client = GLMOCRClient(api_key="test-key")
    retry = client._session.get_adapter("https://").max_retries

    assert 429 not in retry.status_forcelist
    assert retry.respect_retry_after_header is False
    assert 500 in retry.status_forcelist


def test_unexpected_response_shape_records_fail_closed_diagnostic():
    client = GLMOCRClient(api_key="test-key")

    assert client._parse_response({"unexpected": []}, source_size=(100, 100)) == []
    assert client.request_failure_count == 1


def test_rate_limit_retries_without_switching_offline(monkeypatch):
    client = GLMOCRClient(api_key="test-key")
    responses = iter(
        [
            _APIResponse(429, headers={"Retry-After": "1"}),
            _APIResponse(200, payload={"layout_details": []}),
        ]
    )
    monkeypatch.setattr(client._session, "post", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(client, "_wait_for_rate_limit_slot", lambda: None)
    monkeypatch.setattr(client, "_set_rate_limit_cooldown", lambda _seconds: None)

    result = client._call_api({"file": "test"})

    assert result == {"layout_details": []}
    assert client.request_failure_count == 0
    assert client._offline_mode is False


def test_exhausted_rate_limit_fails_closed_without_permanent_offline(monkeypatch):
    client = GLMOCRClient(api_key="test-key")
    monkeypatch.setattr(
        client._session,
        "post",
        lambda *args, **kwargs: _APIResponse(429),
    )
    monkeypatch.setattr(client, "_wait_for_rate_limit_slot", lambda: None)
    monkeypatch.setattr(client, "_set_rate_limit_cooldown", lambda _seconds: None)

    assert client._call_api({"file": "test"}) is None
    assert client.request_failure_count == 1
    assert client._offline_mode is False
