import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import run_summer_coupang_queue_once as queue_runner


@pytest.fixture(autouse=True)
def allow_plain_coupang_urls_for_legacy_queue_tests(monkeypatch):
    monkeypatch.setenv(queue_runner.AFFILIATE_LINK_REQUIRED_ENV, "0")
    # Never contend with a real automation run's single-instance lock.
    monkeypatch.setenv(queue_runner.QUEUE_SKIP_LOCK_ENV, "1")
    # These legacy queue-flow tests stub ``run_sourcing`` and intentionally
    # exercise the marketplace branch. Production now defaults to
    # ``platform_video``; pinning the branch here prevents accidental live
    # browser/network work and keeps the unit boundary explicit.
    monkeypatch.setattr(queue_runner, "get_sourcing_method", lambda: "coupang")


def test_load_queue_accepts_utf8_bom(monkeypatch, tmp_path):
    queue_path = tmp_path / "queue.json"
    queue_path.write_text('\ufeff{"items": []}', encoding="utf-8")
    monkeypatch.setattr(queue_runner, "QUEUE_PATH", queue_path)

    assert queue_runner.load_queue() == {"items": []}


def test_build_run_dir_strips_coupang_query_parameters(monkeypatch, tmp_path):
    monkeypatch.setattr(queue_runner.Path, "home", classmethod(lambda _cls: tmp_path))

    run_dir = queue_runner.build_run_dir(
        {
            "planned_number": "[228]",
            "coupang_url": (
                "https://www.coupang.com/vp/products/8904338758"
                "?itemId=26004154612&vendorItemId=92986244700"
            ),
        }
    )

    assert run_dir.is_dir()
    assert run_dir.name.startswith("summer_coupang_queue_228_8904338758_")
    assert "?" not in run_dir.name


