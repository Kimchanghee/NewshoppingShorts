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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    from ui.windows.startup_splash import StartupSplash
    splash = StartupSplash()
    splash.show()

    worker = StartupWorker()
    controller = None

    def on_finished():
        global controller
        try:
            from startup.app_controller import AppController
            controller = AppController(app)
            splash.hide()
            controller.start() # Shows login window
            splash.close()
        except Exception as e:
            logging.error(f"Startup error: {e}")

    worker.progress.connect(splash.set_progress)
    worker.status.connect(splash.set_status)
    worker.finished.connect(on_finished)
    worker.start()

    sys.exit(app.exec())
