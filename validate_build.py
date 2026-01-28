"""
Pre-execution validation script for ssmaker build
Checks if all required files and dependencies are present before running the application
"""

import os
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def check_file_exists(path, description):
    """Check if a file exists and print the result"""
    exists = os.path.exists(path)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists


def check_directory_exists(path, description):
    """Check if a directory exists and print the result"""
    exists = os.path.isdir(path)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists


def get_directory_size(path):
    """Calculate total size of a directory in GB"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().size
            elif entry.is_dir(follow_symlinks=False):
                total += get_directory_size(entry.path)
    except Exception as e:
        print(f"  Warning: Could not calculate size for {path}: {e}")
    return total / (1024**3)


def validate_build():
    """Main validation function"""
    print("=" * 60)
    print("SSMaker Build Validation Script")
    print("=" * 60)
    print()

    # Determine build directory
    script_dir = Path(__file__).parent
    build_dir = script_dir / "dist" / "ssmaker"

    print(f"Build directory: {build_dir}")
    print()

    all_checks_passed = True

    # Check main executable
    print("[1] Main Executable")
    exe_path = build_dir / "ssmaker.exe"
    if check_file_exists(exe_path, "ssmaker.exe"):
        size_mb = os.path.getsize(exe_path) / (1024**2)
        print(f"    Size: {size_mb:.2f} MB")
    else:
        all_checks_passed = False
    print()

    # Check _internal directory
    print("[2] Dependencies Directory")
    internal_dir = build_dir / "_internal"
    if check_directory_exists(internal_dir, "_internal folder"):
        size_gb = get_directory_size(internal_dir)
        print(f"    Size: {size_gb:.2f} GB")
    else:
        all_checks_passed = False
        print()
        return all_checks_passed
    print()

    # Check critical Python packages
    print("[3] Critical Python Dependencies")
    critical_packages = [
        ("onnxruntime", "ONNX Runtime for AI model inference"),
        ("faster_whisper", "Faster-Whisper STT engine"),
        ("ctranslate2", "CTranslate2 inference engine"),
        ("rapidocr_onnxruntime", "OCR engine"),
        ("certifi", "SSL certificates"),
    ]

    for package, description in critical_packages:
        package_path = internal_dir / package
        if not check_directory_exists(package_path, f"{package} - {description}"):
            all_checks_passed = False
    print()

    # Check FFmpeg
    print("[4] FFmpeg (Video Processing)")
    imageio_ffmpeg_path = internal_dir / "imageio_ffmpeg"
    if not check_directory_exists(imageio_ffmpeg_path, "imageio_ffmpeg"):
        all_checks_passed = False
    print()

    # Check SSL libraries
    print("[5] SSL Libraries")
    ssl_pyd = internal_dir / "_ssl.pyd"
    libssl_dll = internal_dir / "libssl-3.dll"
    if not check_file_exists(ssl_pyd, "_ssl.pyd"):
        all_checks_passed = False
    if not check_file_exists(libssl_dll, "libssl-3.dll"):
        all_checks_passed = False
    print()

    # Check Faster-Whisper models (CTranslate2 format)
    print("[6] Faster-Whisper AI Models")
    whisper_models_dir = internal_dir / "faster_whisper_models"
    if check_directory_exists(whisper_models_dir, "faster_whisper_models folder"):
        # Faster-Whisper 모델은 폴더 구조: {model_size}/model.bin
        models = ["tiny", "base", "small"]
        models_found = 0
        for model in models:
            model_dir = whisper_models_dir / model
            model_bin = model_dir / "model.bin"
            if os.path.isdir(model_dir):
                if check_file_exists(model_bin, f"  {model}/model.bin"):
                    size_mb = os.path.getsize(model_bin) / (1024**2)
                    if size_mb < 1024:
                        print(f"      Size: {size_mb:.0f} MB")
                    else:
                        print(f"      Size: {size_mb/1024:.1f} GB")
                    models_found += 1
                else:
                    print(f"  ✗ {model}/model.bin not found (optional)")
            else:
                print(f"  - {model} model not downloaded (optional)")

        if models_found == 0:
            print("  ⚠ No Faster-Whisper models found - will download on first run")

        total_size = get_directory_size(whisper_models_dir)
        print(f"    Total models size: {total_size:.2f} GB")
    else:
        print("  ⚠ faster_whisper_models folder not found - models will download on first run")
        # 모델이 없어도 빌드는 성공으로 처리 (첫 실행 시 다운로드)
    print()

    # Final result
    print("=" * 60)
    if all_checks_passed:
        print("✓ ALL CHECKS PASSED - Build is ready for distribution")
        print("=" * 60)
        return True
    else:
        print("✗ VALIDATION FAILED - Some required files are missing")
        print("=" * 60)
        print()
        print("Recommended actions:")
        print("1. Run: python download_whisper_models.py")
        print("2. Run: pyinstaller --clean -y ssmaker.spec")
        print("3. Run this validation script again")
        return False


if __name__ == "__main__":
    success = validate_build()
    sys.exit(0 if success else 1)
