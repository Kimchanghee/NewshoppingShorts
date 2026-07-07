# -*- coding: utf-8 -*-
"""Uploaded-registry duplicate-guard tests."""

from managers.uploaded_registry import UploadedRegistry, normalize_product_key


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