def test_queue_platform_sourcing_forwards_configured_sources_and_threshold(
    monkeypatch, tmp_path
):
    from core.sourcing import platform_pipeline
    import managers.settings_manager as sm

    captured = {}

    class _Settings:
        def get_platform_video_sources(self):
            return ["kuaishou", "douyin"]

    async def fake_run_platform_sourcing(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return {"ok": False, "error": "test stop", "product_info": {}}

    monkeypatch.setattr(sm, "get_settings_manager", lambda: _Settings())
    monkeypatch.setattr(
        platform_pipeline, "run_platform_sourcing", fake_run_platform_sourcing
    )
    monkeypatch.setattr(queue_runner, "get_gemini_client", lambda: None)

    report = queue_runner.asyncio.run(
        queue_runner.run_platform_sourcing_for_queue(
            {
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "planned_number": "[001]",
                "product_name": "mini fan",
            },
            tmp_path,
            0.94,
        )
    )

    assert captured["platforms"] == ["kuaishou", "douyin"]
    assert captured["min_similarity_score"] == 0.94
    assert captured["product_name_hint"] == "mini fan"
    assert report["ok"] is False


def test_build_upload_item_uses_problem_hook_metadata_title():
    item = {
        "planned_number": "[047]",
        "category": "cooling_bedding",
        "coupang_url": "https://www.coupang.com/vp/products/9455176108",
    }
    rendered = {
        "product_name": "cooling bedding product",
        "final_video": "final.mp4",
        "render_integrity": {"ok": True},
    }
    report = {
        "_report_path": "report.json",
        "selected_source_url": "https://www.aliexpress.com/item/1005001234567890.html",
    }

    upload_item = queue_runner.build_upload_item(
        rendered,
        item,
        report,
        "https://www.coupang.com/vp/products/9455176108",
        "public",
    )
    expected_title = queue_runner.YouTubeManager.ensure_coupang_title_compliance(
        queue_runner.SUMMER_UPLOAD_METADATA["cooling_bedding"]["title"],
        marker_position="suffix",
    )

    assert upload_item["title"] == expected_title
    assert not upload_item["title"].startswith(queue_runner.COUPANG_PAID_PROMOTION_TITLE_MARKER)
    assert upload_item["title"].endswith(queue_runner.COUPANG_PAID_PROMOTION_TITLE_MARKER)
    assert upload_item["paid_marker_position"] == "suffix"
    assert "[047]" in upload_item["description"]
    assert "Linktree" in upload_item["description"]
    assert upload_item["summer_upload_metadata"]["tags"] == queue_runner.SUMMER_UPLOAD_METADATA["cooling_bedding"]["tags"]
    assert upload_item["marketplace_source_url"] == (
        "https://www.aliexpress.com/item/1005001234567890.html"
    )


def test_public_product_title_prefers_korean_coupang_title_over_sourcing_keyword():
    item = {
        "product_name": "toucan water gun set mixed colors",
        "product_title": "투칸 워터건 2종 물놀이용품, 혼합색상, 1개",
    }

    title = queue_runner.public_product_title(
        item,
        {"product_info": {"name": "toucan water gun"}},
    )

    assert title == "투칸 워터건 2종 물놀이용품, 혼합색상, 1개"


def test_youtube_preflight_block_does_not_consume_pending(monkeypatch, capsys):
    payload = {
        "items": [
            {"planned_number": "[030]", "status": "pending", "attempts": 0, "result": {}},
            {"planned_number": "[031]", "status": "pending", "attempts": 1, "result": {}},
        ]
    }

    def fail_if_called(_payload):
        raise AssertionError("pending queue must not be processed without YouTube OAuth")

    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(queue_runner, "linktree_publish_ready", lambda: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "youtube_upload_ready",
        lambda: {
            "ok": False,
            "reason": "youtube_not_connected",
            "blocking_reason": "YouTube OAuth token is missing or invalid.",
        },
    )
    monkeypatch.setattr(queue_runner, "process_pending_items", fail_if_called)

    assert queue_runner.main() == 1
    output = json.loads(capsys.readouterr().out)

    assert output["processed"] is False
    assert output["reason"] == "youtube_not_connected"
    assert output["pending_count"] == 2
    assert payload["items"][0]["status"] == "pending"
    assert payload["items"][0]["attempts"] == 0
    assert payload["items"][1]["status"] == "pending"
    assert payload["items"][1]["attempts"] == 1


def test_linktree_preflight_block_does_not_consume_pending(monkeypatch, capsys):
    monkeypatch.setenv("SSMAKER_LINKTREE_BLOCK_UPLOAD", "1")
    payload = {
        "items": [
            {"planned_number": "[030]", "status": "pending", "attempts": 0, "result": {}},
            {"planned_number": "[031]", "status": "pending", "attempts": 1, "result": {}},
        ]
    }

    def fail_if_called(_payload, **_kwargs):
        raise AssertionError("pending queue must not be processed without Linktree publish path")

    def fail_youtube_preflight():
        raise AssertionError("YouTube preflight must not run before Linktree is ready")

    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(
        queue_runner,
        "linktree_publish_ready",
        lambda: {
            "ok": False,
            "reason": "linktree_not_connected",
            "blocking_reason": "Linktree webhook URL is not configured.",
        },
    )
    monkeypatch.setattr(queue_runner, "youtube_upload_ready", fail_youtube_preflight)
    monkeypatch.setattr(queue_runner, "process_pending_items", fail_if_called)

    assert queue_runner.main() == 1
    output = json.loads(capsys.readouterr().out)

    assert output["processed"] is False
    assert output["reason"] == "linktree_not_connected"
    assert output["pending_count"] == 2
    assert output["upload_required_count"] == 2
    assert payload["items"][0]["status"] == "pending"
    assert payload["items"][0]["attempts"] == 0
    assert payload["items"][1]["status"] == "pending"
    assert payload["items"][1]["attempts"] == 1


def test_linktree_preflight_warning_does_not_block_upload_by_default(monkeypatch, capsys):
    payload = {
        "items": [
            {"planned_number": "[030]", "status": "pending", "attempts": 0, "result": {}},
        ]
    }
    called = {"youtube": 0, "processed": 0}

    def fake_youtube_preflight():
        called["youtube"] += 1
        return {"ok": True}

    async def fake_process_pending(_payload, **_kwargs):
        called["processed"] += 1
        return {"processed": True, "status": "completed", "planned_number": "[030]"}

    monkeypatch.delenv("SSMAKER_LINKTREE_BLOCK_UPLOAD", raising=False)
    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(
        queue_runner,
        "linktree_publish_ready",
        lambda: {
            "ok": False,
            "reason": "linktree_not_connected",
            "blocking_reason": "Linktree webhook URL is not configured.",
        },
    )
    monkeypatch.setattr(queue_runner, "youtube_upload_ready", fake_youtube_preflight)
    monkeypatch.setattr(queue_runner, "gemini_api_key_preflight_ready", lambda **_kwargs: {"ok": True})
    monkeypatch.setattr(queue_runner, "process_pending_items", fake_process_pending)

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["processed"] is True
    assert output["status"] == "completed"
    assert called == {"youtube": 1, "processed": 1}


def test_gemini_preflight_block_does_not_consume_due_pending(monkeypatch, capsys):
    payload = {
        "items": [
            {
                "planned_number": "[146]",
                "product_name": "pool tube",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-18T04:00:00+09:00",
                "result": {},
            }
        ]
    }
    preflight_calls = []

    def fail_if_called(_payload, **_kwargs):
        raise AssertionError("pending queue must not be processed when all Gemini keys are invalid")

    def fake_gemini_preflight(*, pending_count, next_item):
        preflight_calls.append((pending_count, next_item["planned_number"]))
        return {
            "ok": False,
            "reason": "gemini_api_keys_rejected",
            "blocking_reason": "All configured Gemini API keys were rejected.",
            "alert_path": "C:/Users/HOME/.ssmaker/alerts/summer_coupang_gemini_api_key_alert.json",
            "popup_launched": True,
            "invalid_aliases": [{"alias": "api_1", "google_status": "INVALID_ARGUMENT"}],
            "missing_aliases": ["api_2"],
        }

    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(queue_runner, "linktree_publish_ready", lambda: {"ok": True})
    monkeypatch.setattr(queue_runner, "youtube_upload_ready", lambda: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 18, 7, 26, 26, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "gemini_api_key_preflight_ready", fake_gemini_preflight)
    monkeypatch.setattr(queue_runner, "process_pending_items", fail_if_called)

    assert queue_runner.main() == 1
    output = json.loads(capsys.readouterr().out)

    assert preflight_calls == [(1, "[146]")]
    assert output["processed"] is False
    assert output["reason"] == "gemini_api_keys_rejected"
    assert output["pending_count"] == 1
    assert output["next_planned_number"] == "[146]"
    assert output["popup_launched"] is True
    assert payload["items"][0]["status"] == "pending"
    assert payload["items"][0]["attempts"] == 0


def test_gemini_preflight_skips_future_scheduled_items(monkeypatch, capsys):
    payload = {
        "items": [
            {
                "planned_number": "[146]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-18T20:26:26+09:00",
                "result": {},
            }
        ]
    }

    def fail_gemini_preflight(**_kwargs):
        raise AssertionError("Gemini preflight must not run before an item is due")

    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(queue_runner, "linktree_publish_ready", lambda: {"ok": True})
    monkeypatch.setattr(queue_runner, "youtube_upload_ready", lambda: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 18, 7, 26, 26, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "gemini_api_key_preflight_ready", fail_gemini_preflight)

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["processed"] is False
    assert output["reason"] == "no_due_items"
    assert payload["items"][0]["status"] == "pending"
    assert payload["items"][0]["attempts"] == 0


def test_gemini_alert_uses_branded_dialog_before_windows_fallback(monkeypatch, tmp_path):
    alert_path = tmp_path / "summer_coupang_gemini_api_key_alert.json"
    launched_paths = []

    def fake_branded_launcher(path):
        launched_paths.append(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["popup_launched"] is False
        assert payload["preflight"]["reason"] == "gemini_api_keys_rejected"
        return True

    def fail_windows_fallback(_title, _message):
        raise AssertionError("Windows MessageBox fallback should not run when branded dialog launches")

    monkeypatch.setattr(queue_runner, "GEMINI_KEY_ALERT_PATH", alert_path)
    monkeypatch.setattr(queue_runner, "_launch_branded_gemini_key_alert", fake_branded_launcher)
    monkeypatch.setattr(queue_runner, "_launch_windows_message_box", fail_windows_fallback)

    alert = queue_runner.maybe_show_gemini_key_alert(
        {
            "ok": False,
            "reason": "gemini_api_keys_rejected",
            "blocking_reason": "All configured Gemini API keys were rejected.",
            "invalid_aliases": [{"alias": "api_1", "google_status": "INVALID_ARGUMENT"}],
            "missing_aliases": ["api_2"],
        },
        pending_count=1,
        next_item={"planned_number": "[148]", "product_name": "water gun"},
    )

    payload = json.loads(alert_path.read_text(encoding="utf-8"))
    assert launched_paths == [alert_path]
    assert alert["popup_launched"] is True
    assert payload["popup_launched"] is True
    assert payload["next_planned_number"] == "[148]"
    assert payload["next_product_name"] == "water gun"


def test_gemini_preflight_fallback_records_warning_without_popup(monkeypatch, tmp_path):
    alert_path = tmp_path / "summer_coupang_gemini_api_key_alert.json"
    preflight = {
        "ok": False,
        "reason": "gemini_api_keys_rejected",
        "blocking_reason": "All configured Gemini API keys were rejected.",
        "invalid_aliases": [
            {
                "alias": "api_1",
                "http_status": 403,
                "google_status": "PERMISSION_DENIED",
            }
        ],
        "missing_aliases": ["api_2"],
    }

    def fail_popup(*_args, **_kwargs):
        raise AssertionError("fallback mode must not launch a blocking Gemini key popup")

    monkeypatch.delenv("SSMAKER_GEMINI_RUNTIME_DISABLED", raising=False)
    monkeypatch.delenv("SSMAKER_GEMINI_RUNTIME_FALLBACK", raising=False)
    monkeypatch.setattr(queue_runner, "GEMINI_KEY_ALERT_PATH", alert_path)
    monkeypatch.setattr(queue_runner, "probe_configured_gemini_api_keys", lambda: preflight)
    monkeypatch.setattr(queue_runner, "maybe_show_gemini_key_alert", fail_popup)

    result = queue_runner.gemini_api_key_preflight_ready(
        pending_count=60,
        next_item={"planned_number": "[168]", "product_name": "mosquito swatter"},
    )

    payload = json.loads(alert_path.read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert result["reason"] == "gemini_runtime_fallback"
    assert result["warning_reason"] == "gemini_api_keys_rejected"
    assert result["fallback_mode"] is True
    assert result["popup_launched"] is False
    assert queue_runner.os.environ["SSMAKER_GEMINI_RUNTIME_DISABLED"] == "1"
    assert payload["fallback_mode"] is True
    assert payload["popup_launched"] is False
    assert payload["popup_throttled"] is True
    assert payload["next_planned_number"] == "[168]"
    assert payload["preflight"]["reason"] == "gemini_api_keys_rejected"
    assert "Gemini" in payload["message"]
    assert "Edge TTS" in payload["message"]


def test_get_gemini_client_returns_none_when_runtime_disabled(monkeypatch):
    monkeypatch.setenv("SSMAKER_GEMINI_RUNTIME_DISABLED", "1")

    assert queue_runner.get_gemini_client() is None


def test_process_pending_items_skips_items_scheduled_for_later(monkeypatch):
    payload = {
        "items": [
            {
                "planned_number": "[031]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-18T20:26:26+09:00",
                "result": {},
            }
        ]
    }

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("future scheduled items must not be processed early")

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 18, 7, 26, 26, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "run_sourcing", fail_if_called)

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert result["processed"] is False
    assert result["reason"] == "no_due_items"
    assert result["pending_count"] == 1
    assert result["next_scheduled_at"] == "2026-06-18T20:26:26+09:00"
    assert payload["items"][0]["status"] == "pending"
    assert payload["items"][0]["attempts"] == 0


def test_process_pending_items_force_run_now_processes_future_item(monkeypatch, tmp_path):
    payload = {
        "items": [
            {
                "planned_number": "[031]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-18T20:26:26+09:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "result": {},
            }
        ]
    }
    calls = []

    monkeypatch.setenv(queue_runner.FORCE_RUN_NOW_ENV, "1")
    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 18, 7, 26, 26, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(queue_runner, "build_run_dir", lambda _item: tmp_path / "run")

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "best_similarity": 0.0,
            "match_error": "not found",
            "match_status": "not_found",
            "_report_path": str(tmp_path / "report.json"),
            "product_info": {"name": "future item"},
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[031]"]
    assert result["processed"] is True
    assert result["status"] == "skipped_low_similarity"
    assert payload["items"][0]["status"] == "skipped_low_similarity"
    assert payload["items"][0]["attempts"] == 1


def test_realign_pending_schedule_after_run_now_preserves_four_hour_cadence():
    payload = {
        "automation_policy": {"interval_minutes": 240},
        "items": [
            {
                "planned_number": "[141]",
                "status": "completed",
                "scheduled_at": "2026-06-25T12:27:27+09:00",
            },
            {
                "planned_number": "[142]",
                "status": "pending",
                "scheduled_at": "2026-06-25T16:27:27+09:00",
            },
            {
                "planned_number": "[143]",
                "status": "pending",
                "scheduled_at": "2026-06-25T20:27:27+09:00",
            },
        ],
    }

    result = queue_runner.realign_pending_schedule_after_run_now(
        payload,
        base_time=datetime(2026, 6, 25, 0, 26, 0, tzinfo=timezone.utc),
    )

    assert result == {
        "rescheduled_count": 2,
        "next_scheduled_at": "2026-06-25T04:26:00+00:00",
        "interval_minutes": 240,
    }
    assert payload["items"][0]["scheduled_at"] == "2026-06-25T12:27:27+09:00"
    assert payload["items"][1]["scheduled_at"] == "2026-06-25T04:26:00+00:00"
    assert payload["items"][2]["scheduled_at"] == "2026-06-25T08:26:00+00:00"
    assert payload["items"][1]["scheduled_interval_minutes"] == 240


def test_realign_pending_schedule_after_run_now_uses_scheduler_next_run():
    payload = {
        "automation_policy": {"interval_minutes": 240},
        "items": [
            {
                "planned_number": "[149]",
                "status": "pending",
                "scheduled_at": "2026-06-27T13:46:46+09:00",
            },
            {
                "planned_number": "[150]",
                "status": "pending",
                "scheduled_at": "2026-06-27T17:46:46+09:00",
            },
        ],
    }

    result = queue_runner.realign_pending_schedule_after_run_now(
        payload,
        base_time=datetime(2026, 6, 27, 0, 46, 46, tzinfo=timezone.utc),
        first_scheduled_at=datetime(2026, 6, 27, 3, 27, 27, tzinfo=timezone.utc),
    )

    # Seconds are floored so items stamped from the scheduler's reported
    # NextRunTime (:27:27) are still due when the trigger fires (~:27:00).
    assert result == {
        "rescheduled_count": 2,
        "next_scheduled_at": "2026-06-27T03:27:00+00:00",
        "interval_minutes": 240,
    }
    assert payload["items"][0]["scheduled_at"] == "2026-06-27T03:27:00+00:00"
    assert payload["items"][1]["scheduled_at"] == "2026-06-27T07:27:00+00:00"


def test_process_pending_items_continues_after_product_not_found_skip(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[032]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "result": {},
            },
            {
                "planned_number": "[033]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T04:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/2",
                "result": {},
            },
        ],
    }
    calls = []

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 19, 0, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(
        queue_runner,
        "build_run_dir",
        lambda item: tmp_path / str(item.get("planned_number")).strip("[]"),
    )

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        if item["planned_number"] == "[032]":
            return {
                "best_similarity": 0.0,
                "match_error": "상품을 못찾았습니다.",
                "match_status": "not_found",
                "_report_path": str(tmp_path / "report-032.json"),
                "product_info": {"name": "skip item"},
            }
        return {
            "best_similarity": 1.0,
            "_report_path": str(tmp_path / "report-033.json"),
            "product_info": {"name": "good item"},
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)
    monkeypatch.setattr(
        queue_runner,
        "select_safe_marketplace_item",
        lambda report, _min_similarity: None
        if report.get("match_error")
        else {
            "video_file": str(tmp_path / "video.mp4"),
            "title": "matching video",
            "product": {"title": "matching product"},
            "url": "https://1688.example/item",
            "auto_publish_safe": True,
            "requires_review": False,
        },
    )
    monkeypatch.setattr(
        queue_runner,
        "render_single_item",
        lambda *_args, **_kwargs: {
            "render_ok": True,
            "final_video": str(tmp_path / "final.mp4"),
            "upload_quality": {"ok": True, "reasons": []},
            "_render_result_path": str(tmp_path / "render.json"),
        },
    )
    monkeypatch.setattr(queue_runner, "build_upload_item", lambda *_args, **_kwargs: {"upload": True})
    monkeypatch.setattr(
        queue_runner,
        "upload_verified_render",
        lambda *_args, **_kwargs: {"video_url": "https://youtu.be/next"},
    )
    monkeypatch.setattr(queue_runner, "verify_youtube", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "publish_linktree_if_possible",
        lambda *_args, **_kwargs: {"ok": True},
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[032]", "[033]"]
    assert result["status"] == "completed"
    assert result["planned_number"] == "[033]"
    assert result["skip_count"] == 1
    assert result["skipped_before"][0]["planned_number"] == "[032]"
    assert payload["items"][0]["status"] == "skipped_low_similarity"
    assert payload["items"][0]["attempts"] == 1
    assert payload["items"][1]["status"] == "completed"
    assert payload["items"][1]["attempts"] == 1


def test_process_pending_items_skips_invalid_pending_without_url(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[037]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-30T12:00:00+00:00",
                "result": {},
            },
            {
                "planned_number": "[158]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-30T12:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/9436801457",
                "result": {},
            },
        ],
    }
    calls = []

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 30, 12, 30, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(queue_runner, "build_run_dir", lambda item: tmp_path / item["planned_number"].strip("[]"))

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "best_similarity": 1.0,
            "match_status": "matched",
            "_report_path": str(tmp_path / "report.json"),
            "product_info": {"name": "valid item"},
            "sourced_products": [
                {
                    "source": "aliexpress",
                    "similarity": 1.0,
                    "video_file": str(tmp_path / "source.mp4"),
                    "auto_publish_safe": True,
                    "requires_review": False,
                }
            ],
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)
    monkeypatch.setattr(
        queue_runner,
        "render_single_item",
        lambda *_args, **_kwargs: {
            "render_ok": True,
            "final_video": str(tmp_path / "final.mp4"),
            "upload_quality": {"ok": True, "reasons": []},
            "_render_result_path": str(tmp_path / "render.json"),
        },
    )
    monkeypatch.setattr(queue_runner, "build_upload_item", lambda *_args, **_kwargs: {"upload": True})
    monkeypatch.setattr(
        queue_runner,
        "upload_verified_render",
        lambda *_args, **_kwargs: {"video_url": "https://youtu.be/valid"},
    )
    monkeypatch.setattr(queue_runner, "verify_youtube", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(queue_runner, "publish_linktree_if_possible", lambda *_args, **_kwargs: {"ok": True})

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[158]"]
    assert result["status"] == "completed"
    assert result["planned_number"] == "[158]"
    assert result["skip_count"] == 1
    assert result["skipped_before"][0]["status"] == "skipped_invalid_queue_item"
    assert payload["items"][0]["status"] == "skipped_invalid_queue_item"
    assert payload["items"][1]["status"] == "completed"


def test_process_pending_items_continues_after_render_quality_skip(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[032]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "result": {},
            },
            {
                "planned_number": "[033]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T04:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/2",
                "result": {},
            },
        ],
    }
    calls = []
    render_calls = []

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 19, 4, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(
        queue_runner,
        "build_run_dir",
        lambda item: tmp_path / str(item.get("planned_number")).strip("[]"),
    )

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "best_similarity": 1.0,
            "match_status": "matched",
            "_report_path": str(tmp_path / f"{item['planned_number']}.json"),
            "product_info": {"name": f"good item {item['planned_number']}"},
            "sourced_products": [
                {
                    "source": "aliexpress",
                    "similarity": 1.0,
                    "video_file": str(tmp_path / "source.mp4"),
                    "auto_publish_safe": True,
                    "requires_review": False,
                }
            ],
        }

    def fake_render(job, _run_dir):
        render_calls.append(job["index"])
        if job["index"] == 32:
            return {
                "render_ok": True,
                "final_video": str(tmp_path / "too-short.mp4"),
                "upload_quality": {"ok": False, "reasons": ["duration_too_short"]},
                "_render_result_path": str(tmp_path / "render-032.json"),
            }
        return {
            "render_ok": True,
            "final_video": str(tmp_path / "final.mp4"),
            "upload_quality": {"ok": True, "reasons": []},
            "_render_result_path": str(tmp_path / "render-033.json"),
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)
    monkeypatch.setattr(queue_runner, "render_single_item", fake_render)
    monkeypatch.setattr(queue_runner, "build_upload_item", lambda *_args, **_kwargs: {"upload": True})
    monkeypatch.setattr(
        queue_runner,
        "upload_verified_render",
        lambda *_args, **_kwargs: {"video_url": "https://youtu.be/next"},
    )
    monkeypatch.setattr(queue_runner, "verify_youtube", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "publish_linktree_if_possible",
        lambda *_args, **_kwargs: {"ok": True},
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[032]", "[033]"]
    assert render_calls == [32, 33]
    assert result["status"] == "completed"
    assert result["planned_number"] == "[033]"
    assert result["skip_count"] == 1
    assert payload["items"][0]["status"] == "skipped_quality_gate"
    assert payload["items"][1]["status"] == "completed"


def test_process_pending_items_continues_after_render_quality_exception(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[032]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "result": {},
            },
            {
                "planned_number": "[033]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T04:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/2",
                "result": {},
            },
        ],
    }
    calls = []
    render_calls = []

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 19, 4, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(
        queue_runner,
        "build_run_dir",
        lambda item: tmp_path / str(item.get("planned_number")).strip("[]"),
    )

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "best_similarity": 1.0,
            "match_status": "matched",
            "_report_path": str(tmp_path / f"{item['planned_number']}.json"),
            "product_info": {"name": f"good item {item['planned_number']}"},
            "sourced_products": [
                {
                    "source": "aliexpress",
                    "similarity": 1.0,
                    "video_file": str(tmp_path / "source.mp4"),
                    "auto_publish_safe": True,
                    "requires_review": False,
                }
            ],
        }

    def fake_render(job, _run_dir):
        render_calls.append(job["index"])
        if job["index"] == 32:
            raise RuntimeError("No generated video for job 1")
        return {
            "render_ok": True,
            "final_video": str(tmp_path / "final.mp4"),
            "upload_quality": {"ok": True, "reasons": []},
            "_render_result_path": str(tmp_path / "render-033.json"),
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)
    monkeypatch.setattr(queue_runner, "render_single_item", fake_render)
    monkeypatch.setattr(queue_runner, "build_upload_item", lambda *_args, **_kwargs: {"upload": True})
    monkeypatch.setattr(
        queue_runner,
        "upload_verified_render",
        lambda *_args, **_kwargs: {"video_url": "https://youtu.be/next"},
    )
    monkeypatch.setattr(queue_runner, "verify_youtube", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "publish_linktree_if_possible",
        lambda *_args, **_kwargs: {"ok": True},
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[032]", "[033]"]
    assert render_calls == [32, 33]
    assert result["status"] == "completed"
    assert result["planned_number"] == "[033]"
    assert result["skip_count"] == 1
    assert payload["items"][0]["status"] == "skipped_quality_gate"
    assert payload["items"][1]["status"] == "completed"


def test_process_pending_items_skips_duplicate_fan_family_before_sourcing(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[033]",
                "status": "completed",
                "category": "cooling_handheld_fan",
                "product_name": "portable handheld fan",
                "coupang_url": "https://www.coupang.com/vp/products/100",
                "result": {"youtube_url": "https://youtu.be/already"},
            },
            {
                "planned_number": "[055]",
                "status": "pending",
                "category": "clip_fan",
                "product_name": "portable clip fan stroller desk fan",
                "attempts": 0,
                "scheduled_at": "2026-06-21T20:26:26+09:00",
                "coupang_url": "https://www.coupang.com/vp/products/200",
                "result": {},
            },
            {
                "planned_number": "[056]",
                "status": "pending",
                "category": "mosquito_trap",
                "product_name": "mosquito trap",
                "attempts": 0,
                "scheduled_at": "2026-06-22T00:26:26+09:00",
                "coupang_url": "https://www.coupang.com/vp/products/300",
                "result": {},
            },
        ],
    }
    calls = []

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 22, 0, 30, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(
        queue_runner,
        "build_run_dir",
        lambda item: tmp_path / str(item.get("planned_number")).strip("[]"),
    )

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "best_similarity": 1.0,
            "match_status": "matched",
            "_report_path": str(tmp_path / f"{item['planned_number']}.json"),
            "product_info": {"name": item["product_name"]},
            "sourced_products": [
                {
                    "source": "aliexpress",
                    "similarity": 1.0,
                    "video_file": str(tmp_path / "source.mp4"),
                    "auto_publish_safe": True,
                    "requires_review": False,
                }
            ],
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)
    monkeypatch.setattr(
        queue_runner,
        "render_single_item",
        lambda *_args, **_kwargs: {
            "render_ok": True,
            "final_video": str(tmp_path / "final.mp4"),
            "upload_quality": {"ok": True, "reasons": []},
            "_render_result_path": str(tmp_path / "render.json"),
        },
    )
    monkeypatch.setattr(queue_runner, "build_upload_item", lambda *_args, **_kwargs: {"upload": True})
    monkeypatch.setattr(
        queue_runner,
        "upload_verified_render",
        lambda *_args, **_kwargs: {"video_url": "https://youtu.be/next"},
    )
    monkeypatch.setattr(queue_runner, "verify_youtube", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "publish_linktree_if_possible",
        lambda *_args, **_kwargs: {"ok": True},
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[056]"]
    assert payload["items"][1]["status"] == "skipped_duplicate_product"
    assert payload["items"][1]["attempts"] == 0
    assert "family 'fan'" in payload["items"][1]["result"]["blocking_reason"]
    assert result["status"] == "completed"
    assert result["planned_number"] == "[056]"
    assert result["skip_count"] == 1


def test_duplicate_upload_reason_blocks_same_normalized_product_name():
    payload = {
        "items": [
            {
                "planned_number": "[047]",
                "status": "completed",
                "category": "cooling_bedding",
                "product_name": "Cooling Bedding Pad Summer Cool Mat",
                "coupang_url": "https://www.coupang.com/vp/products/1",
            },
            {
                "planned_number": "[061]",
                "status": "pending",
                "category": "cooling_bedding",
                "product_name": "cooling bedding pad summer cool mat",
                "coupang_url": "https://www.coupang.com/vp/products/2",
            },
        ]
    }

    reason = queue_runner.duplicate_upload_reason(payload["items"][1], payload)

    assert "Duplicate product name" in reason


def test_process_pending_items_stops_on_sourcing_system_blocker(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[032]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "result": {},
            },
            {
                "planned_number": "[033]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T04:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/2",
                "result": {},
            },
        ],
    }
    calls = []

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 19, 0, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(queue_runner, "build_run_dir", lambda _item: tmp_path / "run")

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "best_similarity": None,
            "error": "키워드 변환에 실패했습니다. Gemini API 키를 설정해주세요.",
            "match_status": "keyword_convert_failed",
            "_report_path": str(tmp_path / "report.json"),
            "product_info": {"name": "blocked item"},
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[032]"]
    assert result["status"] == "failed"
    assert result["blocking_type"] == "sourcing_system_blocker"
    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][0]["attempts"] == 1
    assert payload["items"][1]["status"] == "pending"
    assert payload["items"][1]["attempts"] == 0


