"""Render integrity checks for automatic uploads.

The automatic upload path must only publish videos produced by the program's
final render pipeline. This module keeps that check local to the video pipeline
so helper scripts or raw source files cannot silently bypass TTS/subtitle/blur
requirements.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from typing import Any, Dict, Iterable, Optional


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if hasattr(value, "get"):
        try:
            return bool(value.get())
        except Exception:
            return default
    return bool(value)


def _abs(path: str) -> str:
    try:
        return os.path.abspath(os.path.expanduser(str(path or "")))
    except Exception:
        return str(path or "")


def _progress_state(app: Any, key: str) -> Dict[str, Any]:
    states = getattr(app, "progress_states", {}) or {}
    state = states.get(key, {}) if isinstance(states, dict) else {}
    return dict(state) if isinstance(state, dict) else {}


def _audio_paths(app: Any) -> list[str]:
    paths: list[str] = []
    sync_info = getattr(app, "tts_sync_info", {}) or {}
    if isinstance(sync_info, dict) and sync_info.get("file_path"):
        paths.append(str(sync_info.get("file_path")))

    for entry in getattr(app, "_per_line_tts", []) or []:
        if not isinstance(entry, dict):
            continue
        for key in ("path", "file_path", "audio_path"):
            value = entry.get(key)
            if value:
                paths.append(str(value))
                break

    seen = set()
    unique: list[str] = []
    for path in paths:
        normalized = _abs(path)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(path)
    return unique


def _path_exists_any(paths: Iterable[str]) -> bool:
    return any(os.path.exists(path) for path in paths if path)


def _probe_video(path: str) -> Dict[str, Any]:
    """Return minimal media facts using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        path,
    ]
    kwargs: Dict[str, Any] = {
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    raw = subprocess.check_output(cmd, **kwargs)
    info = json.loads(raw)
    streams = info.get("streams", []) or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    return {
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "has_video": bool(video_stream),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "duration": float(info.get("format", {}).get("duration") or 0.0),
    }


def create_render_integrity_metadata(
    app: Any,
    video_path: str,
    *,
    subtitle_applied: bool,
    subtitle_count: int,
    voice: str = "",
) -> Dict[str, Any]:
    """Capture render facts immediately after the final MP4 is encoded."""
    sync_info = getattr(app, "tts_sync_info", {}) or {}
    if not isinstance(sync_info, dict):
        sync_info = {}

    per_line_tts = getattr(app, "_per_line_tts", []) or []
    blur_metadata = getattr(app, "latest_blur_metadata", {}) or {}
    if not isinstance(blur_metadata, dict):
        blur_metadata = {}

    metadata = {
        "schema": 1,
        "source": "batch_final_render",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "video_path": video_path,
        "voice": voice or "",
        "tts": {
            "file_path": sync_info.get("file_path", ""),
            "segment_count": len(per_line_tts),
            "audio_paths": _audio_paths(app),
        },
        "subtitles": {
            "requested": _as_bool(getattr(app, "add_subtitles", True), True),
            "applied": bool(subtitle_applied),
            "count": int(subtitle_count or 0),
            "state": _progress_state(app, "subtitle_overlay"),
        },
        "blur": {
            "requested": _as_bool(getattr(app, "apply_blur", True), True),
            "state": _progress_state(app, "subtitle"),
            **blur_metadata,
        },
        "finalize": _progress_state(app, "finalize"),
    }
    return metadata


def _find_render_metadata(
    app: Any,
    video_path: str,
    video_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if isinstance(video_info, dict) and isinstance(video_info.get("render_integrity"), dict):
        return dict(video_info["render_integrity"])

    target = _abs(video_path)
    mapping = getattr(app, "render_integrity_by_path", {}) or {}
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            if _abs(key) == target and isinstance(value, dict):
                return dict(value)

    latest = getattr(app, "final_render_integrity", {}) or {}
    if isinstance(latest, dict) and _abs(latest.get("video_path", "")) == target:
        return dict(latest)

    return {}


def validate_render_ready_for_upload(
    app: Any,
    video_path: str,
    video_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate that a final render has TTS, subtitles, and blur before upload."""
    reasons: list[str] = []
    path = str(video_path or "")
    if not path or not os.path.exists(path):
        reasons.append("missing_video_file")

    metadata = _find_render_metadata(app, path, video_info)
    if not metadata:
        reasons.append("missing_program_render_metadata")
    elif metadata.get("source") != "batch_final_render":
        reasons.append("not_batch_final_render")

    probe: Dict[str, Any] = {}
    if path and os.path.exists(path):
        try:
            probe = _probe_video(path)
            if not probe.get("has_video"):
                reasons.append("missing_video_stream")
            if not probe.get("has_audio"):
                reasons.append("missing_audio_stream")
        except Exception as exc:
            probe = {"error": str(exc)}
            reasons.append("media_probe_failed")

    tts = metadata.get("tts", {}) if isinstance(metadata, dict) else {}
    if int(tts.get("segment_count") or 0) <= 0:
        reasons.append("missing_tts_segments")
    if not _path_exists_any(tts.get("audio_paths") or [tts.get("file_path", "")]):
        reasons.append("missing_tts_audio_file")

    subtitles = metadata.get("subtitles", {}) if isinstance(metadata, dict) else {}
    subtitle_state = subtitles.get("state", {}) if isinstance(subtitles, dict) else {}
    if not subtitles.get("requested", True):
        reasons.append("subtitles_disabled")
    if not subtitles.get("applied"):
        reasons.append("subtitles_not_burned_in")
    if int(subtitles.get("count") or 0) <= 0:
        reasons.append("missing_subtitle_clips")
    if isinstance(subtitle_state, dict) and subtitle_state.get("status") == "error":
        reasons.append("subtitle_overlay_error")

    blur = metadata.get("blur", {}) if isinstance(metadata, dict) else {}
    blur_state = blur.get("state", {}) if isinstance(blur, dict) else {}
    blur_reason = str(blur.get("reason") or "")
    no_blur_needed = bool(blur.get("completed")) and blur_reason == "no_chinese_regions_detected"
    if not blur.get("requested", True):
        reasons.append("blur_disabled")
    if isinstance(blur_state, dict) and blur_state.get("status") == "error":
        reasons.append("blur_error")
    if not blur.get("applied") and not no_blur_needed:
        reasons.append("blur_not_applied")
    if int(blur.get("regions") or 0) <= 0 and not no_blur_needed:
        reasons.append("missing_blur_regions")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "video_path": path,
        "probe": probe,
        "metadata": metadata,
    }


def summarize_integrity_failure(result: Dict[str, Any]) -> str:
    reasons = result.get("reasons") or []
    if not reasons:
        return "render integrity passed"
    return ", ".join(str(reason) for reason in reasons)
