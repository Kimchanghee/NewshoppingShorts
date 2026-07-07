# -*- coding: utf-8 -*-
"""
3플랫폼 로그인 도우미 — 자동화 브라우저 프로필로 도우인/콰이쇼우/샤오홍슈를 열어준다.

여기서 한 번 로그인해 두면(QR 스캔 등) 영구 프로필(~/.ssmaker/zendriver_profile)에
세션이 저장되어, 이후 3플랫폼 자동 소싱의 검색·다운로드 성공률이 크게 올라간다.

사용: python scripts/open_platform_login.py  (로그인 끝나면 창을 그냥 닫으면 됨)
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.utf8_boot import force_utf8
    force_utf8()
except Exception:
    pass

LOGIN_URLS = [
    "https://www.douyin.com/",       # 우상단 로그인 → QR
    "https://www.kuaishou.com/",     # 로그인 → QR
    "https://www.xiaohongshu.com/",  # 로그인 → QR
]


async def main() -> int:
    from core.sourcing.platform_shorts_searcher import start_browser
    browser = await start_browser()
    tabs = []
    for u in LOGIN_URLS:
        try:
            tabs.append(await browser.get(u, new_tab=True))
        except Exception as e:
            print(f"열기 실패 {u}: {e}", flush=True)
    print("세 사이트가 열렸습니다. 각 사이트에 로그인(QR 스캔)해 주세요.", flush=True)
    print("로그인이 끝나면 이 창에서 Enter — 브라우저를 닫고 세션을 저장합니다.", flush=True)
    try:
        await asyncio.to_thread(input)
    except Exception:
        # 파이프 실행 등 stdin이 없으면 10분 대기 후 종료.
        await asyncio.sleep(600)
    try:
        await browser.stop()
    except Exception:
        pass
    print("완료 — 세션이 프로필에 저장되었습니다.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.new_event_loop().run_until_complete(main()))
