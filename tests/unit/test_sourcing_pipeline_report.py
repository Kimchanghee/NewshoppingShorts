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
