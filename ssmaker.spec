# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

print("=" * 60)
print("[Build] Starting SSMaker build configuration...")
print("=" * 60)

# 모든 패키지 수집
datas = [
    ('resource', 'resource'),
    ('fonts', 'fonts'),
    ('ui', 'ui'),
    ('core', 'core'),
    ('utils', 'utils'),
    ('managers', 'managers'),
    ('processors', 'processors'),
    ('caller', 'caller'),
    ('app', 'app'),
    ('prompts', 'prompts'),
    ('voice_profiles.py', '.'),
    ('config', 'config'),  # config package (constants, etc.)
]

# RapidOCR 데이터 포함 (ONNX 모델)
try:
    rapidocr_datas = collect_data_files('rapidocr_onnxruntime')
    datas += rapidocr_datas
    print(f"[Build] RapidOCR data files: {len(rapidocr_datas)} items")
except Exception as e:
    print(f"[Build] RapidOCR data not found: {e}")

binaries = []

# onnxruntime DLL 명시적 포함 (OCR용)
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
except Exception as e:
    print(f"[Build] ONNX Runtime binaries not found: {e}")

# VC++ Runtime DLL 포함 (onnxruntime 의존성)
# 다른 컴퓨터에서 실행 시 필요한 런타임 DLL 포함
vc_runtime_dlls = [
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'concrt140.dll',
    'api-ms-win-crt-runtime-l1-1-0.dll',
    'api-ms-win-crt-heap-l1-1-0.dll',
    'api-ms-win-crt-string-l1-1-0.dll',
    'api-ms-win-crt-stdio-l1-1-0.dll',
    'api-ms-win-crt-convert-l1-1-0.dll',
    'api-ms-win-crt-math-l1-1-0.dll',
    'api-ms-win-crt-locale-l1-1-0.dll',
    'api-ms-win-crt-time-l1-1-0.dll',
    'api-ms-win-crt-environment-l1-1-0.dll',
    'api-ms-win-crt-process-l1-1-0.dll',
    'api-ms-win-crt-filesystem-l1-1-0.dll',
    'api-ms-win-crt-utility-l1-1-0.dll',
]
for dll_name in vc_runtime_dlls:
    # System32와 SysWOW64 모두 확인
    for sys_dir in ['C:\\Windows\\System32', 'C:\\Windows\\SysWOW64']:
        dll_path = os.path.join(sys_dir, dll_name)
        if os.path.exists(dll_path):
            binaries += [(dll_path, '.')]
            print(f"[Build] VC++ Runtime: {dll_name}")
            break

# imageio_ffmpeg 바이너리 포함
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if ffmpeg_exe and os.path.exists(ffmpeg_exe):
        binaries += [(ffmpeg_exe, 'imageio_ffmpeg')]
        print(f"[Build] FFmpeg binary included: {ffmpeg_exe}")
except Exception as e:
    print(f"[Build] FFmpeg binary not found: {e}")

# certifi 인증서 포함 (HTTPS 필수)
try:
    import certifi
    cert_path = certifi.where()
    if os.path.exists(cert_path):
        datas += [(cert_path, 'certifi')]
        print(f"[Build] SSL certificates included: {cert_path}")
except Exception as e:
    print(f"[Build] Certifi not found: {e}")

# PyQt5 플러그인 포함 (다른 컴퓨터에서 GUI 실행 필수)
try:
    from PyQt5.QtCore import QLibraryInfo
    qt_plugins_path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    if os.path.exists(qt_plugins_path):
        # 필수 플러그인 디렉토리
        plugin_dirs = ['platforms', 'styles', 'imageformats', 'iconengines']
        for plugin_dir in plugin_dirs:
            plugin_path = os.path.join(qt_plugins_path, plugin_dir)
            if os.path.exists(plugin_path):
                datas += [(plugin_path, os.path.join('PyQt5', 'Qt5', 'plugins', plugin_dir))]
                print(f"[Build] PyQt5 plugin included: {plugin_dir}")
