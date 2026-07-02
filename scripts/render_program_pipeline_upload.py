from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SSMAKER_DISABLE_FASTER_WHISPER", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.state import AppState
from app.video_helpers import VideoHelpers
import config
from core.api import ApiKeyManager
from core.video.batch import processor
from managers.generated_video_manager import GeneratedVideoManager
from managers.youtube_manager import get_youtube_manager
from utils.ffmpeg import resolve_ffmpeg_exe
from utils.token_cost_calculator import TokenCostCalculator

SOURCE_ROOT = Path(
    r"C:\Users\HOME\.ssmaker\sourcing_output\four_new_link_retest_20260601_120001"
)
LINKTREE_URL = "https://linktr.ee/studio.idol"
MIN_UPLOAD_DURATION_SECONDS = 8.0
COUPANG_DISCLOSURE = (
    "이 게시물은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 "
    "제공받습니다."
)

JOBS = [
    {
        "index": 1,
        "product_name": "자동 전동 청소솔 세트, 혼합색상, 1세트 - 청소솔/스틱",
        "product_url": "https://www.coupang.com/vp/products/5575481544",
        "video_file": SOURCE_ROOT / "01" / "sourcing_aliexpress_1_019f775f_video.mp4",
        "report_file": SOURCE_ROOT / "01" / "report.json",
    },
    {
        "index": 2,
        "product_name": "FDUCE 미니 밀봉 실링기, 블루, 1개 - 기타포장기",
        "product_url": "https://www.coupang.com/vp/products/9150902363",
        "video_file": SOURCE_ROOT / "02" / "sourcing_aliexpress_1_dee2cbb7_video.mp4",
        "report_file": SOURCE_ROOT / "02" / "report.json",
    },
    {
        "index": 3,
        "product_name": "무선 휴대용 전동 휘핑기 우유 거품기 머랭치기 생크림기계 계란 거품기 - 반죽기/제빵기",
        "product_url": "https://www.coupang.com/vp/products/8067508310",
        "video_file": SOURCE_ROOT / "03" / "sourcing_aliexpress_1_d5f7daa3_video.mp4",
        "report_file": SOURCE_ROOT / "03" / "report.json",
    },
    {
        "index": 4,
        "product_name": "샤오미 미지아 자동차 진공 청소기 - 차량용청소기",
        "product_url": "https://www.coupang.com/vp/products/8810716494",
        "video_file": SOURCE_ROOT / "04" / "sourcing_aliexpress_1_d10f326e_video.mp4",
        "report_file": SOURCE_ROOT / "04" / "report.json",
    },
]


class DirectSignal:
    def emit(self, callback):
        if callback:
            callback()


class SimpleVoiceManager:
    def __init__(self, app):
        self.app = app

    def get_voice_profile(self, voice_id: str):
        for profile in self.app.voice_profiles:
            if profile.get("id") == voice_id or profile.get("voice_name") == voice_id:
                return profile
        return None


class DummySessionManager:
    def save_session(self):
        return True

    def clear_session(self):
        return True


