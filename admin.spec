# -*- mode: python ; coding: utf-8 -*-
"""
Admin Dashboard PyInstaller Spec File
관리자 대시보드 빌드 설정 - 모든 모듈 포함
"""

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# ui 패키지 전체 수집
ui_datas, ui_binaries, ui_hiddenimports = collect_all('ui')

# requests 패키지 수집
requests_datas, requests_binaries, requests_hiddenimports = collect_all('requests')

# 모든 hiddenimports 합치기
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
] + ui_hiddenimports + requests_hiddenimports + collect_submodules('ui')

# ui 폴더를 datas에 추가
datas = [
    ('ui', 'ui'),
]

a = Analysis(
    ['admin_launcher.py'],
    pathex=[os.path.abspath('.')],
    binaries=ui_binaries + requests_binaries,
    datas=datas + ui_datas + requests_datas,
    hiddenimports=all_hiddenimports,
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
