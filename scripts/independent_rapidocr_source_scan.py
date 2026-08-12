#!/usr/bin/env python3
"""Isolated all-frame RapidOCR source scan for precision subtitle detection."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys


# OCR at 2x for 720-wide vertical sources.  A 1.5x pass matches the renderer,
# but compression can make tiny rotating labels readable only after output;
# the extra source headroom catches those glyphs before rendering.
UPSCALE_TARGET_WIDTH = 1440
# Ten-frame sampling could miss a tiny label exposed for only 4-6 frames.
# A 3-frame stride gives a 10 Hz high-resolution safety pass at 30 fps while
# the base-resolution OCR still scans every source frame.
UPSCALE_SAMPLE_STRIDE = 3


def _source_cache_path(video_path: str) -> Path:
    """Return a content- and implementation-addressed cache path."""
    digest = hashlib.sha256()
    with open(video_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    digest.update(Path(__file__).read_bytes())
    try:
        from importlib.metadata import version

        digest.update(version("rapidocr-onnxruntime").encode("utf-8"))
    except Exception:
        digest.update(b"rapidocr-version-unknown")
    root = Path(__file__).resolve().parents[1]
    return root / "artifacts" / "precision_ocr_cache" / "source_scans" / f"{digest.hexdigest()}.json"


def _restore_cached_scan(video_path: str, result_path: str) -> bool:
    cache_path = _source_cache_path(video_path)
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if not (
            isinstance(payload, dict)
            and payload.get("ok")
            and int(payload.get("scanned_frames", -1))
            == int(payload.get("expected_frames", -2))
        ):
            return False
        shutil.copyfile(cache_path, result_path)
        print("[Source independent OCR] verified cache hit", flush=True)
        return True
    except Exception:
        return False


def _store_cached_scan(video_path: str, result_path: str, result: dict) -> None:
    if not result.get("ok"):
        return
    cache_path = _source_cache_path(video_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(f".{os.getpid()}.tmp")
    try:
        shutil.copyfile(result_path, temporary)
        os.replace(temporary, cache_path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def _has_chinese(value: object) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(value or ""))


def _box_iou(left: list[float], right: list[float]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(1.0, (left[2] - left[0]) * (left[3] - left[1]))
    right_area = max(1.0, (right[2] - right[0]) * (right[3] - right[1]))
    return intersection / (left_area + right_area - intersection)


def _normalized_detections(detections, scale: float = 1.0) -> list[dict]:
    """Return Chinese OCR boxes in original-frame coordinates."""
    normalized = []
    safe_scale = max(1e-6, float(scale))
    for detection in detections or []:
        if not isinstance(detection, (list, tuple)) or len(detection) < 3:
            continue
        polygon, text_value, confidence_value = detection[:3]
        text_value = str(text_value or "")
        try:
            confidence = float(confidence_value)
            points = [
                [float(point[0]) / safe_scale, float(point[1]) / safe_scale]
                for point in polygon
            ]
        except (TypeError, ValueError, IndexError):
            continue
        if len(points) < 4 or confidence < 0.45 or not _has_chinese(text_value):
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        normalized.append(
            {
                "polygon": points,
                "text": text_value,
                "confidence": confidence,
                "box": [min(xs), min(ys), max(xs), max(ys)],
            }
        )
    return normalized


def _merge_frame_detections(*groups: list[dict]) -> list[dict]:
    """Deduplicate multi-scale detections while retaining distinct text rows."""
    merged = []
    for item in sorted(
        (candidate for group in groups for candidate in group),
        key=lambda candidate: (
            float(candidate.get("confidence", 0.0)),
            len(str(candidate.get("text", ""))),
        ),
        reverse=True,
    ):
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(merged)
                if _box_iou(item["box"], existing["box"]) >= 0.55
            ),
            None,
        )
        if duplicate_index is None:
            merged.append(item)
    return merged


def _is_scene_cut(previous_frame, current_frame) -> bool:
    """Cheap hard-cut detector matching the main OCR pipeline."""
    if previous_frame is None or current_frame is None:
        return False
    try:
        import cv2
        import numpy as np

        def gray160(frame):
            gray = (
                cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if len(frame.shape) == 3
                else frame
            )
            height, width = gray.shape[:2]
            if width != 160:
                target_height = max(1, int(round(height * (160.0 / max(1, width)))))
                gray = cv2.resize(
                    gray, (160, target_height), interpolation=cv2.INTER_AREA
                )
            return gray

        gray_a = gray160(previous_frame)
        gray_b = gray160(current_frame)
        if gray_a.shape != gray_b.shape:
            gray_b = cv2.resize(
                gray_b,
                (gray_a.shape[1], gray_a.shape[0]),
                interpolation=cv2.INTER_AREA,
            )
        mad = float(
            np.mean(np.abs(gray_a.astype(np.float32) - gray_b.astype(np.float32)))
        ) / 255.0
        hist_a = cv2.calcHist([gray_a], [0], None, [32], [0, 256])
        hist_b = cv2.calcHist([gray_b], [0], None, [32], [0, 256])
        cv2.normalize(hist_a, hist_a)
        cv2.normalize(hist_b, hist_b)
        correlation = float(
            cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
        )
        return mad >= 0.28 and correlation < 0.55
    except Exception:
        return False


def scan(video_path: str) -> dict:
    import cv2

    try:
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
    except Exception as exc:
        return {
            "ok": False,
            "reason": "independent_ocr_unavailable",
            "error_type": type(exc).__name__,
            "regions": [],
            "scanned_frames": 0,
        }

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "ok": False,
            "reason": "source_video_open_failed",
            "regions": [],
            "scanned_frames": 0,
        }
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if not math.isfinite(fps) or fps <= 0 or total_frames <= 0:
        cap.release()
        return {
            "ok": False,
            "reason": "source_video_timing_invalid",
            "regions": [],
            "scanned_frames": 0,
        }

    regions = []
    scanned = 0
    previous_time = -1.0
    previous_scene_frame = None
    scene_counter = 0
    try:
        for frame_index in range(total_frames):
            ok, frame = cap.read()
            if not ok or frame is None:
                return {
                    "ok": False,
                    "reason": "source_frame_decode_failed",
                    "regions": regions,
                    "scanned_frames": scanned,
                    "expected_frames": total_frames,
                }
            reported_msec = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
            time_value = reported_msec / 1000.0 if reported_msec > 0 else frame_index / fps
            if time_value <= previous_time:
                time_value = max(frame_index / fps, previous_time + 1.0 / fps)
            previous_time = time_value
            if _is_scene_cut(previous_scene_frame, frame):
                scene_counter += 1
            previous_scene_frame = frame

            output = engine(frame)
            detections = output[0] if isinstance(output, tuple) else output
            primary = _normalized_detections(detections)

            # The final renderer scales 720-wide sources to 1080. Small product
            # labels can therefore become readable only after rendering. Sample
            # a matching high-resolution OCR pass, then let the main pipeline's
            # frame-backed visual tracker fill the intervening frames.
            upscaled = []
            height, width = frame.shape[:2]
            if (
                width < UPSCALE_TARGET_WIDTH
                and frame_index % UPSCALE_SAMPLE_STRIDE == 0
            ):
                scale = min(2.0, UPSCALE_TARGET_WIDTH / float(max(1, width)))
                resized = cv2.resize(
                    frame,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_CUBIC,
                )
                scaled_output = engine(resized)
                scaled_detections = (
                    scaled_output[0]
                    if isinstance(scaled_output, tuple)
                    else scaled_output
                )
                upscaled = _normalized_detections(scaled_detections, scale=scale)

            scanned += 1
            for detection in _merge_frame_detections(primary, upscaled):
                regions.append(
                    {
                        "frame_index": frame_index,
                        "time": time_value,
                        "polygon": detection["polygon"],
                        "text": detection["text"],
                        "confidence": detection["confidence"],
                        "scene_id": f"rapidocr:{scene_counter}",
                    }
                )
            if scanned % 100 == 0:
                print(
                    f"[Source independent OCR] {scanned}/{total_frames} frames",
                    flush=True,
                )
    except Exception as exc:
        return {
            "ok": False,
            "reason": "independent_ocr_runtime_failed",
            "error_type": type(exc).__name__,
            "regions": regions,
            "scanned_frames": scanned,
            "expected_frames": total_frames,
        }
    finally:
        cap.release()

    return {
        "ok": scanned == total_frames,
        "engine": "rapidocr",
        "full_frame_scan": True,
        "regions": regions,
        "scanned_frames": scanned,
        "expected_frames": total_frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_path")
    parser.add_argument("result_path")
    args = parser.parse_args()
    if _restore_cached_scan(args.video_path, args.result_path):
        return 0
    result = scan(args.video_path)
    with open(args.result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False)
    _store_cached_scan(args.video_path, args.result_path, result)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
