# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - Entry Point (PyQt6)
"""
import sys
import os
import logging
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtWidgets import QApplication

# Environmental settings for HighDPI
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# Windows DPI awareness (must be called before QApplication)
try:
    from startup.environment import setup_dpi_awareness
    setup_dpi_awareness()
except Exception:
    pass

# 빌드 환경(Frozen)에서 리소스 경로 처리
if getattr(sys, "frozen", False):
    _base_path = getattr(sys, "_MEIPASS", "")
    
    # 1. ffmpeg 경로 설정
    _ffmpeg_dir = os.path.join(_base_path, "resource", "bin")
    if os.path.exists(_ffmpeg_dir):
        os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        _ffmpeg_exe = os.path.join(_ffmpeg_dir, "ffmpeg.exe")
        # Ensure MoviePy/imageio-ffmpeg uses the bundled ffmpeg instead of trying to download/find one.
        if os.path.exists(_ffmpeg_exe):
            os.environ.setdefault("IMAGEIO_FFMPEG_EXE", _ffmpeg_exe)
    
    # 2. Whisper 모델 경로 환경변수 (필요 시)
    _whisper_path = os.path.join(_base_path, "faster_whisper_models")
    if os.path.exists(_whisper_path):
        os.environ["WHISPER_MODEL_PATH"] = _whisper_path

# Load environment variables from .env file (EXE: _MEIPASS, 개발: CWD)
try:
    from dotenv import load_dotenv
    if getattr(sys, "frozen", False):
        _exe_dir = os.path.dirname(sys.executable)
        _candidates = [
            os.path.join(_exe_dir, ".env"),
            os.path.join(os.path.expanduser("~"), ".ssmaker", ".env"),
        ]
        for _p in _candidates:
            if os.path.exists(_p):
                load_dotenv(_p, override=False)
                break
    else:
        load_dotenv(override=False)
except ImportError:
    pass

# Logging setup for EXE environment
def setup_logging():
    log_dir = os.path.join(os.path.expanduser('~'), '.ssmaker', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'ssmaker.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_file

class StartupWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    status = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def run(self):
        try:
            import time

            # Stage 1: Initialize (10%)
            self.status.emit("초기화 중...")
            self.progress.emit(10)

            # Stage 2: Load configuration (20%)
            self.status.emit("설정 로딩 중...")
            import config
            self.progress.emit(20)

            # Stage 3: Load core utilities (30%)
            self.status.emit("유틸리티 로딩 중...")
            from utils.logging_config import get_logger
            from caller import rest, ui_controller
            self.progress.emit(30)

            # Stage 4: Load PyQt6 core modules (45%)
            self.status.emit("UI 프레임워크 로딩 중...")
            from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
            from PyQt6.QtCore import Qt, QTimer
            self.progress.emit(45)

            # Stage 5: Load design system (55%)
            self.status.emit("디자인 시스템 로딩 중...")
            from ui.design_system_v2 import get_design_system
            from ui.theme_manager import get_theme_manager
            self.progress.emit(55)

            # Stage 6: Load login UI (70%)
            self.status.emit("로그인 화면 준비 중...")
            from ui.login_Ui import Ui_LoginWindow
            from ui.windows.login_window import Login
            self.progress.emit(70)

            # Stage 7: Load app controller (85%)
            self.status.emit("앱 컨트롤러 준비 중...")
            from startup.app_controller import AppController
            self.progress.emit(85)

            # Stage 8: Pre-load main app module (95%)
            self.status.emit("메인 앱 모듈 로딩 중...")
            import main  # Pre-import to catch ModuleNotFoundError early
            self.progress.emit(95)
            time.sleep(0.1)

            # Complete (100%)
            self.status.emit("준비 완료!")
            self.progress.emit(100)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
            logging.error(f"Worker exception: {e}", exc_info=True)

if __name__ == "__main__":
    # Setup logging first
    log_file = setup_logging()
    logging.info("Application starting...")

    app = QApplication(sys.argv)
    
    from ui.windows.startup_splash import StartupSplash
    from PyQt6.QtWidgets import QMessageBox

    splash = StartupSplash()
    splash.show()

    worker = StartupWorker()
    controller = None

    def on_error(error_msg):
        logging.error(f"Startup worker error: {error_msg}")
        splash.close()
        QMessageBox.critical(None, "시작 오류", 
            f"애플리케이션을 시작할 수 없습니다:\n{error_msg}\n\n"
            f"로그 파일: {log_file}\n\n프로그램을 종료합니다.")
        sys.exit(1)

    def on_finished():
        global controller
        try:
            worker.quit()
            worker.wait()

            from startup.app_controller import AppController
            controller = AppController(app)
            controller.splash = splash  # Splash managed by AppController
            controller.start()

            logging.info("Application controller started successfully")
        except Exception as e:
            logging.error(f"Startup error: {e}", exc_info=True)
            splash.close()
            QMessageBox.critical(None, "시작 오류",
                f"애플리케이션 초기화 중 오류가 발생했습니다.\n{str(e)}\n\n"
                f"로그 파일: {log_file}")
            sys.exit(1)

    worker.progress.connect(splash.set_progress)
    worker.status.connect(splash.set_status)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)  # Connect error signal
    
    worker.start()

    sys.exit(app.exec())