except Exception as e:
    print(f"[Build] PyQt5 plugins not found: {e}")

# moviepy 데이터 포함
try:
    moviepy_datas = collect_data_files('moviepy')
    datas += moviepy_datas
    print(f"[Build] MoviePy data files: {len(moviepy_datas)} items")
except Exception as e:
    print(f"[Build] MoviePy data not found: {e}")

# cv2 (OpenCV) 데이터 포함
try:
    cv2_datas = collect_data_files('cv2')
    datas += cv2_datas
    print(f"[Build] OpenCV data files: {len(cv2_datas)} items")
except Exception as e:
    print(f"[Build] OpenCV data not found: {e}")

# fontTools 데이터 포함
try:
    fonttools_datas = collect_data_files('fontTools')
    datas += fonttools_datas
    print(f"[Build] FontTools data files: {len(fonttools_datas)} items")
except Exception as e:
    print(f"[Build] FontTools data not found: {e}")

# Faster-Whisper / CTranslate2 데이터 포함
try:
    faster_whisper_datas = collect_data_files('faster_whisper')
    datas += faster_whisper_datas
    print(f"[Build] Faster-Whisper data files: {len(faster_whisper_datas)} items")
except Exception as e:
    print(f"[Build] Faster-Whisper data not found: {e}")

try:
    ctranslate2_datas = collect_data_files('ctranslate2')
    datas += ctranslate2_datas
    print(f"[Build] CTranslate2 data files: {len(ctranslate2_datas)} items")
except Exception as e:
    print(f"[Build] CTranslate2 data not found: {e}")

# Faster-Whisper 모델 캐시 포함 (오프라인 실행을 위해)
# CTranslate2 형식 모델 (HuggingFace 캐시에서 로드)
# 런타임 코드는 faster_whisper_models/{model_size}/model.bin 경로를 찾음
try:
    import os as os_module
    import re as re_module
    hf_cache = os_module.path.join(os_module.path.expanduser("~"), ".cache", "huggingface", "hub")

    if os_module.path.exists(hf_cache):
        whisper_models = []
        # faster-whisper 모델 디렉토리 찾기
        # 패턴: models--Systran--faster-whisper-{size}
        model_size_pattern = re_module.compile(r'faster-whisper-(tiny|base|small|medium|large)', re_module.IGNORECASE)

        for dir_name in os_module.listdir(hf_cache):
            if 'faster-whisper' in dir_name.lower() and os_module.path.isdir(os_module.path.join(hf_cache, dir_name)):
                # 모델 크기 추출
                match = model_size_pattern.search(dir_name)
                if not match:
                    continue
                model_size = match.group(1).lower()

                model_dir = os_module.path.join(hf_cache, dir_name)
                snapshots_dir = os_module.path.join(model_dir, "snapshots")
                if os_module.path.exists(snapshots_dir):
                    for snapshot in os_module.listdir(snapshots_dir):
                        snapshot_path = os_module.path.join(snapshots_dir, snapshot)
                        if os_module.path.isdir(snapshot_path):
                            # 런타임 코드와 일치하도록 faster_whisper_models/{size}/ 구조로 복사
                            for file in os_module.listdir(snapshot_path):
                                file_path = os_module.path.join(snapshot_path, file)
                                if os_module.path.isfile(file_path):
                                    dest_dir = os_module.path.join("faster_whisper_models", model_size)
                                    whisper_models.append((file_path, dest_dir))
                            print(f"[Build] Faster-Whisper model included: {model_size} from {dir_name}")
                            break  # 첫 번째 스냅샷만 사용

        if whisper_models:
            datas += whisper_models
            print(f"[Build] Total Faster-Whisper model files: {len(whisper_models)}")
        else:
            print("[Build WARNING] Faster-Whisper 모델이 캐시에 없습니다. 첫 실행 시 자동 다운로드됩니다.")
    else:
        print("[Build WARNING] HuggingFace 캐시 디렉토리가 없습니다. 첫 실행 시 모델이 자동 다운로드됩니다.")
