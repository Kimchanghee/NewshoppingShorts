# -*- coding: utf-8 -*-
"""
영상 완성도(품질) 자동 분석 하네스.

렌더된 쇼츠(mp4)를 스캔해 해상도/9:16/길이/오디오 유무를 점검하고,
프레임 지각해시(aHash)로 서로 유사·중복인 영상을 그룹핑한다.

사용:
  python scripts/analyze_video_quality.py [--dir <folder>] [--limit N] [--json out.json]

기본 폴더: ~/.ssmaker/sourcing_output (sourcing_ 접두 원본 클립은 제외, 최종 렌더만).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _CV = True
except Exception:
    _CV = False


def ffprobe(path: str) -> dict:
    """Return {width,height,duration,has_audio} via ffprobe JSON."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        ).stdout
        data = json.loads(out or "{}")
    except Exception:
        return {"width": 0, "height": 0, "duration": 0.0, "has_audio": False}
    w = h = 0
    has_audio = False
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not w:
            w, h = int(s.get("width", 0) or 0), int(s.get("height", 0) or 0)
        if s.get("codec_type") == "audio":
            has_audio = True
    dur = float(data.get("format", {}).get("duration", 0) or 0)
    return {"width": w, "height": h, "duration": dur, "has_audio": has_audio}


def ahash(path: str) -> int | None:
    """8x8 average-hash of a frame ~1s in. None if unreadable."""
    if not _CV:
        return None
    try:
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * 1.0))
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        cap.release()
        if not ok:
            return None
        g = cv2.cvtColor(cv2.resize(frame, (8, 8)), cv2.COLOR_BGR2GRAY)
        bits = (g >= g.mean()).flatten()
        h = 0
        for b in bits:
            h = (h << 1) | int(b)
        return h
    except Exception:
        return None


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def find_finals(root: str) -> list[str]:
    finals = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if not fn.lower().endswith(".mp4"):
                continue
            if fn.startswith("sourcing_"):  # raw source clips, not finals
                continue
            if fn.endswith("_min8s.mp4"):   # short variant of same render
                continue
            finals.append(os.path.join(dp, fn))
    return finals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(os.path.expanduser("~"), ".ssmaker", "sourcing_output"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    finals = sorted(find_finals(args.dir), key=os.path.getmtime, reverse=True)
    if args.limit:
        finals = finals[: args.limit]
    print(f"분석 대상 최종 렌더: {len(finals)}개  (폴더: {args.dir})")
    if not finals:
        return 0

    rows = []
    hashes = {}
    for i, p in enumerate(finals, 1):
        meta = ffprobe(p)
        w, h, dur = meta["width"], meta["height"], meta["duration"]
        portrait_916 = bool(w and h and abs((w / h) - (9 / 16)) < 0.03)
        dur_ok = 3.0 <= dur <= 90.0
        rows.append({
            "file": os.path.basename(p), "path": p, "w": w, "h": h,
            "duration": round(dur, 1), "has_audio": meta["has_audio"],
            "portrait_916": portrait_916, "duration_ok": dur_ok,
        })
        hh = ahash(p)
        if hh is not None:
            hashes[p] = hh
        if i % 25 == 0:
            print(f"  ...{i}/{len(finals)}")

    # 품질 집계
    n = len(rows)
    def pct(k):
        c = sum(1 for r in rows if r[k]); return f"{c}/{n} ({100*c//max(1,n)}%)"
    print("=" * 64)
    print(f"9:16 세로형 :  {pct('portrait_916')}")
    print(f"길이 3~90s  :  {pct('duration_ok')}")
    print(f"오디오 있음 :  {pct('has_audio')}")
    res = defaultdict(int)
    for r in rows:
        res[f"{r['w']}x{r['h']}"] += 1
    print("해상도 분포 :  " + ", ".join(f"{k}×{v}" for k, v in sorted(res.items(), key=lambda x: -x[1])[:6]))

    # 중복 그룹 (aHash Hamming <= 6)
    items = list(hashes.items())
    seen = set()
    groups = []
    for i in range(len(items)):
        pi, hi = items[i]
        if pi in seen:
            continue
        grp = [pi]
        for j in range(i + 1, len(items)):
            pj, hj = items[j]
            if pj in seen:
                continue
            if hamming(hi, hj) <= 6:
                grp.append(pj); seen.add(pj)
        if len(grp) > 1:
            seen.add(pi); groups.append(grp)
    dup_files = sum(len(g) for g in groups)
    print("=" * 64)
    print(f"유사/중복 그룹: {len(groups)}개, 중복 영상 {dup_files}개 (aHash 유사)")
    for g in sorted(groups, key=len, reverse=True)[:8]:
        print(f"  [{len(g)}개] " + " | ".join(os.path.basename(x)[:40] for x in g[:4]) + (" ..." if len(g) > 4 else ""))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"rows": rows, "duplicate_groups": [[os.path.basename(x) for x in g] for g in groups]},
                      f, ensure_ascii=False, indent=2)
        print(f"\nJSON 저장: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