def test_process_pending_items_retries_prior_system_skip(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[032]",
                "status": "skipped_low_similarity",
                "attempts": 1,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "result": {
                    "blocking_reason": "상품을 못찾았습니다. 해외 마켓에서 실제 시연 영상이 있는 동일 상품을 찾지 못했습니다.",
                },
            },
            {
                "planned_number": "[040]",
                "status": "skipped_low_similarity",
                "attempts": 1,
                "scheduled_at": "2026-06-20T08:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/2",
                "result": {
                    "blocking_reason": "키워드 변환에 실패했습니다. Gemini API 키를 설정해주세요.",
                    "match_status": "not_checked",
                },
            },
            {
                "planned_number": "[041]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-20T12:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/3",
                "result": {},
            },
        ],
    }
    calls = []

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 20, 8, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(
        queue_runner,
        "build_run_dir",
        lambda item: tmp_path / str(item.get("planned_number")).strip("[]"),
    )

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "best_similarity": 0.0,
            "match_error": "not found",
            "match_status": "not_found",
            "_report_path": str(tmp_path / f"{item['planned_number']}.json"),
            "product_info": {"name": "skip item"},
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)

    assert queue_runner.pending_item_count(payload) == 2
    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[040]", "[041]"]
    assert result["status"] == "skipped_low_similarity"
    assert result["skip_count"] == 2
    assert payload["items"][0]["attempts"] == 1
    assert payload["items"][1]["attempts"] == 2
    assert payload["items"][2]["attempts"] == 1


