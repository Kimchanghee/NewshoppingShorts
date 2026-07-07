# -*- coding: utf-8 -*-
"""3플랫폼 소싱 파이프라인(신규 개선분) 유닛 테스트."""
import asyncio
import os

import pytest

from core.sourcing import platform_pipeline as pp
from core.sourcing import platform_shorts_searcher as searcher
from core.video import reeditor
from managers import uploaded_registry as reg_mod


# ── build_queries: 중국어 우선 + 중복 제거 ──

def test_build_queries_orders_chinese_first():
    q = pp.build_queries("미니 선풍기", {"chinese": "迷你风扇", "english": "mini fan"})
    assert q == ["迷你风扇", "미니 선풍기", "mini fan"]


def test_build_queries_skips_empty_and_duplicates():
    q = pp.build_queries("mini fan", {"chinese": "", "english": "mini fan"})
    assert q == ["mini fan"]


# ── 키워드 변환: Gemini 실패 시 rule-based 폴백 ──

def test_convert_keywords_falls_back_to_rules_without_client():
    kw = asyncio.new_event_loop().run_until_complete(
        pp._convert_keywords("수세미 거치대", None)
    )
    assert kw.get("chinese")  # rule-based compound 매칭
    assert kw.get("english")


# ── reeditor: ffmpeg 명령 생성 ──