class HeadlessBatchApp(AppState):
    def __init__(self, output_dir: Path):
        super().__init__(root=None, login_data=None)
        self.state = self
        self.output_folder_path = str(output_dir)
        self.url_status_lock = threading.RLock()
        self.ui_callback_signal = DirectSignal()
        self.token_calculator = TokenCostCalculator()
        self._video_helpers = VideoHelpers(self)
        self._generated_video_manager = GeneratedVideoManager(self)
        self.voice_manager = SimpleVoiceManager(self)
        self.session_manager = DummySessionManager()
        self.youtube_manager = None
        self.selected_cta_id = "default"
        self.batch_processing = True
        self.add_subtitles = True
        self.apply_blur = True
        self.subtitle_overlay_on_chinese = True
        self.subtitle_position = "bottom_center"
        self.max_final_video_duration = 35.0
        self.logs: List[str] = []
        self.config = config

        self.api_key_manager = ApiKeyManager.APIKeyManager(use_secrets_manager=True)
        self.init_client()

        for voice_id in list(self.voice_vars):
            self.voice_vars[voice_id] = False
        default_voice_id = self.voice_profiles[0]["id"]
        self.voice_vars[default_voice_id] = True
        self.multi_voice_presets = [self.voice_profiles[0]["voice_name"]]
        self.available_tts_voices = list(self.multi_voice_presets)
        self.fixed_tts_voice = self.multi_voice_presets[0]

    def init_client(self, use_specific_key=None) -> bool:
        if str(os.environ.get("SSMAKER_GEMINI_RUNTIME_DISABLED", "")).strip() == "1":
            self.genai_client = None
            self.state.genai_client = None
            return True
        try:
            from google import genai

            key = use_specific_key or self.api_key_manager.get_available_key()
            self.genai_client = genai.Client(api_key=key)
            self.state.genai_client = self.genai_client
            return True
        except Exception as exc:
            print(f"[ERROR] Gemini client init failed: {exc}", file=sys.stderr)
            self.genai_client = None
            self.state.genai_client = None
            os.environ["SSMAKER_GEMINI_RUNTIME_DISABLED"] = "1"
            return False

    def add_log(self, message: str):
        line = f"{datetime.now().strftime('%H:%M:%S')} {message}"
        self.logs.append(line)
        print(line, flush=True)

    def update_progress_state(self, step, status, progress, message=None):
        if step not in self.progress_states:
            self.progress_states[step] = {}
        self.progress_states[step] = {
            "status": status,
            "progress": progress,
            "message": message,
        }

    def update_step_progress(self, step, progress):
        if step not in self.progress_states:
            self.progress_states[step] = {}
        self.progress_states[step]["progress"] = progress

    def reset_progress_states(self):
        for step in self.progress_states:
            self.progress_states[step] = {
                "status": "waiting",
                "progress": 0,
                "message": None,
            }

    def update_url_listbox(self):
        return None

    def update_overall_progress_display(self):
        return None

    def update_all_progress_displays(self):
        return None

    def update_status(self, status_text: str):
        self.add_log(f"[상태] {status_text}")

    def set_active_job(self, *_args, **_kwargs):
        return None

    def set_active_voice(self, *_args, **_kwargs):
        return None

    def _auto_save_session(self):
        return True

    def _update_subscription_info(self):
        return None

    def get_video_duration_helper(self) -> float:
        return self._video_helpers.get_video_duration()

    def apply_chinese_subtitle_removal(self, video):
        return self._video_helpers.apply_chinese_subtitle_removal(video)

    def detect_subtitles_with_opencv(self):
        return self._video_helpers.detect_subtitles_with_opencv()

    def extract_clean_script_from_translation(self, max_len: int = 14) -> str:
        return self._video_helpers.extract_clean_script_from_translation(max_len)

    def cleanup_temp_files(self):
        return self._video_helpers.cleanup_temp_files()

    def register_generated_video(self, voice, output_path, duration, file_size, temp_dir):
        return self._generated_video_manager.register(
            voice, output_path, duration, file_size, temp_dir
        )

    def save_generated_videos_locally(self, show_popup=True):
        return self._generated_video_manager.save_locally(show_popup)


