# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hidden_imports = [
    'PyQt6.sip',
    'google.genai', 'google.genai.types',
    'google.oauth2.credentials',
    'moviepy.video.fx.all',
    'pydub.effects', 'pydub.utils',
    'rapidocr_onnxruntime', 'onnxruntime.capi',
    'faster_whisper', 'ctranslate2',
    'ui.components.custom_dialog',
]
hidden_imports += collect_submodules('vertexai')
hidden_imports += collect_submodules('google.cloud.aiplatform')
hidden_imports += collect_submodules('google.api_core')
hidden_imports += collect_submodules('grpc')
hidden_imports += collect_submodules('PyQt6')

datas = [
    ('resource', 'resource'),
    ('version.json', '.'),
    ('fonts', 'fonts'),
]
# Only include whisper models if folder exists
if os.path.exists('faster_whisper_models'):
    datas.append(('faster_whisper_models', 'faster_whisper_models'))
datas += collect_data_files('vertexai')
datas += collect_data_files('google.cloud.aiplatform')
datas += collect_data_files('certifi')
datas += collect_data_files('imageio_ffmpeg')

a = Analysis(
    ['ssmaker.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[],
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
)
