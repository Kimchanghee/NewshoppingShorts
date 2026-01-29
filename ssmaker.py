# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - Entry Point

Fast startup with instant splash screen.
Heavy initialization happens in background while splash is visible.
"""

import sys
import os
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication

# =============================================================================
# Step 1: Minimal setup for instant splash (MUST be first and fast)
# =============================================================================
from startup.package_installer import ensure_stdio

ensure_stdio()

# Qt environment (must be before QApplication)
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"


class StartupWorker(QtCore.QThread):
    """Background worker for heavy initialization tasks."""

    progress = QtCore.pyqtSignal(int)
    status = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def run(self):
        try:
            self.status.emit("패키지 확인 중...")
            self.progress.emit(10)

            # 1. Package Check
            from startup.package_installer import check_and_install_packages

            check_and_install_packages()
            self.progress.emit(20)

            # 2. Environment Setup
            self.status.emit("환경 설정 중...")
            from startup.environment import (
                setup_dpi_awareness,
                setup_ffmpeg_path,
                load_onnxruntime,
            )

            setup_dpi_awareness()
            self.progress.emit(30)

            self.status.emit("FFmpeg 설정 중...")
            setup_ffmpeg_path()
            self.progress.emit(40)

            self.status.emit("ONNX Runtime 로딩...")
            load_onnxruntime()
            self.progress.emit(50)

            # 3. Logging Setup
            self.status.emit("로깅 초기화...")
            from pathlib import Path
            from utils.logging_config import AppLogger

            AppLogger.setup(
                log_dir=Path("logs"),
                level="INFO",
                console_level="INFO",
                file_level="DEBUG",
            )
            self.progress.emit(60)

            # 4. Resource Loading (Fonts, TTS samples)
            self.status.emit("리소스 확인 중...")
            try:
                # Ensure TTS directory exists
                from utils.tts_config import get_safe_tts_base_dir

                base_dir = get_safe_tts_base_dir()
                os.makedirs(os.path.join(base_dir, "voice_samples"), exist_ok=True)

                # Check critical fonts
                from startup.constants import REQUIRED_FONTS
                # (Simple check only, detailed check in Initializer)
            except Exception:
                pass
            self.progress.emit(70)

            # 5. Controller Preparation
            self.status.emit("앱 컨트롤러 준비...")
            # Import controller (triggers more imports)
            from startup.app_controller import AppController

            # Just import here to warm up cache
            self.progress.emit(90)

            self.status.emit("준비 완료!")
            self.progress.emit(100)
            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))


if __name__ == "__main__":
    # PyQt5 HighDPI attributes (before QApplication creation)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    try:
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_Use96Dpi, False)
    except AttributeError:
        pass

    app = QApplication(sys.argv)

    # Font DPI settings
    font = app.font()
    font.setStyleStrategy(QtGui.QFont.PreferAntialias)
    app.setFont(font)

    # Show splash IMMEDIATELY (before any heavy imports)
    from ui.windows.startup_splash import StartupSplash

    splash = StartupSplash()
    splash.show()

    # Worker for background initialization
    worker = StartupWorker()

    # Global references to prevent garbage collection
    controller = None
    login_window = None

    def on_progress(val):
        splash.set_progress(val)

    def on_status(msg):
        splash.set_status(msg)

    def on_error(msg):
        # Show error and exit
        splash.set_status(f"오류: {msg}")
        # In a real app, maybe show a message box here
        # For now, just close after a delay
        QtCore.QTimer.singleShot(3000, app.quit)

    def on_finished():
        global controller, login_window
        try:
            # Final imports and launch
            from startup.app_controller import AppController
            from ui.windows.login_window import Login

            controller = AppController(app)
            login_window = Login()
            login_window.controller = controller
            controller.login_window = login_window  # Link back

            # Transition: Hide Splash -> Show Login -> Close Splash
            splash.hide()
            login_window.show()
            splash.close()

        except Exception as e:
            on_error(str(e))

    worker.progress.connect(on_progress)
    worker.status.connect(on_status)
    worker.error.connect(on_error)
    worker.finished.connect(on_finished)

    # Start initialization in background
    worker.start()

    # Run Qt event loop
    exit_code = app.exec_()

    # After successful login (PyQt loop ended), launch main app (Tkinter)
    if controller and controller.login_data:
        import tkinter as tk
        from main import VideoAnalyzerGUI

        root = tk.Tk()
        gui = VideoAnalyzerGUI(
            root, login_data=controller.login_data, preloaded_ocr=controller.ocr_reader
        )
        root.mainloop()

    sys.exit(exit_code)