def test_reedit_cmd_default_has_audio_and_no_speed(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(str(src), str(tmp_path / "out.mp4"))
    joined = " ".join(cmd)
    assert "setpts" not in joined and "atempo" not in joined
    assert "-an" not in cmd and "-c:a" in cmd


def test_reedit_cmd_speed_applies_setpts_and_atempo(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(str(src), str(tmp_path / "out.mp4"), speed=1.03)
    joined = " ".join(cmd)
    assert "setpts=PTS/1.0300" in joined
    assert "atempo=1.0300" in joined


def test_reedit_cmd_mirror_and_mute(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(
        str(src), str(tmp_path / "out.mp4"), mirror=True, mute=True
    )
    joined = " ".join(cmd)
    assert "hflip" in joined
    assert "-an" in cmd and "atempo" not in joined


def test_reedit_cmd_bgm_replaces_audio(tmp_path):
    src = tmp_path / "in.mp4"
    bgm = tmp_path / "bgm.mp3"
    src.write_bytes(b"x")
    bgm.write_bytes(b"x")
    cmd = reeditor.build_reedit_cmd(
        str(src), str(tmp_path / "out.mp4"), bgm_path=str(bgm)
    )
    assert "-stream_loop" in cmd and "-shortest" in cmd
    assert "-map" in cmd  # 원본 오디오 대신 BGM 매핑


# ── uploaded_registry: 소스 재사용 차단 ──

def test_registry_source_roundtrip(tmp_path):
    reg = reg_mod.UploadedRegistry(path=str(tmp_path / "reg.json"))
    url = "https://www.douyin.com/video/7351234567890123456?from=search"
    assert not reg.is_source_used(url)
    reg.record_source(url, meta={"platform": "douyin"})
    # 쿼리스트링이 달라도 같은 소스로 판정
    assert reg.is_source_used("https://www.douyin.com/video/7351234567890123456?x=1")
    assert reg_mod.normalize_source_id(url) in reg.used_source_ids()
    # 재로드에도 유지(영구 저장)
    reg2 = reg_mod.UploadedRegistry(path=str(tmp_path / "reg.json"))
    assert reg2.is_source_used(url)


def test_normalize_source_id_strips_query_and_case():
    a = reg_mod.normalize_source_id("https://www.KUAISHOU.com/short-video/AbC123?x=1#t")
    b = reg_mod.normalize_source_id("https://www.kuaishou.com/short-video/abc123")
    assert a == b


# ── searcher: 페이지 링크 패턴 + 후보 검증 ──

_SAMPLE_HTML = """
<a href="https://www.douyin.com/video/7351234567890123456">v1</a>
<a href="/video/7359999999999999999?from=search">v2</a>
<a href="https://www.kuaishou.com/short-video/3xf8a9b2c1d5e7">k1</a>
<a href="https://www.xiaohongshu.com/explore/66a1b2c3d4e5f6a7b8c9d0e1">x1</a>
<a href="https://www.bilibili.com/video/BV1xx411c7mD">b1</a>
<a href="//www.bilibili.com/video/BV1yy411c7mE?from=search">b2</a>
"""


def test_page_link_pattern_douyin_dedup():
    pat = searcher._PAGE_LINK_PATTERNS["douyin"]
    ids = {m.group(2) for m in pat.finditer(_SAMPLE_HTML)}
    assert ids == {"7351234567890123456", "7359999999999999999"}


def test_page_link_pattern_kuaishou_and_xhs():
    assert searcher._PAGE_LINK_PATTERNS["kuaishou"].search(_SAMPLE_HTML).group(2) == "3xf8a9b2c1d5e7"
    assert searcher._PAGE_LINK_PATTERNS["xiaohongshu"].search(_SAMPLE_HTML)


def test_page_link_pattern_bilibili():
    ids = {m.group(2) for m in searcher._PAGE_LINK_PATTERNS["bilibili"].finditer(_SAMPLE_HTML)}
    assert ids == {"BV1xx411c7mD", "BV1yy411c7mE"}
    assert "bilibili" in searcher._YTDLP_PLATFORMS
    assert searcher.DEFAULT_PLATFORM_ORDER[-1] == "bilibili"


def test_settings_platform_sources_migration_appends_bilibili(monkeypatch, tmp_path):
    from managers.settings_manager import SettingsManager
    sm = SettingsManager.__new__(SettingsManager)
    sm._settings = {"platform_video_sources": ["douyin", "kuaishou"]}
    import threading
    sm._lock = threading.RLock()
    assert sm.get_platform_video_sources() == ["douyin", "kuaishou", "bilibili"]


def test_validate_source_video_rejects_bad_duration(monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 300_000)
    monkeypatch.setattr(searcher, "probe_media_file",
                        lambda p: {"duration": 200.0, "width": 1080, "height": 1920})
    ok, why = searcher.validate_source_video(str(f))
    assert not ok and "duration" in why


def test_validate_source_video_rejects_low_res(monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 300_000)
    monkeypatch.setattr(searcher, "probe_media_file",
                        lambda p: {"duration": 20.0, "width": 320, "height": 568})
    ok, why = searcher.validate_source_video(str(f))
    assert not ok and "resolution" in why


def test_validate_source_video_accepts_good(monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 300_000)
    monkeypatch.setattr(searcher, "probe_media_file",
                        lambda p: {"duration": 21.0, "width": 720, "height": 1280})
    ok, why = searcher.validate_source_video(str(f))
    assert ok, why


def test_validate_source_video_probe_unavailable_uses_size(monkeypatch, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * 300_000)
    monkeypatch.setattr(searcher, "probe_media_file", lambda p: {})
    ok, why = searcher.validate_source_video(str(f))
    assert ok and why == "probe_unavailable"


# ── cleanup: 보존 기간 지난 산출물 정리 ──

def test_cleanup_old_outputs(tmp_path):
    old = tmp_path / "old.mp4"
    new = tmp_path / "new.mp4"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    past = 1_000_000_000  # 2001년
    os.utime(old, (past, past))
    removed = pp.cleanup_old_outputs(str(tmp_path), retention_days=7)
    assert removed == 1
    assert new.exists() and not old.exists()


# ── 큐 스크립트: 3플랫폼 분기 헬퍼 ──

def test_queue_platform_helpers(tmp_path, monkeypatch):
    from scripts import run_summer_coupang_queue_once as queue_runner

    assert queue_runner.is_platform_system_blocker("브라우저를 시작할 수 없습니다: x")
    assert queue_runner.is_platform_system_blocker("zendriver launch failed")
    assert not queue_runner.is_platform_system_blocker("세 채널 모두에서 영상을 찾지 못했어요")

    # final_video 없음 → render_ok False + 품질 게이트 사유 포함
    report = {"final_video": "", "render_integrity": {"ok": False}}
    rendered = queue_runner.platform_rendered_result(report, tmp_path, "테스트 상품")
    assert rendered["render_ok"] is False
    assert rendered["upload_quality"]["ok"] is False
    assert (tmp_path / "rendered" / "render_result.json").exists()


def test_queue_get_sourcing_method_defaults_to_coupang(monkeypatch):
    from scripts import run_summer_coupang_queue_once as queue_runner

    class _Boom:
        def get_automation_sourcing_method(self):
            raise RuntimeError("no settings")

    import managers.settings_manager as sm
    monkeypatch.setattr(sm, "get_settings_manager", lambda: _Boom())
    assert queue_runner.get_sourcing_method() == "coupang"
