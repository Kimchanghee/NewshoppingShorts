# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules
import os

block_cipher = None

project_path = os.path.abspath('.')

# Data files
datas = [
    ('ui', 'ui'),
    ('caller', 'caller'),
    ('utils', 'utils'),
    ('resource', 'resource'),
]

# Binaries
binaries = []

# Hidden imports
all_hiddenimports = [
    'PyQt5',
    'PyQt5.QtWidgets',
    'PyQt5.QtGui',
    'PyQt5.QtCore',
    'PyQt5.sip',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
] + collect_submodules('ui') + collect_submodules('caller') + collect_submodules('utils')

# Collect requests completely
requests_datas, requests_binaries, requests_hiddenimports = collect_all('requests')
datas += requests_datas
binaries += requests_binaries
all_hiddenimports += requests_hiddenimports

excludes = [
    'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 
    'cv2', 'torch', 'tensorflow', 'google', 'moviepy', 
    'faster_whisper', 'whisper', 'openai-whisper'
]

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
    icon=['resource\\app_icon.ico'],
)

# COLLECT is not needed for --onefile mode
