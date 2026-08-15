from pathlib import Path
from urllib.parse import urlparse
import hashlib
import zipfile

import pytest

from config.font_catalog import (
    ArchiveSource,
    FontAsset,
    FONT_BY_ID,
    FONT_CHOICES,
    FONT_IDS,
    HANGUL_SENTINELS,
    LICENSE_NOTICES,
)
from scripts import download_all_fonts_final as font_sync
from managers.settings_manager import SettingsManager
from scripts.verify_font_assets import verify_font_directory, verify_font_file


ROOT = Path(__file__).resolve().parents[2]


def test_font_catalog_has_seven_pinned_official_choices():
    assert FONT_IDS == (
        "seoul_hangang",
        "pretendard",
        "noto_sans_kr",
        "suit",
        "gmarketsans",
        "paperlogy",
        "unpeople_gothic",
    )
    assert HANGUL_SENTINELS == (0xAC00, 0xD55C, 0xAE00)
    assert len({choice.asset.filename for choice in FONT_CHOICES}) == 7
    assert len({choice.asset.sha256 for choice in FONT_CHOICES}) == 7

    for choice in FONT_CHOICES:
        source = choice.asset.archive.url if choice.asset.archive else choice.asset.url
        assert source is not None
        assert urlparse(source).scheme == "https"
        assert "fonts-archive" not in source
        assert choice.asset.size > 100_000
        assert len(choice.asset.sha256) == 64
        assert choice.asset.family
        assert choice.asset.style
        assert choice.asset.hangul_codepoints
        for notice_name in choice.license_files:
            assert notice_name in LICENSE_NOTICES

    seoul = FONT_BY_ID["seoul_hangang"].asset
    assert seoul.archive is not None
    assert seoul.archive.size == 50_350_440
    assert seoul.archive.sha256 == (
        "7ab485b98f5b1a1b05cfd04484dd49a62f856be8506223cd99e5ea1a33e400a7"
    )
    assert seoul.archive.member.endswith("/SeoulHangangB.ttf")

    unpeople = FONT_BY_ID["unpeople_gothic"].asset
    assert unpeople.browser_user_agent is True
    assert unpeople.size == 2_495_412
    assert unpeople.sha256 == (
        "eed9c46a5e5627d5c837facb8eae2c246489f1995edf5e4d02ba54c4bc0fff58"
    )


def test_bundled_font_assets_and_notices_match_catalog():
    errors = verify_font_directory(
        ROOT / "fonts",
        ROOT / "resources" / "licenses",
    )
    assert errors == []


def test_verifier_rejects_a_modified_font(tmp_path):
    choice = FONT_BY_ID["suit"]
    original = ROOT / "fonts" / choice.asset.filename
    modified = tmp_path / choice.asset.filename
    modified.write_bytes(original.read_bytes() + b"tampered")

    errors = verify_font_file(modified, choice.asset)
    assert any("size" in error for error in errors)
    assert any("sha256" in error for error in errors)


def test_settings_migrate_legacy_and_invalid_font_ids():
    normalized = SettingsManager._normalize_settings(
        {"font_id": "gmarket_sans", "watermark_font_id": "not-a-font"}
    )
    assert normalized["font_id"] == "gmarketsans"
    assert normalized["watermark_font_id"] == "pretendard"


def test_font_redirect_handler_rejects_host_outside_asset_allowlist():
    handler = font_sync._ApprovedRedirectHandler(frozenset({"github.com"}))

    with pytest.raises(ValueError, match="not approved"):
        handler.redirect_request(
            type("Request", (), {"full_url": "https://github.com/font.zip"})(),
            None,
            302,
            "Found",
            {},
            "https://evil.example/font.zip",
        )

    with pytest.raises(ValueError, match="not approved"):
        font_sync._validate_download_url(
            "https://github.com:444/font.zip", frozenset({"github.com"})
        )


def test_zip_member_declared_size_must_match_pinned_asset(monkeypatch, tmp_path):
    archive_path = tmp_path / "font.zip"
    with zipfile.ZipFile(archive_path, "w") as bundle:
        bundle.writestr("font.ttf", b"four")
    archive_bytes = archive_path.read_bytes()
    asset = FontAsset(
        filename="font.ttf",
        size=3,
        sha256=hashlib.sha256(b"bad").hexdigest(),
        family="Test",
        style="Regular",
        archive=ArchiveSource(
            url="https://github.com/example/font.zip",
            size=len(archive_bytes),
            sha256=hashlib.sha256(archive_bytes).hexdigest(),
            member="font.ttf",
        ),
    )
    monkeypatch.setattr(font_sync, "_download", lambda *_args, **_kwargs: archive_path)

    with pytest.raises(ValueError, match="archive member size"):
        font_sync._decoded_bytes(asset, tmp_path)
