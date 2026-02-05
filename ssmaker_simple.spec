# -*- mode: python ; coding: utf-8 -*-
"""
Shopping Shorts Maker - PyInstaller Spec (Complete Distribution)

사용법:
  pyinstaller --clean ssmaker_simple.spec
"""

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

print("=" * 60)
print("[Build] SSMaker Distribution Build Starting...")
print("=" * 60)

# =============================================================================
# Data files - 모든 리소스, 모듈, 폰트, 음성 샘플 포함
# =============================================================================
datas = [
    # 리소스 (아이콘, 로고, TTS 음성 샘플)
    ('resource', 'resource'),
    ('fonts', 'fonts'),
    ('version.json', '.'),

    # 업데이터 (ssmaker.exe 안에 번들, 업데이트 시 자동 추출)
    ('dist/updater.exe', '.'),

    # 앱 모듈 (Python 소스)
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
]

# 외부 패키지 데이터 파일
for pkg_name in [
    'certifi',
    'imageio_ffmpeg',
    'faster_whisper',
    'ctranslate2',
    'rapidocr_onnxruntime',
    'google.genai',
    'vertexai',
    'google.cloud.aiplatform',
]:
    try:
        pkg_data = collect_data_files(pkg_name)
        datas += pkg_data
        print(f"[Build] {pkg_name} data: {len(pkg_data)} files")
    except Exception:
        print(f"[Build WARNING] {pkg_name} data not found (skipped)")

# =============================================================================
# Binaries - FFmpeg, ONNX Runtime, VC++ Runtime
# =============================================================================
binaries = []

# FFmpeg binary (imageio_ffmpeg)
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if ffmpeg_exe and os.path.exists(ffmpeg_exe):
        binaries += [(ffmpeg_exe, 'imageio_ffmpeg')]
        print(f"[Build] FFmpeg: {ffmpeg_exe}")
except Exception:
    print("[Build WARNING] FFmpeg binary not found - video encoding may fail")

# ONNX Runtime DLL (for OCR - Python < 3.13 only)
try:
    import onnxruntime
    ort_path = os.path.dirname(onnxruntime.__file__)
    capi_path = os.path.join(ort_path, 'capi')
    if os.path.exists(capi_path):
        for dll_file in os.listdir(capi_path):
            if dll_file.endswith(('.dll', '.pyd')):
                full_path = os.path.join(capi_path, dll_file)
                binaries += [(full_path, 'onnxruntime/capi')]
                print(f"[Build] ONNX Runtime: {dll_file}")
except Exception:
    print("[Build INFO] ONNX Runtime not available (OCR will use Tesseract fallback)")

