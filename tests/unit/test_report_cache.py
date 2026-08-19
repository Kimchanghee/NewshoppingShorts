import asyncio
import json
import os
from pathlib import Path

from core.sourcing import report_cache
from core.sourcing.pipeline import (
    SourcingPipeline,
    create_product_image_video_fallback,
    find_cached_publish_safe_video,
)


def _write_report(path: Path, payload: dict, *, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_default_report_roots_use_both_app_outputs_unless_env_replaces_them(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("SSMAKER_SOURCING_CACHE_ROOT", raising=False)

    roots = report_cache.get_default_report_roots()

    assert [root.name for root in roots] == ["sourcing_output", "platform_video_output"]
    assert len({str(root).casefold() for root in roots}) == 2
    assert all(root.is_absolute() for root in roots)

    configured = tmp_path / "nested" / ".." / "cache"
    monkeypatch.setenv("SSMAKER_SOURCING_CACHE_ROOT", str(configured))

    assert report_cache.get_default_report_roots() == [configured.resolve()]
    assert report_cache.get_default_report_root() == configured.resolve()


def test_iter_report_payloads_merges_roots_with_global_order_limit_and_isolation(
    tmp_path, monkeypatch
):
    root_a = tmp_path / "a_root"
    root_b = tmp_path / "b_root"
    newest = _write_report(
        root_b / "newest" / "report.json", {"marker": "newest"}, mtime=300
    )
    tied_a = _write_report(
        root_a / "tied" / "report.json", {"marker": "tied-a"}, mtime=200
    )
    tied_b = _write_report(
        root_b / "tied" / "report.json", {"marker": "tied-b"}, mtime=200
    )
    monkeypatch.setattr(
        report_cache, "get_default_report_roots", lambda: [root_b, root_a]
    )

    merged = list(report_cache.iter_report_payloads(limit=2))

    assert [payload["marker"] for _, payload in merged] == ["newest", "tied-a"]
    assert [path for path, _ in merged] == [newest.resolve(), tied_a.resolve()]

    isolated = list(report_cache.iter_report_payloads(root_b, limit=10))
    assert [payload["marker"] for _, payload in isolated] == ["newest", "tied-b"]
    assert [path for path, _ in isolated] == [newest.resolve(), tied_b.resolve()]


def test_iter_report_payloads_rejects_report_symlink_outside_root(
    tmp_path, monkeypatch
):
    cache_root = tmp_path / "cache"
    outside_report = _write_report(
        tmp_path / "outside-report.json", {"marker": "outside"}, mtime=100
    )
    linked_report = cache_root / "escaped" / "report.json"
    linked_report.parent.mkdir(parents=True, exist_ok=True)
    try:
        linked_report.symlink_to(outside_report)
    except OSError:
        linked_report.write_text("{}", encoding="utf-8")
        original_resolve = Path.resolve
        linked_absolute = linked_report.absolute()

        def resolve_as_external(path, *args, **kwargs):
            if path.absolute() == linked_absolute:
                return outside_report.absolute()
            return original_resolve(path, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", resolve_as_external)

    assert list(report_cache.iter_report_payloads(cache_root)) == []


def test_report_matching_accepts_affiliate_purchase_urls_but_product_id_conflicts_win():
    partner_url = "https://link.coupang.com/a/sharedCode"

    assert report_cache.report_matches_target(
        {"purchase_url": partner_url, "product_info": {"name": "same"}},
        target_product_info={"affiliate_url": partner_url, "name": "different"},
    )

    assert not report_cache.report_matches_target(
        {
            "coupang_url": "https://www.coupang.com/vp/products/222",
            "purchase_url": partner_url,
            "product_info": {"name": "same"},
        },
        target_url="https://www.coupang.com/vp/products/111",
        target_product_info={"affiliate_url": partner_url, "name": "same"},
    )


def test_coupang_identity_extractors_reject_lookalike_hosts_and_embedded_urls():
    assert report_cache.extract_coupang_product_id(
        "https://www.coupang.com/vp/products/9441995525"
    ) == "9441995525"
    assert report_cache.extract_coupang_partner_code(
        "https://link.coupang.com/a/f8i3PuVSqi"
    ) == "f8i3PuVSqi"

    assert report_cache.extract_coupang_product_id(
        "https://evil.example/vp/products/9441995525"
    ) == ""
    assert report_cache.extract_coupang_partner_code(
        "https://evil.example/?next=https://link.coupang.com/a/f8i3PuVSqi"
    ) == ""
    assert report_cache.extract_coupang_partner_code(
        "https://link.coupang.com.evil.example/a/f8i3PuVSqi"
    ) == ""
    assert report_cache.extract_coupang_product_id(
        "https://www.coupang.com:80/vp/products/9441995525"
    ) == ""
    assert report_cache.extract_coupang_product_id(
        "http://www.coupang.com:443/vp/products/9441995525"
    ) == ""


def test_publish_safe_cache_wrapper_requires_explicit_safe_flags(
    tmp_path, monkeypatch
):
    cache_root = tmp_path / "cache"
    output_dir = tmp_path / "new_run"
    partner_url = "https://link.coupang.com/a/fullAutoSafe"
    product_info = {"name": "Portable milk frother", "affiliate_url": partner_url}

    entries = [
        ("implicit", 300, {}, "https://www.aliexpress.com/item/1000000000001.html"),
        (
            "review",
            200,
            {"auto_publish_safe": True, "requires_review": True},
            "https://www.aliexpress.com/item/1000000000002.html",
        ),
        (
            "safe",
            100,
            {"auto_publish_safe": True, "requires_review": False},
            "https://www.aliexpress.com/item/1000000000003.html",
        ),
    ]
    video_paths = {}
    for label, mtime, safety, source_url in entries:
        report_dir = cache_root / label
        video_path = report_dir / f"{label}.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"x" * (128 * 1024))
        video_paths[label] = video_path
        _write_report(
            report_dir / "report.json",
            {
                "affiliate_url": partner_url,
                "product_info": product_info,
                "sourced_products": [
                    {
                        "source": "aliexpress",
                        "title": "Portable milk frother demonstration",
                        "url": source_url,
                        "similarity": 0.95,
                        "video_file": str(video_path),
                        **safety,
                    }
                ],
            },
            mtime=mtime,
        )
    monkeypatch.setenv("SSMAKER_SOURCING_CACHE_ROOT", str(cache_root))

    pipeline = SourcingPipeline(
        coupang_url=partner_url,
        output_dir=str(output_dir),
        min_similarity_score=0.8,
    )
    pipeline.product_info = dict(product_info)
    legacy_cached = pipeline._find_cached_marketplace_video()
    strict_cached = find_cached_publish_safe_video(
        partner_url,
        product_info,
        output_dir,
        used_source_ids=set(),
        min_similarity_score=0.8,
    )

    assert legacy_cached["video_file"] == str(video_paths["implicit"])
    assert strict_cached["video_file"] == str(video_paths["safe"])
    assert strict_cached["auto_publish_safe"] is True
    assert strict_cached["requires_review"] is False


def test_publish_safe_cache_reuses_verified_platform_report(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    run_dir = cache_root / "platform-run"
    video = run_dir / "edited.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"v" * (128 * 1024))
    partner_url = "https://link.coupang.com/a/platformSafe"
    _write_report(
        run_dir / "report_platform_20260815_010203_abcd1234.json",
        {
            "ok": True,
            "sourcing_method": "platform_video",
            "coupang_url": partner_url,
            "product_info": {},
            "hit": {
                "platform": "douyin",
                "title": "Portable milk frother demonstration",
                "video_url": "https://www.douyin.com/video/7351234567890123456",
                "relevance_score": 0.96,
            },
            "selected_source_url": (
                "https://www.douyin.com/video/7351234567890123456"
            ),
            "selected_source_id": "douyin:7351234567890123456",
            "final_video": str(video),
            "auto_publish_safe": True,
            "requires_review": False,
            "render_integrity": {
                "ok": True,
                "source": "platform_video",
                "platform": "douyin",
            },
        },
        mtime=300,
    )
    monkeypatch.setenv("SSMAKER_SOURCING_CACHE_ROOT", str(cache_root))

    cached = find_cached_publish_safe_video(
        partner_url,
        {},
        tmp_path / "new-run",
        used_source_ids=set(),
        min_similarity_score=0.8,
    )

    assert cached is not None
    assert cached["video_file"] == str(video.resolve())
    assert cached["product"]["title"] == "Portable milk frother demonstration"
    assert cached["auto_publish_safe"] is True


def test_publish_safe_cache_reuses_verified_download_only_platform_report(
    tmp_path, monkeypatch
):
    cache_root = tmp_path / "cache"
    run_dir = cache_root / "platform-download"
    video = run_dir / "downloaded.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"v" * (128 * 1024))
    product_url = "https://www.coupang.com/vp/products/9411394523"
    partner_url = "https://link.coupang.com/a/newPartnerCode"
    _write_report(
        run_dir / "report_platform_20260819_010203_abcd1234.json",
        {
            "ok": True,
            "download_only": True,
            "sourcing_method": "platform_video",
            "coupang_url": partner_url,
            "product_info": {"name": "fountain water gun", "url": product_url},
            "hit": {
                "platform": "douyin",
                "title": "fountain water gun demo",
                "video_url": "https://www.douyin.com/video/7397297191397739811",
                "relevance_score": 0.96,
            },
            "selected_source_url": (
                "https://www.douyin.com/video/7397297191397739811"
            ),
            "downloaded_video": str(video),
            "auto_publish_safe": True,
            "requires_review": False,
            "render_integrity": {
                "ok": True,
                "source": "platform_video_download",
                "platform": "douyin",
            },
        },
        mtime=300,
    )
    monkeypatch.setenv("SSMAKER_SOURCING_CACHE_ROOT", str(cache_root))

    cached = find_cached_publish_safe_video(
        partner_url,
        {"name": "fountain water gun", "url": product_url},
        tmp_path / "new-run",
        used_source_ids=set(),
        min_similarity_score=0.8,
    )

    assert cached is not None
    assert cached["video_file"] == str(video.resolve())
    assert cached["source"] == "douyin"
    assert cached["auto_publish_safe"] is True


def test_publish_safe_cache_rejects_paths_outside_cache_root(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    report_dir = cache_root / "reports"
    outside_video = tmp_path / "outside.mp4"
    outside_video.write_bytes(b"x" * (128 * 1024))
    partner_url = "https://link.coupang.com/a/pathEscape"
    unsafe_paths = [
        str(outside_video.resolve()),
        str(Path("..") / ".." / ".." / outside_video.name),
        r"\\attacker\share\video.mp4",
    ]

    symlink_path = report_dir / "outside-link.mp4"
    try:
        symlink_path.parent.mkdir(parents=True, exist_ok=True)
        symlink_path.symlink_to(outside_video)
    except OSError:
        pass
    else:
        unsafe_paths.append(str(symlink_path))

    for index, video_path in enumerate(unsafe_paths):
        _write_report(
            report_dir / f"case-{index}" / "report.json",
            {
                "affiliate_url": partner_url,
                "product_info": {"name": "Path escape product"},
                "sourced_products": [
                    {
                        "source": "aliexpress",
                        "title": "Path escape product demonstration",
                        "url": f"https://www.aliexpress.com/item/{index}.html",
                        "similarity": 0.99,
                        "video_file": video_path,
                        "auto_publish_safe": True,
                        "requires_review": False,
                    }
                ],
            },
            mtime=400 - index,
        )
    monkeypatch.setenv("SSMAKER_SOURCING_CACHE_ROOT", str(cache_root))

    assert find_cached_publish_safe_video(
        partner_url,
        {"name": "Path escape product"},
        tmp_path / "new-run",
        used_source_ids=set(),
        min_similarity_score=0.8,
    ) is None


def test_product_image_fallback_wrapper_reuses_pipeline_generator(tmp_path, monkeypatch):
    observed = {}

    async def fake_create(self, image_url):
        observed["url"] = self.coupang_url
        observed["product_info"] = self.product_info
        observed["output_dir"] = self.output_dir
        observed["image_url"] = image_url
        return {"auto_publish_safe": False, "requires_review": True}

    monkeypatch.setattr(SourcingPipeline, "_create_product_image_video", fake_create)
    product_info = {
        "name": "test",
        "image": "//thumbnail.coupangcdn.com/product.jpg",
    }

    result = asyncio.run(
        create_product_image_video_fallback(
            "https://www.coupang.com/vp/products/123",
            product_info,
            tmp_path,
        )
    )

    assert result == {"auto_publish_safe": False, "requires_review": True}
    assert observed == {
        "url": "https://www.coupang.com/vp/products/123",
        "product_info": {
            **product_info,
            "image": "https://thumbnail.coupangcdn.com/product.jpg",
        },
        "output_dir": str(tmp_path),
        "image_url": "https://thumbnail.coupangcdn.com/product.jpg",
    }


def test_product_image_fallback_rejects_untrusted_image_host(tmp_path, monkeypatch):
    called = False

    async def unexpected_create(self, image_url):
        nonlocal called
        called = True
        return {"video_file": "unexpected.mp4"}

    monkeypatch.setattr(SourcingPipeline, "_create_product_image_video", unexpected_create)

    result = asyncio.run(
        create_product_image_video_fallback(
            "https://link.coupang.com/a/unsafeImage",
            {"name": "unsafe", "image": "https://127.0.0.1/private.png"},
            tmp_path,
        )
    )

    assert result is None
    assert called is False


def test_product_image_download_rejects_declared_oversize_response(
    tmp_path, monkeypatch
):
    from core.sourcing import pipeline as pipeline_module
    from utils import Tool

    class OversizeResponse:
        status = 200
        headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": str(pipeline_module.MAX_PRODUCT_IMAGE_BYTES + 1),
        }

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _amount=-1):  # pragma: no cover - size rejected first
            raise AssertionError("oversized body must not be read")

    monkeypatch.setattr(
        Tool,
        "open_validated_url",
        lambda *_args, **_kwargs: OversizeResponse(),
    )
    pipeline = SourcingPipeline(
        coupang_url="https://link.coupang.com/a/oversize",
        output_dir=str(tmp_path),
    )
    pipeline.product_info = {"name": "oversized image"}

    assert pipeline._create_product_image_video_sync(
        "https://thumbnail.coupangcdn.com/oversized.jpg"
    ) is None
