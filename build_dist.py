# -*- coding: utf-8 -*-
"""
SSMaker Distribution Builder

원클릭 빌드: ssmaker.exe 단일 파일 배포 (updater.exe 내장)

사용법:
  python build_dist.py
"""

import os
import sys
import json
import shutil
import subprocess
import time
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
VERSION_FILE = ROOT_DIR / "version.json"


def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def clean_build():
    """이전 빌드 아티팩트 정리"""
    log("Cleaning previous build artifacts...")
    for d in [BUILD_DIR, DIST_DIR]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            log(f"  Removed: {d}")
    DIST_DIR.mkdir(parents=True, exist_ok=True)


def update_version_json():
    """version.json 빌드 날짜/번호 업데이트"""
    if not VERSION_FILE.exists():
        data = {
            "version": "1.1.0",
            "build_date": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "build_number": "1",
            "min_required_version": "1.0.0",
            "update_channel": "stable"
        }
    else:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        data["build_date"] = datetime.now().strftime("%Y-%m-%d")
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["build_number"] = str(int(data.get("build_number", "0")) + 1)

    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    log(f"Version: {data['version']} (build #{data['build_number']})")
    return data


def build_updater():
    """updater.exe 빌드 (ssmaker.exe 안에 번들될 예정)"""
    spec_file = ROOT_DIR / "updater.spec"
    if not spec_file.exists():
        log("updater.spec not found, skipping updater build", "WARNING")
        return False

    log("Building updater.exe (will be bundled inside ssmaker.exe)...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", str(spec_file)],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        log(f"updater.exe build FAILED:\n{result.stderr[-500:]}", "ERROR")
        return False

    updater_exe = DIST_DIR / "updater.exe"
    if updater_exe.exists():
        size_mb = updater_exe.stat().st_size / 1024 / 1024
        log(f"updater.exe built: {size_mb:.1f} MB (will be embedded in ssmaker.exe)")
        return True

    log("updater.exe not found after build", "ERROR")
    return False


def build_ssmaker():
    """ssmaker.exe 빌드 (updater.exe 포함 단일 파일)"""
    spec_file = ROOT_DIR / "ssmaker_simple.spec"
    if not spec_file.exists():
        log("ssmaker_simple.spec not found!", "ERROR")
        return False

    # updater.exe가 dist/에 있는지 확인 (spec에서 'dist/updater.exe'로 참조)
    updater_in_dist = DIST_DIR / "updater.exe"
    if not updater_in_dist.exists():
        log("WARNING: updater.exe not in dist/ - auto-update will not work", "WARNING")

    log("Building ssmaker.exe (this may take several minutes)...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", str(spec_file)],
        cwd=str(ROOT_DIR),
        timeout=1200,
    )

    if result.returncode != 0:
        log("ssmaker.exe build FAILED", "ERROR")
        return False

    ssmaker_exe = DIST_DIR / "ssmaker.exe"
    if ssmaker_exe.exists():
        size_mb = ssmaker_exe.stat().st_size / 1024 / 1024
        log(f"ssmaker.exe: {size_mb:.1f} MB (single-file distribution)")
        return True

    log("ssmaker.exe not found after build", "ERROR")
    return False


def print_summary():
    """빌드 결과 요약"""
    ssmaker_exe = DIST_DIR / "ssmaker.exe"
    if not ssmaker_exe.exists():
        log("ssmaker.exe not found!", "ERROR")
        return

    size_mb = ssmaker_exe.stat().st_size / 1024 / 1024

    print("\n" + "=" * 60)
    print("  [Build Complete] Single-file Distribution")
    print("=" * 60)
    print(f"  ssmaker.exe              {size_mb:>10.1f} MB")
    print(f"  {'-' * 40}")
    print(f"  Location: {ssmaker_exe}")
    print("")
    print("  This single file contains everything:")
    print("  - All Python packages & modules")
    print("  - Fonts, TTS audio samples, resources")
    print("  - FFmpeg, Whisper models")
    print("  - Auto-updater (embedded)")
    print("=" * 60)


def main():
    start = time.time()
    print("=" * 60)
    print("  SSMaker Single-File Distribution Builder")
    print("=" * 60)

    # 1. Clean
    clean_build()

    # 2. Update version
    update_version_json()

    # 3. Build updater.exe first (will be embedded in ssmaker.exe)
    updater_ok = build_updater()
    if not updater_ok:
        log("Continuing without updater.exe (auto-update disabled)", "WARNING")

    # 4. Build ssmaker.exe (includes updater.exe inside)
    ssmaker_ok = build_ssmaker()
    if not ssmaker_ok:
        log("ssmaker.exe build failed! Aborting.", "ERROR")
        sys.exit(1)

    # 5. Summary
    elapsed = time.time() - start
    print_summary()
    log(f"Build completed in {elapsed:.0f}s ({elapsed / 60:.1f}min)")
    print("\nDistribute: dist/ssmaker.exe (single file, everything included)")


if __name__ == "__main__":
    main()
