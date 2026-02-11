# -*- mode: python ; coding: utf-8 -*-
"""
Admin Dashboard PyInstaller Spec
관리자 대시보드 빌드 설정 (standalone exe, 설치형 X)

Usage:
  python -m PyInstaller admin_dashboard.spec
"""
import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None
project_root = os.path.abspath('.')

# ─────────────────────────────────────────────────────────────────────────────
# 1. Data & Dependencies
# ─────────────────────────────────────────────────────────────────────────────
datas = [
    ('resource', 'resource'),
]

# Bundle .env if present (contains SSMAKER_ADMIN_KEY)
_env_file = os.path.join(project_root, '.env')
if os.path.exists(_env_file):
    datas.append((_env_file, '.'))
    print("[admin_spec] Including .env for admin key")

hidden_imports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'requests',
    'dotenv',
    'ui.design_system_v2',
    'ui.admin_dashboard',
    'ui.admin_dialogs',
    'ui.components.admin_loading_splash',
]

binaries = []

# Collect PyQt6 fully (plugins, etc.)
for pkg in ['PyQt6']:
    try:
        tmp = collect_all(pkg)
        datas += tmp[0]
        binaries += tmp[1]
        hidden_imports += tmp[2]
    except Exception as e:
        print(f"[admin_spec] WARNING: collect_all('{pkg}') failed: {e!r}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Analysis
# ─────────────────────────────────────────────────────────────────────────────
a = Analysis(
    ['scripts/admin_launcher.py'],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'numpy', 'pandas', 'scipy',
        'moviepy', 'faster_whisper', 'ctranslate2',
        'onnxruntime', 'tkinter', 'matplotlib',
        'PIL', 'cv2', 'tensorflow',
        'openai', 'google.generativeai', 'google.genai',
        'pydub', 'edge_tts', 'av',
        'selenium', 'webdriver_manager', 'bs4',
        'pytesseract', 'imageio', 'imageio_ffmpeg',
        'tqdm',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Build (onefile - 단일 exe)
# ─────────────────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='admin_dashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resource/admin_icon.ico',
)