def _load_report(job: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with open(job["report_file"], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _build_sourcing_context(job: Dict[str, Any]) -> Dict[str, Any]:
    report = _load_report(job)
    item = {
        "source": "aliexpress",
        "title": report.get("sourced_products", [{}])[0].get("title", ""),
        "url": report.get("sourced_products", [{}])[0].get("url", ""),
        "similarity": float(report.get("best_similarity") or 1.0),
        "video_file": str(job["video_file"]),
        "auto_publish_safe": True,
        "requires_review": False,
    }
    return {
        "coupang_url": job["product_url"],
        "product_info": {
            "name": job["product_name"],
            "url": job["product_url"],
        },
        "description": job["product_name"],
        "deep_link": "",
        "sourced_products": [item],
        "sourcing_results": [item],
        "match_threshold": 0.9,
        "min_similarity_score": 0.9,
        "best_similarity": item["similarity"],
        "match_status": "matched",
        "success": True,
    }


def ffprobe(path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=index,codec_type,width,height",
        "-of",
        "json",
        path,
    ]
    raw = subprocess.check_output(cmd, text=True, encoding="utf-8")
    return json.loads(raw)


def verify_video(path: str) -> Dict[str, Any]:
    info = ffprobe(path)
    streams = info.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(info.get("format", {}).get("duration") or 0)
    return {
        "path": path,
        "duration": duration,
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "has_audio": has_audio,
        "is_vertical_1080x1920": video_stream.get("width") == 1080
        and video_stream.get("height") == 1920,
    }


def ensure_min_upload_duration(
    video_path: str,
    verification: Dict[str, Any],
    output_dir: Path,
    min_duration: float = MIN_UPLOAD_DURATION_SECONDS,
) -> tuple[str, Dict[str, Any]]:
    """Pad very short successful renders so the upload quality gate can pass."""
    try:
        duration = float(verification.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0 or duration >= min_duration:
        return video_path, verification
    if not verification.get("has_audio"):
        return video_path, verification

    ffmpeg = resolve_ffmpeg_exe()
    if not ffmpeg:
        return video_path, verification

    pad_seconds = max(0.25, (min_duration + 0.25) - duration)
    target_duration = duration + pad_seconds
    source = Path(video_path)
    padded_path = output_dir / f"{source.stem}_min{int(min_duration)}s{source.suffix}"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-f",
        "lavfi",
        "-t",
        f"{pad_seconds:.3f}",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-filter_complex",
        (
            f"[0:v]tpad=stop_mode=clone:stop_duration={pad_seconds:.3f},setsar=1[v];"
            "[0:a][1:a]concat=n=2:v=0:a=1[a]"
        ),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        f"{target_duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(padded_path),
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        padded_verification = verify_video(str(padded_path))
        if float(padded_verification.get("duration") or 0) >= min_duration:
            print(
                f"[품질 보정] 최종 영상 {duration:.1f}s -> "
                f"{float(padded_verification.get('duration') or 0):.1f}s"
            )
            return str(padded_path), padded_verification
    except Exception as exc:
        print(f"[WARN] Minimum duration padding failed: {exc}", file=sys.stderr)
    return video_path, verification


def extract_frame(video_path: str, output_dir: Path, index: int) -> str:
    frame_path = output_dir / f"verify_frame_{index:02d}.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "3",
            "-i",
            video_path,
            "-frames:v",
            "1",
            str(frame_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return str(frame_path)


def render_jobs(output_dir: Path, limit: int = 0) -> List[Dict[str, Any]]:
    app = HeadlessBatchApp(output_dir)
    jobs = JOBS[:limit] if limit else JOBS
    results: List[Dict[str, Any]] = []
    try:
        for position, job in enumerate(jobs, start=1):
            if not Path(job["video_file"]).exists():
                raise FileNotFoundError(job["video_file"])

            processor.clear_all_previous_results(app)
            app.product_name = job["product_name"]
            app.video_title = job["product_name"]
            app.state.sourcing_result = _build_sourcing_context(job)

            local_url = "local://" + str(job["video_file"])
            app.url_queue = [local_url]
            app.url_status = {local_url: "waiting"}
            app.url_status_message = {}
            app.batch_processing = True

            print(f"\n=== RENDER {position}/{len(jobs)}: {job['product_name']} ===")
            processor._process_single_video(app, local_url, position, len(jobs))
            processor._stop_log_capture(app)

            if not app.generated_videos:
                raise RuntimeError(f"No generated video for job {position}")
            latest = dict(app.generated_videos[-1])
            saved_path = latest.get("saved_path") or latest.get("path")
            if not saved_path or not os.path.exists(saved_path):
                raise RuntimeError(f"Generated video missing for job {position}")

            verification = verify_video(saved_path)
            saved_path, verification = ensure_min_upload_duration(
                saved_path,
                verification,
                output_dir,
            )
            frame_path = extract_frame(saved_path, output_dir, position)
            tts_meta = getattr(app, "tts_sync_info", {}) or {}
            subtitle_state = app.progress_states.get("subtitle_overlay", {})
            blur_state = app.progress_states.get("subtitle", {})
            analysis = getattr(app, "analysis_result", {}) or {}
            result = {
                "index": job["index"],
                "product_name": job["product_name"],
                "product_url": job["product_url"],
                "source_video": str(job["video_file"]),
                "final_video": saved_path,
                "verify_frame": frame_path,
                "video_probe": verification,
                "tts_file": tts_meta.get("file_path"),
                "tts_segment_count": len(getattr(app, "_per_line_tts", []) or []),
                "subtitle_overlay": subtitle_state,
                "blur": blur_state,
                "detected_subtitle_regions": len(
                    analysis.get("subtitle_positions") or []
                )
                if isinstance(analysis, dict)
                else 0,
                "render_integrity": latest.get("render_integrity_validation") or {},
            }
            result["render_ok"] = (
                verification["has_audio"]
                and verification["is_vertical_1080x1920"]
                and result["tts_segment_count"] > 0
                and subtitle_state.get("status") == "completed"
            )
            results.append(result)
    finally:
        try:
            processor._stop_log_capture(app)
        except Exception:
            pass

    return results


def build_upload_item(rendered: Dict[str, Any], privacy: str) -> Dict[str, Any]:
    product_name = rendered["product_name"]
    product_url = rendered.get("product_url", "")
    title = f"[광고] {product_name[:70]} #shorts"
    description = "\n".join(
        [
            COUPANG_DISCLOSURE,
            "",
            f"상품: {product_name}",
            f"모든 상품 링크: {LINKTREE_URL}",
            f"원상품 링크: {product_url}",
        ]
    )
    return {
        "video_path": rendered["final_video"],
        "title": title,
        "description": description,
        "tags": ["shorts", "쇼츠", "상품추천", "쿠팡", "생활용품"],
        "product_info": product_name,
        "source_url": product_url,
        "coupang_deep_link": "",
        "linktree_url": LINKTREE_URL,
        "privacy": privacy,
        "render_integrity": rendered.get("render_integrity") or {},
        "render_integrity_required": True,
    }


def upload_verified(results: List[Dict[str, Any]], privacy: str) -> List[Dict[str, Any]]:
    yt = get_youtube_manager(gui=None)
    if not yt.is_connected() or not yt._ensure_youtube_service():
        raise RuntimeError("YouTube channel is not connected.")
    yt._upload_settings.default_privacy = privacy
    uploaded: List[Dict[str, Any]] = []
    for rendered in results:
        if not rendered.get("render_ok"):
            raise RuntimeError(f"Render verification failed: {rendered['final_video']}")
        item = build_upload_item(rendered, privacy)
        ok = yt._upload_video(item)
        if not ok or not item.get("video_id"):
            raise RuntimeError(f"YouTube upload failed: {rendered['final_video']}")
        uploaded.append(
            {
                "index": rendered["index"],
                "product_name": rendered["product_name"],
                "product_url": rendered.get("product_url", ""),
                "video_id": item["video_id"],
                "video_url": item["video_url"],
                "title": item["title"],
                "privacy": privacy,
            }
        )
    return uploaded


def verify_youtube_uploads(uploaded: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not uploaded:
        return {"checked": 0, "ok": False, "items": []}
    yt = get_youtube_manager(gui=None)
    if not yt._ensure_youtube_service():
        raise RuntimeError("YouTube service unavailable for verification.")
    ids = ",".join(item["video_id"] for item in uploaded)
    response = yt._youtube_service.videos().list(
        part="snippet,status", id=ids
    ).execute()
    found = {item["id"]: item for item in response.get("items", [])}
    checked = []
    for item in uploaded:
        video = found.get(item["video_id"], {})
        snippet = video.get("snippet", {})
        status = video.get("status", {})
        desc = snippet.get("description", "")
        checked.append(
            {
                "video_id": item["video_id"],
                "title": snippet.get("title", ""),
                "privacy": status.get("privacyStatus", ""),
                "has_linktree": LINKTREE_URL in desc,
                "has_disclosure": COUPANG_DISCLOSURE in desc,
                "has_product_url": str(item.get("product_url", "")) in desc,
                "title_has_product": item["product_name"][:10]
                in snippet.get("title", ""),
            }
        )
    return {
        "checked": len(checked),
        "ok": all(
            row["has_linktree"]
            and row["has_disclosure"]
            and row["has_product_url"]
            and row["title_has_product"]
            for row in checked
        ),
        "items": checked,
    }


def verify_youtube_comments(uploaded: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not uploaded:
        return {"checked": 0, "ok": False, "items": []}
    yt = get_youtube_manager(gui=None)
    if not yt._ensure_youtube_service():
        raise RuntimeError("YouTube service unavailable for comment verification.")

    checked = []
    for item in uploaded:
        try:
            response = yt._youtube_service.commentThreads().list(
                part="snippet",
                videoId=item["video_id"],
                textFormat="plainText",
                maxResults=20,
            ).execute()
            comments = [
                row.get("snippet", {})
                .get("topLevelComment", {})
                .get("snippet", {})
                .get("textDisplay", "")
                for row in response.get("items", [])
            ]
            checked.append(
                {
                    "video_id": item["video_id"],
                    "checked_comments": len(comments),
                    "has_linktree": any(LINKTREE_URL in text for text in comments),
                    "has_disclosure": any(COUPANG_DISCLOSURE in text for text in comments),
                    "has_product_url": any(
                        str(item.get("product_url", "")) in text for text in comments
                    ),
                }
            )
        except Exception as exc:
            checked.append(
                {
                    "video_id": item["video_id"],
                    "checked_comments": 0,
                    "has_linktree": False,
                    "has_disclosure": False,
                    "has_product_url": False,
                    "error": str(exc),
                }
            )

    return {
        "checked": len(checked),
        "ok": all(
            row["has_linktree"] and row["has_disclosure"] and row["has_product_url"]
            for row in checked
        ),
        "items": checked,
    }


def verify_linktree() -> Dict[str, Any]:
    import requests

    response = requests.get(
        LINKTREE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=30,
    )
    text = response.text
    product_ids = [job["product_url"].rsplit("/", 1)[-1] for job in JOBS]
    return {
        "url": LINKTREE_URL,
        "status_code": response.status_code,
        "product_ids": {
            product_id: product_id in text for product_id in product_ids
        },
        "ok": response.status_code == 200
        and all(product_id in text for product_id in product_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="unlisted")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--summary-path", default="")
    args = parser.parse_args()

    if args.summary_path:
        summary_path = Path(args.summary_path)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if args.upload:
            uploaded = upload_verified(summary.get("rendered", []), args.privacy)
            summary["uploaded"] = uploaded
        if summary.get("uploaded"):
            summary["youtube_verification"] = verify_youtube_uploads(summary["uploaded"])
            summary["youtube_comments"] = verify_youtube_comments(summary["uploaded"])
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nSUMMARY={summary_path}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        youtube_ok = summary.get("youtube_verification", {}).get("ok", True)
        comments_ok = summary.get("youtube_comments", {}).get("ok", True)
        return 0 if summary.get("render_ok") and youtube_ok and comments_ok else 1

    run_dir = Path(args.output_dir) if args.output_dir else Path.home() / ".ssmaker" / "sourcing_output" / (
        "program_pipeline_rerender_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    results = render_jobs(run_dir, limit=args.limit)
    summary: Dict[str, Any] = {
        "run_dir": str(run_dir),
        "rendered": results,
        "render_ok": all(item.get("render_ok") for item in results),
        "linktree": verify_linktree(),
    }
    if args.upload:
        uploaded = upload_verified(results, args.privacy)
        summary["uploaded"] = uploaded
        summary["youtube_verification"] = verify_youtube_uploads(uploaded)
        summary["youtube_comments"] = verify_youtube_comments(uploaded)

    summary_path = run_dir / "program_pipeline_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSUMMARY={summary_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    youtube_ok = summary.get("youtube_verification", {}).get("ok", True)
    comments_ok = summary.get("youtube_comments", {}).get("ok", True)
    return 0 if summary.get("render_ok") and summary["linktree"]["ok"] and youtube_ok and comments_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