except Exception as e:
    print(f"[Build WARNING] Faster-Whisper 모델 수집 중 오류 (무시됨): {e}")

hiddenimports = []

# 주요 패키지 전체 수집
packages_to_collect = [
    'pkg_resources',
    'setuptools',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'cv2',
    'numpy',
    'pandas',
    'scipy',
    'sklearn',
    'skimage',
    'matplotlib',
    'moviepy',
    'imageio',
    'imageio_ffmpeg',
    'rapidocr_onnxruntime',  # OCR 엔진 (경량)
    'onnxruntime',  # RapidOCR 의존성 (DLL 포함 필수)
    'faster_whisper',  # Faster-Whisper (CTranslate2 기반 고속 STT)
    'ctranslate2',  # CTranslate2 (Faster-Whisper 의존성)
    'tokenizers',  # HuggingFace tokenizers
    'huggingface_hub',  # 모델 다운로드
    'regex',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    'cryptography',
    'PyQt5',
    'tkinter',
    'pydub',
    'ffmpeg',
    'lxml',
    'openpyxl',
    'numba',
    'llvmlite',
    'scipy',  # Faster-Whisper 의존성
    'google',
    'google.genai',
    'httpx',
    'httpcore',
    'anyio',
    'sniffio',
    'h11',
    # 추가 패키지
    'fontTools',
    'fontTools.ttLib',
    'simpleaudio',
    'wave',
    'audioop',
    'winsound',
]

for pkg in packages_to_collect:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except:
        pass

