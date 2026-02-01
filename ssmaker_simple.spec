# -*- mode: python ; coding: utf-8 -*-
"""
Shopping Shorts Maker - Simple PyInstaller Spec

사용법:
  pyinstaller --onefile --windowed --clean ssmaker_simple.spec
"""

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

print("=" * 60)
print("[Build] Starting build...")
print("=" * 60)

# =============================================================================
# Data files
# =============================================================================
datas = [
    ('fonts', 'fonts'),
    ('config', 'config'),
    ('core', 'core'),
    ('core/video', 'core/video'),
    ('core/video/batch', 'core/video/batch'),
    ('core/audio', 'core/audio'),
    ('core/api', 'core/api'),
    ('core/download', 'core/download'),
    ('utils', 'utils'),
    ('managers', 'managers'),
    ('processors', 'processors'),
    ('caller', 'caller'),
    ('app', 'app'),
    ('prompts', 'prompts'),
    ('startup', 'startup'),
    ('ui', 'ui'),
    ('ui/windows', 'ui/windows'),
    ('ui/panels', 'ui/panels'),
    ('ui/components', 'ui/components'),
    ('voice_profiles.py', '.'),
    ('resource', 'resource'),
]

# Collect data files from key packages
try:
    datas += collect_data_files('rapidocr_onnxruntime')
    print(f"[Build] RapidOCR data: included")
except:
    print("[Build WARNING] RapidOCR not installed")



try:
    datas += collect_data_files('faster_whisper')
    print(f"[Build] Faster-Whisper data: included")
except:
    print("[Build WARNING] Faster-Whisper not installed")

try:
    datas += collect_data_files('ctranslate2')
    print(f"[Build] CTranslate2 data: included")
except:
    print("[Build WARNING] CTranslate2 not installed")





# =============================================================================
# Binaries
# =============================================================================
binaries = []

# FFmpeg binary
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if ffmpeg_exe and os.path.exists(ffmpeg_exe):
        binaries += [(ffmpeg_exe, 'imageio_ffmpeg')]
        print(f"[Build] FFmpeg: {ffmpeg_exe}")
except:
    print("[Build WARNING] FFmpeg binary not found")

# ONNX Runtime DLL (for OCR)
try:
    import onnxruntime
    ort_path = os.path.dirname(onnxruntime.__file__)
    capi_path = os.path.join(ort_path, 'capi')
    if os.path.exists(capi_path):
        for dll_file in os.listdir(capi_path):
            if dll_file.endswith(('.dll', '.pyd')):
                full_path = os.path.join(capi_path, dll_file)
                binaries += [(full_path, 'onnxruntime/capi')]
                print(f"[Build] ONNX Runtime binary: {dll_file}")
except:
    print("[Build WARNING] ONNX Runtime binaries not found")

# VC++ Runtime DLL (for onnxruntime)
vc_runtime_dlls = [
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'concrt140.dll',
]
for dll_name in vc_runtime_dlls:
    for sys_dir in ['C:\\Windows\\System32', 'C:\\Windows\\SysWOW64']:
        dll_path = os.path.join(sys_dir, dll_name)
        if os.path.exists(dll_path):
            binaries += [(dll_path, '.')]
            print(f"[Build] VC++ Runtime: {dll_name}")
            break

# =============================================================================
# Hidden imports
# =============================================================================
hiddenimports = [
    # Core packages
    'core',
    'core.video',
    'core.video.batch',
    'core.audio',
    'core.api',
    'core.download',
    
    # Processors
    'processors',
    'processors.subtitle_detector',
    'processors.subtitle_processor',
    'processors.tts_processor',
    'processors.video_composer',
    
    # Managers
    'managers',
    'managers.queue_manager',
    'managers.progress_manager',
    'managers.voice_manager',
    'managers.output_manager',
    'managers.session_manager',
    
    # UI
    'ui',
    'ui.panels',
    'ui.windows',
    'ui.components',
    
    # Utils
    'utils',
    'utils.logging_config',
    'utils.secrets_manager',
    'utils.ocr_backend',
    'utils.tts_config',
    'utils.korean_text_processor',
    
    # Startup
    'startup',
    'startup.package_installer',
    'startup.environment',
    'startup.app_controller',
    
    # Caller
    'caller',
    'caller.rest',
    
    # App
    'app',
    'app.api_handler',
    'app.batch_handler',
    'app.login_handler',
    
    # External packages
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtWidgets',
    'PyQt6.QtGui',
    'PyQt6.sip',
    'cv2',
    'numpy',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'moviepy',
    'moviepy.video',
    'moviepy.video.io',
    'moviepy.video.io.VideoFileClip',
    'moviepy.video.compositing',
    'moviepy.audio',
    'moviepy.audio.io',
    'moviepy.audio.io.AudioFileClip',
    'moviepy.audio.AudioClip',
    'pydub',
    'pydub.audio_segment',
    'pydub.effects',
    'pydub.generators',
    'pydub.utils',
    'google.genai',
    'google.genai.types',
    'google.api_core',
    'google.auth',
    'google.auth.transport',
    'google.auth.transport.requests',
    'anthropic',
    'anthropic._client',
    'anthropic.types',
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.backends',
    'cryptography.hazmat.backends.default_backend',
    'httpx',
    'httpx._transports',
    'httpx._transports.default',
    'httpx._transports.http11',
    'httpx._transports.httpcore',
    'httpcore',
    'httpcore._async_http11',
    'httpcore._http11',
    'httpcore._status',
    'h11',
    'certifi',
    'certifi.core',
    'requests',
    'requests.adapters',
    'requests.auth',
    'urllib3',
    'platformdirs',
    'psutil',
    'psutil._common',
    'psutil._pswindows',
    'tokenizers',
    'huggingface_hub',
    
    # Video processing
    'core.video.batch.utils',
    'core.video.batch.encoder',
    'core.video.batch.tts_generator',
    'core.video.batch.tts_speed',
    'core.video.batch.whisper_analyzer',
    
    # Audio processing
    'core.audio.pipeline',
    'core.audio.audio_utils',
    
    # Korean text processing
    'utils.korean_text_processor',
    'utils.token_cost_calculator',
]

# Collect all submodules for key packages
for pkg in ['google.genai', 'anthropic', 'httpx', 'httpcore', 'moviepy', 'cv2', 'numpy', 'PIL']:
    try:
        hiddenimports += collect_submodules(pkg)
        print(f"[Build] Collected submodules from {pkg}")
    except:
        pass

# Deduplicate lists to prevent "multiple copies" errors
datas = list(set(datas))
binaries = list(set(binaries))
hiddenimports = list(set(hiddenimports))
print(f"[Build] Unique properties: {len(datas)} datas, {len(binaries)} binaries, {len(hiddenimports)} imports")

# =============================================================================
# Analysis
# =============================================================================
a = Analysis(
    ['ssmaker.py'],
    pathex=[os.getcwd()],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.sip'],
    noarchive=False,
)

pyz = PYZ(a.pure)

# =============================================================================
# EXE
# =============================================================================
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
    upx_exclude=[
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'msvcp140.dll',
        'msvcp140_1.dll',
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
