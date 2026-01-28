"""
Audio Utilities for TTS Processing

Contains audio processing utilities like ffmpeg setup, silence trimming,
and audio segment preparation.
"""

import os
from typing import Optional

from pydub import AudioSegment
from pydub.utils import which
from pydub.silence import detect_leading_silence

from caller import ui_controller


def _ensure_pydub_converter() -> Optional[str]:
    """pydub가 사용할 ffmpeg 경로를 확보 (imageio-ffmpeg 우선)."""
    try:
        converter = getattr(AudioSegment, "converter", None)
        resolved = None

        if converter:
            resolved = which(converter) or (converter if os.path.exists(converter) else None)

        if not resolved:
            resolved = which("ffmpeg")

        if not resolved:
            try:
                import imageio_ffmpeg
                candidate = imageio_ffmpeg.get_ffmpeg_exe()
                resolved = candidate if candidate and os.path.exists(candidate) else None
            except Exception as e:
                ui_controller.write_error_log(e)

        if resolved:
            AudioSegment.converter = resolved
            AudioSegment.ffmpeg = resolved  # type: ignore[attr-defined]
        return resolved
    except Exception as e:
        ui_controller.write_error_log(e)
        return None


def _write_wave_fallback(audio_segment: AudioSegment, path: str, sample_rate: int = 44100) -> None:
    """ffmpeg 없이 WAV로 저장."""
    import wave
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(audio_segment.channels)
        wf.setsampwidth(audio_segment.sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_segment.raw_data)


def _trim_silence(
    segment: AudioSegment,
    *,
    silence_threshold_db: int = -45,
    chunk_size_ms: int = 10,
    minimum_retain_ms: int = 120,
) -> AudioSegment:
    """
    레퍼런스 프로그램 방식: 과도한 앞/뒤 무음을 제거하되 너무 많이 자르지 않음.
    """
    if segment.duration_seconds <= 0:
        return segment

    start_trim = detect_leading_silence(
        segment, silence_threshold=silence_threshold_db, chunk_size=chunk_size_ms
    )
    end_trim = detect_leading_silence(
        segment.reverse(), silence_threshold=silence_threshold_db, chunk_size=chunk_size_ms
    )

    if start_trim <= 0 and end_trim <= 0:
        return segment

    trimmed = segment[start_trim : len(segment) - end_trim if end_trim else None]
    if len(trimmed) < minimum_retain_ms:
        return segment
    return trimmed


def _prepare_segment(segment: AudioSegment) -> AudioSegment:
    """
    레퍼런스 프로그램 방식: 무음 트림 후 프레임레이트/채널 정규화.
    """
    if segment.duration_seconds <= 0:
        return segment.set_frame_rate(44100).set_channels(2)

    trimmed = _trim_silence(segment)
    normalized = trimmed.set_frame_rate(44100).set_channels(2)
    return normalized