# 추가 hiddenimports
hiddenimports += [
    'pkg_resources.py2_warn',
    'pkg_resources._vendor',
    'pkg_resources._vendor.jaraco',
    'pkg_resources._vendor.jaraco.text',
    'pkg_resources._vendor.jaraco.functools',
    'pkg_resources._vendor.jaraco.context',
    'pkg_resources._vendor.more_itertools',
    'pkg_resources._vendor.more_itertools.more',
    'pkg_resources._vendor.more_itertools.recipes',
    'pkg_resources._vendor.packaging',
    'pkg_resources._vendor.packaging.version',
    'pkg_resources._vendor.packaging.specifiers',
    'pkg_resources._vendor.packaging.requirements',
    'pkg_resources._vendor.platformdirs',
    'setuptools._vendor',
    'setuptools._vendor.jaraco',
    'setuptools._vendor.jaraco.text',
    'setuptools._vendor.jaraco.functools',
    'setuptools._vendor.jaraco.context',
    'setuptools._vendor.more_itertools',
    'setuptools._vendor.more_itertools.more',
    'setuptools._vendor.more_itertools.recipes',
    'setuptools._vendor.packaging',
    'setuptools._vendor.packaging.version',
    'setuptools._vendor.packaging.specifiers',
    'setuptools._vendor.packaging.requirements',
    'setuptools._vendor.platformdirs',
    'setuptools._distutils',
    'distutils',
    'encodings',
    'codecs',
    'json',
    'decimal',
    'difflib',
    'inspect',
    'logging',
    'multiprocessing',
    'queue',
    'socket',
    'sqlite3',
    'ssl',
    'threading',
    'traceback',
    'webbrowser',
    'xml',
    'xml.etree',
    'xml.etree.ElementTree',
    'importlib',
    'importlib.metadata',
    'importlib.resources',
    'importlib_metadata',
    'importlib_resources',
    'typing_extensions',
    'jaraco',
    'jaraco.text',
    'jaraco.functools',
    'jaraco.context',
    'more_itertools',
    'zipp',
    'platformdirs',
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
    # Faster-Whisper (로컬 STT - CTranslate2 기반)
    'faster_whisper',
    'faster_whisper.transcribe',
    'faster_whisper.audio',
    'faster_whisper.tokenizer',
    'faster_whisper.vad',
    'ctranslate2',
    'ctranslate2.converters',
    'ctranslate2.specs',
    'tokenizers',
    'huggingface_hub',
    'huggingface_hub.file_download',
    'huggingface_hub.hf_api',
    'huggingface_hub.utils',
    'regex',
    # Google Gemini API
    'google',
    'google.genai',
    'google.genai.types',
    'google.auth',
    'google.auth.transport',
    'google.auth.transport.requests',
    # HTTP 클라이언트
    'httpx',
    'httpx._transports',
    'httpx._transports.default',
    'httpcore',
    'h11',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'sniffio',
    # 프로젝트 모듈
    'voice_profiles',
    'config',
    'caller',
    'caller.rest',
    'caller.ui_controller',
    'app',
    'app.api_handler',
    'app.batch_handler',
    'app.login_handler',
    'app.state',
    'core',
    'core.video',
    'core.video.batch',
    'core.video.batch.utils',
    'core.video.batch.processor',
    'core.video.batch.tts_handler',
    'core.video.batch.subtitle_handler',
    'core.video.batch.analysis',
    'core.video.VideoTool',
    'core.video.CreateFinalVideo',
    'core.video.DynamicBatch',
    'core.video.VideoExtract',
    'core.api',
    'core.api.ApiKeyManager',
    'core.api.ApiController',
    'core.download',
    'core.download.DouyinExtract',
    'core.download.TicktokExtract',
    'utils',
    'utils.util',
    'utils.Tool',
    'utils.DriverConfig',
    'utils.ocr_backend',
    'managers',
    'managers.voice_manager',
    'managers.session_manager',
    'managers.progress_manager',
    'processors',
    'processors.subtitle_processor',
    'processors.tts_processor',
    'processors.video_composer',
    'utils.korean_text_processor',
    'ui',
    'ui.panels',
    'ui.panels.voice_panel',
    'ui.panels.font_panel',
    'ui.panels.cta_panel',
    'ui.panels.queue_panel',
    'ui.panels.progress_panel',
    'ui.panels.header_panel',
    'ui.panels.url_input_panel',
    # 'ui.panels.status_bar',  # 존재하지 않는 모듈 - 제거됨
    'ui.components',
    'ui.components.custom_dialog',
    'ui.components.loading_splash',
    'ui.process_ui',
    # 폰트 관련
    'fontTools',
    'fontTools.ttLib',
    'fontTools.ttLib.TTFont',
    # moviepy/imageio 관련
    'imageio',
    'imageio.core',
    'imageio.plugins',
    'imageio_ffmpeg',
    'imageio_ffmpeg._utils',
    'proglog',
    'decorator',
    'tqdm',
    # 표준 라이브러리 (자주 누락됨)
    'asyncio',
    'concurrent',
    'concurrent.futures',
    'contextlib',
    'copy',
    'dataclasses',
    'datetime',
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'functools',
    'hashlib',
    'html',
    'html.parser',
    'http',
    'http.client',
    'io',
    'itertools',
    'math',
    'mimetypes',
    'operator',
    'os',
    'os.path',
    'pathlib',
    'pickle',
    'platform',
    'pprint',
    'random',
    're',
    'secrets',
    'shutil',
    'signal',
    'stat',
    'string',
    'struct',
    'subprocess',
    'sys',
    'tempfile',
    'textwrap',
    'time',
    'types',
    'typing',
    'unicodedata',
    'unittest',
    'urllib',
    'urllib.parse',
    'urllib.request',
    'uuid',
    'warnings',
    'weakref',
    'zipfile',
    # 네트워크/비동기 관련
    'aiohttp',
    'asyncio.events',
    'asyncio.base_events',
    'asyncio.coroutines',
    'asyncio.futures',
    'asyncio.locks',
    'asyncio.protocols',
    'asyncio.queues',
    'asyncio.runners',
    'asyncio.streams',
    'asyncio.tasks',
    'asyncio.transports',
    # PIL/Pillow 세부 모듈
    'PIL._imaging',
    'PIL.ImageFile',
    'PIL.ImageFilter',
    'PIL.ImageOps',
    'PIL.ImageEnhance',
    'PIL.ImageColor',
    'PIL.ImagePalette',
    'PIL.ImageSequence',
    'PIL.ImageChops',
    'PIL.JpegImagePlugin',
    'PIL.PngImagePlugin',
    'PIL.GifImagePlugin',
    'PIL.BmpImagePlugin',
    'PIL.TiffImagePlugin',
    # numpy/scipy 세부 모듈
    'numpy.core',
    'numpy.core._methods',
    'numpy.core._dtype_ctypes',
    'numpy.lib',
    'numpy.linalg',
    'numpy.fft',
    'numpy.random',
    'scipy.ndimage',
    'scipy.signal',
    'scipy.interpolate',
    # moviepy 세부 모듈 (moviepy 2.x API)
    'moviepy',
    'moviepy.video',
    'moviepy.video.io',
    'moviepy.video.io.VideoFileClip',
    'moviepy.video.io.ImageSequenceClip',
    'moviepy.video.fx',
    'moviepy.video.fx.all',
    'moviepy.video.compositing',
    'moviepy.video.compositing.CompositeVideoClip',
    'moviepy.video.compositing.concatenate',
    'moviepy.video.VideoClip',
    'moviepy.audio',
    'moviepy.audio.io',
    'moviepy.audio.io.AudioFileClip',
    'moviepy.audio.fx',
    'moviepy.audio.fx.all',
    'moviepy.audio.AudioClip',
    'moviepy.Clip',
    'moviepy.decorators',
    'moviepy.tools',
    'moviepy.config',
    # pydub 관련
    'pydub.effects',
    'pydub.silence',
    'pydub.utils',
    'pydub.generators',
    # Google API 세부 모듈
    'google.api_core',
    'google.api_core.exceptions',
    'google.api_core.retry',
    'google.protobuf',
    'google.protobuf.json_format',
    # Windows 전용
    'win32api',
    'win32con',
    'win32gui',
    'win32file',
    'pywintypes',
    'pythoncom',
    # 기타
    'base64',
    'binascii',
    'collections',
    'collections.abc',
    'enum',
    'gc',
    'getpass',
    'glob',
    'gzip',
    'heapq',
    'hmac',
    'locale',
    'numbers',
    'abc',
    'atexit',
    'bisect',
    'array',
    # Numba 세부 모듈 (Librosa 의존성 - 동적 로딩 모듈)
    'numba',
    'numba.core',
    'numba.core.types',
    'numba.core.types.old_scalars',
    'numba.core.types.scalars',
    'numba.core.types.abstract',
    'numba.core.types.common',
    'numba.core.types.containers',
    'numba.core.types.functions',
    'numba.core.types.iterators',
    'numba.core.types.misc',
    'numba.core.types.npytypes',
    'numba.core.ccallback',
    'numba.core.cgutils',
    'numba.core.compiler',
    'numba.core.config',
    'numba.core.datamodel',
    'numba.core.decorators',
    'numba.core.dispatcher',
    'numba.core.errors',
    'numba.core.event',
    'numba.core.extending',
    'numba.core.funcdesc',
    'numba.core.imputils',
    'numba.core.inline_closurecall',
    'numba.core.ir',
    'numba.core.lowering',
    'numba.core.registry',
    'numba.core.runtime',
    'numba.core.serialize',
    'numba.core.sigutils',
    'numba.core.tracing',
    'numba.core.typing',
    'numba.core.typing.templates',
    'numba.core.typing.typeof',
    'numba.core.ufunc',
    'numba.core.unsafe',
    'numba.core.utils',
    'numba.cpython',
    'numba.misc',
    'numba.np',
    'numba.np.arraymath',
    'numba.np.linalg',
    'numba.np.ufunc',
    'numba.parfors',
    'numba.typed',
    'llvmlite',
    'llvmlite.binding',
    'llvmlite.ir',
    # Librosa (오디오 처리)
    'librosa',
    'librosa.core',
    'librosa.util',
    'librosa.feature',
    'librosa.filters',
    # Faster-Whisper 추가 의존성
    'more_itertools',
    'more_itertools.recipes',
    'av',  # PyAV (오디오/비디오 디코딩)
    # RapidOCR (경량 OCR 엔진)
    'rapidocr_onnxruntime',
    'onnxruntime',
    'onnxruntime.capi',
    'onnxruntime.capi._pybind_state',
    'onnxruntime.capi.onnxruntime_pybind11_state',
    'onnx',
    'pyclipper',
    'shapely',
    # Anthropic API
    'anthropic',
    'anthropic._client',
    'anthropic._exceptions',
    'anthropic.types',
    'anthropic.resources',
    # 추가 의존성
    'colorama',
    'psutil',
    'tenacity',
    'distro',
    'websockets',
    'pydantic',
    'pydantic.fields',
    'pydantic_core',
    'annotated_types',
    # Python 3.12+ audioop 대체
    'audioop_lts',
    # 프로젝트 추가 모듈
    'core.video.batch.encoder',
    'core.video.batch.tts_generator',
    'core.video.batch.tts_speed',
    'core.video.batch.audio_utils',
    'core.video.batch.whisper_analyzer',
    'core.video.video_validator',
    'managers.queue_manager',
    'managers.output_manager',
    'managers.settings_manager',
    'processors.subtitle_detector',
    'prompts',
    'prompts.video_analysis',
    'prompts.translation',
    'prompts.tts_voice',
    'prompts.audio_analysis',
    'prompts.subtitle_split',
    'prompts.video_validation',
    'ui.login_Ui',
    'utils.token_cost_calculator',
]

