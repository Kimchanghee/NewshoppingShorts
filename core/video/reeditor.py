# -*- coding: utf-8 -*-
"""
3플랫폼 영상 재편집기 — 저작권 완화 + 쇼츠 포맷 통일.

원본(도우인/콰이쇼우 등)을 그대로 재업로드하면 저작권 스트라이크 리스크가 크므로,
반드시 변형을 가한다:
  1) 가장자리 크롭 → 코너 워터마크/로고 제거 + 프레임 변형
  2) 1080x1920(9:16) 리프레임(센터 크롭)
  3) 상단 훅 텍스트 오버레이(한국어, 선택)

ffmpeg 단일 패스. 폰트는 프로젝트 fonts/ 사용.
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Optional

from utils.logging_config import get_logger

try:
    from utils.utf8_boot import utf8_env
except Exception:  # pragma: no cover
    def utf8_env(extra=None):
        e = dict(os.environ)
        if extra:
            e.update(extra)
        return e

logger = get_logger(__name__)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_FONT = os.path.join(_REPO_ROOT, "fonts", "Pretendard-Bold.ttf")


def _ffmpeg_font_path(path: str) -> str:
    """Escape a Windows font path for ffmpeg drawtext fontfile=."""
    p = path.replace("\\", "/")
    p = p.replace(":", "\\:")  # escape drive colon
    return p


def _strip_unrenderable(text: str) -> str:
    """Drop emoji / pictographs the Korean TTF can't render (avoid □ tofu)."""
    out = []
    for ch in str(text or ""):
        o = ord(ch)
        if o > 0xFFFF:  # emoji / supplementary planes
            continue
        if 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF or 0xFE00 <= o <= 0xFE0F:
            continue  # misc symbols / dingbats / variation selectors
        out.append(ch)
    return "".join(out)


def _escape_drawtext(text: str) -> str:
    """Escape text for ffmpeg drawtext."""
    t = _strip_unrenderable(text)
    t = t.replace("\\", "").replace("'", "").replace(":", "\\:").replace("%", "\\%")
    t = re.sub(r"[\r\n]+", " ", t).strip()
    return t[:40]


def build_reedit_cmd(
    input_path: str,
    output_path: str,
    hook_text: str = "",
    crop_margin: float = 0.06,
    font_path: Optional[str] = None,
    speed: float = 1.0,
    mirror: bool = False,
    mute: bool = False,
    bgm_path: Optional[str] = None,
) -> list:
    """reedit용 ffmpeg 명령 생성(테스트 가능하도록 분리)."""
    m = max(0.0, min(0.2, float(crop_margin)))
    font = font_path or _DEFAULT_FONT
    spd = max(0.9, min(1.15, float(speed or 1.0)))

    # 1) 가장자리 크롭(워터마크 제거) → 2) 9:16 커버 스케일 + 센터 크롭
    vf = (
        f"crop=iw*{1 - 2 * m:.4f}:ih*{1 - 2 * m:.4f}:iw*{m:.4f}:ih*{m:.4f},"
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,setsar=1"
    )
    if mirror:
        vf += ",hflip"
    if abs(spd - 1.0) > 1e-6:
        vf += f",setpts=PTS/{spd:.4f}"
    # 3) 훅 텍스트(선택)
    if hook_text and os.path.exists(font):
        txt = _escape_drawtext(hook_text)
        if txt:
            vf += (
                f",drawtext=fontfile='{_ffmpeg_font_path(font)}':text='{txt}':"
                f"fontcolor=white:fontsize=64:borderw=6:bordercolor=black:"
                f"x=(w-text_w)/2:y=140"
            )

    use_bgm = bool(bgm_path and os.path.exists(bgm_path))
    cmd = ["ffmpeg", "-y", "-i", input_path]
    if use_bgm:
        cmd += ["-stream_loop", "-1", "-i", bgm_path]
    cmd += ["-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    if use_bgm:
        # 원본 음성 제거 + BGM 교체(가장 강한 저작권 완화).
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-shortest",
                "-c:a", "aac", "-b:a", "128k"]
    elif mute:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
        if abs(spd - 1.0) > 1e-6:
            cmd += ["-af", f"atempo={spd:.4f}"]
    cmd += ["-movflags", "+faststart", output_path]
    return cmd


def reedit(
    input_path: str,
    output_path: str,
    hook_text: str = "",
    crop_margin: float = 0.06,
    font_path: Optional[str] = None,
    timeout: int = 300,
    speed: float = 1.0,
    mirror: bool = False,
    mute: bool = False,
    bgm_path: Optional[str] = None,
) -> bool:
    """
    Transform a source short into a branding-free 1080x1920 clip.

    Args:
        input_path: source video
        output_path: destination mp4
        hook_text: optional Korean hook overlaid top (skipped if empty/font missing)
        crop_margin: fraction (0~0.2) cropped off each edge to drop corner watermarks
        font_path: TTF for hook text; defaults to project Pretendard-Bold
        speed: 재생 속도(0.9~1.15) — 1.03 권장(Content ID 완화)
        mirror: 좌우 반전(원본과 프레임 차별화)
        mute: 원본 오디오 제거(bgm_path 없을 때만 의미)
        bgm_path: 있으면 원본 음성 제거 후 BGM 교체
    Returns:
        True on success.
    """
    if not os.path.exists(input_path):
        logger.warning("[Reeditor] 입력 없음: %s", input_path)
        return False

    cmd = build_reedit_cmd(
        input_path, output_path, hook_text=hook_text, crop_margin=crop_margin,
        font_path=font_path, speed=speed, mirror=mirror, mute=mute, bgm_path=bgm_path,
    )
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=utf8_env(), timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ok = r.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
        if not ok:
            logger.warning("[Reeditor] 재편집 실패: %s", (r.stderr or "")[-300:])
        return ok
    except Exception as e:
        logger.warning("[Reeditor] 예외: %s", e)
        return False
