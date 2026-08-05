# -*- coding: utf-8 -*-
"""Desktop quota-consumption retry contract tests."""

import uuid
import inspect

import pytest
import requests

from caller import rest


class _Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"success": True, "remaining": 3, "used": 2, "replayed": True}


def test_consume_work_retries_with_the_same_idempotency_key(monkeypatch):
    key = str(uuid.uuid4())
    calls = []

    class _Session:
        def post(self, url, json, headers, timeout):
            calls.append((url, dict(json), dict(headers), timeout))
            if len(calls) == 1:
                raise requests.exceptions.Timeout("lost response")
            return _Response()

    monkeypatch.setattr(rest, "_get_auth_token", lambda: "desktop-jwt")
    monkeypatch.setattr(rest, "_secure_session", _Session())
    monkeypatch.setattr(rest.time, "sleep", lambda _seconds: None)

    result = rest.consumeWork("42", key)

    assert result["success"] is True
    assert len(calls) == 2
    assert calls[0][1]["idempotency_key"] == calls[1][1]["idempotency_key"] == key
    assert calls[0][0].endswith("/user/work/use-v2")


def test_consume_work_rejects_invalid_idempotency_key_without_network(monkeypatch):
    class _UnexpectedSession:
        def post(self, *args, **kwargs):  # pragma: no cover - must never execute
            raise AssertionError("network request must not be made")

    monkeypatch.setattr(rest, "_get_auth_token", lambda: "desktop-jwt")
    monkeypatch.setattr(rest, "_secure_session", _UnexpectedSession())

    result = rest.consumeWork("42", "not-a-uuid")

    assert result["success"] is False
    assert result["remaining"] is None


def test_reservation_transitions_retry_same_key_and_route(monkeypatch):
    key = str(uuid.uuid4())
    calls = []

    class _Session:
        def post(self, url, json, headers, timeout):
            calls.append((url, dict(json)))
            return _Response()

    monkeypatch.setattr(rest, "_get_auth_token", lambda: "desktop-jwt")
    monkeypatch.setattr(rest, "_secure_session", _Session())

    assert rest.reserveWork("42", key)["success"] is True
    assert rest.finalizeWork("42", key)["success"] is True
    assert rest.releaseWork("42", key)["success"] is True
    assert [url.rsplit("/", 1)[-1] for url, _ in calls] == [
        "reserve-v3",
        "finalize-v3",
        "release-v3",
    ]
    assert all(body["idempotency_key"] == key for _, body in calls)


def test_work_reservation_store_reuses_key_until_terminal_transition(tmp_path):
    from managers.work_reservation_store import WorkReservationStore

    path = tmp_path / "reservations.json"
    first_store = WorkReservationStore(path)
    first = first_store.get_or_create("batch:one")

    assert WorkReservationStore(path).get_or_create("batch:one") == first
    first_store.remove("batch:one")
    assert WorkReservationStore(path).get_or_create("batch:one") != first


def test_all_production_modes_share_durable_reservation_contract(monkeypatch, tmp_path):
    from core.video.batch import processor
    from managers.work_quota import DurableWorkReservation
    from managers.work_reservation_store import WorkReservationStore
    from ui.panels import sourcing_panel

    assert processor.DurableWorkReservation is DurableWorkReservation
    assert sourcing_panel.DurableWorkReservation is DurableWorkReservation

    store = WorkReservationStore(tmp_path / "mode-reservations.json")
    transitions = []
    monkeypatch.setattr(
        "managers.work_quota.rest.reserveWork",
        lambda user_id, key: {
            "success": True,
            "reservation_status": "reserved",
            "idempotency_key": key,
        },
    )
    monkeypatch.setattr(
        "managers.work_quota.rest.finalizeWork",
        lambda user_id, key: transitions.append(("finalize", key)) or {
            "success": True,
            "reservation_status": "completed",
        },
    )
    reservation, result = DurableWorkReservation.begin(
        "42", "single:https://example/video", store=store
    )
    persisted_key = reservation.idempotency_key

    assert result["reservation_status"] == "reserved"
    assert reservation.finalize()["success"] is True
    assert transitions == [("finalize", persisted_key)]
    assert store.get_or_create("single:https://example/video", "42") != persisted_key


def test_failed_mode_releases_reservation_without_finalizing(monkeypatch, tmp_path):
    from managers.work_quota import DurableWorkReservation
    from managers.work_reservation_store import WorkReservationStore

    store = WorkReservationStore(tmp_path / "failed-reservations.json")
    monkeypatch.setattr(
        "managers.work_quota.rest.reserveWork",
        lambda user_id, key: {
            "success": True,
            "reservation_status": "reserved",
        },
    )
    monkeypatch.setattr(
        "managers.work_quota.rest.releaseWork",
        lambda user_id, key: {
            "success": True,
            "reservation_status": "released",
        },
    )
    reservation, _ = DurableWorkReservation.begin(
        "42", "mix:job-1", store=store
    )
    persisted_key = reservation.idempotency_key
    assert reservation.release()["success"] is True
    assert store.get_or_create("mix:job-1", "42") != persisted_key


