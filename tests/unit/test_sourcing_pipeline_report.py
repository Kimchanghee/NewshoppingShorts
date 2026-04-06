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