def test_select_safe_item_rejects_coupang_image_fallback():
    report = {
        "match_status": "not_found",
        "best_similarity": None,
        "sourced_products": [
            {
                "source": "coupang_image",
                "title": "Exact Coupang product image",
                "url": "https://www.coupang.com/vp/products/1",
                "similarity": 1.0,
                "video_file": "fallback.mp4",
                "fallback_reason": "no_marketplace_video",
                "auto_publish_safe": False,
                "requires_review": True,
            }
        ],
    }

    item = queue_runner.select_safe_marketplace_item(report, 0.9)

    assert item is None


def test_select_safe_item_accepts_verified_marketplace_demo():
    report = {
        "match_status": "matched",
        "best_similarity": 0.96,
        "sourced_products": [
            {
                "source": "aliexpress",
                "title": "Wearable neck fan demo",
                "url": "https://www.aliexpress.com/item/1.html",
                "similarity": 0.96,
                "video_file": "demo.mp4",
                "auto_publish_safe": True,
                "requires_review": False,
            }
        ],
    }

    item = queue_runner.select_safe_marketplace_item(report, 0.9)

    assert item is not None
    assert item["source"] == "aliexpress"


def test_select_safe_item_accepts_verified_cached_marketplace_demo():
    report = {
        "match_status": "matched",
        "best_similarity": 0.92,
        "sourced_products": [
            {
                "source": "1688",
                "similarity": 0.92,
                "video_file": "cached.mp4",
                "fallback_reason": "cached_marketplace_video",
                "auto_publish_safe": True,
                "requires_review": False,
            }
        ],
    }

    assert queue_runner.select_safe_marketplace_item(report, 0.9) is not None
    assert queue_runner.select_safe_marketplace_item(report, 0.95) is None


