# -*- coding: utf-8 -*-
"""Uploaded-registry duplicate-guard tests."""

import json
import threading

import pytest
import managers.uploaded_registry as uploaded_registry_module

from managers.uploaded_registry import (
    RegistryIntegrityError,
    UploadedRegistry,
    normalize_product_key,
)


def test_normalize_product_key_stable():
    a = normalize_product_key("모기 퇴치기 LED", "https://link.coupang.com/a/xyz?lptag=1")
    b = normalize_product_key("모기 퇴치기 LED", "https://link.coupang.com/a/xyz?lptag=2")
    assert a == b  # query string stripped
    assert a  # non-empty


def test_product_key_duplicate_blocked(tmp_path):
    reg = UploadedRegistry(path=str(tmp_path / "reg.json"))
    key = normalize_product_key("전동 물총", "https://link.coupang.com/a/aaa")
    assert reg.is_duplicate(product_key=key)[0] is False
    reg.record(product_key=key, video_id="vid1")
    is_dup, reason = reg.is_duplicate(product_key=key)
    assert is_dup is True
    assert "이미 업로드" in reason


def test_persistence_across_instances(tmp_path):
    p = str(tmp_path / "reg.json")
    key = normalize_product_key("쿨매트", "https://link.coupang.com/a/bbb")
    UploadedRegistry(path=p).record(product_key=key, video_id="v")
    # New instance loads persisted state.
    assert UploadedRegistry(path=p).is_duplicate(product_key=key)[0] is True


def test_distinct_products_not_duplicate(tmp_path):
    reg = UploadedRegistry(path=str(tmp_path / "reg.json"))
    k1 = normalize_product_key("선풍기", "https://link.coupang.com/a/1")
    k2 = normalize_product_key("모기채", "https://link.coupang.com/a/2")
    reg.record(product_key=k1, video_id="v1")
    assert reg.is_duplicate(product_key=k2)[0] is False


def test_corrupt_primary_recovers_from_current_backup(tmp_path):
    path = tmp_path / "reg.json"
    key = normalize_product_key("백업 보존 상품", "https://www.coupang.com/vp/products/1")
    UploadedRegistry(path=str(path)).record(product_key=key, video_id="v1")

    path.write_text("{broken", encoding="utf-8")
    recovered = UploadedRegistry(path=str(path))

    assert recovered.is_duplicate(product_key=key)[0] is True
    assert json.loads(path.read_text(encoding="utf-8"))["product_keys"][key]["video_id"] == "v1"


def test_corrupt_primary_and_backup_fail_closed(tmp_path):
    path = tmp_path / "reg.json"
    path.write_text("{broken", encoding="utf-8")
    (tmp_path / "reg.json.bak").write_text("[]", encoding="utf-8")

    with pytest.raises(RegistryIntegrityError, match="모두 손상"):
        UploadedRegistry(path=str(path))


def test_atomic_replace_failure_keeps_previous_registry(tmp_path, monkeypatch):
    path = tmp_path / "reg.json"
    first = normalize_product_key("첫 상품", "https://www.coupang.com/vp/products/1")
    second = normalize_product_key("둘째 상품", "https://www.coupang.com/vp/products/2")
    registry = UploadedRegistry(path=str(path))
    registry.record(product_key=first, video_id="v1")
    real_replace = __import__("os").replace

    def fail_main_replace(source, destination):
        if str(destination) == str(path):
            raise OSError("simulated interruption")
        return real_replace(source, destination)

    monkeypatch.setattr("managers.uploaded_registry.os.replace", fail_main_replace)
    with pytest.raises(RegistryIntegrityError):
        registry.record(product_key=second, video_id="v2")

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert first in persisted["product_keys"]
    assert second not in persisted["product_keys"]


def test_concurrent_registry_instances_merge_without_lost_updates(tmp_path):
    path = str(tmp_path / "reg.json")
    first = UploadedRegistry(path=path)
    second = UploadedRegistry(path=path)
    barrier = threading.Barrier(2)
    failures = []

    def record(registry, key, video_id):
        try:
            barrier.wait(timeout=3)
            registry.record(product_key=key, video_id=video_id)
        except Exception as exc:  # pragma: no cover - assertion reports details
            failures.append(exc)

    keys = [
        normalize_product_key("동시 상품 A", "https://www.coupang.com/vp/products/10"),
        normalize_product_key("동시 상품 B", "https://www.coupang.com/vp/products/20"),
    ]
    threads = [
        threading.Thread(target=record, args=(first, keys[0], "a")),
        threading.Thread(target=record, args=(second, keys[1], "b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not failures
    merged = UploadedRegistry(path=path)
    assert all(merged.is_duplicate(product_key=key)[0] for key in keys)


def test_preupload_reservation_is_atomic_across_process_instances(tmp_path):
    path = str(tmp_path / "reg.json")
    key = normalize_product_key("원자 예약 상품", "https://www.coupang.com/vp/products/30")
    first = UploadedRegistry(path=path)
    second = UploadedRegistry(path=path)

    reservation_id, reason = first.reserve(product_key=key)
    competing_id, competing_reason = second.reserve(product_key=key)

    assert reservation_id and not reason
    assert competing_id is None
    assert "예약" in competing_reason

    first.finalize_reservation(reservation_id, video_id="youtube-30")
    reloaded = UploadedRegistry(path=path)
    assert reloaded.is_duplicate(product_key=key)[0] is True


def test_failed_preupload_reservation_can_be_released(tmp_path):
    path = str(tmp_path / "reg.json")
    key = normalize_product_key("실패 예약 상품", "https://www.coupang.com/vp/products/40")
    registry = UploadedRegistry(path=path)
    reservation_id, _ = registry.reserve(product_key=key)
    registry.release_reservation(reservation_id)

    retry_id, reason = UploadedRegistry(path=path).reserve(product_key=key)
    assert retry_id and not reason


def test_stale_reservation_stays_blocking_until_explicit_reconciliation(tmp_path, monkeypatch):
    path = str(tmp_path / "reg.json")
    key = normalize_product_key("중단 복구 상품", "https://www.coupang.com/vp/products/50")
    monkeypatch.setattr(uploaded_registry_module.time, "time", lambda: 1_000.0)
    registry = UploadedRegistry(path=path)
    reservation_id, _ = registry.reserve(product_key=key)

    monkeypatch.setattr(uploaded_registry_module.time, "time", lambda: 1_061.0)
    stale = UploadedRegistry(path=path).stale_reservations(older_than_seconds=60)
    blocked_id, reason = UploadedRegistry(path=path).reserve(product_key=key)

    assert reservation_id in stale
    assert blocked_id is None and "예약" in reason

    registry.reconcile_reservation(reservation_id, uploaded=False)
    retry_id, retry_reason = UploadedRegistry(path=path).reserve(product_key=key)
    assert retry_id and not retry_reason
