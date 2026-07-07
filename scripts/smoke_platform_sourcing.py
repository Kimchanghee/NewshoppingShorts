# -*- coding: utf-8 -*-
"""
3플랫폼 소싱 실전 스모크 — 업로드 없이 '쿠팡 링크 → 검색 → 다운로드 → 재편집'까지 검증.

사용:
    python scripts/smoke_platform_sourcing.py <쿠팡 상품 URL> [--platforms douyin,kuaishou]

주의: 실제 Chrome 창이 뜬다(영구 프로필). YouTube 업로드는 하지 않는다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.utf8_boot import force_utf8  # 인코딩 근본 차단
    force_utf8()
except Exception:
    pass

# INFO 로그(플랫폼별 검색 상세)가 보이도록 로깅 초기화.
try:
    from pathlib import Path as _P
    from utils.logging_config import AppLogger
    AppLogger.setup(log_dir=_P("logs"), level="INFO", console_level="INFO")
except Exception:
    import logging as _lg
    _lg.basicConfig(level=_lg.INFO)


def _make_gemini_client():
    """큐 스크립트와 동일 경로로 Gemini 클라이언트 생성(없으면 None)."""
    try:
        from google import genai
        from core.api import ApiKeyManager
        key = ApiKeyManager.APIKeyManager(use_secrets_manager=True).get_available_key()
        return genai.Client(api_key=key) if key else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("coupang_url")
    ap.add_argument("--platforms", default="", help="쉼표구분(douyin,kuaishou,xiaohongshu)")
    ap.add_argument("--skip-dedup", action="store_true", help="소스 재사용 차단 무시(반복 스모크용)")
    args = ap.parse_args()

    from core.sourcing.platform_pipeline import run_platform_sourcing

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()] or None

    def progress(step: str, msg: str, pct: float) -> None:
        print(f"[{step}] {pct:.0%} {msg}", flush=True)

    async def _run():
        kwargs = {}
        if args.skip_dedup:
            # 레지스트리 스킵셋을 비우기 위해 임시 monkeypatch 없이 옵션 경로 제공이 없으므로,
            # 여기서는 검색 전 스킵셋만 무력화한다.
            import managers.uploaded_registry as reg
            reg.get_uploaded_registry().used_source_ids = lambda: set()  # type: ignore
        return await run_platform_sourcing(
            args.coupang_url, progress=progress, platforms=platforms,
            gemini_client=_make_gemini_client(), **kwargs
        )

    report = asyncio.new_event_loop().run_until_complete(_run())
    out = {k: report.get(k) for k in
           ("ok", "error", "deep_link", "keywords", "queries", "hit", "final_video")}
    out["product_name"] = (report.get("product_info") or {}).get("name", "")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str), flush=True)

    fv = report.get("final_video") or ""
    if report.get("ok") and fv and os.path.exists(fv):
        print(f"SMOKE_OK size={os.path.getsize(fv)/1e6:.1f}MB path={fv}", flush=True)
        return 0
    print("SMOKE_FAIL", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
