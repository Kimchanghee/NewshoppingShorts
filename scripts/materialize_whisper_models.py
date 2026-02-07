# -*- coding: utf-8 -*-
"""
Materialize Faster-Whisper HuggingFace cache into flat files for bundling.

Why:
  HuggingFace cache uses symlinks under snapshots/ pointing to blobs/.
  PyInstaller often packages the symlink itself (0-byte/link stub) instead of
  the target content, causing runtime failures in frozen builds.

What this does:
  For each model size directory under `faster_whisper_models/<size>/`,
  copy (dereference) snapshot files into:
    faster_whisper_models/<size>/{model.bin,config.json,tokenizer.json,vocabulary.txt}
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


REQUIRED_FILES = ["model.bin", "config.json", "tokenizer.json", "vocabulary.txt"]


def _find_snapshot_dir(size_dir: Path) -> Path | None:
    # Expected: faster_whisper_models/<size>/models--*/snapshots/*/
    snapshots = []
    for model_dir in size_dir.glob("models--*/snapshots/*"):
        if not model_dir.is_dir():
            continue
        if (model_dir / "model.bin").exists():
            snapshots.append(model_dir)
    if not snapshots:
        return None
    # Prefer most recently modified snapshot.
    snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return snapshots[0]


def materialize_models(root: Path) -> int:
    changed = 0
    if not root.is_dir():
        print(f"[materialize] missing dir: {root}")
        return changed

    for size_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        snap = _find_snapshot_dir(size_dir)
        if snap is None:
            print(f"[materialize] skip (no snapshot): {size_dir.name}")
            continue

        print(f"[materialize] {size_dir.name}: snapshot={snap}")

        for fname in REQUIRED_FILES:
            src = snap / fname
            if not src.exists():
                print(f"  - missing in snapshot: {fname}")
                continue

            dst = size_dir / fname

            # Always overwrite; ensures we replace a previous symlink/stub.
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                # copy2 follows symlinks by default and copies the target content.
                shutil.copy2(src, dst)
            except OSError as e:
                print(f"  - copy failed {fname}: {e}")
                continue

            sz = dst.stat().st_size
            if fname == "model.bin" and sz < 10_000_000:
                # model.bin should be huge; warn loudly.
                print(f"  - WARN: model.bin too small after copy: {sz} bytes ({dst})")
            else:
                print(f"  - OK: {fname} ({sz} bytes)")
            changed += 1

    return changed


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    root = project_root / "faster_whisper_models"
    count = materialize_models(root)
    print(f"[materialize] done: {count} files updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