@pytest.mark.parametrize("terminal_status", ["expired", "released"])
def test_terminal_reservation_key_rotates_once_and_same_job_recovers(
    monkeypatch, tmp_path, terminal_status
):
    from managers.work_quota import DurableWorkReservation
    from managers.work_reservation_store import WorkReservationStore

    store = WorkReservationStore(tmp_path / "expired-reservations.json")
    calls = []

    def reserve(_user_id, key):
        calls.append(key)
        if len(calls) == 1:
            return {"success": False, "reservation_status": terminal_status}
        return {"success": True, "reservation_status": "reserved"}

    monkeypatch.setattr("managers.work_quota.rest.reserveWork", reserve)
    reservation, result = DurableWorkReservation.begin(
        "42", "batch:https://example", store=store
    )

    assert result["success"] is True
    assert result["reservation_status"] == "reserved"
    assert len(calls) == 2 and calls[0] != calls[1]
    assert reservation.idempotency_key == calls[1]
    assert store.get_or_create("batch:https://example", "42") == calls[1]


def test_pending_finalize_recovers_without_release_or_new_charge(monkeypatch, tmp_path):
    from managers.work_quota import DurableWorkReservation
    from managers.work_reservation_store import WorkReservationStore

    store = WorkReservationStore(tmp_path / "pending-reservations.json")
    monkeypatch.setattr(
        "managers.work_quota.rest.reserveWork",
        lambda _user_id, _key: {"success": True, "reservation_status": "reserved"},
    )
    reservation, _ = DurableWorkReservation.begin("42", "platform:one", store=store)
    reservation.mark_pending_finalize()

    transitions = []
    monkeypatch.setattr(
        "managers.work_quota.rest.finalizeWork",
        lambda _user_id, key: transitions.append(("finalize", key)) or {
            "success": True,
            "reservation_status": "completed",
        },
    )
    monkeypatch.setattr(
        "managers.work_quota.rest.releaseWork",
        lambda *_args: transitions.append(("release", "unexpected")) or {},
    )

    recovered, result = DurableWorkReservation.begin("42", "platform:one", store=store)

    assert result["recovered_pending_delivery"] is True
    assert recovered.finalized is True
    assert recovered.release()["success"] is False
    assert transitions == [("finalize", reservation.idempotency_key)]
    assert store.state("platform:one", "42") == "completed_pending_delivery"
    recovered.complete_delivery()
    assert store.state("platform:one", "42") == ""


def test_direct_platform_finalize_outage_does_not_publish_or_release(monkeypatch, tmp_path):
    from ui.panels.sourcing_panel import SourcingPanel

    video = tmp_path / "edited.mp4"
    video.write_bytes(b"video")
    events = []

    class _Reservation:
        finalized = False

        def mark_pending_finalize(self):
            events.append("pending")

        def finalize(self):
            events.append("finalize")
            return {"success": False, "reservation_status": "unknown"}

        def can_release(self):
            return False

        def release(self):
            events.append("release")
            return {"success": True}

    reservation = _Reservation()
    monkeypatch.setattr(
        "ui.panels.sourcing_panel.DurableWorkReservation.begin",
        lambda *_args, **_kwargs: (
            reservation,
            {"success": True, "reservation_status": "reserved"},
        ),
    )

    async def _pipeline(*_args, **_kwargs):
        return {
            "ok": True,
            "product_info": {"name": "상품"},
            "hit": {"platform": "douyin"},
            "final_video": str(video),
            "deep_link": "",
            "purchase_url": "https://www.coupang.com/vp/products/1",
            "render_integrity": {"ok": True},
        }

    monkeypatch.setattr("core.sourcing.platform_pipeline.run_platform_sourcing", _pipeline)

    class _Panel:
        def _on_pipeline_progress(self, *_args):
            return None

        def _safe_set_results(self, text):
            events.append(("result", text))

        def _reset_start_button(self):
            events.append("reset")

    class _YouTube:
        def add_to_upload_queue(self, **_kwargs):
            events.append("youtube")

    SourcingPanel._run_platform_pipeline(
        _Panel(),
        "https://www.coupang.com/vp/products/1",
        0.9,
        True,
        True,
        None,
        _YouTube(),
        "42",
        "platform:https://www.coupang.com/vp/products/1",
    )

    assert events[:2] == ["pending", "finalize"]
    assert "youtube" not in events
    assert "release" not in events


def test_batch_and_direct_publication_are_gated_after_finalize():
    from core.video.batch import processor
    from ui.panels.sourcing_panel import SourcingPanel

    batch_source = inspect.getsource(processor._process_single_video)
    batch_loop_source = inspect.getsource(processor.dynamic_batch_processing_thread)
    direct_source = inspect.getsource(SourcingPanel._run_platform_pipeline)

    assert batch_source.index("quota_result = active_reservation.finalize()") < batch_source.index(
        "publish_coupang_link_with_metadata"
    )
    assert batch_source.index("quota_result = active_reservation.finalize()") < batch_source.index(
        "yt_manager.add_to_upload_queue"
    )
    assert direct_source.index("finalized = work_reservation.finalize()") < direct_source.index(
        "lm.publish_coupang_link"
    )
    assert direct_source.index("finalized = work_reservation.finalize()") < direct_source.index(
        "youtube_manager.add_to_upload_queue"
    )
    recovered_index = batch_loop_source.index(
        'if work_consume_result.get("recovered_pending_delivery")'
    )
    stop_index = batch_loop_source.index("app.batch_processing = False", recovered_index)
    render_index = batch_loop_source.index("_process_single_video(app", recovered_index)
    assert recovered_index < stop_index < render_index


