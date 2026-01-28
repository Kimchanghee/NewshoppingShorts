# -*- coding: utf-8 -*-
"""
PyInstaller Runtime Hook
다른 컴퓨터에서 실행 시 필요한 환경 변수 및 경로 설정

This hook runs before the main application starts.
"""
import os
import sys


def _setup_runtime_environment():
    """런타임 환경 설정"""
    # PyInstaller가 생성한 임시 디렉토리 경로
    if getattr(sys, 'frozen', False):
        # EXE로 실행 중
        base_path = sys._MEIPASS

        # SSL 인증서 경로 설정 (HTTPS 요청 시 필수)
        cert_path = os.path.join(base_path, 'certifi', 'cacert.pem')
        if os.path.exists(cert_path):
            os.environ['SSL_CERT_FILE'] = cert_path
            os.environ['REQUESTS_CA_BUNDLE'] = cert_path

        # PyQt5 플러그인 경로 설정
        qt_plugin_path = os.path.join(base_path, 'PyQt5', 'Qt5', 'plugins')
        if os.path.exists(qt_plugin_path):
            os.environ['QT_PLUGIN_PATH'] = qt_plugin_path

        # QML 경로 설정 (필요시)
        qml_path = os.path.join(base_path, 'PyQt5', 'Qt5', 'qml')
        if os.path.exists(qml_path):
            os.environ['QML2_IMPORT_PATH'] = qml_path

        # imageio-ffmpeg 경로 설정
        ffmpeg_path = os.path.join(base_path, 'imageio_ffmpeg')
        if os.path.exists(ffmpeg_path):
            os.environ['IMAGEIO_FFMPEG_EXE'] = os.path.join(ffmpeg_path, 'ffmpeg-win64-v4.2.2.exe')

        # Faster-Whisper 모델 경로 설정
        whisper_model_path = os.path.join(base_path, 'faster_whisper_models')
        if os.path.exists(whisper_model_path):
            os.environ['FASTER_WHISPER_MODEL_PATH'] = whisper_model_path

        # ONNX Runtime 라이브러리 경로 추가
        onnx_path = os.path.join(base_path, 'onnxruntime', 'capi')
        if os.path.exists(onnx_path) and onnx_path not in os.environ.get('PATH', ''):
            os.environ['PATH'] = onnx_path + os.pathsep + os.environ.get('PATH', '')

        # 임시 디렉토리 설정 (moviepy 등에서 사용)
        temp_dir = os.path.join(os.environ.get('TEMP', os.getcwd()), 'ssmaker_temp')
        os.makedirs(temp_dir, exist_ok=True)
        os.environ['TMPDIR'] = temp_dir
        os.environ['TEMP'] = temp_dir
        os.environ['TMP'] = temp_dir


# 런타임 환경 설정 실행
_setup_runtime_environment()
