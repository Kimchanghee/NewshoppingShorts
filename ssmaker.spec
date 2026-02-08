# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

block_cipher = None
project_root = os.path.abspath('.')

# ─────────────────────────────────────────────────────────────────────────────
# 1. Dependency Collection
# ─────────────────────────────────────────────────────────────────────────────
packages_to_collect = [
    'moviepy', 
    'imageio',
    'imageio_ffmpeg',
    'openai', 
    'google.genai',
    'faster_whisper',
    'ctranslate2',
    'onnxruntime',
    'PIL',
    'cv2',
    'PyQt6',
    'qtawesome',
    'pandas',
    'numpy',
    'requests',
    'tqdm',
]

hidden_imports = []
datas = [
    ('resource', 'resource'),
    # Fonts are intentionally not bundled (see .gitignore). The app falls back to system fonts.
    ('version.json', '.'),
]

binaries = []

for package in packages_to_collect:
    try:
        tmp_ret = collect_all(package)
    except Exception as e:
        # Keep CI/builds resilient when optional packages are not installed.
        print(f"[spec] WARNING: collect_all('{package}') failed: {e!r}")
        continue
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hidden_imports += tmp_ret[2]

# Some packages (e.g. imageio) call importlib.metadata at runtime.
# PyInstaller does not include package metadata unless explicitly requested.
for dist_name in ("imageio", "imageio-ffmpeg", "moviepy"):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass

# Include updater.exe in the bundle (auto-update extracts it next to ssmaker.exe).
_updater_exe = os.path.join(project_root, "dist", "updater.exe")
if os.path.exists(_updater_exe):
    datas.append((_updater_exe, "."))

if os.path.exists('faster_whisper_models'):
    # Include only materialized flat files to avoid shipping HF cache symlinks.
    model_root = os.path.join(project_root, "faster_whisper_models")
    print(f"[spec] Including faster_whisper_models from: {model_root}")
    model_files_added = 0
    for size in os.listdir(model_root):
        size_dir = os.path.join(model_root, size)
        if not os.path.isdir(size_dir):
            continue
        for fname in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
            src = os.path.join(size_dir, fname)
            if os.path.exists(src):
                size_mb = os.path.getsize(src) / (1024 * 1024)
                dst_path = os.path.join("faster_whisper_models", size)
                print(f"[spec]   Adding: {fname} ({size_mb:.1f}MB) -> {dst_path}")
                datas.append((src, dst_path))
                model_files_added += 1
    print(f"[spec] Total faster_whisper model files added: {model_files_added}")
else:
    print("[spec] WARNING: faster_whisper_models directory not found!")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Analysis
# ─────────────────────────────────────────────────────────────────────────────
a = Analysis(
    ['ssmaker.py'],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ─────────────────────────────────────────────────────────────────────────────
# 3. PYZ & EXE (One-File 모드로 통합)
# ─────────────────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,   # 바이너리 직접 포함
    a.zipfiles,   # zip파일 직접 포함
    a.datas,      # 모든 데이터 직접 포함
    [],
    name='ssmaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None, # 실행 시 임시 폴더에 압축 해제
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resource/app_icon.ico' if os.path.exists('resource/app_icon.ico') else None,
    uac_admin=True,
)