def test_select_safe_item_rejects_unknown_similarity():
    report = {
        "match_status": "matched",
        "best_similarity": None,
        "sourced_products": [
            {
                "source": "aliexpress",
                "title": "Unknown score demo",
                "url": "https://www.aliexpress.com/item/1.html",
                "video_file": "demo.mp4",
                "auto_publish_safe": True,
                "requires_review": False,
            }
        ],
    }

    item = queue_runner.select_safe_marketplace_item(report, 0.9)

    assert item is None


def test_validate_render_upload_quality_blocks_short_non_vertical_video(tmp_path):
    final_video = tmp_path / "short.mp4"
    final_video.write_bytes(b"x" * 128)

    result = queue_runner.validate_render_upload_quality(
        {
            "final_video": str(final_video),
            "render_ok": True,
            "tts_segment_count": 1,
            "video_probe": {
                "duration": 3.0,
                "has_audio": True,
                "is_vertical_1080x1920": False,
            },
            "render_integrity": {"ok": True},
        }
    )

    assert result["ok"] is False
    assert "duration_too_short" in result["reasons"]
    assert "not_vertical_1080x1920" in result["reasons"]
    assert "final_video_too_small" in result["reasons"]


def test_platform_reedit_quality_profile_does_not_require_tts(tmp_path):
    final_video = tmp_path / "platform.mp4"
    final_video.write_bytes(b"x" * queue_runner.MIN_FINAL_VIDEO_BYTES)
    base = {
        "final_video": str(final_video),
        "render_ok": True,
        "tts_segment_count": 0,
        "video_probe": {
            "duration": 20.0,
            "has_audio": True,
            "is_vertical_1080x1920": True,
        },
        "render_integrity": {"ok": True},
    }

    platform = queue_runner.validate_render_upload_quality(
        {**base, "quality_profile": "platform_reedit"}
    )
    narrated = queue_runner.validate_render_upload_quality(
        {**base, "quality_profile": "narrated_marketplace"}
    )

    assert platform["ok"] is True
    assert "missing_tts_segments" not in platform["reasons"]
    assert narrated["ok"] is False
    assert "missing_tts_segments" in narrated["reasons"]


def test_publish_linktree_accepts_existing_public_card(monkeypatch):
    class FakeLinktreeManager:
        def format_publish_index(self, index):
            return f"[{int(index):03d}]"

        def _build_numbered_product_title(self, product_name, index):
            return f"[{int(index):03d}] {product_name}"

        def get_settings(self):
            return {"webhook_url": ""}

        def get_profile_url(self):
            return "https://linktr.ee/studio.idol"

    monkeypatch.setattr(queue_runner, "get_linktree_manager", lambda: FakeLinktreeManager())
    monkeypatch.setattr(
        queue_runner,
        "verify_linktree_public_card",
        lambda number, url, **_kwargs: {
            "ok": True,
            "has_number": number == "[036]",
            "has_purchase_url": url.endswith("/9169351491"),
            "has_title": True,
        },
    )

    result = queue_runner.publish_linktree_if_possible(
        {
            "planned_number": "[036]",
            "coupang_url": "https://www.coupang.com/vp/products/9169351491",
            "product_title": "캠핑용 무선 선풍기",
        },
        "desk camping fan",
        "https://www.coupang.com/vp/products/9169351491",
    )

    assert result["ok"] is True
    assert result["method"] == "public_existing"
    assert result["blocking_reason"] == ""


def test_publish_linktree_without_webhook_does_not_open_browser_by_default(monkeypatch):
    class FakeLinktreeManager:
        def format_publish_index(self, index):
            return f"[{int(index):03d}]"

        def _build_numbered_product_title(self, product_name, index):
            return f"[{int(index):03d}] {product_name}"

        def get_settings(self):
            return {"webhook_url": ""}

        def get_profile_url(self):
            return "https://linktr.ee/studio.idol"

        def publish_link(self, *_args, **_kwargs):
            raise AssertionError("publish_link must not run when no webhook and browser fallback is disabled")

    checks = []

    monkeypatch.delenv("SSMAKER_LINKTREE_BROWSER_PUBLISH", raising=False)
    monkeypatch.setattr(queue_runner, "get_linktree_manager", lambda: FakeLinktreeManager())
    monkeypatch.setattr(queue_runner, "linktree_browser_publish_enabled", lambda: False)
    monkeypatch.setattr(
        queue_runner,
        "verify_linktree_public_card",
        lambda number, url, **_kwargs: checks.append((number, url, _kwargs)) or {"ok": False},
    )

    result = queue_runner.publish_linktree_if_possible(
        {
            "planned_number": "[036]",
            "coupang_url": "https://www.coupang.com/vp/products/9169351491",
            "product_title": "캠핑용 무선 선풍기",
        },
        "desk camping fan",
        "https://www.coupang.com/vp/products/9169351491",
    )

    assert result["ok"] is False
    assert result["method"] == "browser_disabled"
    assert result["webhook_sent"] is False
    assert "visible browser fallback is disabled" in result["blocking_reason"]
    assert len(checks) == 1


def test_verify_linktree_public_card_retries_until_public_page_updates(monkeypatch):
    calls = []
    purchase_url = "https://www.coupang.com/vp/products/9169351491"

    class FakeResponse:
        status_code = 200

        @property
        def text(self):
            if len(calls) < 2:
                return "not updated yet"
            return f"[036] 캠핑용 무선 선풍기 {purchase_url}"

    def fake_get(*_args, **_kwargs):
        calls.append(True)
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    result = queue_runner.verify_linktree_public_card(
        "[036]",
        purchase_url,
        expected_title="[036] 캠핑용 무선 선풍기",
        attempts=3,
        delay_seconds=0,
    )

    assert result["ok"] is True
    assert result["attempts"] == 2
    assert len(calls) == 2


def test_verify_linktree_public_card_rejects_matching_number_and_url_with_wrong_title(monkeypatch):
    purchase_url = "https://link.coupang.com/a/ggKpNXe3Y4"

    class FakeResponse:
        status_code = 200
        text = f"[245] toucan water gun set mixed colors {purchase_url}"

    monkeypatch.setattr("requests.get", lambda *_args, **_kwargs: FakeResponse())

    result = queue_runner.verify_linktree_public_card(
        "[245]",
        purchase_url,
        expected_title="[245] 투칸 워터건 2종 물놀이용품",
    )

    assert result["ok"] is False
    assert result["has_number"] is True
    assert result["has_purchase_url"] is True
    assert result["has_title"] is False


