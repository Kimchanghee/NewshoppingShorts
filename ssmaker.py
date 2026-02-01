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
    update_detected = QtCore.pyqtSignal(dict) # Signals to main thread to show prompt

    def run(self):
        try:
            import time
            import requests

            # Stage 0: Check for updates (5%)
            self.status.emit("업데이트 확인 중...")
            self.progress.emit(5)
            try:
                # We can't import AppController here yet, let's just do a direct check
                # or read from version.json
                base_url = "https://ssmaker-auth-api-1049571775048.us-central1.run.app" # Use same as AppController
                
                # Get current version
                curr_ver = "1.0.0"
                v_path = "version.json"
                if os.path.exists(v_path):
                    import json
                    with open(v_path, 'r') as f:
                        curr_ver = json.load(f).get("version", "1.0.0")
                
                response = requests.get(f"{base_url}/app/version/check", params={"current_version": curr_ver}, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("update_available"):
                        self.update_detected.emit(data)
                        # We don't stop here, but main thread might interrupt us
            except Exception as e:
                logging.warning(f"Update check failed during splash: {e}")

            # Stage 1: Initialize (15%)
            self.status.emit("초기화 중...")
            self.progress.emit(15)
            time.sleep(0.1)

            # Stage 2: Load configuration (25%)
            self.status.emit("설정 로딩 중...")
            self.progress.emit(25)
            import config
            time.sleep(0.1)

            # Stage 3: Load UI components (50%)
            self.status.emit("UI 구성 요소 로딩 중...")
            self.progress.emit(50)
            time.sleep(0.1)

            # Stage 4: Load app controller (75%)
            self.status.emit("앱 컨트롤러 준비 중...")
            self.progress.emit(75)
            from startup.app_controller import AppController
            time.sleep(0.1)

            # Stage 5: Final setup (95%)
            self.status.emit("최종 확인 중...")
            self.progress.emit(95)
            time.sleep(0.1)

            # Complete (100%)
            self.status.emit("완료!")
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
            splash.hide()
            controller.start() # Shows login window
            splash.close()
            logging.info("Application controller started successfully")
        except Exception as e:
            logging.error(f"Startup error: {e}", exc_info=True)
            splash.close()
            QMessageBox.critical(None, "시작 오류", 
                f"애플리케이션 초기화 중 오류가 발생했습니다.\n{str(e)}\n\n"
                f"로그 파일: {log_file}")
            sys.exit(1)

    def on_update_detected(data):
        # We need to show the prompt. But splash is on.
        # Let's hide splash temporarily or show dialog over it.
        # AppController has the logic, but it's not instantiated yet.
        # We'll just instantiate a temporary AppController to use its methods
        # or just duplicate the prompt logic here for simplicity in this entry point.
        from startup.app_controller import AppController
        tmp_controller = AppController(app)
        tmp_controller.handle_update_available(data)

    worker.progress.connect(splash.set_progress)
    worker.status.connect(splash.set_status)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)  # Connect error signal
    worker.update_detected.connect(on_update_detected)
    
    worker.start()

    sys.exit(app.exec())