# collect_submodules로 서브모듈 완전 수집
submodule_packages = [
    'google.genai',
    'anthropic',
    'httpx',
    'httpcore',
    'anyio',
    'moviepy',
    'imageio',
    'PIL',
    'cv2',
    'numpy',
    'scipy',
    'pydub',
    'rapidocr_onnxruntime',  # OCR 엔진
    'faster_whisper',  # Faster-Whisper (CTranslate2 기반)
    'ctranslate2',  # CTranslate2
    'huggingface_hub',  # 모델 다운로드
    'tokenizers',  # HuggingFace tokenizers
    'numba',
    'llvmlite',
    'librosa',
    'onnxruntime',  # RapidOCR 의존성
    'pydantic',
    'pydantic_core',
    'colorama',
    'psutil',
]

for pkg in submodule_packages:
    try:
        subs = collect_submodules(pkg)
        hiddenimports += subs
        print(f"[Build] Collected {len(subs)} submodules from {pkg}")
    except Exception as e:
        print(f"[Build] Could not collect submodules from {pkg}: {e}")

# 중복 제거
hiddenimports = list(set(hiddenimports))
print(f"[Build] Total hiddenimports: {len(hiddenimports)}")

# av 패키지 필수 모듈만 포함 (faster-whisper 의존성)
# av.sidedata 등 일부 서브모듈이 PyInstaller에서 크래시를 유발하므로 제외
av_problematic = ['av.sidedata', 'av.bitstream', 'av.datasets']
hiddenimports = [h for h in hiddenimports if h not in av_problematic]

# av 기본 모듈 명시적 추가 (faster-whisper가 필요로 함)
av_required = ['av', 'av.audio', 'av.video', 'av.container', 'av.codec', 'av.filter', 'av.subtitles', 'av.logging', 'av.error']
for mod in av_required:
    if mod not in hiddenimports:
        hiddenimports.append(mod)
print(f"[Build] After av adjustment: {len(hiddenimports)} hiddenimports")

a = Analysis(
    ['ssmaker.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],  # 런타임 환경 설정 훅
    excludes=['av.sidedata', 'av.bitstream', 'av.datasets'],  # 문제 유발 서브모듈만 제외
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
    upx_exclude=[
        # UPX 압축에서 제외할 DLL (호환성 문제 방지)
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'msvcp140.dll',
        'python*.dll',
        'Qt*.dll',
    ],
    runtime_tmpdir=None,
    console=False,  # 배포용: 콘솔 창 숨김 (디버깅 시 True로 변경)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resource/app_icon.ico' if os.path.exists('resource/app_icon.ico') else None,
)