def test_process_pending_items_marks_linktree_retry_pending_after_upload(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[036]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/9169351491",
                "result": {},
            },
        ],
    }

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 19, 0, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(queue_runner, "build_run_dir", lambda _item: tmp_path / "run")

    async def fake_run_sourcing(*_args, **_kwargs):
        return {
            "best_similarity": 1.0,
            "match_status": "matched",
            "_report_path": str(tmp_path / "report.json"),
            "product_info": {"name": "desk camping fan"},
            "sourced_products": [
                {
                    "source": "aliexpress",
                    "similarity": 1.0,
                    "video_file": str(tmp_path / "source.mp4"),
                    "auto_publish_safe": True,
                    "requires_review": False,
                }
            ],
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)
    monkeypatch.setattr(
        queue_runner,
        "render_single_item",
        lambda *_args, **_kwargs: {
            "render_ok": True,
            "final_video": str(tmp_path / "final.mp4"),
            "upload_quality": {"ok": True, "reasons": []},
            "_render_result_path": str(tmp_path / "render.json"),
        },
    )
    monkeypatch.setattr(queue_runner, "build_upload_item", lambda *_args, **_kwargs: {"upload": True})
    monkeypatch.setattr(
        queue_runner,
        "upload_verified_render",
        lambda *_args, **_kwargs: {"video_url": "https://youtu.be/linktree-wait"},
    )
    monkeypatch.setattr(queue_runner, "verify_youtube", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "publish_linktree_if_possible",
        lambda *_args, **_kwargs: {
            "ok": False,
            "method": "webhook",
            "blocking_reason": "Linktree webhook publish did not verify on the public page.",
        },
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert result["status"] == queue_runner.LINKTREE_RETRY_STATUS
    assert result["linktree_retry"] is True
    assert payload["items"][0]["status"] == queue_runner.LINKTREE_RETRY_STATUS
    assert payload["items"][0]["result"]["youtube_url"] == "https://youtu.be/linktree-wait"
    assert payload["items"][0]["result"]["linktree_result"]["ok"] is False


def test_process_pending_items_retries_linktree_only_without_youtube_reupload(monkeypatch):
    payload = {
        "items": [
            {
                "planned_number": "[036]",
                "status": queue_runner.LINKTREE_RETRY_STATUS,
                "attempts": 1,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/9169351491",
                "product_name": "cooling towel sports towel",
                "product_title": "나이키 쿨링 타월",
                "result": {
                    "purchase_url": "https://www.coupang.com/vp/products/9169351491",
                    "youtube_url": "https://youtu.be/already-uploaded",
                    "render_path": "C:/tmp/final.mp4",
                    "linktree_result": {"ok": False},
                },
            },
        ],
    }

    async def fail_sourcing(*_args, **_kwargs):
        raise AssertionError("Linktree-only retry must not run sourcing")

    def fail_upload(*_args, **_kwargs):
        raise AssertionError("Linktree-only retry must not upload YouTube again")

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 19, 0, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(queue_runner, "run_sourcing", fail_sourcing)
    monkeypatch.setattr(queue_runner, "upload_verified_render", fail_upload)
    monkeypatch.setenv(queue_runner.LINKTREE_RETRY_MAX_ATTEMPTS_ENV, "2")

    published = {}

    def fake_publish(_item, product_name, _purchase_url):
        published["product_name"] = product_name
        return {
            "ok": True,
            "method": "public_existing",
            "blocking_reason": "",
        }

    monkeypatch.setattr(
        queue_runner,
        "publish_linktree_if_possible",
        fake_publish,
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert result["status"] == "completed"
    assert result["linktree_ok"] is True
    assert published["product_name"] == "나이키 쿨링 타월"
    assert payload["items"][0]["status"] == "completed"
    assert payload["items"][0]["attempts"] == 2
    assert payload["items"][0]["result"]["youtube_url"] == "https://youtu.be/already-uploaded"


def test_process_pending_items_exhausts_linktree_retry_without_republishing(monkeypatch):
    payload = {
        "items": [
            {
                "planned_number": "[149]",
                "status": queue_runner.LINKTREE_RETRY_STATUS,
                # attempts counts the original run too; +1 means the retry
                # budget is spent.
                "attempts": queue_runner.DEFAULT_LINKTREE_RETRY_MAX_ATTEMPTS + 1,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/1889046462",
                "product_name": "inflatable swimming ring tube",
                "result": {
                    "purchase_url": "https://www.coupang.com/vp/products/1889046462",
                    "youtube_url": "https://youtu.be/already-uploaded",
                    "render_path": "C:/tmp/final.mp4",
                    "linktree_result": {
                        "ok": False,
                        "method": "browser",
                        "blocking_reason": "Linktree publish call failed.",
                    },
                },
            },
            {
                "planned_number": "[150]",
                "status": "pending",
                "scheduled_at": "2026-06-19T04:00:00+00:00",
                "result": {},
            },
        ],
    }

    def fail_publish(*_args, **_kwargs):
        raise AssertionError("Exhausted Linktree retries must not publish again")

    class _StubLinktreeManager:
        def format_publish_index(self, number):
            return f"[{number:03d}]" if number else ""

        def _build_numbered_product_title(self, product_name, number):
            return f"[{number:03d}] {product_name}" if number else product_name

        def get_profile_url(self):
            return "https://linktr.ee/example"

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 19, 0, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(queue_runner, "publish_linktree_if_possible", fail_publish)
    monkeypatch.setattr(queue_runner, "get_linktree_manager", lambda: _StubLinktreeManager())
    monkeypatch.setattr(
        queue_runner,
        "verify_linktree_public_card",
        lambda *_args, **_kwargs: {"ok": False},
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert result["status"] == queue_runner.LINKTREE_FAILED_STATUS
    assert result["blocking_type"] == "linktree_retry_exhausted"
    assert payload["items"][0]["status"] == queue_runner.LINKTREE_FAILED_STATUS
    assert payload["items"][0]["result"]["youtube_url"] == "https://youtu.be/already-uploaded"
    assert payload["items"][0]["result"]["linktree_result"]["retry_exhausted"] is True
    assert payload["items"][1]["status"] == "pending"


def test_main_settles_exhausted_linktree_retry_then_processes_due_upload(monkeypatch, capsys):
    payload = {
        "items": [
            {
                "planned_number": "[157]",
                "status": queue_runner.LINKTREE_RETRY_STATUS,
                # attempts counts the original run too; +1 means the retry
                # budget is spent.
                "attempts": queue_runner.DEFAULT_LINKTREE_RETRY_MAX_ATTEMPTS + 1,
                "scheduled_at": "2026-06-30T12:27:27+09:00",
                "result": {
                    "purchase_url": "https://www.coupang.com/vp/products/1",
                    "youtube_url": "https://youtu.be/already-uploaded",
                    "render_path": "C:/tmp/final.mp4",
                    "linktree_result": {"ok": False},
                },
            },
            {
                "planned_number": "[158]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-30T12:27:27+09:00",
                "result": {},
            },
        ]
    }

    async def fake_process(process_payload, **_kwargs):
        assert process_payload["items"][0]["status"] == queue_runner.LINKTREE_FAILED_STATUS
        assert process_payload["items"][1]["status"] == "pending"
        return {
            "processed": True,
            "status": "completed",
            "planned_number": "[158]",
            "youtube_url": "https://youtu.be/next-upload",
            "linktree_ok": True,
        }

    class _StubLinktreeManager:
        def format_publish_index(self, number):
            return f"[{number:03d}]" if number else ""

        def _build_numbered_product_title(self, product_name, number):
            return f"[{number:03d}] {product_name}" if number else product_name

        def get_profile_url(self):
            return "https://linktr.ee/example"

    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 30, 12, 30, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "get_linktree_manager", lambda: _StubLinktreeManager())
    monkeypatch.setattr(
        queue_runner,
        "verify_linktree_public_card",
        lambda *_args, **_kwargs: {"ok": False},
    )
    monkeypatch.setattr(queue_runner, "linktree_publish_ready", lambda: {"ok": True})
    monkeypatch.setattr(queue_runner, "youtube_upload_ready", lambda: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "gemini_api_key_preflight_ready",
        lambda **_kwargs: {"ok": True},
    )
    monkeypatch.setattr(queue_runner, "process_pending_items", fake_process)

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["status"] == "completed"
    assert output["planned_number"] == "[158]"
    assert output["linktree_housekeeping_count"] == 1
    assert output["linktree_housekeeping"][0]["planned_number"] == "[157]"
    assert payload["items"][0]["status"] == queue_runner.LINKTREE_FAILED_STATUS


def test_settle_exhausted_linktree_retry_requires_matching_korean_title(monkeypatch):
    item = {
        "planned_number": "[245]",
        "status": queue_runner.LINKTREE_RETRY_STATUS,
        "attempts": queue_runner.DEFAULT_LINKTREE_RETRY_MAX_ATTEMPTS + 1,
        "product_name": "toucan water gun set mixed colors",
        "product_title": "투칸 워터건 2종 물놀이용품, 혼합색상, 1개",
        "result": {
            "purchase_url": "https://link.coupang.com/a/ggKpNXe3Y4",
            "youtube_url": "https://youtu.be/already-uploaded",
            "render_path": "C:/tmp/final.mp4",
            "linktree_result": {"ok": False},
        },
    }

    class _StubLinktreeManager:
        def format_publish_index(self, number):
            return f"[{number:03d}]"

        def _build_numbered_product_title(self, product_name, number):
            assert product_name.startswith("투칸 워터건")
            return "[245] 투칸 워터건 2종 물놀이용품"

        def get_profile_url(self):
            return "https://linktr.ee/studio.idol"

    checks = []

    def fake_verify(number, purchase_url, **kwargs):
        checks.append((number, purchase_url, kwargs))
        return {
            "ok": True,
            "has_number": True,
            "has_purchase_url": True,
            "has_title": True,
        }

    monkeypatch.setattr(queue_runner, "get_linktree_manager", lambda: _StubLinktreeManager())
    monkeypatch.setattr(queue_runner, "verify_linktree_public_card", fake_verify)

    result = queue_runner.settle_linktree_retry_item(item)

    assert result["status"] == "completed"
    assert item["status"] == "completed"
    assert item["result"]["linktree_result"]["title"] == "[245] 투칸 워터건 2종 물놀이용품"
    assert checks == [
        (
            "[245]",
            "https://link.coupang.com/a/ggKpNXe3Y4",
            {"expected_title": "[245] 투칸 워터건 2종 물놀이용품"},
        )
    ]


def test_linktree_retry_blocked_when_youtube_video_is_gone(monkeypatch):
    payload = {
        "items": [
            {
                "planned_number": "[190]",
                "status": queue_runner.LINKTREE_RETRY_STATUS,
                "attempts": 1,
                "scheduled_at": "2026-07-05T00:00:00+09:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "product_name": "gone video product",
                "result": {
                    "purchase_url": "https://link.coupang.com/a/gone",
                    "youtube_url": "https://youtu.be/deleted-video",
                    "render_path": "C:/tmp/final.mp4",
                    "linktree_result": {"ok": False},
                },
            },
        ],
    }

    def fail_publish(*_args, **_kwargs):
        raise AssertionError("Must not create a Linktree card for a missing video")

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone(timedelta(hours=9))),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(queue_runner, "publish_linktree_if_possible", fail_publish)
    monkeypatch.setattr(queue_runner, "youtube_video_is_live", lambda _url: False)

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert result["status"] == queue_runner.LINKTREE_FAILED_STATUS
    assert result["blocking_type"] == "youtube_video_missing"
    assert payload["items"][0]["status"] == queue_runner.LINKTREE_FAILED_STATUS


def test_resolved_linktree_retry_does_not_pull_future_upload_forward(monkeypatch):
    payload = {
        "items": [
            {
                "planned_number": "[184]",
                "status": queue_runner.LINKTREE_RETRY_STATUS,
                "attempts": 1,
                "scheduled_at": "2026-07-05T16:27:00+09:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "product_name": "cooling towel",
                "result": {
                    "purchase_url": "https://link.coupang.com/a/abc",
                    "youtube_url": "https://youtu.be/already-uploaded",
                    "render_path": "C:/tmp/final.mp4",
                    "linktree_result": {"ok": False},
                },
            },
            {
                "planned_number": "[185]",
                "status": "pending",
                "attempts": 0,
                # Scheduled two hours in the future: must NOT be processed
                # just because the retry above resolved.
                "scheduled_at": "2026-07-05T20:27:00+09:00",
                "coupang_url": "https://www.coupang.com/vp/products/2",
                "result": {},
            },
        ],
    }

    async def fail_sourcing(*_args, **_kwargs):
        raise AssertionError("Future-scheduled upload must not start early")

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 7, 5, 18, 0, 0, tzinfo=timezone(timedelta(hours=9))),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(queue_runner, "run_sourcing", fail_sourcing)
    monkeypatch.setattr(
        queue_runner,
        "validate_purchase_url_for_upload",
        lambda _item, _url: {"ok": True},
    )
    monkeypatch.setattr(
        queue_runner,
        "publish_linktree_if_possible",
        lambda _item, _name, _url: {"ok": True, "method": "public_existing", "blocking_reason": ""},
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert result["status"] == "completed"
    assert result["reason"] == "linktree_retries_resolved"
    assert result["linktree_ok"] is True
    assert payload["items"][0]["status"] == "completed"
    assert payload["items"][1]["status"] == "pending"
    assert payload["items"][1]["attempts"] == 0


def test_single_instance_lock_is_reentrant_within_process(tmp_path, monkeypatch):
    monkeypatch.setenv(queue_runner.QUEUE_SKIP_LOCK_ENV, "0")
    monkeypatch.setattr(queue_runner.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(queue_runner, "_LOCK_HANDLE", None)

    first = queue_runner.acquire_single_instance_lock()
    assert first is not None
    # Same process must be able to re-enter (tests call main() repeatedly).
    assert queue_runner.acquire_single_instance_lock() is first
    assert (tmp_path / ".ssmaker" / "summer_coupang_queue_once.lock").exists()

    first.close()
    monkeypatch.setattr(queue_runner, "_LOCK_HANDLE", None)


def test_single_instance_lock_can_be_disabled_by_env(monkeypatch):
    monkeypatch.setattr(queue_runner, "_LOCK_HANDLE", None)
    monkeypatch.setenv(queue_runner.QUEUE_SKIP_LOCK_ENV, "1")

    assert queue_runner.acquire_single_instance_lock() is not None
    # Env-disabled path must not persist a handle.
    assert queue_runner._LOCK_HANDLE is None


def test_main_returns_success_for_linktree_retry_pending(monkeypatch, capsys):
    payload = {
        "items": [
            {
                "planned_number": "[036]",
                "status": queue_runner.LINKTREE_RETRY_STATUS,
                "attempts": 1,
                "result": {"youtube_url": "https://youtu.be/already-uploaded"},
            },
            {
                "planned_number": "[037]",
                "status": "pending",
                "attempts": 0,
                "result": {},
            },
        ]
    }

    async def retry_pending(_payload, **_kwargs):
        return {
            "processed": True,
            "status": queue_runner.LINKTREE_RETRY_STATUS,
            "planned_number": "[036]",
            "linktree_retry": True,
        }

    def fail_youtube_preflight():
        raise AssertionError("Linktree-only retry must not require YouTube OAuth")

    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setenv(queue_runner.LINKTREE_RETRY_MAX_ATTEMPTS_ENV, "2")
    monkeypatch.setattr(queue_runner, "youtube_upload_ready", fail_youtube_preflight)
    monkeypatch.setattr(queue_runner, "process_pending_items", retry_pending)

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == queue_runner.LINKTREE_RETRY_STATUS


def test_process_pending_items_continues_skips_until_no_candidates_remain(monkeypatch, tmp_path):
    payload = {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": "[032]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T00:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/1",
                "result": {},
            },
            {
                "planned_number": "[033]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T04:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/2",
                "result": {},
            },
            {
                "planned_number": "[034]",
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-06-19T08:00:00+00:00",
                "coupang_url": "https://www.coupang.com/vp/products/3",
                "result": {},
            },
        ],
    }
    calls = []

    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 6, 19, 0, 1, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(
        queue_runner,
        "build_run_dir",
        lambda item: tmp_path / str(item.get("planned_number")).strip("[]"),
    )

    async def fake_run_sourcing(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "best_similarity": 0.0,
            "match_error": "not found",
            "match_status": "not_found",
            "_report_path": str(tmp_path / f"{item['planned_number']}.json"),
            "product_info": {"name": "skip item"},
        }

    monkeypatch.setattr(queue_runner, "run_sourcing", fake_run_sourcing)

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[032]", "[033]", "[034]"]
    assert result["status"] == "skipped_low_similarity"
    assert result["skip_count"] == 3
    assert payload["items"][0]["status"] == "skipped_low_similarity"
    assert payload["items"][1]["status"] == "skipped_low_similarity"
    assert payload["items"][2]["status"] == "skipped_low_similarity"
    assert payload["items"][2]["attempts"] == 1


