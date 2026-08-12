#!/usr/bin/env python3
"""Isolated high-resolution OCR pass for small rotated top-corner labels."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from importlib.metadata import version
from pathlib import Path
import shutil

try:
    from independent_rapidocr_source_scan import _has_chinese, _is_scene_cut
except ModuleNotFoundError:  # imported as ``scripts.*`` by unit tests/app code
    from scripts.independent_rapidocr_source_scan import _has_chinese, _is_scene_cut


SAMPLE_STRIDE = 3
CROP_WIDTH = 360
CROP_HEIGHT = 220
UPSCALE = 3.0
SIDE_SAMPLE_STRIDE = 2
SIDE_CROP_WIDTH = 300
SIDE_UPSCALE = 1.5


def _cache_path(video_path: str) -> Path:
    digest = hashlib.sha256()
    with open(video_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    digest.update(Path(__file__).read_bytes())
    digest.update(
        (Path(__file__).with_name("independent_rapidocr_source_scan.py")).read_bytes()
    )
    try:
        digest.update(version("rapidocr-onnxruntime").encode("utf-8"))
    except Exception:
        digest.update(b"rapidocr-version-unknown")
    root = Path(__file__).resolve().parents[1]
    return (
        root
        / "artifacts"
        / "precision_ocr_cache"
        / "corner_scans"
        / f"{digest.hexdigest()}.json"
    )


def _restore(video_path: str, result_path: str) -> bool:
    try:
        cache_path = _cache_path(video_path)
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if not (
            isinstance(payload, dict)
            and payload.get("ok")
            and int(payload.get("scanned_frames", -1))
            == int(payload.get("expected_frames", -2))
        ):
            return False
        shutil.copyfile(cache_path, result_path)
        print("[Source corner OCR] verified cache hit", flush=True)
        return True
    except Exception:
        return False


def _store(video_path: str, result_path: str, result: dict) -> None:
    if not result.get("ok"):
        return
    cache_path = _cache_path(video_path)
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


def _map_top_corner_detections(
    detections, *, frame_width: int, frame_height: int, crop_width: int,
    crop_height: int, scale: float = UPSCALE
) -> list[dict]:
    """Map a left+right top-corner montage back to source-frame pixels."""
    mapped = []
    safe_scale = max(1e-6, float(scale))
    split = float(crop_width)
    for detection in detections or []:
        if not isinstance(detection, (list, tuple)) or len(detection) < 3:
            continue
        polygon, text_value, confidence_value = detection[:3]
        try:
            confidence = float(confidence_value)
            montage_points = [
                [float(point[0]) / safe_scale, float(point[1]) / safe_scale]
                for point in polygon
            ]
        except (TypeError, ValueError, IndexError):
            continue
        if (
            len(montage_points) < 4
            or confidence < 0.45
            or not _has_chinese(text_value)
        ):
            continue
        xs = [point[0] for point in montage_points]
        center_x = sum(xs) / len(xs)
        # A detector box crossing the synthetic seam does not represent one
        # physical source label and must never become a broad blur mask.
        if min(xs) < split < max(xs):
            continue
        right_corner = center_x >= split
        x_offset = frame_width - crop_width if right_corner else 0
        montage_offset = split if right_corner else 0.0
        points = [
            [
                max(
                    0.0,
                    min(float(frame_width - 1), x_offset + point[0] - montage_offset),
                ),
                max(0.0, min(float(frame_height - 1), point[1])),
            ]
            for point in montage_points
        ]
        if max(point[1] for point in points) > crop_height + 1:
            continue
        mapped.append(
            {
                "polygon": points,
                "text": str(text_value or ""),
                "confidence": confidence,
            }
        )
    return mapped


def _map_side_strip_detections(
    detections, *, frame_width: int, frame_height: int, crop_width: int,
    scale: float = SIDE_UPSCALE
) -> list[dict]:
    """Map a left+right full-height strip montage back to source pixels."""
    mapped = []
    safe_scale = max(1e-6, float(scale))
    split = float(crop_width)
    for detection in detections or []:
        if not isinstance(detection, (list, tuple)) or len(detection) < 3:
            continue
        polygon, text_value, confidence_value = detection[:3]
        try:
            confidence = float(confidence_value)
            montage_points = [
                [float(point[0]) / safe_scale, float(point[1]) / safe_scale]
                for point in polygon
            ]
        except (TypeError, ValueError, IndexError):
            continue
        if (
            len(montage_points) < 4
            or confidence < 0.45
            or not _has_chinese(text_value)
        ):
            continue
        xs = [point[0] for point in montage_points]
        if min(xs) < split < max(xs):
            continue
        right_side = sum(xs) / len(xs) >= split
        x_offset = frame_width - crop_width if right_side else 0
        montage_offset = split if right_side else 0.0
        points = [
            [
                max(
                    0.0,
                    min(float(frame_width - 1), x_offset + point[0] - montage_offset),
                ),
                max(0.0, min(float(frame_height - 1), point[1])),
            ]
            for point in montage_points
        ]
        mapped.append(
            {
                "polygon": points,
                "text": str(text_value or ""),
                "confidence": confidence,
            }
        )
    return mapped


def scan(video_path: str) -> dict:
    import cv2
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"ok": False, "reason": "source_video_open_failed", "regions": []}
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if not math.isfinite(fps) or fps <= 0 or total_frames <= 0:
        cap.release()
        return {"ok": False, "reason": "source_video_timing_invalid", "regions": []}
    engine = RapidOCR()
    regions = []
    scanned = 0
    scene_counter = 0
    previous_scene_frame = None
    previous_time = -1.0
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
            scanned += 1
            height, width = frame.shape[:2]
            frame_detections = []
            if frame_index % SAMPLE_STRIDE == 0:
                crop_width = min(CROP_WIDTH, max(1, width // 2))
                crop_height = min(CROP_HEIGHT, height)
                montage = np.concatenate(
                    [
                        frame[:crop_height, :crop_width],
                        frame[:crop_height, width - crop_width :],
                    ],
                    axis=1,
                )
                enlarged = cv2.resize(
                    montage,
                    None,
                    fx=UPSCALE,
                    fy=UPSCALE,
                    interpolation=cv2.INTER_CUBIC,
                )
                output = engine(enlarged)
                detections = output[0] if isinstance(output, tuple) else output
                frame_detections.extend(
                    _map_top_corner_detections(
                        detections,
                        frame_width=width,
                        frame_height=height,
                        crop_width=crop_width,
                        crop_height=crop_height,
                    )
                )
            if frame_index % SIDE_SAMPLE_STRIDE == 0:
                side_width = min(SIDE_CROP_WIDTH, max(1, width // 2))
                side_montage = np.concatenate(
                    [frame[:, :side_width], frame[:, width - side_width :]], axis=1
                )
                side_enlarged = cv2.resize(
                    side_montage,
                    None,
                    fx=SIDE_UPSCALE,
                    fy=SIDE_UPSCALE,
                    interpolation=cv2.INTER_CUBIC,
                )
                side_output = engine(side_enlarged)
                side_detections = (
                    side_output[0] if isinstance(side_output, tuple) else side_output
                )
                frame_detections.extend(
                    _map_side_strip_detections(
                        side_detections,
                        frame_width=width,
                        frame_height=height,
                        crop_width=side_width,
                    )
                )
            for detection in frame_detections:
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
            if scanned % 300 == 0:
                print(f"[Source corner OCR] {scanned}/{total_frames} frames", flush=True)
    finally:
        cap.release()
    return {
        "ok": scanned == total_frames,
        "engine": "rapidocr_corner",
        "regions": regions,
        "scanned_frames": scanned,
        "expected_frames": total_frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_path")
    parser.add_argument("result_path")
    args = parser.parse_args()
    if _restore(args.video_path, args.result_path):
        return 0
    result = scan(args.video_path)
    with open(args.result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False)
    _store(args.video_path, args.result_path, result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
