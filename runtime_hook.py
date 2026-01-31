# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Runtime Hook
다른 컴퓨터에서 실행 시 필요한 환경 변수 및 경로 설정
"""

import os
import sys

def _setup_runtime_environment():
    """런타임 환경 설정"""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        
        # PyInstaller 6+ onedir layout: items inside _internal subdirectory
        internal_path = os.path.join(base_path, "_internal")
        
        def find_path(subdir):
            # Check both root and _internal
            p1 = os.path.join(base_path, subdir)
            if os.path.exists(p1): return p1
            p2 = os.path.join(internal_path, subdir)
            if os.path.exists(p2): return p2
            return None

        # SSL 인증서
        cert_path = find_path("certifi/cacert.pem")
        if cert_path:
            os.environ["SSL_CERT_FILE"] = cert_path
            os.environ["REQUESTS_CA_BUNDLE"] = cert_path

        # FFmpeg
        ffmpeg_dir = find_path("ffmpeg")
        # Fallback to imageio_ffmpeg
        if not ffmpeg_dir:
            ffmpeg_dir = find_path("imageio_ffmpeg/binaries")
            
        if ffmpeg_dir:
            ffmpeg_exe = None
            for f in os.listdir(ffmpeg_dir):
                if f.lower().startswith("ffmpeg") and f.lower().endswith(".exe"):
                    ffmpeg_exe = os.path.join(ffmpeg_dir, f)
                    break
            if ffmpeg_exe:
                os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

        # Faster-Whisper Models
        whisper_model_path = find_path("faster_whisper_models")
        if whisper_model_path:
            os.environ["FASTER_WHISPER_MODEL_PATH"] = whisper_model_path
            # Also set the app-specific attribute if possible, but environment variable is better

        # ONNX Runtime
        onnx_path = find_path("onnxruntime/capi")
        if onnx_path:
            os.environ["PATH"] = onnx_path + os.pathsep + os.environ.get("PATH", "")

        # Temp directory
        temp_dir = os.path.join(os.environ.get("TEMP", os.getcwd()), "ssmaker_temp")
        os.makedirs(temp_dir, exist_ok=True)
        os.environ["TMPDIR"] = temp_dir
        os.environ["TEMP"] = temp_dir
        os.environ["TMP"] = temp_dir

_setup_runtime_environment()