# VC++ Runtime DLL
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
# Hidden imports - 모든 내부/외부 모듈
# =============================================================================
hiddenimports = [
    # ── 내부 모듈 (앱) ──
    'config',
    'voice_profiles',
    'main',

    # Core
    'core',
    'core.providers',
    'core.video',
    'core.video.batch',
    'core.video.batch.processor',
    'core.video.batch.analysis',
    'core.video.batch.audio_utils',
    'core.video.batch.encoder',
    'core.video.batch.subtitle_handler',
    'core.video.batch.tts_generator',
    'core.video.batch.tts_handler',
    'core.video.batch.tts_speed',
    'core.video.batch.utils',
    'core.video.batch.whisper_analyzer',
    'core.video.CreateFinalVideo',
    'core.video.DynamicBatch',
    'core.video.VideoExtract',
    'core.video.VideoTool',
    'core.video.video_validator',
    'core.audio',
    'core.audio.pipeline',
    'core.api',
    'core.api.ApiKeyManager',
    'core.api.ApiController',
    'core.download',
    'core.download.DouyinExtract',
    'core.download.TicktokExtract',

    # Processors
    'processors',
    'processors.subtitle_detector',
    'processors.subtitle_processor',
    'processors.tts_processor',
    'processors.video_composer',

    # Managers
    'managers',
    'managers.queue_manager',
    'managers.processing_queue',
    'managers.progress_manager',
    'managers.voice_manager',
    'managers.output_manager',
    'managers.session_manager',
    'managers.settings_manager',
    'managers.subscription_manager',
    'managers.tiktok_manager',
    'managers.youtube_manager',

    # UI
    'ui',
    'ui.panels',
    'ui.windows',
    'ui.components',
    'ui.design_system_v2',
    'ui.theme_manager',

    # Utils
    'utils',
    'utils.logging_config',
    'utils.secrets_manager',
    'utils.auto_updater',
    'utils.ocr_backend',
    'utils.tts_config',
    'utils.korean_text_processor',
    'utils.token_cost_calculator',

    # Startup
    'startup',
    'startup.package_installer',
    'startup.environment',
    'startup.initializer',
    'startup.app_controller',
    'startup.constants',

    # Caller
    'caller',
    'caller.rest',
    'caller.ui_controller',

    # App handlers
    'app',
    'app.state',
    'app.api_handler',
    'app.batch_handler',
    'app.login_handler',
    'app.exit_handler',

    # Prompts
    'prompts',
    'prompts.video_analysis',
    'prompts.audio_analysis',
    'prompts.translation',
    'prompts.tts_voice',
    'prompts.subtitle_split',
    'prompts.video_validation',

    # ── 외부 패키지 ──
    # PyQt6
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtWidgets',
    'PyQt6.QtGui',
    'PyQt6.QtNetwork',
    'PyQt6.sip',

    # Vision / Image
    'cv2',
    'numpy',
    'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL.ImageFilter',
    'skimage',

    # Video / Audio
    'moviepy',
    'moviepy.video', 'moviepy.video.io', 'moviepy.video.io.VideoFileClip',
    'moviepy.video.compositing', 'moviepy.video.fx', 'moviepy.video.fx.all',
    'moviepy.audio', 'moviepy.audio.io', 'moviepy.audio.io.AudioFileClip',
    'moviepy.audio.AudioClip',
    'pydub', 'pydub.audio_segment', 'pydub.effects', 'pydub.generators', 'pydub.utils',
    'imageio', 'imageio_ffmpeg',
    'av',
    'audioop_lts',

    # Whisper / TTS
    'faster_whisper',
    'ctranslate2',
    'edge_tts',

    # Google AI
    'google.genai', 'google.genai.types',
    'google.api_core', 'google.api_core.exceptions',
    'google.auth', 'google.auth.transport', 'google.auth.transport.requests',
    'google.oauth2', 'google.oauth2.credentials',

    # Anthropic
    'anthropic', 'anthropic._client', 'anthropic.types',

    # HTTP
    'httpx', 'httpx._transports', 'httpx._transports.default',
    'httpcore', 'httpcore._async_http11', 'httpcore._http11', 'httpcore._status',
    'h11',
    'requests', 'requests.adapters', 'requests.auth',
    'urllib3',

    # Security
    'cryptography', 'cryptography.fernet',
    'cryptography.hazmat', 'cryptography.hazmat.primitives',
    'cryptography.hazmat.backends', 'cryptography.hazmat.backends.default_backend',
    'jose', 'jwt',

    # Misc
    'certifi', 'certifi.core',
    'platformdirs',
    'psutil', 'psutil._common', 'psutil._pswindows',
    'tokenizers',
    'huggingface_hub',
    'tqdm',
    'colorama',
    'dotenv',
    'yt_dlp',
]

# 주요 패키지의 모든 서브모듈 자동 수집
for pkg in [
    'google.genai', 'google.api_core', 'google.auth',
    'anthropic', 'httpx', 'httpcore',
    'moviepy', 'cv2', 'numpy', 'PIL',
    'PyQt6', 'pydub', 'cryptography',
    'faster_whisper', 'ctranslate2',
]:
    try:
        hiddenimports += collect_submodules(pkg)
        print(f"[Build] Collected submodules: {pkg}")
    except Exception:
        pass

# Deduplicate
datas = list(set(datas))
binaries = list(set(binaries))
hiddenimports = list(set(hiddenimports))
print(f"[Build] Total: {len(datas)} datas, {len(binaries)} binaries, {len(hiddenimports)} imports")

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
    runtime_hooks=['runtime_hook.py'],
    excludes=[
        # PyQt5 충돌 방지
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.sip',
        # 백엔드 전용 (클라이언트 앱에 불필요)
        'fastapi', 'uvicorn', 'sqlalchemy', 'sqlmodel',
        'starlette', 'slowapi',
        # 테스트
        'pytest', 'pytest_cov',
        # 불필요한 대형 패키지
        'matplotlib', 'pandas', 'streamlit', 'selenium', 'playwright',
        'PySide6', 'PySide6_Addons', 'PySide6_Essentials',
        'IPython', 'jupyter', 'notebook',
        'tensorflow', 'torch', 'keras',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# =============================================================================
# EXE - Single file distribution
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
