#!/usr/bin/env python3
"""Render a clean Coupang Partners compliant vertical short."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import wave
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from google import genai
from google.genai import types

import config
from utils.ffmpeg import ensure_ffmpeg_on_path
from utils.secrets_manager import SecretsManager


WIDTH = 1080
HEIGHT = 1920
FPS = 30
DISCLOSURE = "쿠팡 파트너스 활동의 일환으로 수수료를 제공받습니다."
TTS_MODEL = getattr(config, "GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview")


KNOWN_PRODUCTS = {
    "eyloSW": {
        "title": "리치덕 싱크대 물빠짐 304 스텐 수세미거치대",
        "link": "https://link.coupang.com/a/eyloSW",
        "image": "~/.ssmaker/review_drafts/20260429_retry_products/eyloSW_product.jpg",
    },
    "eyoqoE": {
        "title": "존글로벌 음식물 거름망 거치대 + 거름망",
        "link": "https://link.coupang.com/a/eyoqoE",
        "image": "~/.ssmaker/review_drafts/20260429_retry_products/eyoqoE_product.jpg",
    },
    "eyoqVk": {
        "title": "구띵 스테인레스 접착식 다용도 수세미 거치대 2개",
        "link": "https://link.coupang.com/a/eyoqVk",
        "image": "~/.ssmaker/review_drafts/20260429_retry_products/eyoqVk_product.jpg",
    },
}


def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        words = paragraph.split()
        current = ""
        for word in words:
            probe = f"{current} {word}".strip()
            box = font.getbbox(probe)
            if box[2] - box[0] <= max_width or not current:
                current = probe
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def _text_center(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] = (255, 255, 255),
    max_width: int = 900,
    line_gap: int = 12,
) -> int:
    lines = _wrap(text, font, max_width)
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        x = (WIDTH - (box[2] - box[0])) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += (box[3] - box[1]) + line_gap
    return y


def _rounded_rect(
    image: Image.Image,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle(xy, radius=radius, fill=fill)
    image.alpha_composite(overlay)


def _load_api_key() -> str:
    for key in getattr(config, "GEMINI_API_KEYS", {}).values():
        if key and key.strip():
            return key.strip()
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    for i in range(1, 9):
        key = SecretsManager.get_api_key(f"gemini_api_{i}")
        if key and key.strip():
            return key.strip()
    legacy = SecretsManager.get_api_key("gemini")
    return legacy.strip() if legacy else ""


def _save_wav(path: Path, audio_data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if audio_data[:4] == b"RIFF":
        path.write_bytes(audio_data)
        return
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio_data)


def _audio_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def generate_tts(script: str, output_path: Path, voice: str) -> float:
    key = _load_api_key()
    if not key:
        raise RuntimeError("Gemini API key is not configured")

    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=[script],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    try:
        audio_data = response.candidates[0].content.parts[0].inline_data.data
    except (AttributeError, IndexError) as exc:
        raise RuntimeError("Gemini TTS response did not include audio") from exc
    if not audio_data:
        raise RuntimeError("Gemini TTS returned empty audio")

    _save_wav(output_path, audio_data)
    return _audio_duration(output_path)


def render_silent_video(
    product_image: Path,
    title: str,
    script_lines: list[str],
    duration: float,
    output_path: Path,
) -> None:
    import cv2
    import numpy as np

    image = Image.open(product_image).convert("RGB")
    bg_base = ImageOps.fit(image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    bg_base = bg_base.filter(ImageFilter.GaussianBlur(34))
    bg_base = ImageEnhance.Brightness(bg_base).enhance(0.54)
    bg_base = ImageEnhance.Color(bg_base).enhance(0.78)

    fg_base = image.copy()
    fg_base.thumbnail((820, 820), Image.Resampling.LANCZOS)

    title_font = _font(68, "bold")
    caption_font = _font(58, "bold")
    small_font = _font(34)
    disclosure_font = _font(28)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".silent.tmp.mp4")
    writer = cv2.VideoWriter(
        str(temp_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (WIDTH, HEIGHT),
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV VideoWriter could not open output")

    total_frames = int(math.ceil(duration * FPS))
    phases = [
        (0.00, 0.25, script_lines[0]),
        (0.25, 0.52, script_lines[1]),
        (0.52, 0.78, script_lines[2]),
        (0.78, 1.01, script_lines[3]),
    ]

    for frame_index in range(total_frames):
        progress = frame_index / max(1, total_frames - 1)
        frame = bg_base.copy().convert("RGBA")
        draw = ImageDraw.Draw(frame)

        zoom = 1.0 + 0.07 * progress + 0.012 * math.sin(progress * math.pi * 4)
        fg_size = (int(fg_base.width * zoom), int(fg_base.height * zoom))
        fg = fg_base.resize(fg_size, Image.Resampling.LANCZOS).convert("RGBA")

        shadow = Image.new("RGBA", (fg.width + 70, fg.height + 70), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (35, 35, fg.width + 35, fg.height + 35),
            radius=44,
            fill=(0, 0, 0, 145),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(24))
        x = (WIDTH - fg.width) // 2
        y = 390 + int(18 * math.sin(progress * math.pi * 2)) - fg.height // 12
        frame.alpha_composite(shadow, (x - 35, y - 35))

        white_card = Image.new("RGBA", (fg.width + 36, fg.height + 36), (255, 255, 255, 232))
        mask = Image.new("L", white_card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *white_card.size), radius=42, fill=255)
        frame.paste(white_card, (x - 18, y - 18), mask)
        frame.alpha_composite(fg, (x, y))

        _rounded_rect(frame, (56, 66, 318, 132), 26, (7, 31, 45, 220))
        draw.text((86, 80), "[광고] 쇼핑", font=small_font, fill=(255, 255, 255))

        _text_center(draw, title, 185, title_font, max_width=940)

        current_caption = script_lines[-1]
        for start, end, text in phases:
            if start <= progress < end:
                current_caption = text
                break

        _rounded_rect(frame, (72, 1398, WIDTH - 72, 1592), 34, (0, 0, 0, 185))
        _text_center(draw, current_caption, 1438, caption_font, max_width=860)

        draw.text((82, 1758), DISCLOSURE, font=disclosure_font, fill=(255, 255, 255))
        draw.text((82, 1810), "상품 링크는 설명란에서 확인", font=small_font, fill=(255, 255, 255))

        writer.write(cv2.cvtColor(np.array(frame.convert("RGB")), cv2.COLOR_RGB2BGR))

    writer.release()
    os.replace(temp_path, output_path)


def mux_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    ffmpeg = ensure_ffmpeg_on_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg is not available")

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
        str(output_path),
    ]
    env = os.environ.copy()
    env["PATH"] = str(Path.home() / ".ssmaker" / "bin") + os.pathsep + env.get("PATH", "")
    subprocess.run(cmd, check=True, env=env)


def _default_script(title: str) -> tuple[str, list[str]]:
    clean_title = title.replace("-", " ").strip()
    narration = (
        f"{clean_title}. 싱크대 주변에 붙여두면 수세미를 더 깔끔하게 말릴 수 있어요. "
        "물 빠짐이 좋아서 젖은 수세미가 바닥에 닿지 않고, 스테인레스 느낌이라 주방이 훨씬 정돈돼 보입니다. "
        "상품 링크는 설명란에서 확인하세요."
    )
    captions = [
        "싱크대 주변 정리용 수세미 거치대",
        "젖은 수세미를 바닥에서 띄워 보관",
        "물 빠짐과 건조가 더 깔끔하게",
        "상품 링크는 설명란에서 확인",
    ]
    return narration, captions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", default="eyoqVk", choices=sorted(KNOWN_PRODUCTS))
    parser.add_argument("--title", default="")
    parser.add_argument("--link", default="")
    parser.add_argument("--image", default="")
    parser.add_argument("--voice", default="Kore")
    parser.add_argument("--out-dir", default="~/.ssmaker/review_drafts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    product = dict(KNOWN_PRODUCTS[args.code])
    if args.title:
        product["title"] = args.title
    if args.link:
        product["link"] = args.link
    if args.image:
        product["image"] = args.image

    title = product["title"]
    image_path = Path(os.path.expanduser(product["image"])).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Product image not found: {image_path}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(os.path.expanduser(args.out_dir)) / f"{stamp}_clean_coupang_partner"
    out_dir.mkdir(parents=True, exist_ok=True)

    narration, captions = _default_script(title)
    audio_path = out_dir / f"{args.code}_narration.wav"
    silent_video = out_dir / f"{args.code}_clean_silent.mp4"
    final_video = out_dir / f"{args.code}_clean_partner_short.mp4"

    print(f"[1/4] Gemini TTS: {args.voice}")
    audio_duration = generate_tts(narration, audio_path, args.voice)
    duration = max(16.0, min(24.0, audio_duration + 0.8))
    print(f"      audio={audio_duration:.2f}s video={duration:.2f}s")

    print("[2/4] Rendering clean vertical video")
    render_silent_video(image_path, title, captions, duration, silent_video)

    print("[3/4] Muxing audio")
    mux_audio(silent_video, audio_path, final_video)

    print("[4/4] Writing metadata")
    metadata = {
        "code": args.code,
        "title": title,
        "coupang_url": product["link"],
        "product_image": str(image_path),
        "narration": narration,
        "audio": str(audio_path),
        "silent_video": str(silent_video),
        "video": str(final_video),
        "duration_sec": round(duration, 2),
        "disclosure": DISCLOSURE,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"OK: {final_video}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: ffmpeg failed with exit code {exc.returncode}")
        raise SystemExit(exc.returncode)
