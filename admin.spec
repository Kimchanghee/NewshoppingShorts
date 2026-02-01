# -*- mode: python ; coding: utf-8 -*-
"""
Admin Dashboard PyInstaller Spec
관리자 대시보드 빌드 설정

사용법:
  pyinstaller --clean admin.spec
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files
import os

block_cipher = None

project_path = os.path.abspath('.')

# =============================================================================
# Data files
# =============================================================================
datas = [
    ('ui', 'ui'),
    ('caller', 'caller'),
    ('utils', 'utils'),
    ('resource', 'resource'),
    ('app', 'app'),
]

# Collect data files from key packages
try:
    datas += collect_data_files('certifi')
    print("[Build] Certifi data: included")
except:
    pass

# =============================================================================
# Binaries
# =============================================================================
binaries = []

# =============================================================================
# Hidden imports
# =============================================================================
all_hiddenimports = [
    # PyQt6
    'PyQt6',
    'PyQt6.QtWidgets',
    'PyQt6.QtGui',
    'PyQt6.QtCore',
    'PyQt6.sip',
    
    # Network
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    
    # Utils
    'logging',
    'json',
    'datetime',
    'threading',
    
    # App modules
    'ui.admin_dashboard',
    'caller.rest',
    'app.state',
]

# Collect submodules
all_hiddenimports += collect_submodules('ui')
all_hiddenimports += collect_submodules('caller')
all_hiddenimports += collect_submodules('app')

# Collect requests completely
requests_datas, requests_binaries, requests_hiddenimports = collect_all('requests')
datas += requests_datas
binaries += requests_binaries
all_hiddenimports += requests_hiddenimports

# Collect PyQt6 completely
try:
    pyqt6_datas, pyqt6_binaries, pyqt6_hiddenimports = collect_all('PyQt6')
    datas += pyqt6_datas
    binaries += pyqt6_binaries
    all_hiddenimports += pyqt6_hiddenimports
    print("[Build] PyQt6: fully collected")
except:
    print("[Build WARNING] PyQt6 collect_all failed")

# Remove duplicates
all_hiddenimports = list(set(all_hiddenimports))
print(f"[Build] Total hiddenimports: {len(all_hiddenimports)}")

excludes = [
    'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 
    'cv2', 'torch', 'tensorflow', 'google', 'moviepy', 
    'faster_whisper', 'whisper', 'openai-whisper',
    'vertexai', 'anthropic'
]

# =============================================================================
# Analysis
# =============================================================================
a = Analysis(
    ['admin_launcher.py'],
    pathex=[project_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# =============================================================================
# EXE
# =============================================================================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AdminDashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resource/app_icon.ico' if os.path.exists('resource/app_icon.ico') else None,
)