def test_main_returns_success_for_policy_skip(monkeypatch, capsys):
    payload = {
        "items": [
            {"planned_number": "[032]", "status": "pending", "attempts": 0, "result": {}},
        ]
    }

    async def policy_skip(_payload, **_kwargs):
        return {
            "processed": True,
            "status": "skipped_low_similarity",
            "planned_number": "[032]",
            "reason": "no safe matching video found",
        }

    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(queue_runner, "linktree_publish_ready", lambda: {"ok": True})
    monkeypatch.setattr(
        queue_runner,
        "youtube_upload_ready",
        lambda: {"ok": True},
    )
    monkeypatch.setattr(
        queue_runner,
        "gemini_api_key_preflight_ready",
        lambda **_kwargs: {"ok": True},
    )
    monkeypatch.setattr(queue_runner, "process_pending_items", policy_skip)

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "skipped_low_similarity"


def _platform_queue_payload(*numbers):
    return {
        "automation_policy": {
            "min_similarity_score": 0.9,
            "youtube_privacy": "unlisted",
        },
        "items": [
            {
                "planned_number": number,
                "status": "pending",
                "attempts": 0,
                "scheduled_at": "2026-08-15T00:00:00+00:00",
                "coupang_url": f"https://www.coupang.com/vp/products/{index}",
                "product_name": f"product {index}",
                "result": {},
            }
            for index, number in enumerate(numbers, start=201)
        ],
    }


