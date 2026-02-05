# -*- mode: python ; coding: utf-8 -*-
"""
Admin Dashboard PyInstaller Spec
관리자 대시보드 단일 EXE 빌드

사용법:
  pyinstaller --clean admin.spec
"""

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

print("=" * 60)
print("[Build] Admin Dashboard Build Starting...")
print("=" * 60)

# =============================================================================
# Data files
# =============================================================================
datas = [
    ('resource', 'resource'),
]

# certifi (SSL)
try:
    datas += collect_data_files('certifi')
    print("[Build] certifi data: included")
except Exception:
    pass

# =============================================================================
# Hidden imports
# =============================================================================
hiddenimports = [
    # PyQt6
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtGui', 'PyQt6.QtCore', 'PyQt6.sip',

    # Network
    'requests', 'requests.adapters', 'requests.auth',
    'urllib3', 'certifi', 'charset_normalizer', 'idna',

    # App modules
    'ui.admin_dashboard',
    'ui.admin_dialogs',
    'ui.design_system_v2',
    'ui.components.admin_loading_splash',

    # dotenv (optional)
    'dotenv',
]

# PyQt6 submodules
try:
    hiddenimports += collect_submodules('PyQt6')
    print("[Build] PyQt6 submodules: collected")
except Exception:
    pass

hiddenimports = list(set(hiddenimports))
print(f"[Build] Total: {len(hiddenimports)} imports")

# =============================================================================
# Analysis
# =============================================================================
a = Analysis(
    ['admin_launcher.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PySide6',
        'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL',
        'cv2', 'torch', 'tensorflow', 'moviepy',
        'faster_whisper', 'ctranslate2', 'whisper',
        'vertexai', 'anthropic', 'google.genai',
        'pydub', 'imageio', 'imageio_ffmpeg',
        'pytest', 'IPython', 'jupyter', 'notebook',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# =============================================================================
# EXE - Single file
# =============================================================================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AdminDashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'msvcp140.dll',
        'python*.dll',
        'Qt*.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resource/app_icon.ico' if os.path.exists('resource/app_icon.ico') else None,
)
