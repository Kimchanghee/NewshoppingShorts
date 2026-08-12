#!/usr/bin/env python3
"""Render five sourced Coupang cases through the real batch application path.

This QA harness deliberately has no upload or publish option.  Its input is the
download-only summary produced by ``live_platform_batch_regression.py`` and its
output is a private diagnostic manifest, a sanitized QA summary, and five MP4 files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SSMAKER_DISABLE_FASTER_WHISPER", "1")

from core.video.batch import processor
from caller import rest
from scripts.render_program_pipeline_upload import HeadlessBatchApp, verify_video
from utils.ffmpeg import resolve_ffmpeg_exe
from utils.ocr_backend import create_ocr_reader
from config.constants import GLMOCRSettings, OCRThresholds

MAX_RENDER_SOURCE_SECONDS = 35.0
PRECISION_CODE_FILES = (
    "config/constants.py",
    "utils/glm_ocr_client.py",
    "processors/subtitle_detector.py",
    "processors/subtitle_processor.py",
    "app/video_helpers.py",
    "core/video/batch/analysis.py",
    "core/video/batch/processor.py",
    "core/video/CreateFinalVideo.py",
    "core/video/VideoTool.py",
    "scripts/render_program_pipeline_upload.py",
    "scripts/independent_rapidocr_audit.py",
    "scripts/independent_rapidocr_source_scan.py",
    "scripts/independent_rapidocr_corner_scan.py",
    "scripts/render_precision_ocr_validation.py",
)

# QA renders may use authenticated product/OCR services, but they must not emit
# unrelated user-progress telemetry or publish/upload the generated media.
rest.log_user_action = lambda *_args, **_kwargs: None


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_fingerprint() -> str:
    digest = hashlib.sha256()
    for relative_path in PRECISION_CODE_FILES:
        path = ROOT / relative_path
        digest.update(relative_path.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _null_decode(path: str) -> Dict[str, Any]:
    ffmpeg = resolve_ffmpeg_exe() or "ffmpeg"
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-i", path, "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "error": result.stderr[-2000:] if result.returncode else "",
    }


def _frame_inventory(path: str) -> Dict[str, Any]:
    """Decode every frame and record timestamp monotonicity for exhaustive QA."""
    import cv2
    import math

    cap = cv2.VideoCapture(path)
    frame_count = 0
    timestamps: List[float] = []
    decoder_monotonic = True
    monotonic = True
    previous = -1.0
    try:
        if not cap.isOpened():
            return {"ok": False, "frame_count": 0, "timestamps_monotonic": False}
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            raw_milliseconds = float(cap.get(cv2.CAP_PROP_POS_MSEC))
            timestamp = raw_milliseconds / 1000.0
            if (
                not math.isfinite(timestamp)
                or timestamp < 0
                or (frame_count > 0 and timestamp <= previous + 1e-6)
            ):
                decoder_monotonic = False
                fallback = frame_count / fps if fps > 0 else float(frame_count)
                timestamp = max(fallback, previous + (1.0 / fps if fps > 0 else 1.0))
            if timestamp + 1e-6 < previous:
                monotonic = False
            timestamps.append(round(timestamp, 6))
            previous = timestamp
            frame_count += 1
    finally:
        cap.release()
    return {
        "ok": frame_count > 0,
        "frame_count": frame_count,
        "timestamps_monotonic": monotonic,
        "decoder_timestamps_monotonic": decoder_monotonic,
        "first_timestamp": timestamps[0] if timestamps else None,
        "last_timestamp": timestamps[-1] if timestamps else None,
        "timestamps": timestamps,
    }


def _collect_runtime_blur_coverage(
    app, max_rendered_slot: int | None = None
) -> Dict[str, Any]:
    """Prove that every rendered polygon slot changed source pixels."""
    expected = set(getattr(app, "_precision_blur_expected_slots", set()) or set())
    seen = set(getattr(app, "_precision_blur_seen_slots", set()) or set())
    active = set(getattr(app, "_precision_blur_active_slots", set()) or set())
    deltas = dict(getattr(app, "_precision_blur_slot_deltas", {}) or {})
    last_rendered = (
        int(max_rendered_slot)
        if max_rendered_slot is not None
        else (max(seen) if seen else -1)
    )
    expected_rendered = {slot for slot in expected if slot <= last_rendered}
    missing_application = sorted(expected_rendered - active)
    unchanged = sorted(
        slot
        for slot in expected_rendered & active
        if float(deltas.get(slot, 0.0) or 0.0) <= 0.5
    )
    checked = len(expected_rendered)
    applied = checked - len(missing_application)
    return {
        "ok": bool(checked > 0 and not missing_application and not unchanged),
        "expected_rendered_slots": checked,
        "applied_slots": applied,
        "coverage_ratio": round(applied / checked, 6) if checked else 0.0,
        "missing_application_count": len(missing_application),
        "unchanged_mask_count": len(unchanged),
        "minimum_delta": (
            round(min(float(deltas[slot]) for slot in expected_rendered & active), 4)
            if expected_rendered & active
            else None
        ),
    }


def _post_render_residual_ocr_audit(
    video_path: str,
    subtitle_positions: List[Dict[str, Any]],
    ocr_reader,
    overlay_records: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Re-OCR representative and uniform final frames; any Chinese is a failure."""
    import cv2
    import math

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"ok": False, "reason": "final_video_open_failed", "sampled_frames": 0}
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if not math.isfinite(fps) or fps <= 0 or total_frames <= 0:
        cap.release()
        return {"ok": False, "reason": "final_video_timing_invalid", "sampled_frames": 0}

    duration = total_frames / fps
    target_indices = {
        min(total_frames - 1, int(round(time_value * fps)))
        for time_value in (
            step * 0.5 for step in range(int(math.ceil(duration / 0.5)) + 1)
        )
        if 0 <= time_value < duration
    }
    for position in subtitle_positions or []:
        frame_regions = list(position.get("frame_regions") or [])
        if frame_regions:
            candidates = [frame_regions[0], frame_regions[len(frame_regions) // 2], frame_regions[-1]]
            highest = max(
                frame_regions,
                key=lambda item: float(item.get("confidence", 0.0) or 0.0),
            )
            candidates.append(highest)
            for item in candidates:
                try:
                    time_value = float(item.get("time"))
                except (TypeError, ValueError):
                    continue
                if 0 <= time_value < duration:
                    target_indices.add(
                        min(total_frames - 1, int(round(time_value * fps)))
                    )
        else:
            try:
                start = max(0.0, float(position.get("start_time", 0.0) or 0.0))
                end = min(
                    duration,
                    float(position.get("end_time", duration) or duration),
                )
            except (TypeError, ValueError):
                continue
            for time_value in (start, (start + end) / 2.0, max(start, end - 1.0 / fps)):
                if 0 <= time_value < duration:
                    target_indices.add(
                        min(total_frames - 1, int(round(time_value * fps)))
                    )

    client = getattr(ocr_reader, "_glm_client", None)
    request_failures_before = int(getattr(client, "request_failure_count", 0) or 0)
    invalid_before = int(getattr(client, "invalid_coordinate_count", 0) or 0)
    pending_frames = []
    pending_indices = []
    residuals = []
    ignored_known_overlay_count = 0
    batch_errors = 0
    sampled = 0
    batch_size = max(1, int(GLMOCRSettings.OPTIMAL_BATCH_SIZE))

    def flush():
        nonlocal sampled, batch_errors, ignored_known_overlay_count
        if not pending_frames:
            return
        try:
            results = ocr_reader.readtext_batch(pending_frames)
        except Exception:
            batch_errors += 1
            pending_frames.clear()
            pending_indices.clear()
            return
        if not isinstance(results, (list, tuple)) or len(results) != len(pending_frames):
            batch_errors += 1
            results = list(results or [])
        for offset, frame_index in enumerate(pending_indices):
            detections = results[offset] if offset < len(results) else []
            for detection in detections or []:
                if not isinstance(detection, (list, tuple)) or len(detection) < 2:
                    continue
                text_value = str(detection[1] or "")
                try:
                    confidence = float(detection[2]) if len(detection) >= 3 else 1.0
                except (TypeError, ValueError):
                    confidence = 0.0
                chinese_count = sum(
                    1 for character in text_value if "\u4e00" <= character <= "\u9fff"
                )
                if chinese_count and confidence >= OCRThresholds.CONFIDENCE_MIN:
                    try:
                        polygon = detection[0]
                        xs = [float(point[0]) for point in polygon]
                        ys = [float(point[1]) for point in polygon]
                        box = [min(xs), min(ys), max(xs), max(ys)]
                    except Exception:
                        box = None
                    if box is not None:
                        from scripts.independent_rapidocr_audit import (
                            _covered_by_known_overlay,
                        )

                        if _covered_by_known_overlay(
                            box, frame_index, fps, overlay_records or []
                        ):
                            ignored_known_overlay_count += 1
                            continue
                    residuals.append(
                        {
                            "frame_index": frame_index,
                            "time": round(frame_index / fps, 3),
                            "text": text_value[:80],
                            "confidence": round(confidence, 4),
                            # Private QA evidence used by the bounded repair
                            # pass below.  The shareable summary never exposes
                            # coordinates or source metadata.
                            "polygon": [
                                [round(float(point[0]), 3), round(float(point[1]), 3)]
                                for point in (polygon or [])
                                if isinstance(point, (list, tuple)) and len(point) >= 2
                            ],
                        }
                    )
        sampled += len(pending_frames)
        pending_frames.clear()
        pending_indices.clear()

    try:
        targets = set(target_indices)
        frame_index = 0
        while targets:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if frame_index in targets:
                pending_frames.append(frame)
                pending_indices.append(frame_index)
                targets.remove(frame_index)
                if len(pending_frames) >= batch_size:
                    flush()
            frame_index += 1
        flush()
        undecoded_targets = len(targets)
    finally:
        cap.release()

    request_failure_delta = max(
        0, int(getattr(client, "request_failure_count", 0) or 0) - request_failures_before
    )
    invalid_delta = max(
        0, int(getattr(client, "invalid_coordinate_count", 0) or 0) - invalid_before
    )
    ok = bool(
        sampled == len(target_indices)
        and not residuals
        and batch_errors == 0
        and request_failure_delta == 0
        and invalid_delta == 0
        and undecoded_targets == 0
    )
    return {
        "ok": ok,
        "sampled_frames": sampled,
        "requested_frames": len(target_indices),
        "residual_detection_count": len(residuals),
        "ignored_known_overlay_count": ignored_known_overlay_count,
        "residuals": residuals[:50],
        "batch_errors": batch_errors,
        "request_failure_count": request_failure_delta,
        "invalid_coordinate_count": invalid_delta,
        "undecoded_target_count": undecoded_targets,
    }


def _build_residual_repair_positions(
    residuals: List[Dict[str, Any]],
    *,
    fps: float,
    frame_width: int,
    frame_height: int,
) -> List[Dict[str, Any]]:
    """Build separate, short-lived tracks from verified final-frame residuals.

    The audit can find tiny moving compliance/product labels which the source
    OCR missed during a transient API failure.  Never union unrelated boxes:
    detections are linked only when they are close in both time and space, and
    the normal polygon renderer interpolates within each resulting track.
    """
    if fps <= 0 or frame_width <= 0 or frame_height <= 0:
        return []

    observations = []
    for item in residuals or []:
        polygon = item.get("polygon") if isinstance(item, dict) else None
        if not isinstance(polygon, (list, tuple)) or len(polygon) < 4:
            continue
        points = []
        try:
            for point in polygon:
                x = min(float(frame_width - 1), max(0.0, float(point[0])))
                y = min(float(frame_height - 1), max(0.0, float(point[1])))
                points.append([int(round(x)), int(round(y))])
            time_value = max(0.0, float(item.get("time", 0.0) or 0.0))
        except (TypeError, ValueError, IndexError):
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        if max(xs) <= min(xs) or max(ys) <= min(ys):
            continue
        observations.append(
            {
                "time": time_value,
                "frame_index": int(round(time_value * fps)),
                "polygon": points,
                "box": [min(xs), min(ys), max(xs), max(ys)],
            }
        )

    tracks: List[List[Dict[str, Any]]] = []
    max_gap = max(2.0 / fps, 1.25)
    max_dx = max(24.0, frame_width * 0.22)
    max_dy = max(24.0, frame_height * 0.18)
    for observation in sorted(observations, key=lambda value: value["time"]):
        box = observation["box"]
        center = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
        best_track = None
        best_distance = None
        for track in tracks:
            previous = track[-1]
            gap = observation["time"] - previous["time"]
            if gap < 0 or gap > max_gap:
                continue
            previous_box = previous["box"]
            previous_center = (
                (previous_box[0] + previous_box[2]) / 2.0,
                (previous_box[1] + previous_box[3]) / 2.0,
            )
            dx = abs(center[0] - previous_center[0])
            dy = abs(center[1] - previous_center[1])
            if dx > max_dx or dy > max_dy:
                continue
            distance = dx / max_dx + dy / max_dy
            if best_distance is None or distance < best_distance:
                best_track = track
                best_distance = distance
        if best_track is None:
            tracks.append([observation])
        else:
            best_track.append(observation)

    positions = []
    for track_index, track in enumerate(tracks):
        marker = f"__post_render_verified_residual_{track_index}__"
        frame_regions = [
            {
                "time": item["time"],
                "frame_index": item["frame_index"],
                "scene_id": f"post_render_repair:{track_index}",
                "text": marker,
                "source": "glm_post_render_audit",
                "confidence": 1.0,
                "polygon": item["polygon"],
            }
            for item in track
        ]
        positions.append(
            {
                "start_time": track[0]["time"],
                "end_time": track[-1]["time"],
                "frame_regions": frame_regions,
            }
        )
    return positions


def _repair_residual_chinese_video(
    video_path: str,
    residuals: List[Dict[str, Any]],
    *,
    attempt: int,
) -> Dict[str, Any]:
    """Apply a bounded second-pass blur to audit-confirmed residual polygons."""
    from moviepy.editor import VideoFileClip
    from processors.subtitle_processor import SubtitleProcessor

    clip = VideoFileClip(video_path)
    output_path = str(
        Path(video_path).with_name(
            f"{Path(video_path).stem}_ocr_repaired_{int(attempt)}.mp4"
        )
    )
    gui = type("ResidualRepairGUI", (), {})()
    gui.ocr_reader = None
    try:
        positions = _build_residual_repair_positions(
            residuals,
            fps=float(clip.fps),
            frame_width=int(clip.w),
            frame_height=int(clip.h),
        )
        if not positions:
            return {
                "ok": False,
                "reason": "no_valid_residual_polygons",
                "output_path": "",
                "track_count": 0,
            }
        processed = SubtitleProcessor(gui).apply_opencv_blur_enhanced_v2(
            clip, positions, int(clip.w), int(clip.h)
        )
        processed.write_videofile(
            output_path,
            codec="h264_nvenc",
            audio_codec="aac",
            fps=float(clip.fps),
            preset="p4",
            threads=4,
            logger=None,
        )
        if processed is not clip:
            processed.close()
        coverage = _collect_runtime_blur_coverage(
            gui,
            max_rendered_slot=max(
                -1, int(round(float(clip.duration) * float(clip.fps))) - 1
            ),
        )
        return {
            "ok": bool(os.path.isfile(output_path) and coverage.get("ok")),
            "reason": "",
            "output_path": output_path,
            "track_count": len(positions),
            "input_residual_count": len(residuals or []),
            "coverage": coverage,
        }
    finally:
        clip.close()


def _post_render_independent_full_frame_audit(
    video_path: str, engine=None, overlay_records: List[Dict[str, Any]] | None = None
) -> Dict[str, Any]:
    """Scan every encoded frame with an independent local Chinese OCR engine."""
    import cv2
    import math

    if engine is None:
        overlay_path = None
        command = [sys.executable, str(ROOT / "scripts" / "independent_rapidocr_audit.py"), video_path]
        if overlay_records:
            handle = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", encoding="utf-8", delete=False
            )
            try:
                json.dump(overlay_records, handle, ensure_ascii=False)
                overlay_path = handle.name
            finally:
                handle.close()
            command.append(overlay_path)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        result = None
        prefix = "__RAPIDOCR_AUDIT_RESULT__="
        if process.stdout is not None:
            for line in process.stdout:
                stripped = line.rstrip()
                if stripped.startswith(prefix):
                    try:
                        result = json.loads(stripped[len(prefix) :])
                    except Exception:
                        result = None
                elif stripped:
                    print(stripped, flush=True)
        return_code = process.wait()
        if overlay_path:
            try:
                os.unlink(overlay_path)
            except OSError:
                pass
        if isinstance(result, dict):
            return result
        return {
            "ok": False,
            "engine": "rapidocr",
            "full_frame_scan": True,
            "reason": "independent_ocr_process_failed",
            "return_code": return_code,
            "scanned_frames": 0,
        }

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "ok": False,
            "engine": "rapidocr",
            "full_frame_scan": True,
            "reason": "final_video_open_failed",
            "scanned_frames": 0,
        }
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if not math.isfinite(fps) or fps <= 0 or total_frames <= 0:
        cap.release()
        return {
            "ok": False,
            "engine": "rapidocr",
            "full_frame_scan": True,
            "reason": "final_video_timing_invalid",
            "scanned_frames": 0,
        }

    candidates = []
    scanned = 0
    errors = 0
    ignored_known_overlay_count = 0
    try:
        for frame_index in range(total_frames):
            ok, frame = cap.read()
            if not ok or frame is None:
                errors += 1
                break
            try:
                output = engine(frame)
                detections = output[0] if isinstance(output, tuple) else output
            except Exception:
                errors += 1
                break
            scanned += 1
            for detection in detections or []:
                if not isinstance(detection, (list, tuple)) or len(detection) < 3:
                    continue
                text_value = str(detection[1] or "")
                try:
                    confidence = float(detection[2])
                except (TypeError, ValueError):
                    confidence = 0.0
                chinese_count = sum(
                    1 for character in text_value if "\u4e00" <= character <= "\u9fff"
                )
                readable = bool(
                    (chinese_count >= 2 and confidence >= 0.45)
                    or (chinese_count == 1 and confidence >= 0.85)
                )
                if readable:
                    try:
                        polygon = detection[0]
                        xs = [float(point[0]) for point in polygon]
                        ys = [float(point[1]) for point in polygon]
                        box = [min(xs), min(ys), max(xs), max(ys)]
                    except Exception:
                        continue
                    from scripts.independent_rapidocr_audit import _covered_by_known_overlay

                    if _covered_by_known_overlay(
                        box, frame_index, fps, overlay_records or []
                    ):
                        ignored_known_overlay_count += 1
                        continue
                    candidates.append(
                        {
                            "frame_index": frame_index,
                            "time": round(frame_index / fps, 3),
                            "text": text_value[:80],
                            "confidence": round(confidence, 4),
                            "box": box,
                            "frame_width": int(frame.shape[1]),
                            "frame_height": int(frame.shape[0]),
                        }
                    )
            if scanned % 100 == 0:
                print(
                    f"[QA independent OCR] {scanned}/{total_frames} frames",
                    flush=True,
                )
    finally:
        cap.release()

    def spatially_related(left, right):
        left_box, right_box = left["box"], right["box"]
        left_width = max(1.0, left_box[2] - left_box[0])
        left_height = max(1.0, left_box[3] - left_box[1])
        right_width = max(1.0, right_box[2] - right_box[0])
        right_height = max(1.0, right_box[3] - right_box[1])
        return bool(
            abs((left_box[0] + left_box[2]) / 2.0 - (right_box[0] + right_box[2]) / 2.0)
            <= max(left_width, right_width)
            and abs((left_box[1] + left_box[3]) / 2.0 - (right_box[1] + right_box[3]) / 2.0)
            <= max(left_height, right_height)
        )

    residuals = []
    for candidate in candidates:
        corroborated = any(
            other is not candidate
            and 0 < abs(other["frame_index"] - candidate["frame_index"]) <= 2
            and spatially_related(candidate, other)
            for other in candidates
        )
        box = candidate["box"]
        width = max(1.0, float(box[2]) - float(box[0]))
        height = max(1.0, float(box[3]) - float(box[1]))
        frame_width = float(candidate.get("frame_width", 0.0) or 0.0)
        frame_height = float(candidate.get("frame_height", 0.0) or 0.0)
        plausible_single_glyph_geometry = bool(
            frame_width <= 0.0
            or frame_height <= 0.0
            or (
                width <= frame_width * 0.18
                and height <= frame_height * 0.12
            )
        )
        chinese_count = sum(
            1 for character in candidate["text"] if "\u4e00" <= character <= "\u9fff"
        )
        if (
            candidate["confidence"] >= 0.95
            and (chinese_count != 1 or plausible_single_glyph_geometry)
        ) or corroborated:
            residuals.append(candidate)

    return {
        "ok": bool(scanned == total_frames and not residuals and errors == 0),
        "engine": "rapidocr",
        "full_frame_scan": True,
        "scanned_frames": scanned,
        "expected_frames": total_frames,
        "residual_detection_count": len(residuals),
        "ignored_known_overlay_count": ignored_known_overlay_count,
        "residuals": [
            {key: value for key, value in item.items() if key != "box"}
            for item in residuals[:50]
        ],
        "error_count": errors,
    }


