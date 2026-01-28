# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - Entry Point

Fast startup with instant splash screen.
Heavy initialization happens in background while splash is visible.
"""
import sys
import os

# =============================================================================
# Step 1: Minimal setup for instant splash (MUST be first and fast)
# =============================================================================
from startup.package_installer import ensure_stdio

ensure_stdio()

# Qt environment (must be before QApplication)
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

# =============================================================================
# Main Entry Point - Show splash IMMEDIATELY
# =============================================================================
if __name__ == "__main__":
    from PyQt5 import QtCore, QtWidgets, QtGui
    from PyQt5.QtWidgets import QApplication

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
    app.processEvents()

    # =============================================================================
    # Step 2: Heavy initialization in background while splash is visible
    # =============================================================================
    splash.set_status("패키지 확인 중...")
    splash.set_progress(5)
    app.processEvents()

    from startup.package_installer import check_and_install_packages
    check_and_install_packages()

    splash.set_status("환경 설정 중...")
    splash.set_progress(15)
    app.processEvents()

    from startup.environment import (
        setup_dpi_awareness,
        setup_ffmpeg_path,
        load_onnxruntime,
    )
    setup_dpi_awareness()

    splash.set_status("FFmpeg 설정 중...")
    splash.set_progress(25)
    app.processEvents()
    setup_ffmpeg_path()

    splash.set_status("ONNX Runtime 로딩...")
    splash.set_progress(40)
    app.processEvents()
    load_onnxruntime()

    splash.set_status("로깅 초기화...")
    splash.set_progress(50)
    app.processEvents()

    from pathlib import Path
    from utils.logging_config import AppLogger, get_logger

    AppLogger.setup(
        log_dir=Path("logs"),
        level="INFO",
        console_level="INFO",
        file_level="DEBUG"
    )
    logger = get_logger(__name__)

    splash.set_status("로그인 창 준비...")
    splash.set_progress(70)
    app.processEvents()

    # Import controller (triggers more imports)
    from startup.app_controller import AppController

    splash.set_status("준비 완료!")
    splash.set_progress(100)
    app.processEvents()

    # Close splash and show login
    import tempfile
    import traceback
    from datetime import datetime

    try:
        # Pre-create controller and login window for smooth transition
        controller = AppController(app)

        # Import Login for pre-creation
        from ui.windows.login_window import Login
        controller.login_window = Login()
        controller.login_window.controller = controller
        app.processEvents()

        # Now close splash and show login (smooth transition)
        splash.hide()
        controller.login_window.show()
        app.processEvents()
        splash.close()

        # Run Qt event loop
        exit_code = app.exec_()

        # After successful login, launch main app
        if controller.login_data:
            import tkinter as tk
            from main import VideoAnalyzerGUI

            root = tk.Tk()
            gui = VideoAnalyzerGUI(
                root,
                login_data=controller.login_data,
                preloaded_ocr=controller.ocr_reader
            )
            root.mainloop()

        sys.exit(exit_code)

    except Exception as e:
        logger.critical("프로그램 실행 중 치명적 오류 발생: %s", e, exc_info=True)

        # Write error log to temp directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_log_path = os.path.join(
            tempfile.gettempdir(),
            f"ssmaker_error_{timestamp}.txt"
        )
        try:
            with open(error_log_path, "w", encoding="utf-8") as f:
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Error: {e}\n\n")
                f.write(traceback.format_exc())
            logger.info("Error log saved to: %s", error_log_path)
        except Exception as log_err:
            logger.error("Failed to write error log: %s", log_err)

        raise
