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

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv might not be installed yet

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

            # Stage 8: Final validation (95%)
            self.status.emit("최종 확인 중...")
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
            # Thread cleanup
            worker.quit()
            worker.wait()

            from startup.app_controller import AppController
            controller = AppController(app)

            # Connect Login window's ready signal to close splash
            def on_login_ready():
                splash.close()
                logging.info("Login window ready, splash closed")

            controller.start()  # Creates and shows login window

            # Connect the signal after start() creates the login_window
            if controller.login_window:
                controller.login_window.window_ready.connect(on_login_ready)
            else:
                # Fallback if login_window not created
                splash.close()

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
