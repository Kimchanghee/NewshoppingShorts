# -*- mode: python ; coding: utf-8 -*-
"""
Admin Dashboard PyInstaller Spec File
관리자 대시보드 빌드 설정
"""

block_cipher = None

a = Analysis(
    ['admin_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'PyQt5.QtCore',
        'requests',
        'urllib3',
        'ui',
        'ui.admin_dashboard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
        'google',
        'moviepy',
        'faster_whisper',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SSMaker_Admin',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SSMaker_Admin',
)
