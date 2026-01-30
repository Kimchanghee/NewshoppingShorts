# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import imageio_ffmpeg

datas = [('resource', 'resource'), ('fonts', 'fonts'), ('ui', 'ui'), ('core', 'core'), ('utils', 'utils'), ('managers', 'managers'), ('processors', 'processors'), ('caller', 'caller'), ('app', 'app'), ('prompts', 'prompts'), ('startup', 'startup')]
binaries = []
hiddenimports = ['faster_whisper', 'ctranslate2', 'rapidocr_onnxruntime', 'skimage', 'sklearn', 'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui', 'audioop', 'pyaudioop']

# Add ffmpeg binary explicitly - get path and copy to root
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
if ffmpeg_exe and os.path.exists(ffmpeg_exe):
    # Add ffmpeg binary explicitly to a dedicated 'ffmpeg' directory
    # This ensures we have a clean, known location regardless of imageio_ffmpeg internals
    binaries.append((ffmpeg_exe, 'ffmpeg'))
    
tmp_ret = collect_all('moviepy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('imageio')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('opencv-python')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('Pillow')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('numpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('scipy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pydub')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('edge_tts')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('yt_dlp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('google-genai')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('anthropic')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('fastapi')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sqlalchemy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pymysql')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Exclude API keys and sensitive files from build
excludes = [
    'pytest',
    'tests',
    '__pycache__',
    '*.pyc',
    '.git',
    'backend/.env',
    'api_keys_config.json',
    '*.env',
    '*_key.txt',
    '*_keys.txt',
    '*_keys.json',
    '~/.newshopping/.secrets',
    '~/.newshopping/.encryption_key',
]


a = Analysis(
    ['ssmaker.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ssmaker',
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
