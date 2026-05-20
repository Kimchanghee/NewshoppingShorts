"""FFmpeg discovery helpers shared by video and audio pipelines."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def _prepend_path(directory: str) -> None:
    if not directory:
        return
    current = os.environ.get("PATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    if directory not in parts:
        os.environ["PATH"] = directory + (os.pathsep + current if current else "")


def _candidate_paths() -> list[Path]:
    exe_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    bases: list[Path] = []

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            bases.append(Path(meipass))
        bases.append(Path(sys.executable).resolve().parent)

    bases.extend(
        [
            Path(__file__).resolve().parents[1],
            Path.cwd(),
            Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"),
            Path("/opt/local/bin"),
            Path("/usr/bin"),
        ]
    )

    candidates: list[Path] = []
    for base in bases:
        candidates.extend(
            [
                base / exe_name,
                base / "resource" / "bin" / exe_name,
                base / "resources" / "bin" / exe_name,
                base / "imageio_ffmpeg" / exe_name,
            ]
        )
    return candidates


def resolve_ffmpeg_exe() -> Optional[str]:
    """Return a usable FFmpeg executable path, including imageio's bundled binary."""
    env_value = os.environ.get("IMAGEIO_FFMPEG_EXE", "").strip()
    if env_value and Path(env_value).is_file():
        return env_value

    system_value = shutil.which("ffmpeg")
    if system_value:
        return system_value

    for candidate in _candidate_paths():
        if candidate.is_file():
            return str(candidate)

    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled
    except Exception:
        return None

    return None


def _ensure_ffmpeg_command(ffmpeg_exe: str) -> None:
    """Make subprocess calls to plain `ffmpeg` work even for imageio binary names."""
    if shutil.which("ffmpeg"):
        return

    wrapper_dir = Path.home() / ".ssmaker" / "bin"
    wrapper_dir.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        wrapper = wrapper_dir / "ffmpeg.bat"
        wrapper.write_text(f'@"{ffmpeg_exe}" %*\r\n', encoding="utf-8")
    else:
        wrapper = wrapper_dir / "ffmpeg"
        try:
            if wrapper.exists() or wrapper.is_symlink():
                wrapper.unlink()
            wrapper.symlink_to(ffmpeg_exe)
        except OSError:
            wrapper.write_text(f'#!/bin/sh\nexec "{ffmpeg_exe}" "$@"\n', encoding="utf-8")
        wrapper.chmod(0o755)

    _prepend_path(str(wrapper_dir))


def ensure_ffmpeg_on_path() -> Optional[str]:
    """Configure environment variables and PATH for FFmpeg consumers."""
    ffmpeg_exe = resolve_ffmpeg_exe()
    if not ffmpeg_exe:
        return None

    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
    _prepend_path(str(Path(ffmpeg_exe).parent))
    _ensure_ffmpeg_command(ffmpeg_exe)
    return ffmpeg_exe