def _prepare_platform_queue_test(monkeypatch, tmp_path):
    monkeypatch.setattr(queue_runner, "get_sourcing_method", lambda: "platform_video")
    monkeypatch.setattr(
        queue_runner,
        "now_datetime",
        lambda: datetime(2026, 8, 15, 1, 0, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(queue_runner, "save_queue", lambda _payload: None)
    monkeypatch.setattr(
        queue_runner,
        "build_run_dir",
        lambda item: tmp_path / str(item.get("planned_number")).strip("[]"),
    )


def test_platform_system_blocker_requires_structured_browser_failure_code():
    assert queue_runner.is_platform_system_blocker(
        {"failure": {"code": "browser_start_failed"}}
    )
    assert queue_runner.is_platform_system_blocker(
        {"failure": {"code": "browser_session_failed"}}
    )
    assert queue_runner.is_platform_system_blocker(
        {"fallback_failure": {"code": "browser_session_failed"}}
    )
    assert not queue_runner.is_platform_system_blocker(
        {
            "error": "browser chrome zendriver traceback",
            "failure": {"code": "no_matching_video"},
        }
    )
    assert not queue_runner.is_platform_system_blocker(
        {"error": "browser_start_failed"}
    )


def test_platform_browser_failure_opens_per_run_circuit_without_burning_later_attempts(
    monkeypatch, tmp_path
):
    payload = _platform_queue_payload("[201]", "[202]")
    _prepare_platform_queue_test(monkeypatch, tmp_path)
    calls = []

    async def browser_failure(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "ok": False,
            "final_video": "",
            "error": "The browser could not start.",
            "failure": {
                "code": "browser_start_failed",
                "cause": "Chrome launch failed",
                "retriable": True,
            },
            "_report_path": str(tmp_path / "report.json"),
            "product_info": {"name": item["product_name"]},
        }

    monkeypatch.setattr(
        queue_runner, "run_platform_sourcing_for_queue", browser_failure
    )

    summary = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[201]"]
    assert summary["status"] == "retry_pending_sourcing"
    assert summary["blocking_type"] == "sourcing_system_blocker"
    assert summary["outcome_code"] == "source_unavailable"
    first, second = payload["items"]
    assert first["status"] == "retry_pending_sourcing"
    assert first["attempts"] == 1
    assert first["result"]["failure"]["code"] == "browser_start_failed"
    assert first["result"]["outcome_code"] == "source_unavailable"
    assert second["status"] == "pending"
    assert second["attempts"] == 0
    assert second["result"]["deferred_by_circuit"] is True
    assert second["result"]["blocking_reason"] == "The browser could not start."
    assert second["result"]["outcome_code"] == "source_unavailable"


def test_platform_circuit_resets_for_each_process_call(monkeypatch, tmp_path):
    payload = _platform_queue_payload("[211]")
    _prepare_platform_queue_test(monkeypatch, tmp_path)

    async def browser_failure(item, *_args, **_kwargs):
        return {
            "ok": False,
            "final_video": "",
            "error": "Browser session ended.",
            "failure": {"code": "browser_session_failed"},
            "_report_path": str(tmp_path / "failure.json"),
            "product_info": {"name": item["product_name"]},
        }

    monkeypatch.setattr(
        queue_runner, "run_platform_sourcing_for_queue", browser_failure
    )
    queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    retry_calls = []

    async def ordinary_no_result(item, *_args, **_kwargs):
        retry_calls.append(item["planned_number"])
        return {
            "ok": False,
            "final_video": "",
            "error": "No matching video was found.",
            "failure": {"code": "no_matching_video"},
            "_report_path": str(tmp_path / "retry.json"),
            "product_info": {"name": item["product_name"]},
        }

    monkeypatch.setattr(
        queue_runner, "run_platform_sourcing_for_queue", ordinary_no_result
    )
    summary = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert retry_calls == ["[211]"]
    assert payload["items"][0]["attempts"] == 2
    assert payload["items"][0]["status"] == "skipped_low_similarity"
    assert summary["status"] == "skipped_low_similarity"


def test_platform_no_result_does_not_open_circuit(monkeypatch, tmp_path):
    payload = _platform_queue_payload("[221]", "[222]")
    _prepare_platform_queue_test(monkeypatch, tmp_path)
    calls = []

    async def ordinary_no_result(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "ok": False,
            "final_video": "",
            "error": "No matching video was found in enabled providers.",
            "failure": {"code": "no_matching_video"},
            "_report_path": str(tmp_path / f"{item['planned_number']}.json"),
            "product_info": {"name": item["product_name"]},
        }

    monkeypatch.setattr(
        queue_runner, "run_platform_sourcing_for_queue", ordinary_no_result
    )

    queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[221]", "[222]"]
    assert [item["attempts"] for item in payload["items"]] == [1, 1]
    assert [item["status"] for item in payload["items"]] == [
        "skipped_low_similarity",
        "skipped_low_similarity",
    ]


@pytest.mark.parametrize(
    "safety_fields",
    [
        {"auto_publish_safe": False, "requires_review": True},
        {},
        {"auto_publish_safe": None, "requires_review": False},
        {"auto_publish_safe": "true", "requires_review": False},
        {"auto_publish_safe": 0, "requires_review": False},
        {"auto_publish_safe": True, "requires_review": None},
    ],
    ids=["review", "missing", "none", "string", "zero", "review-missing"],
)
def test_review_only_platform_result_completes_locally_without_delivery(
    monkeypatch, tmp_path, safety_fields
):
    payload = _platform_queue_payload("[231]")
    _prepare_platform_queue_test(monkeypatch, tmp_path)
    video_path = tmp_path / "review-only.mp4"
    report_path = tmp_path / "report.json"

    async def review_only_result(item, *_args, **_kwargs):
        return {
            "ok": True,
            "final_video": str(video_path),
            "fallback_reason": "product_image_fallback",
            "_report_path": str(report_path),
            "product_info": {"name": item["product_name"]},
            **safety_fields,
        }

    def unexpected(*_args, **_kwargs):
        raise AssertionError("review-only result must not enter delivery")

    monkeypatch.setattr(
        queue_runner, "run_platform_sourcing_for_queue", review_only_result
    )
    monkeypatch.setattr(queue_runner, "validate_purchase_url_for_upload", unexpected)
    monkeypatch.setattr(queue_runner, "platform_rendered_result", unexpected)
    monkeypatch.setattr(queue_runner, "upload_verified_render", unexpected)
    monkeypatch.setattr(queue_runner, "publish_linktree_if_possible", unexpected)

    summary = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    item = payload["items"][0]
    assert summary["status"] == "completed_review_only"
    assert item["status"] == "completed_review_only"
    assert item["attempts"] == 1
    assert item["result"]["render_path"] == str(video_path)
    assert item["result"]["final_video"] == str(video_path)
    assert item["result"]["report_path"] == str(report_path)
    assert item["result"]["fallback"] == "product_image_fallback"


def test_review_fallback_browser_failure_opens_circuit_for_later_items(
    monkeypatch, tmp_path
):
    payload = _platform_queue_payload("[241]", "[242]")
    _prepare_platform_queue_test(monkeypatch, tmp_path)
    calls = []

    async def review_fallback(item, *_args, **_kwargs):
        calls.append(item["planned_number"])
        return {
            "ok": True,
            "final_video": str(tmp_path / "review-only.mp4"),
            "fallback_reason": "product_image_fallback",
            "fallback_failure": {
                "code": "browser_session_failed",
                "cause": "Browser session ended.",
                "retriable": True,
            },
            "failure": None,
            "error": "",
            "auto_publish_safe": False,
            "requires_review": True,
            "_report_path": str(tmp_path / "report.json"),
            "product_info": {"name": item["product_name"]},
        }

    monkeypatch.setattr(
        queue_runner, "run_platform_sourcing_for_queue", review_fallback
    )

    summary = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert calls == ["[241]"]
    assert summary["status"] == "retry_pending_sourcing"
    first, second = payload["items"]
    assert first["status"] == "completed_review_only"
    assert first["attempts"] == 1
    assert first["result"]["fallback_failure"]["code"] == (
        "browser_session_failed"
    )
    assert second["status"] == "pending"
    assert second["attempts"] == 0
    assert second["result"]["deferred_by_circuit"] is True
    assert second["result"]["failure"]["code"] == "browser_session_failed"


def test_new_queue_statuses_are_retryable_or_terminal_as_intended():
    from managers import summer_coupang_queue_status as queue_status

    assert queue_runner.is_processable_queue_item(
        {"status": "retry_pending_sourcing"}
    )
    assert not queue_runner.is_processable_queue_item(
        {"status": "completed_review_only"}
    )
    assert queue_status._status_bucket("retry_pending_sourcing") == "waiting"
    assert queue_status._status_bucket("completed_review_only") == "skipped"
