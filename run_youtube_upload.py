# -*- coding: utf-8 -*-
"""
쿠팡 풀 자동화 — YouTube 업로드 단독 실행 스크립트.

전제:
  - ~/.ssmaker/.ssmaker_credentials/youtube/client_secrets.json 이 존재 (Cloud Console에서 발급한 Desktop OAuth client)
  - ~/.ssmaker/sourcing_output/ 에 업로드할 영상 파일이 있음

수행:
  1. YouTubeManager.connect_channel() 호출 → 첫 실행 시 브라우저 열려 OAuth 동의 후 토큰 자동 저장 (~/.ssmaker/youtube_token.json)
  2. add_to_upload_queue() 로 큐에 영상 등록 (제목/설명/태그 자동 SEO 생성)
  3. _upload_video() 직접 호출로 즉시 업로드 (스레드 루프 안 거침)
  4. 업로드 완료 후 https://youtu.be/{video_id} 출력

사용:
    cd ~/Documents/github/NewshoppingShorts
    source .venv/bin/activate
    python run_youtube_upload.py
또는 영상 파일 경로 명시:
    python run_youtube_upload.py /Users/aicompany/.ssmaker/sourcing_output/sourcing_aliexpress_2_video.mp4
또는 쿠팡 URL까지 명시:
    python run_youtube_upload.py /path/to/video.mp4 "https://link.coupang.com/a/..."
또는 공개 범위까지 명시:
    python run_youtube_upload.py /path/to/video.mp4 "https://link.coupang.com/a/..." public
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# .env 로드 (Gemini key 등)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


COUPANG_URL = "https://www.coupang.com/vp/products/9423373566?itemId=28009663306"
DEFAULT_VIDEO = os.path.expanduser("~/.ssmaker/sourcing_output/sourcing_aliexpress_2_video.mp4")
PRODUCT_INFO = "쿠팡에서 발견한 추천 상품! 가성비 좋은 인기템 소개합니다."
COUPANG_AFFILIATE_DISCLOSURE = (
    "이 게시물은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)


def _load_context(video_path: str, coupang_url: str = "") -> dict:
    """Best-effort metadata from the newest sourcing report for this video."""
    out_dir = Path(os.path.expanduser("~/.ssmaker/sourcing_output"))
    video_abs = os.path.abspath(os.path.expanduser(video_path))
    reports = sorted(out_dir.glob("report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    def _context_from_report(data: dict) -> dict:
        product = data.get("product_info") or {}
        return {
            "coupang_url": data.get("deep_link") or coupang_url or data.get("coupang_url") or COUPANG_URL,
            "source_url": data.get("coupang_url") or coupang_url or COUPANG_URL,
            "product_name": product.get("name") or "",
            "description": data.get("description") or "",
        }

    for report_path in reports:
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = data.get("sourced_products") or data.get("sourcing_results") or []
        if any(os.path.abspath(str(item.get("video_file", ""))) == video_abs for item in items):
            return _context_from_report(data)

    if coupang_url:
        for report_path in reports:
            try:
                data = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("coupang_url") == coupang_url:
                return _context_from_report(data)

    return {
        "coupang_url": coupang_url or COUPANG_URL,
        "source_url": coupang_url or COUPANG_URL,
        "product_name": "",
        "description": "",
    }


def main(video_path: str, coupang_url: str = "", privacy: str = "unlisted") -> int:
    if not os.path.exists(video_path):
        print(f"[!] 영상 파일이 없습니다: {video_path}")
        return 1

    privacy = (privacy or "unlisted").strip().lower()
    if privacy not in {"private", "unlisted", "public"}:
        print(f"[!] 공개 범위가 올바르지 않습니다: {privacy} (private/unlisted/public)")
        return 1

    context = _load_context(video_path, coupang_url)
    product_name = context.get("product_name") or PRODUCT_INFO
    purchase_url = context.get("coupang_url") or coupang_url or COUPANG_URL
    source_url = context.get("source_url") or purchase_url

    print("=" * 70)
    print("[+] YouTube 업로드 시작")
    print(f"[+] 영상: {video_path} ({os.path.getsize(video_path)/1024/1024:.1f} MB)")
    print(f"[+] 상품: {product_name[:80]}")
    print(f"[+] 링크: {purchase_url}")
    print("=" * 70)

    from managers.youtube_manager import get_youtube_manager, YOUTUBE_API_AVAILABLE

    if not YOUTUBE_API_AVAILABLE:
        print("[!] google-api-python-client / google-auth-oauthlib 미설치. requirements.txt 확인.")
        return 2

    yt = get_youtube_manager()

    # 1) 채널 연결 (첫 실행 시 브라우저 OAuth 동의 창 자동으로 열림)
    print("[1/3] YouTube 채널 OAuth 연결 중... (첫 실행이면 브라우저가 열립니다)")
    if not yt.connect_channel(oauth_timeout_seconds=300):
        print(f"[!] 채널 연결 실패: {yt.get_last_error()}")
        return 3
    info = yt.get_channel_info()
    print(f"[+] 연결됨: {info.get('channel_name', '')} (ID={info.get('id', '')})")
    print(f"    구독자: {info.get('subscriber_count', '0')}, 영상: {info.get('video_count', '0')}")

    # 2) 기본은 unlisted, 승인 증빙처럼 공개 페이지가 필요할 때만 public 지정
    yt._upload_settings.default_privacy = privacy
    yt._upload_settings.made_for_kids = False
    yt._upload_settings.auto_title = True
    yt._upload_settings.auto_description = True
    yt._upload_settings.auto_hashtags = True

    # 3) 큐에 추가 (제목/설명/태그 자동 SEO)
    short_name = product_name[:42] if product_name else "쿠팡 추천 상품"
    title = f"꿀템 발견! {short_name} #shorts"
    desc_lines = [
        COUPANG_AFFILIATE_DISCLOSURE,
        "",
        f"오늘의 쇼핑 추천: {product_name}",
        "",
        "🛒 상품 보기:",
        purchase_url,
        "",
        "🔗 모든 상품 모음:",
        "https://linktr.ee/studio.idol",
        "",
        "─" * 20,
        "실사용에 가까운 쇼핑 정보와 자동화된 상품 소개 영상을 제공합니다.",
    ]
    description = "\n".join(desc_lines)
    tags = ["쇼핑", "추천", "꿀템", "쿠팡", "쇼츠", "shorts", "자동화", "automation"]

    yt.add_to_upload_queue(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        product_info=product_name,
        source_url=source_url,
        coupang_deep_link=purchase_url,
    )

    print(f"[2/3] 업로드 큐 등록됨: {title}")

    # 4) 큐의 첫 번째 아이템을 즉시 업로드 (백그라운드 스레드 안 돌림)
    if not yt._upload_queue:
        print("[!] 큐가 비어있습니다.")
        return 4

    item = yt._upload_queue.pop(0)
    print(f"[3/3] 업로드 진행 중... (대용량이면 시간 걸립니다)")

    success = yt._upload_video(item)
    if not success:
        print("[!] 업로드 실패. ~/.ssmaker/logs/ssmaker.log 확인.")
        return 5

    print("=" * 70)
    print("[✓] YouTube 업로드 완료!")
    print("    채널: https://www.youtube.com/channel/" + (info.get("id") or ""))
    print(f"    공개설정: {privacy}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    video = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VIDEO
    url = sys.argv[2] if len(sys.argv) > 2 else ""
    privacy = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("YOUTUBE_PRIVACY", "unlisted")
    sys.exit(main(video, url, privacy))
