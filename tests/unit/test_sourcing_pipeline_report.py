import json

from core.sourcing.coupang_scraper import _cached_product_from_reports
from core.sourcing.pipeline import SourcingPipeline


def test_get_report_includes_legacy_and_new_result_keys():
    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/12345",
        output_dir=".",
        min_similarity_score=0.9,
    )
    pipeline.sourced_products = [
        {
            "source": "aliexpress",
            "product": {
                "title": "Test Product",
                "url": "https://example.com/item/1",
                "score": 0.91,
            },
            "video_file": "sample.mp4",
            "size_mb": 12.3,
        }
    ]

    report = pipeline.get_report()

    assert report["sourced_products"] == report["sourcing_results"]
    assert report["sourcing_results"][0]["title"] == "Test Product"
    assert report["match_threshold"] == 0.9


def test_image_fallback_report_is_marked_review_only():
    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/12345",
        output_dir=".",
        min_similarity_score=0.9,
    )
    pipeline.sourced_products = [
        {
            "source": "coupang_image",
            "product": {
                "title": "Exact Coupang Product",
                "url": "https://link.coupang.com/a/test",
                "score": 1.0,
                "fallback_reason": "no_marketplace_video",
            },
            "video_file": "fallback.mp4",
            "size_mb": 1.4,
            "fallback_reason": "no_marketplace_video",
            "auto_publish_safe": False,
            "requires_review": True,
        }
    ]

    item = pipeline.get_report()["sourced_products"][0]

    assert item["fallback_reason"] == "no_marketplace_video"
    assert item["auto_publish_safe"] is False
    assert item["requires_review"] is True


def test_similarity_gate_marks_below_threshold_review_only():
    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/12345",
        output_dir=".",
        min_similarity_score=0.9,
    )
    pipeline.sourced_products = [
        {
            "source": "aliexpress",
            "product": {
                "title": "Similar but not strict enough",
                "url": "https://example.com/item/1",
                "score": 0.42,
            },
            "video_file": "sample.mp4",
            "size_mb": 12.3,
        }
    ]

    assert pipeline.evaluate_similarity_threshold() is False

    report = pipeline.get_report()
    item = report["sourced_products"][0]

    assert report["match_status"] == "below_threshold"
    assert report["best_similarity"] == 0.42
    assert item["fallback_reason"] == "below_similarity_threshold"
    assert item["auto_publish_safe"] is False
    assert item["requires_review"] is True


def test_similarity_gate_ignores_coupang_image_fallback_as_match():
    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/12345",
        output_dir=".",
        min_similarity_score=0.9,
    )
    pipeline.sourced_products = [
        {
            "source": "coupang_image",
            "product": {
                "title": "Exact Coupang Product",
                "url": "https://link.coupang.com/a/test",
                "score": 1.0,
            },
            "video_file": "fallback.mp4",
            "size_mb": 1.4,
        }
    ]

    assert pipeline.evaluate_similarity_threshold() is False
    assert pipeline.match_status == "not_found"


def test_scraped_product_info_uses_queue_fallback_for_null_name_and_generic_image():
    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/12345",
        output_dir=".",
        fallback_product_name="KINSCOTER ???? neck fan",
        fallback_category="neck_fan",
    )
    pipeline.product_info = {
        "name": "null -",
        "image": "https://image10.coupangcdn.com/image/mobile/v3/img_fb_like.png",
        "url": "https://www.coupang.com/vp/products/12345",
    }

    pipeline._repair_scraped_product_info()

    assert pipeline.product_info["name"] == "KINSCOTER neck fan"
    assert pipeline.product_info["name_source"] == "queue_fallback"
    assert pipeline.product_info["image"] == ""
    assert pipeline.product_info["image_source"] == "discarded_generic_coupang_image"


def test_scraped_product_info_falls_back_to_category_when_queue_name_is_mojibake():
    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/12345",
        output_dir=".",
        fallback_product_name="???? ???",
        fallback_category="desk_camping_fan",
    )
    pipeline.product_info = {
        "name": "null -",
        "image": "",
        "url": "https://www.coupang.com/vp/products/12345",
    }

    pipeline._repair_scraped_product_info()

    assert pipeline.product_info["name"] == "desk camping fan"


