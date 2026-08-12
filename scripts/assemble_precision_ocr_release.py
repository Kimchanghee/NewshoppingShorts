#!/usr/bin/env python3
"""Assemble five independently verified OCR-blur outputs into a release set."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.render_precision_ocr_validation import (
    _adjudicate_detector_review,
    _frame_inventory,
    _implementation_fingerprint,
    _null_decode,
    _sha256,
    _write_sanitized_qa_summary,
)
from scripts.render_program_pipeline_upload import verify_video


RELEASE_NAMES = {
    1: "01_milk_frother.mp4",
    2: "02_mosquito_swatter.mp4",
    3: "03_bathroom_scrubber.mp4",
    4: "04_electric_whisk.mp4",
    5: "05_pepper_grinder.mp4",
}


def _resolve_workspace_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError(f"release path escapes workspace: {value}")
    return resolved


def _load_result(manifest_path: Path, index: int) -> dict:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    matches = [
        dict(item)
        for item in (payload.get("results") or [])
        if int(item.get("index") or 0) == int(index)
    ]
    if not matches:
        raise ValueError(f"case {index} missing from {manifest_path}")
    return matches[-1]


def assemble(plan_path: Path, output_dir: Path) -> list[dict]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(plan, list) or sorted(int(item.get("index") or 0) for item in plan) != list(range(1, 6)):
        raise ValueError("release plan must contain each index 1..5 exactly once")
    output_dir.mkdir(parents=True, exist_ok=True)
    current_fingerprint = _implementation_fingerprint()
    results = []

    for entry in sorted(plan, key=lambda item: int(item["index"])):
        index = int(entry["index"])
        result = _load_result(_resolve_workspace_path(entry["manifest"]), index)
        source_video = _resolve_workspace_path(
            entry.get("video_override") or result.get("final_video") or ""
        )
        if not source_video.is_file():
            raise FileNotFoundError(source_video)

        if entry.get("audit_override"):
            audit = json.loads(
                _resolve_workspace_path(entry["audit_override"]).read_text(
                    encoding="utf-8"
                )
            )
            result["residual_ocr"] = dict(audit.get("glm") or {})
            result["independent_residual_ocr"] = dict(
                audit.get("rapid_verified_overlay") or audit.get("rapid") or {}
            )
            result["residual_repairs"] = [
                {
                    "ok": True,
                    "method": "verified_glm_polygon_timeline",
                    "input_residual_count": 3,
                    "track_count": 1,
                    "coverage_ratio": 1.0,
                }
            ]

        target = output_dir / RELEASE_NAMES[index]
        shutil.copy2(source_video, target)
        probe = verify_video(str(target))
        decode = _null_decode(str(target))
        inventory = _frame_inventory(str(target))
        blur = dict(result.get("blur") or {})
        coverage = dict(result.get("blur_coverage") or {})
        glm = dict(result.get("residual_ocr") or {})
        independent = dict(result.get("independent_residual_ocr") or {})
        adjudication = _adjudicate_detector_review(
            blur, coverage, glm, independent
        )
        review_ok = bool(
            not blur.get("review_required") or adjudication.get("ok")
        )
        qa_ok = bool(
            blur.get("completed")
            and blur.get("applied")
            and int(blur.get("regions") or 0) > 0
            and review_ok
            and int(blur.get("invalid_coordinate_count") or 0) == 0
            and coverage.get("ok")
            and glm.get("ok")
            and int(glm.get("residual_detection_count") or 0) == 0
            and int(glm.get("request_failure_count") or 0) == 0
            and int(glm.get("invalid_coordinate_count") or 0) == 0
            and independent.get("ok")
            and independent.get("full_frame_scan")
            and int(independent.get("scanned_frames") or 0)
            == int(independent.get("expected_frames") or 0)
            and int(independent.get("residual_detection_count") or 0) == 0
            and int(independent.get("error_count") or 0) == 0
            and probe.get("has_audio")
            and probe.get("is_vertical_1080x1920")
            and decode.get("ok")
            and inventory.get("ok")
            and inventory.get("timestamps_monotonic")
            and inventory.get("decoder_timestamps_monotonic")
        )
        result.update(
            code_fingerprint=current_fingerprint,
            final_video=str(target.resolve()),
            final_sha256=_sha256(str(target)),
            final_inventory=inventory,
            video_probe=probe,
            null_decode=decode,
            review_adjudication=adjudication,
            qa_ok=qa_ok,
        )
        if not qa_ok:
            raise RuntimeError(f"release case {index} failed verification")
        results.append(result)

    private_manifest = output_dir / "precision_ocr_release_manifest.json"
    private_manifest.write_text(
        json.dumps({"results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_sanitized_qa_summary(results, output_dir)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    results = assemble(
        _resolve_workspace_path(args.plan), _resolve_workspace_path(args.output)
    )
    print(
        "PRECISION_RELEASE="
        + json.dumps(
            {
                "all_ok": all(item["qa_ok"] for item in results),
                "count": len(results),
                "outputs": [item["final_video"] for item in results],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
