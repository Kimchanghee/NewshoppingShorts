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
        "waiting": 2,
        "processing": 0,
        "completed": 1,
        "skipped": 0,
        "failed": 0,
    }
    assert snapshot["interval_minutes"] == 240
    assert snapshot["next_planned_number"] == "[031]"
    assert snapshot["next_scheduled_display"] == "06-18 20:26"
    assert snapshot["rows"][0]["status"] == "완료"
    assert snapshot["rows"][1]["status"] == "Linktree 재시도 대기"
    assert snapshot["rows"][2]["upload"] == "예약됨"
    assert snapshot["rows"][2]["order"] == "[032]"


def test_build_snapshot_compacts_quality_gate_rows(tmp_path):
    queue_path = tmp_path / "summer_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "automation_policy": {"interval_minutes": 240},
                "items": [
                    {
                        "planned_number": "[054]",
                        "status": "skipped_quality_gate",
                        "coupang_url": "https://www.coupang.com/vp/products/9521551893",
                        "scheduled_at": "2026-06-21T20:26:26+09:00",
                        "scheduled_order": 1,
                        "attempts": 1,
                        "result": {
                            "blocking_reason": "Render upload quality gate failed: duration_too_short",
                        },
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    snapshot = build_summer_coupang_queue_snapshot(queue_path)

    assert snapshot["counts"]["skipped"] == 1
    assert snapshot["rows"][0]["order"] == "[054]"
    assert snapshot["rows"][0]["status"] == "품질보류"
    assert "자동 업로드 기준을 통과하지 못했어요" in snapshot["rows"][0]["remarks"]
    assert "duration_too_short" not in snapshot["rows"][0]["remarks"]


def test_build_snapshot_labels_duplicate_product_rows(tmp_path):
    queue_path = tmp_path / "summer_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "automation_policy": {"interval_minutes": 240},
                "items": [
                    {
                        "planned_number": "[055]",
                        "status": "skipped_duplicate_product",
                        "coupang_url": "https://www.coupang.com/vp/products/8837884814",
                        "scheduled_at": "2026-06-21T20:26:26+09:00",
                        "scheduled_order": 1,
                        "attempts": 0,
                        "result": {
                            "blocking_reason": "Duplicate product family 'fan' already has 4 completed upload(s).",
                        },
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    snapshot = build_summer_coupang_queue_snapshot(queue_path)

    assert snapshot["counts"]["skipped"] == 1
    assert snapshot["rows"][0]["order"] == "[055]"
    assert snapshot["rows"][0]["status"] == "중복보류"
    assert "이미 처리한 상품과 너무 비슷해" in snapshot["rows"][0]["remarks"]
    assert "Duplicate product family" not in snapshot["rows"][0]["remarks"]


def test_build_snapshot_treats_system_skip_as_retry_waiting(tmp_path):
    queue_path = tmp_path / "summer_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "automation_policy": {"interval_minutes": 240},
                "items": [
                    {
                        "planned_number": "[032]",
                        "status": "skipped_low_similarity",
                        "coupang_url": "https://www.coupang.com/vp/products/1",
                        "scheduled_at": "2026-06-19T00:26:26+09:00",
                        "scheduled_order": 1,
                        "attempts": 1,
                        "result": {
                            "blocking_reason": "상품을 못찾았습니다. 해외 마켓에서 실제 시연 영상이 있는 동일 상품을 찾지 못했습니다.",
                            "match_status": "not_found",
                        },
                    },
                    {
                        "planned_number": "[040]",
                        "status": "skipped_low_similarity",
                        "coupang_url": "https://www.coupang.com/vp/products/2",
                        "scheduled_at": "2026-06-20T08:26:26+09:00",
                        "scheduled_order": 2,
                        "attempts": 1,
                        "result": {
                            "blocking_reason": "키워드 변환에 실패했습니다. Gemini API 키를 설정해주세요.",
                            "match_status": "not_checked",
                        },
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    snapshot = build_summer_coupang_queue_snapshot(queue_path)

    assert snapshot["counts"]["skipped"] == 1
    assert snapshot["counts"]["waiting"] == 1
    assert snapshot["next_planned_number"] == "[040]"
    assert snapshot["rows"][1]["status"] == "재시도 대기"
    assert snapshot["rows"][1]["upload"] == "재시도 대기"
    assert snapshot["rows"][1]["retriable_system_skip"] == "true"


def test_build_snapshot_sanitizes_legacy_linktree_retry_text(tmp_path):
    queue_path = tmp_path / "summer_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "planned_number": "[077]",
                        "status": "failed_linktree_publish",
                        "coupang_url": "https://www.coupang.com/vp/products/77",
                        "scheduled_at": "2026-07-01T20:27:00+09:00",
                        "attempts": 1,
                        "result": {
                            "blocking_reason": (
                                "Linktree publish failed after 1 retry attempts; "
                                "leaving the YouTube upload recorded and moving this item out of the active queue."
                            ),
                            "linktree_result": {
                                "ok": False,
                                "blocking_reason": (
                                    "Linktree publish failed after 1 retry attempts; "
                                    "leaving the YouTube upload recorded and moving this item out of the active queue."
                                ),
                            },
                        },
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    snapshot = build_summer_coupang_queue_snapshot(queue_path)

    remarks = snapshot["rows"][0]["remarks"]
    assert "Linktree 자동 등록을 완료하지 못했어요" in remarks
    assert "YouTube 업로드 기록은 유지" in remarks
    assert "Linktree publish failed" not in remarks
    assert "retry attempts" not in remarks


def test_build_snapshot_replaces_question_mark_mojibake_reason(tmp_path):
    queue_path = tmp_path / "summer_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "planned_number": "[078]",
                        "status": "skipped_low_similarity",
                        "coupang_url": "https://www.coupang.com/vp/products/78",
                        "scheduled_at": "2026-07-01T20:27:00+09:00",
                        "attempts": 1,
                        "result": {
                            "blocking_reason": "??? ??????. ?? ???? ?? ?? ??? ?? ?? ??? ?? ?? ?? ???? ??????.",
                        },
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    snapshot = build_summer_coupang_queue_snapshot(queue_path)

    remarks = snapshot["rows"][0]["remarks"]
    assert "같은 상품으로 확인할 수 있는 영상을 찾지 못해" in remarks
    assert "???" not in remarks
