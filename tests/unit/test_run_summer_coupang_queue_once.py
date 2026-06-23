import json
from datetime import datetime, timezone

from scripts import run_summer_coupang_queue_once as queue_runner


def test_load_queue_accepts_utf8_bom(monkeypatch, tmp_path):
    queue_path = tmp_path / "queue.json"
    queue_path.write_text('\ufeff{"items": []}', encoding="utf-8")
    monkeypatch.setattr(queue_runner, "QUEUE_PATH", queue_path)

    assert queue_runner.load_queue() == {"items": []}


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
    report = {"_report_path": "report.json"}

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

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["processed"] is False
    assert output["reason"] == "youtube_not_connected"
    assert output["pending_count"] == 2
    assert payload["items"][0]["status"] == "pending"
    assert payload["items"][0]["attempts"] == 0
    assert payload["items"][1]["status"] == "pending"
    assert payload["items"][1]["attempts"] == 1


def test_linktree_preflight_block_does_not_consume_pending(monkeypatch, capsys):
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

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["processed"] is False
    assert output["reason"] == "linktree_not_connected"
    assert output["pending_count"] == 2
    assert output["upload_required_count"] == 2
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
        lambda number, url: {
            "ok": True,
            "has_number": number == "[036]",
            "has_purchase_url": url.endswith("/9169351491"),
        },
    )

    result = queue_runner.publish_linktree_if_possible(
        {"planned_number": "[036]", "coupang_url": "https://www.coupang.com/vp/products/9169351491"},
        "desk camping fan",
        "https://www.coupang.com/vp/products/9169351491",
    )

    assert result["ok"] is True
    assert result["method"] == "public_existing"
    assert result["blocking_reason"] == ""


def test_verify_linktree_public_card_retries_until_public_page_updates(monkeypatch):
    calls = []
    purchase_url = "https://www.coupang.com/vp/products/9169351491"

    class FakeResponse:
        status_code = 200

        @property
        def text(self):
            if len(calls) < 2:
                return "not updated yet"
            return f"[036] {purchase_url}"

    def fake_get(*_args, **_kwargs):
        calls.append(True)
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    result = queue_runner.verify_linktree_public_card(
        "[036]",
        purchase_url,
        attempts=3,
        delay_seconds=0,
    )

    assert result["ok"] is True
    assert result["attempts"] == 2
    assert len(calls) == 2


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
    monkeypatch.setattr(
        queue_runner,
        "publish_linktree_if_possible",
        lambda *_args, **_kwargs: {
            "ok": True,
            "method": "public_existing",
            "blocking_reason": "",
        },
    )

    result = queue_runner.asyncio.run(queue_runner.process_pending_items(payload))

    assert result["status"] == "completed"
    assert result["linktree_ok"] is True
    assert payload["items"][0]["status"] == "completed"
    assert payload["items"][0]["attempts"] == 2
    assert payload["items"][0]["result"]["youtube_url"] == "https://youtu.be/already-uploaded"


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
    monkeypatch.setattr(queue_runner, "process_pending_items", policy_skip)

    assert queue_runner.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "skipped_low_similarity"
