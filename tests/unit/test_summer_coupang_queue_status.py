import json

from managers.summer_coupang_queue_status import build_summer_coupang_queue_snapshot


def test_build_snapshot_maps_scheduled_queue_rows(tmp_path):
    queue_path = tmp_path / "summer_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "automation_policy": {"interval_minutes": 240},
                "items": [
                    {
                        "planned_number": "[030]",
                        "status": "completed",
                        "coupang_url": "https://www.coupang.com/vp/products/1",
                        "scheduled_at": "2026-06-18T16:26:26+09:00",
                        "attempts": 1,
                        "result": {
                            "youtube_url": "https://youtu.be/demo",
                            "linktree_result": {"ok": True},
                        },
                    },
                    {
                        "planned_number": "[031]",
                        "status": "completed_linktree_blocked",
                        "coupang_url": "https://www.coupang.com/vp/products/2",
                        "scheduled_at": "2026-06-18T20:26:26+09:00",
                        "attempts": 1,
                        "result": {
                            "youtube": {"video_url": "https://youtu.be/demo2"},
                            "linktree_result": {
                                "ok": False,
                                "blocking_reason": "Linktree webhook URL is not configured.",
                            },
                        },
                    },
                    {
                        "planned_number": "[032]",
                        "status": "pending",
                        "coupang_url": "https://www.coupang.com/vp/products/3",
                        "scheduled_at": "2026-06-19T00:26:26+09:00",
                        "scheduled_order": 3,
                        "attempts": 0,
                        "result": {},
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    snapshot = build_summer_coupang_queue_snapshot(queue_path)

    assert snapshot["total"] == 3
    assert snapshot["counts"] == {
        "waiting": 1,
        "processing": 0,
        "completed": 2,
        "skipped": 0,
        "failed": 0,
    }
    assert snapshot["interval_minutes"] == 240
    assert snapshot["next_planned_number"] == "[032]"
    assert snapshot["next_scheduled_display"] == "06-19 00:26"
    assert snapshot["rows"][0]["status"] == "완료"
    assert snapshot["rows"][1]["status"] == "완료(Linktree 보류)"
    assert snapshot["rows"][2]["upload"] == "예약됨"
