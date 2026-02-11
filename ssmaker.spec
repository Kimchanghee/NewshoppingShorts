# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_submodules

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
    # 'onnxruntime', # Removed to fix access violation on Python 3.13
    'PIL',
    'cv2',
    'PyQt6',
    'qtawesome',
    'pandas',
    'numpy',
    'requests',
    'tqdm',
    'pytesseract',  # OCR support (Tesseract)
    # TTS / Audio processing
    'pydub',
    'edge_tts',
    'av',
    # Browser automation (optional feature set but should be bundled if installed)
    'selenium',
    'webdriver_manager',
    'bs4',
]

hidden_imports = [
    # 'rapidocr_onnxruntime', # Removed due to Access Violation crash on Python 3.13
    # 'shapely',
    # 'pyclipper',
]
datas = [
    ('resource', 'resource'),
    ('version.json', '.'),
]

# Bundle .env file for GLM-OCR API key (if present at build time)
# Bundle .env file was previously included here, but is now excluded for security.
# _env_file = os.path.join(project_root, '.env')
# if os.path.exists(_env_file):
#     datas.append((_env_file, '.'))
#     print("[spec] Including .env file for API key configuration")

# Bundle encrypted secure config (if present at build time)
_secure_config = os.path.join(project_root, 'utils', '.secure_config.enc')
if os.path.exists(_secure_config):
    datas.append((_secure_config, '.'))
    print("[spec] Including .secure_config.enc for encrypted API keys")

_fonts_dir = os.path.join(project_root, 'fonts')
if os.path.isdir(_fonts_dir):
    datas.append((_fonts_dir, 'fonts'))
else:
    print(f"[spec] WARNING: fonts directory not found: {_fonts_dir}")

# Bundle Tesseract runtime (exe + DLLs + tessdata) for end-user machines.
_tesseract_bundle = os.path.join(project_root, 'build_staging', 'tesseract')
if os.path.isdir(_tesseract_bundle):
    datas.append((_tesseract_bundle, 'tesseract'))
else:
    print(f"[spec] WARNING: tesseract bundle not found (blur OCR may not work on user PCs): {_tesseract_bundle}")

binaries = []

# ─────────────────────────────────────────────────────────────────────────────
# Bundle Visual C++ Runtime DLLs explicitly for target machines
# without VC++ Redistributable installed (fixes "Failed to load Python DLL" error).
# ─────────────────────────────────────────────────────────────────────────────
import sysconfig as _sysconfig
_python_base = _sysconfig.get_config_var('base') or os.path.dirname(sys.executable)
for _vcrt_name in ('vcruntime140.dll', 'vcruntime140_1.dll'):
    # 1st priority: Python installation directory (MS Store / official installer)
    _vcrt_path = os.path.join(sys.base_prefix, _vcrt_name)
    if not os.path.exists(_vcrt_path):
        # 2nd priority: System32
        _vcrt_path = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', _vcrt_name)
    if os.path.exists(_vcrt_path):
        binaries.append((_vcrt_path, '.'))
        print(f"[spec] Bundling VC runtime: {_vcrt_path}")
    else:
        print(f"[spec] WARNING: {_vcrt_name} not found - target PCs may need VC++ Redistributable")

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

# Some packages are imported dynamically at runtime (lazy imports) and might be missed by Analysis.
# Force-include their submodules so end-users do not see ModuleNotFoundError.
for mod_name in ("selenium", "webdriver_manager", "bs4", "pydub", "edge_tts", "av"):
    try:
        hidden_imports += collect_submodules(mod_name)
    except Exception as e:
        print(f"[spec] WARNING: collect_submodules('{mod_name}') failed: {e!r}")

# Some packages (e.g. imageio) call importlib.metadata at runtime.
# PyInstaller does not include package metadata unless explicitly requested.
for dist_name in ("imageio", "imageio-ffmpeg", "moviepy"):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass

# Note: updater.exe is no longer bundled. Updates are handled by
# downloading and running the Inno Setup installer silently.

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
    excludes=['tkinter', 'test', 'unittest', 'matplotlib', 'onnxruntime'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ─────────────────────────────────────────────────────────────────────────────
# 3. PYZ & EXE + COLLECT (One-Dir 모드 — Inno Setup 인스톨러와 함께 배포)
# ─────────────────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],                       # onedir: 바이너리/데이터는 COLLECT에서 처리
    exclude_binaries=True,    # EXE에 바이너리 포함하지 않음
    name='ssmaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resource/app_icon.ico' if os.path.exists('resource/app_icon.ico') else None,
    uac_admin=False,
    contents_directory='.',   # 모든 파일을 EXE와 같은 디렉토리에 배치 (flat 구조)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ssmaker',
)