def test_cached_marketplace_video_reuses_nested_safe_report(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    report_dir = cache_root / "old_run" / "01"
    report_dir.mkdir(parents=True)
    video_path = report_dir / "source.mp4"
    video_path.write_bytes(b"x" * (128 * 1024))
    (report_dir / "report.json").write_text(
        json.dumps(
            {
                "coupang_url": "https://www.coupang.com/vp/products/5575481544",
                "product_info": {
                    "name": "Automatic electric cleaning brush set",
                    "url": "https://www.coupang.com/vp/products/5575481544",
                },
                "best_similarity": 1.0,
                "sourced_products": [
                    {
                        "source": "aliexpress",
                        "title": "Electric Spin Scrubber Cleaning Brush",
                        "url": "https://www.aliexpress.com/item/1005010461954174.html",
                        "similarity": 1.0,
                        "video_file": str(video_path),
                        "video_size_mb": 1.2,
                        "auto_publish_safe": True,
                        "requires_review": False,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SSMAKER_SOURCING_CACHE_ROOT", str(cache_root))

    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/5575481544",
        output_dir=str(tmp_path / "new_run"),
        min_similarity_score=0.9,
        enforce_min_similarity=True,
    )
    pipeline.product_info = {
        "name": "Automatic electric cleaning brush set",
        "url": "https://www.coupang.com/vp/products/5575481544",
    }

    cached = pipeline._find_cached_marketplace_video()

    assert cached is not None
    assert cached["fallback_reason"] == "cached_marketplace_video"
    assert cached["auto_publish_safe"] is True
    assert cached["product"]["score"] == 1.0
    assert cached["video_file"] == str(video_path)

    pipeline.sourced_products = [cached]
    assert pipeline.evaluate_similarity_threshold() is True
    assert pipeline.get_report()["sourced_products"][0]["cached_from_report"].endswith("report.json")


def test_cached_marketplace_video_rejects_different_product_id(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    report_dir = cache_root / "old_run"
    report_dir.mkdir(parents=True)
    video_path = report_dir / "source.mp4"
    video_path.write_bytes(b"x" * (128 * 1024))
    (report_dir / "report.json").write_text(
        json.dumps(
            {
                "coupang_url": "https://www.coupang.com/vp/products/9999999999",
                "product_info": {
                    "name": "Same display name",
                    "url": "https://www.coupang.com/vp/products/9999999999",
                },
                "sourced_products": [
                    {
                        "source": "aliexpress",
                        "title": "Electric Spin Scrubber Cleaning Brush",
                        "similarity": 1.0,
                        "video_file": str(video_path),
                        "auto_publish_safe": True,
                        "requires_review": False,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SSMAKER_SOURCING_CACHE_ROOT", str(cache_root))

    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/5575481544",
        output_dir=str(tmp_path / "new_run"),
        min_similarity_score=0.9,
    )
    pipeline.product_info = {
        "name": "Same display name",
        "url": "https://www.coupang.com/vp/products/5575481544",
    }

    assert pipeline._find_cached_marketplace_video() is None


def test_cached_product_info_reads_nested_report_json(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    report_dir = cache_root / "old_run" / "01"
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(
        json.dumps(
            {
                "coupang_url": "https://www.coupang.com/vp/products/12345",
                "product_info": {
                    "name": "Cached Coupang product",
                    "image": "//thumbnail.coupangcdn.com/sample.jpg",
                    "price": "12900",
                    "url": "https://www.coupang.com/vp/products/12345",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SSMAKER_SOURCING_CACHE_ROOT", str(cache_root))

    cached = _cached_product_from_reports("https://www.coupang.com/vp/products/12345")

    assert cached["name"] == "Cached Coupang product"
    assert cached["image"] == "https://thumbnail.coupangcdn.com/sample.jpg"
    assert cached["price"] == "12900"
