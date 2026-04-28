# -*- coding: utf-8 -*-
"""
쿠팡 풀 자동화 CLI 테스트 러너.

GUI 없이 SourcingPipeline 을 직접 돌려서 다음 단계까지 자동 수행:
  1. 쿠팡 상품 분석
  2. (옵션) 쿠팡 파트너스 딥링크
  3. Gemini 키워드 변환 (한국어 → 中/英)
  4. 1688 / AliExpress 검색
  5. 영상 다운로드
  6. 마케팅 설명 생성

다음 단계 (영상 합성 / YouTube / Linktree) 는 별도 스크립트 / Chrome MCP 로 처리.

사용:
    cd ~/Documents/github/NewshoppingShorts
    source .venv/bin/activate
    python run_full_test.py
또는 URL 지정:
    python run_full_test.py "https://www.coupang.com/vp/products/..."
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def _build_gemini_client():
    """config.GEMINI_API_KEYS 또는 GEMINI_API_KEY 환경변수에서 키를 읽어 Gemini 클라이언트 생성.

    프로젝트는 google-genai (new SDK)를 사용. SourcingPipeline 이 기대하는
    `await client.generate_content_async(prompt)` 형태로 래핑.
    """
    import config

    key = ""
    if isinstance(getattr(config, "GEMINI_API_KEYS", {}), dict) and config.GEMINI_API_KEYS:
        key = next(iter(config.GEMINI_API_KEYS.values()), "") or ""
    if not key:
        key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("[!] Gemini API 키가 없습니다. .env 의 GEMINI_API_KEY 또는 SecretsManager 확인 필요.")
        return None

    try:
        from google import genai  # google-genai package
    except ImportError:
        print("[!] google-genai 미설치. pip install google-genai")
        return None

    client = genai.Client(api_key=key)
    model_name = getattr(config, "GEMINI_TEXT_MODEL", "gemini-2.0-flash")

    class GeminiAsyncWrap:
        """SourcingPipeline 이 기대하는 async + .text 응답 인터페이스 래퍼."""
        def __init__(self, c, mn):
            self._c = c
            self._mn = mn

        async def generate_content_async(self, prompt):
            loop = asyncio.get_event_loop()

            def _call():
                # google-genai 새 API: client.models.generate_content(model=..., contents=...)
                return self._c.models.generate_content(
                    model=self._mn, contents=prompt
                )

            return await loop.run_in_executor(None, _call)

    return GeminiAsyncWrap(client, model_name)


def _print_progress(step_id: str, message: str, pct: float):
    bar_total = 20
    done = int(bar_total * pct)
    bar = "█" * done + "░" * (bar_total - done)
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{step_id:>20s}] |{bar}| {pct*100:5.1f}% — {message}")


async def main(coupang_url: str, output_dir: str) -> int:
    print("=" * 70)
    print(f"[+] CoupangFullTest 시작")
    print(f"[+] URL : {coupang_url}")
    print(f"[+] Out : {output_dir}")
    print("=" * 70)

    from core.sourcing.pipeline import SourcingPipeline

    gemini = _build_gemini_client()
    if gemini is None:
        print("[!] Gemini 미설정 — 룰베이스 폴백으로 진행 (1688/AliExpress 검색 정확도 떨어질 수 있음)")

    pipeline = SourcingPipeline(
        coupang_url=coupang_url,
        output_dir=output_dir,
        on_progress=_print_progress,
        gemini_client=gemini,
    )

    success = await pipeline.run_sourcing()

    print()
    print("=" * 70)
    print(f"[+] 최종 결과: {'성공' if success else '실패'}")
    print("=" * 70)

    report = pipeline.get_report()
    report_path = Path(output_dir) / f"report_{datetime.now():%Y%m%d_%H%M%S}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"[+] 리포트: {report_path}")

    if pipeline.product_info:
        print(f"[+] 상품명: {pipeline.product_info.get('name', '')[:60]}")
    if pipeline.deep_link:
        print(f"[+] 딥링크: {pipeline.deep_link}")
    if pipeline.keywords:
        print(f"[+] 키워드: cn={pipeline.keywords.get('chinese','')[:30]} / en={pipeline.keywords.get('english','')[:30]}")
    if pipeline.sourced_products:
        print(f"[+] 다운로드된 영상 ({len(pipeline.sourced_products)}개):")
        for sp in pipeline.sourced_products:
            print(f"    - [{sp['source'].upper()}] {sp['video_file']} ({sp['size_mb']}MB)")
    if pipeline.error:
        print(f"[!] 오류: {pipeline.error}")

    return 0 if success else 1


if __name__ == "__main__":
    DEFAULT_URL = "https://www.coupang.com/vp/products/9423373566?itemId=28009663306"
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    out = os.path.expanduser("~/.ssmaker/sourcing_output")
    os.makedirs(out, exist_ok=True)
    try:
        sys.exit(asyncio.run(main(url, out)))
    except KeyboardInterrupt:
        print("\n[*] 사용자 중단")
        sys.exit(130)
