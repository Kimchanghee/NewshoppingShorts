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
            # Stage 1: Bootstrapping (20%)
            self.status.emit("실행 환경 확인 중...")
            self.progress.emit(20)

            # Stage 2: Configuration (45%)
            self.status.emit("설정 불러오는 중...")
            import config
            self.progress.emit(45)

            # Stage 3: Login UI assets (70%)
            self.status.emit("로그인 화면 준비 중...")
            from ui.login_Ui import Ui_LoginWindow
            from ui.windows.login_window import Login
            self.progress.emit(70)

            # Stage 4: App controller (90%)
            self.status.emit("앱 컨트롤러 준비 중...")
            from startup.app_controller import AppController
            self.progress.emit(90)

            # Complete (100%)
            self.status.emit("로그인 창 여는 중...")
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
    
    # 한글 폰트 설정 (Korean font support)
    from PyQt6.QtGui import QFont, QFontDatabase
    
    # 사용 가능한 한글 폰트 검색
    available_fonts = QFontDatabase.families()
    korean_fonts = ['Pretendard', 'Malgun Gothic', '맑은 고딕', 'NanumGothic', 'Apple SD Gothic Neo']
    default_font = None
    for font_name in korean_fonts:
        if font_name in available_fonts:
            default_font = QFont(font_name, 10)
            break
    
    if default_font is None:
        # 폴백: 시스템 기본 폰트 사용
        default_font = QFont()
        default_font.setPointSize(10)
    
    app.setFont(default_font)
    logging.info(f"Default font set to: {default_font.family()}")
    
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
