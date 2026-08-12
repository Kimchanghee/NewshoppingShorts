#!/usr/bin/env python3
"""Isolated all-frame RapidOCR audit used by precision render QA.

This is intentionally a separate process.  On Windows, importing the full
video application first can load native runtimes that conflict with
onnxruntime; isolation makes an engine failure deterministic and fail-closed.
"""
from __future__ import annotations

import argparse
import json
import math
import sys


RESULT_PREFIX = "__RAPIDOCR_AUDIT_RESULT__="


def _configure_utf8_stdout() -> None:
    """Make Chinese audit results portable on Windows CP949 consoles."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _spatially_related(left: dict, right: dict) -> bool:
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


def _confirmed_residuals(candidates: list[dict]) -> list[dict]:
    """Confirm readable Chinese while rejecting repeated blur hallucinations."""
    residuals = []
    for candidate in candidates:
        corroborated = any(
            other is not candidate
            and 0 < abs(other["frame_index"] - candidate["frame_index"]) <= 2
            and _spatially_related(candidate, other)
            for other in candidates
        )
        chinese_count = int(candidate.get("chinese_count", 0) or 0)
        confidence = float(candidate.get("confidence", 0.0) or 0.0)
        box = candidate.get("box") or [0.0, 0.0, 0.0, 0.0]
        width = max(1.0, float(box[2]) - float(box[0]))
        height = max(1.0, float(box[3]) - float(box[1]))
        aspect = width / height
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
        # A blurred glyph-shaped blob can repeat at the same location and be
        # misread as one Han character around 0.85 confidence. Require a strong
        # 0.95 single-character read; multi-character text may still use
        # adjacent-frame spatial corroboration.
        # Two outlet-slot patterns were repeatedly read as ``三二`` around
        # 0.7 confidence. Real two-character text is normally laid out as a
        # horizontal or vertical run; require that geometry (or >=0.90
        # confidence). Three-or-more Han characters remain fail-closed.
        credible_multi_character = bool(
            chinese_count >= 3
            or confidence >= 0.90
            or aspect >= 1.50
            or aspect <= 0.75
        )
        if (
            confidence >= 0.95
            and (chinese_count != 1 or plausible_single_glyph_geometry)
        ) or (
            chinese_count >= 2 and corroborated and credible_multi_character
        ):
            residuals.append(candidate)
    return residuals


def _covered_by_known_overlay(
    box: list[float], frame_index: int, fps: float, overlays: list[dict]
) -> bool:
    """Return true only when a detection is inside an active rendered overlay."""
    time_value = frame_index / fps
    for overlay in overlays or []:
        try:
            start = float(overlay["start_time"])
            end = float(overlay["end_time"])
            outer = [float(value) for value in overlay["box"]]
        except (KeyError, TypeError, ValueError):
            continue
        if len(outer) != 4 or not (start <= time_value < end):
            continue
        # Two pixels absorb codec ringing at the rounded-rectangle boundary.
        if (
            box[0] >= outer[0] - 2.0
            and box[1] >= outer[1] - 2.0
            and box[2] <= outer[2] + 2.0
            and box[3] <= outer[3] + 2.0
        ):
            return True
    return False


def audit(video_path: str, overlay_records: list[dict] | None = None) -> dict:
    import cv2

    try:
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
    except Exception as exc:
        return {
            "ok": False,
            "engine": "rapidocr",
            "full_frame_scan": True,
            "reason": "independent_ocr_unavailable",
            "error_type": type(exc).__name__,
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
                    1
                    for character in text_value
                    if "\u4e00" <= character <= "\u9fff"
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
                            "chinese_count": chinese_count,
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

    residuals = _confirmed_residuals(candidates)

    return {
        "ok": bool(scanned == total_frames and not residuals and errors == 0),
        "engine": "rapidocr",
        "full_frame_scan": True,
        "scanned_frames": scanned,
        "expected_frames": total_frames,
        "residual_detection_count": len(residuals),
        "ignored_known_overlay_count": ignored_known_overlay_count,
        "residuals": [
            {
                key: value
                for key, value in item.items()
                if key not in {"box", "chinese_count"}
            }
            for item in residuals[:50]
        ],
        "error_count": errors,
    }


def main() -> int:
    _configure_utf8_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("video_path")
    parser.add_argument("overlay_records_path", nargs="?")
    args = parser.parse_args()
    overlay_records = []
    if args.overlay_records_path:
        try:
            with open(args.overlay_records_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                overlay_records = payload
        except Exception as exc:
            result = {
                "ok": False,
                "engine": "rapidocr",
                "full_frame_scan": True,
                "reason": "overlay_records_invalid",
                "error_type": type(exc).__name__,
                "scanned_frames": 0,
            }
            print(RESULT_PREFIX + json.dumps(result, ensure_ascii=False), flush=True)
            return 2
    result = audit(args.video_path, overlay_records=overlay_records)
    print(RESULT_PREFIX + json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
