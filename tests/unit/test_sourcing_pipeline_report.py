from core.sourcing.pipeline import SourcingPipeline


def test_get_report_includes_legacy_and_new_result_keys():
    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/12345",
        output_dir=".",
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


def test_image_fallback_report_is_marked_review_only():
    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/12345",
        output_dir=".",
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
