import json
from datetime import datetime, timezone

from scripts import run_summer_coupang_queue_once as queue_runner


def test_load_queue_accepts_utf8_bom(monkeypatch, tmp_path):
    queue_path = tmp_path / "queue.json"
    queue_path.write_text('\ufeff{"items": []}', encoding="utf-8")
    monkeypatch.setattr(queue_runner, "QUEUE_PATH", queue_path)

    assert queue_runner.load_queue() == {"items": []}


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

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["processed"] is False
    assert output["reason"] == "youtube_not_connected"
    assert output["pending_count"] == 2
    assert payload["items"][0]["status"] == "pending"
    assert payload["items"][0]["attempts"] == 0
    assert payload["items"][1]["status"] == "pending"
    assert payload["items"][1]["attempts"] == 1


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
        },
    )
    monkeypatch.setattr(
        queue_runner,
        "render_single_item",
        lambda *_args, **_kwargs: {
            "render_ok": True,
            "final_video": str(tmp_path / "final.mp4"),
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


def test_main_returns_success_for_policy_skip(monkeypatch, capsys):
    payload = {
        "items": [
            {"planned_number": "[032]", "status": "pending", "attempts": 0, "result": {}},
        ]
    }

    async def policy_skip(_payload):
        return {
            "processed": True,
            "status": "skipped_low_similarity",
            "planned_number": "[032]",
            "reason": "no safe matching video found",
        }

    monkeypatch.setattr(queue_runner, "load_queue", lambda: payload)
    monkeypatch.setattr(
        queue_runner,
        "youtube_upload_ready",
        lambda: {"ok": True},
    )
    monkeypatch.setattr(queue_runner, "process_pending_items", policy_skip)

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "skipped_low_similarity"