def test_enabled_delivery_queue_failure_keeps_completed_checkpoint(monkeypatch, tmp_path):
    from core.video.batch.processor import WorkDeliveryPendingError, _queue_delivery_or_raise
    from managers.work_quota import DurableWorkReservation
    from managers.work_reservation_store import WorkReservationStore

    store = WorkReservationStore(tmp_path / "delivery-pending.json")
    monkeypatch.setattr(
        "managers.work_quota.rest.reserveWork",
        lambda *_args: {"success": True, "reservation_status": "reserved"},
    )
    monkeypatch.setattr(
        "managers.work_quota.rest.finalizeWork",
        lambda *_args: {"success": True, "reservation_status": "completed"},
    )
    reservation, _ = DurableWorkReservation.begin("42", "batch:delivery", store=store)
    reservation.mark_pending_finalize()
    assert reservation.finalize()["success"] is True

    def fail_queue(**_payload):
        raise OSError("queue disk full")

    with pytest.raises(WorkDeliveryPendingError):
        _queue_delivery_or_raise("YouTube", fail_queue, video_path="ready.mp4")
    with pytest.raises(WorkDeliveryPendingError):
        _queue_delivery_or_raise(
            "YouTube",
            lambda **_payload: False,
            video_path="ready.mp4",
        )

    assert store.state("batch:delivery", "42") == "completed_pending_delivery"


def test_recovered_direct_delivery_checkpoint_never_rerenders(monkeypatch):
    from ui.panels.sourcing_panel import SourcingPanel

    events = []

    class _Reservation:
        finalized = True

    monkeypatch.setattr(
        "ui.panels.sourcing_panel.DurableWorkReservation.begin",
        lambda *_args, **_kwargs: (
            _Reservation(),
            {
                "success": True,
                "reservation_status": "completed",
                "recovered_pending_delivery": True,
            },
        ),
    )

    async def must_not_render(*_args, **_kwargs):
        raise AssertionError("completed delivery recovery must not rerender")

    monkeypatch.setattr(
        "core.sourcing.platform_pipeline.run_platform_sourcing", must_not_render
    )

    class _Panel:
        def _safe_set_results(self, text):
            events.append(text)

        def _reset_start_button(self):
            events.append("reset")

    SourcingPanel._run_platform_pipeline(
        _Panel(),
        "https://www.coupang.com/vp/products/1",
        0.9,
        False,
        False,
        None,
        None,
        "42",
        "platform:1",
    )

    assert any("자동 재실행하지 않았습니다" in str(event) for event in events)


def test_completed_local_hint_requires_current_user_server_confirmation(monkeypatch, tmp_path):
    from managers.work_quota import DurableWorkReservation
    from managers.work_reservation_store import WorkReservationStore

    store = WorkReservationStore(tmp_path / "untrusted-completed.json")
    key = store.get_or_create("batch:tampered", "42")
    assert store.set_state(
        "batch:tampered", key, "completed_pending_delivery", "42"
    )
    calls = []
    monkeypatch.setattr(
        "managers.work_quota.rest.finalizeWork",
        lambda user_id, request_key: calls.append((user_id, request_key)) or {
            "success": False,
            "reservation_status": "not_found",
        },
    )

    reservation, result = DurableWorkReservation.begin(
        "42", "batch:tampered", store=store
    )

    assert result["success"] is False
    assert reservation.finalized is False
    assert calls == [("42", key)]


def test_local_reservation_is_namespaced_by_user(monkeypatch, tmp_path):
    from managers.work_quota import DurableWorkReservation
    from managers.work_reservation_store import WorkReservationStore

    store = WorkReservationStore(tmp_path / "user-scoped.json")
    first_key = store.get_or_create("platform:same", "user-a")
    store.set_state(
        "platform:same",
        first_key,
        "completed_pending_delivery",
        "user-a",
    )
    reserve_calls = []
    monkeypatch.setattr(
        "managers.work_quota.rest.reserveWork",
        lambda user_id, key: reserve_calls.append((user_id, key)) or {
            "success": True,
            "reservation_status": "reserved",
        },
    )

    second, result = DurableWorkReservation.begin(
        "user-b", "platform:same", store=store
    )

    assert result["reservation_status"] == "reserved"
    assert second.idempotency_key != first_key
    assert reserve_calls == [("user-b", second.idempotency_key)]
    assert store.state("platform:same", "user-a") == "completed_pending_delivery"
    assert store.get_or_create("platform:same", "user-a") == first_key
