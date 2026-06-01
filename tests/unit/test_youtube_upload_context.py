import json

from run_youtube_upload import _load_context


def test_load_context_finds_nested_sourcing_report(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    output_dir = tmp_path / ".ssmaker" / "sourcing_output" / "batch" / "01"
    output_dir.mkdir(parents=True)
    video_path = output_dir / "matched_video.mp4"
    video_path.write_bytes(b"video")

    report = {
        "coupang_url": "https://www.coupang.com/vp/products/1",
        "deep_link": "https://link.coupang.com/a/abc",
        "product_info": {"name": "FDUCE 미니 밀봉 실링기"},
        "description": "상품 설명",
        "sourced_products": [
            {
                "source": "aliexpress",
                "video_file": str(video_path),
                "auto_publish_safe": True,
                "requires_review": False,
            }
        ],
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False),
        encoding="utf-8",
    )

    context = _load_context(str(video_path))

    assert context["coupang_url"] == "https://link.coupang.com/a/abc"
    assert context["source_url"] == "https://www.coupang.com/vp/products/1"
    assert context["product_name"] == "FDUCE 미니 밀봉 실링기"
    assert context["auto_publish_safe"] is True