def _adjudicate_detector_review(
    blur: Dict[str, Any],
    blur_coverage: Dict[str, Any],
    residual_ocr: Dict[str, Any],
    independent_residual_ocr: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve only a narrow detector uncertainty with stronger final-media evidence.

    An unresolved page-scale OCR box is deliberately never rendered because it
    could obscure most of a frame.  It is safe to adjudicate that warning only
    after the completed MP4 passes both the representative GLM audit and a
    frame-exhaustive independent RapidOCR audit.  Coordinate failures, request
    failures, ambiguous anchors, or any other review reason remain release
    blockers.
    """
    reasons = list(
        dict.fromkeys(
            str(reason)
            for reason in (blur.get("review_reasons") or [])
            if str(reason)
        )
    )
    # A transient source-OCR request failure may be cleared only after the
    # encoded final media itself passes both independent audits.  This is much
    # stronger than assuming the failed source request contained no text.
    allowed_reasons = {
        "oversized_ocr_bbox_without_precise_anchor",
        "ocr_reader_request_failures",
    }
    independent_scanned = int(independent_residual_ocr.get("scanned_frames") or 0)
    independent_expected = int(
        independent_residual_ocr.get("expected_frames") or 0
    )
    conditions = {
        "only_adjudicable_reason": bool(reasons)
        and set(reasons).issubset(allowed_reasons),
        "no_invalid_coordinates": int(blur.get("invalid_coordinate_count") or 0)
        == 0,
        "complete_blur_coverage": bool(blur_coverage.get("ok")),
        "glm_audit_clean": bool(residual_ocr.get("ok"))
        and int(residual_ocr.get("residual_detection_count") or 0) == 0
        and int(residual_ocr.get("request_failure_count") or 0) == 0
        and int(residual_ocr.get("invalid_coordinate_count") or 0) == 0
        and int(residual_ocr.get("undecoded_target_count") or 0) == 0,
        "independent_full_frame_audit_clean": bool(
            independent_residual_ocr.get("ok")
        )
        and bool(independent_residual_ocr.get("full_frame_scan"))
        and independent_expected > 0
        and independent_scanned == independent_expected
        and int(independent_residual_ocr.get("residual_detection_count") or 0)
        == 0
        and int(independent_residual_ocr.get("error_count") or 0) == 0,
    }
    return {
        "ok": bool(blur.get("review_required")) and all(conditions.values()),
        "method": "post_render_dual_engine_full_frame_adjudication",
        "reasons": reasons,
        "conditions": conditions,
    }


def _load_verified_resume_results(output_dir: Path) -> List[Dict[str, Any]]:
    """Reuse only completed local results whose media still verifies."""
    manifest_path = output_dir / "precision_ocr_manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    candidates = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(candidates, list):
        return []

    verified: List[Dict[str, Any]] = []
    current_fingerprint = _implementation_fingerprint()
    for item in candidates:
        final_path = str(item.get("final_video") or "")
        source_path = str(item.get("source_video") or "")
        if (
            not item.get("qa_ok")
            or not (item.get("independent_residual_ocr") or {}).get("ok")
            or item.get("code_fingerprint") != current_fingerprint
            or not os.path.isfile(final_path)
        ):
            continue
        if item.get("final_sha256") != _sha256(final_path):
            continue
        expected_source_hash = str(item.get("source_sha256") or "")
        if os.path.isfile(source_path):
            if not expected_source_hash or _sha256(source_path) != expected_source_hash:
                continue
        else:
            downloaded_path = str(item.get("downloaded_source_video") or "")
            expected_download_hash = str(item.get("downloaded_source_sha256") or "")
            if (
                not os.path.isfile(downloaded_path)
                or not expected_download_hash
                or _sha256(downloaded_path) != expected_download_hash
            ):
                continue
            try:
                source_path = _prepare_render_source(
                    downloaded_path, output_dir, int(item.get("index") or 0)
                )
            except Exception:
                continue
            if expected_source_hash != _sha256(source_path):
                continue
        refreshed = dict(item)
        refreshed["source_video"] = source_path
        refreshed["source_inventory"] = _frame_inventory(source_path)
        refreshed["final_inventory"] = _frame_inventory(final_path)
        if not (
            refreshed["source_inventory"].get("ok")
            and refreshed["source_inventory"].get("timestamps_monotonic")
            and refreshed["source_inventory"].get("decoder_timestamps_monotonic")
            and refreshed["final_inventory"].get("ok")
            and refreshed["final_inventory"].get("timestamps_monotonic")
            and refreshed["final_inventory"].get("decoder_timestamps_monotonic")
            and int(
                (refreshed.get("independent_residual_ocr") or {}).get(
                    "scanned_frames", -1
                )
            )
            == int(refreshed["final_inventory"].get("frame_count") or 0)
        ):
            continue
        verified.append(refreshed)
    return sorted(verified, key=lambda item: int(item.get("index") or 0))


def _prepare_render_source(
    source_path: str, output_dir: Path, index: int
) -> str:
    """Create an isolated render copy bounded to the Shorts duration.

    The production cleanup path may remove its active local input, so the
    download-only sourcing artifact must never be passed through directly.
    """
    import cv2

    cap = cv2.VideoCapture(source_path)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        duration = frames / fps if fps > 0 else 0.0
    finally:
        cap.release()
    ffmpeg = resolve_ffmpeg_exe() or "ffmpeg"
    prepared_dir = output_dir / "prepared_sources"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    target = prepared_dir / f"source_{index:02d}_first35s.mp4"
    if 0 < duration <= MAX_RENDER_SOURCE_SECONDS + 0.05:
        shutil.copy2(source_path, target)
        return str(target)
    target_duration = (
        min(duration, MAX_RENDER_SOURCE_SECONDS)
        if duration > 0
        else MAX_RENDER_SOURCE_SECONDS
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-i",
            source_path,
            "-t",
            f"{target_duration:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
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
            "160k",
            "-movflags",
            "+faststart",
            str(target),
        ],
        check=True,
        timeout=300,
    )
    return str(target)


def _build_sourcing_context(item: Dict[str, Any]) -> Dict[str, Any]:
    source = {
        "source": str(item.get("platform") or "platform"),
        "title": str(item.get("source_title") or ""),
        "url": str(item.get("source_url") or ""),
        "similarity": float(item.get("relevance_score") or 1.0),
        "video_file": str(item.get("video_path") or ""),
        "auto_publish_safe": True,
        "requires_review": False,
    }
    product_name = str(item.get("product_name") or item.get("title_hint") or item.get("slug"))
    affiliate_url = str(item.get("affiliate_url") or "")
    return {
        "coupang_url": affiliate_url,
        "product_info": {"name": product_name, "url": affiliate_url},
        "description": product_name,
        "deep_link": affiliate_url,
        "sourced_products": [source],
        "sourcing_results": [source],
        "match_threshold": float(item.get("required_relevance_score") or 0.75),
        "min_similarity_score": float(item.get("required_relevance_score") or 0.75),
        "best_similarity": source["similarity"],
        "match_status": "matched",
        "success": True,
    }


def _load_cases(summary_path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    cases = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError("sourcing summary must contain a results list")
    allowed_source_root = summary_path.resolve().parent

    def source_is_contained(item: Dict[str, Any]) -> bool:
        try:
            return Path(str(item.get("video_path") or "")).resolve().is_relative_to(
                allowed_source_root
            )
        except (OSError, ValueError):
            return False

    valid = [
        item
        for item in cases
        if item.get("ok")
        and (item.get("media") or {}).get("decode_ok")
        and item.get("video_path")
        and source_is_contained(item)
    ]
    if len(valid) < 5:
        raise ValueError(f"five verified sourced videos are required; got {len(valid)}")
    return valid[:5]


def _write_sanitized_qa_summary(
    results: List[Dict[str, Any]], output_dir: Path
) -> Path:
    """Write a shareable report without URLs, absolute paths, or TTS metadata."""
    cases = []
    for item in results:
        probe = dict(item.get("video_probe") or {})
        blur = dict(item.get("blur") or {})
        coverage = dict(item.get("blur_coverage") or {})
        residual = dict(item.get("residual_ocr") or {})
        independent = dict(item.get("independent_residual_ocr") or {})
        adjudication = dict(item.get("review_adjudication") or {})
        inventory = dict(item.get("final_inventory") or {})
        cases.append(
            {
                "index": int(item.get("index") or 0),
                "slug": str(item.get("slug") or ""),
                "final_sha256": str(item.get("final_sha256") or ""),
                "frame_count": int(inventory.get("frame_count") or 0),
                "resolution": [
                    int(probe.get("width") or 0),
                    int(probe.get("height") or 0),
                ],
                "has_audio": bool(probe.get("has_audio")),
                "blur_regions": int(blur.get("regions") or 0),
                "coverage_ratio": float(coverage.get("coverage_ratio") or 0.0),
                "residual_ocr_sampled_frames": int(residual.get("sampled_frames") or 0),
                "residual_chinese_detections": int(
                    residual.get("residual_detection_count") or 0
                ),
                "independent_ocr_engine": str(independent.get("engine") or ""),
                "independent_full_frame_scan": bool(
                    independent.get("full_frame_scan")
                ),
                "independent_ocr_scanned_frames": int(
                    independent.get("scanned_frames") or 0
                ),
                "independent_residual_chinese_detections": int(
                    independent.get("residual_detection_count") or 0
                ),
                "review_adjudicated": bool(adjudication.get("ok")),
                "qa_ok": bool(item.get("qa_ok")),
            }
        )
    payload = {
        "schema": 1,
        "count": len(cases),
        "all_ok": bool(len(cases) == 5 and all(case["qa_ok"] for case in cases)),
        "cases": cases,
    }
    path = output_dir / "precision_ocr_qa_summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render_cases(
    summary_path: Path, output_dir: Path, only_index: int | None = None
) -> List[Dict[str, Any]]:
    cases = _load_cases(summary_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    app = HeadlessBatchApp(output_dir)
    # The desktop startup controller normally injects the shared OCR backend.
    # This headless production-path harness must do the same explicitly; running
    # without it would exercise only the fail-closed fallback, not OCR blur.
    app.ocr_reader = create_ocr_reader()
    if app.ocr_reader is None:
        raise RuntimeError("precision OCR QA requires an initialized OCR backend")
    app.apply_blur = True
    app.add_subtitles = True
    app.subtitle_overlay_on_chinese = True
    app._precision_record_korean_subtitle_overlays = True
    results = _load_verified_resume_results(output_dir)
    completed_indices = {int(item.get("index") or 0) for item in results}

    try:
        for index, item in enumerate(cases, 1):
            if only_index is not None and index != int(only_index):
                continue
            if index in completed_indices:
                print(f"PRECISION_RESUME {index}/5 already verified", flush=True)
                continue
            started = time.monotonic()
            downloaded_source_path = str(Path(str(item["video_path"])).resolve())
            source_path = _prepare_render_source(
                downloaded_source_path, output_dir, index
            )
            source_inventory = _frame_inventory(source_path)
            if not source_inventory.get("ok"):
                raise RuntimeError(f"source frame inventory failed: {source_path}")

            processor.clear_all_previous_results(app)
            product_name = str(
                item.get("product_name") or item.get("title_hint") or item.get("slug")
            )
            app.product_name = product_name
            app.video_title = product_name
            app.state.sourcing_result = _build_sourcing_context(item)
            local_url = "local://" + source_path
            app.url_queue = [local_url]
            app.url_status = {local_url: "waiting"}
            app.url_status_message = {}
            app.batch_processing = True
            app._precision_korean_subtitle_overlays = []

            print(f"PRECISION_RENDER {index}/5 {item.get('slug', product_name)}", flush=True)
            processor._process_single_video(app, local_url, index, 5)
            processor._stop_log_capture(app)

            if not app.generated_videos:
                raise RuntimeError(f"program produced no video for case {index}")
            latest = dict(app.generated_videos[-1])
            final_path = str(latest.get("saved_path") or latest.get("path") or "")
            if not final_path or not os.path.isfile(final_path):
                raise RuntimeError(f"program output is missing for case {index}")

            blur = dict(getattr(app, "latest_blur_metadata", {}) or {})
            analysis = dict(getattr(app, "analysis_result", {}) or {})
            probe = verify_video(final_path)
            decode = _null_decode(final_path)
            final_inventory = _frame_inventory(final_path)
            blur_coverage = _collect_runtime_blur_coverage(
                app,
                max_rendered_slot=max(
                    -1, int(final_inventory.get("frame_count") or 0) - 1
                ),
            )
            overlay_records = list(
                getattr(app, "_precision_korean_subtitle_overlays", []) or []
            )
            residual_ocr = _post_render_residual_ocr_audit(
                final_path,
                list(analysis.get("subtitle_positions") or []),
                app.ocr_reader,
                overlay_records=overlay_records,
            )
            residual_repairs = []
            # A second OCR engine can reveal a tiny moving label which was
            # absent from the source timeline (for example after an exhausted
            # source API request).  Feed only its exact verified polygons back
            # through the same scene/time-aware renderer, then audit the newly
            # encoded file again.  Never accept a repair without a clean audit.
            for repair_attempt in range(1, 3):
                repairable = list(residual_ocr.get("residuals") or [])
                if not repairable:
                    break
                repair = _repair_residual_chinese_video(
                    final_path, repairable, attempt=repair_attempt
                )
                residual_repairs.append(repair)
                if not repair.get("ok"):
                    break
                final_path = str(repair["output_path"])
                probe = verify_video(final_path)
                decode = _null_decode(final_path)
                final_inventory = _frame_inventory(final_path)
                residual_ocr = _post_render_residual_ocr_audit(
                    final_path,
                    list(analysis.get("subtitle_positions") or []),
                    app.ocr_reader,
                    overlay_records=overlay_records,
                )
            independent_residual_ocr = _post_render_independent_full_frame_audit(
                final_path,
                overlay_records=overlay_records,
            )
            review_adjudication = _adjudicate_detector_review(
                blur,
                blur_coverage,
                residual_ocr,
                independent_residual_ocr,
            )
            qa_ok = bool(
                blur.get("completed")
                and blur.get("applied")
                and int(blur.get("regions") or 0) > 0
                and (
                    not blur.get("review_required")
                    or review_adjudication.get("ok")
                )
                and int(blur.get("invalid_coordinate_count") or 0) == 0
                and blur_coverage.get("ok")
                and residual_ocr.get("ok")
                and independent_residual_ocr.get("ok")
                and probe.get("has_audio")
                and probe.get("is_vertical_1080x1920")
                and decode.get("ok")
                and final_inventory.get("ok")
                and source_inventory.get("timestamps_monotonic")
                and source_inventory.get("decoder_timestamps_monotonic")
                and final_inventory.get("timestamps_monotonic")
                and final_inventory.get("decoder_timestamps_monotonic")
            )
            result = {
                "index": index,
                "code_fingerprint": _implementation_fingerprint(),
                "slug": item.get("slug", ""),
                "affiliate_url": item.get("affiliate_url", ""),
                "product_name": product_name,
                "platform": item.get("platform", ""),
                "source_url": item.get("source_url", ""),
                "source_title": item.get("source_title", ""),
                "source_video": source_path,
                "downloaded_source_video": downloaded_source_path,
                "downloaded_source_sha256": _sha256(downloaded_source_path),
                "source_sha256": _sha256(source_path),
                "source_inventory": source_inventory,
                "final_video": final_path,
                "final_sha256": _sha256(final_path),
                "final_inventory": final_inventory,
                "video_probe": probe,
                "null_decode": decode,
                "blur": blur,
                "blur_coverage": blur_coverage,
                "residual_ocr": residual_ocr,
                "independent_residual_ocr": independent_residual_ocr,
                "residual_repairs": residual_repairs,
                "review_adjudication": review_adjudication,
                "detected_subtitle_regions": len(analysis.get("subtitle_positions") or []),
                "render_integrity": latest.get("render_integrity_validation") or {},
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "qa_ok": qa_ok,
            }
            results.append(result)
            manifest_path = output_dir / "precision_ocr_manifest.json"
            manifest_path.write_text(
                json.dumps({"results": results}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _write_sanitized_qa_summary(results, output_dir)
            if not qa_ok:
                raise RuntimeError(f"precision OCR QA failed for case {index}: {blur}")
    finally:
        try:
            processor._stop_log_capture(app)
        except Exception:
            pass

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="download-only sourcing summary JSON")
    parser.add_argument("--output", required=True, help="local output directory")
    parser.add_argument(
        "--only-index",
        type=int,
        choices=range(1, 6),
        help="diagnostic mode: render and fully audit one of the five cases",
    )
    args = parser.parse_args()

    output_dir = Path(args.output).resolve()
    results = render_cases(
        Path(args.input).resolve(), output_dir, only_index=args.only_index
    )
    expected_count = 1 if args.only_index is not None else 5
    payload = {
        "created_at": datetime.now().astimezone().isoformat(),
        "upload_enabled": False,
        "count": len(results),
        "all_ok": len(results) == expected_count and all(
            item.get("qa_ok") for item in results
        ),
        "results": results,
    }
    manifest_path = output_dir / "precision_ocr_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_sanitized_qa_summary(results, output_dir)
    print(f"PRECISION_OCR_MANIFEST={manifest_path}")
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
