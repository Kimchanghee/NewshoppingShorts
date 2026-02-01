# -*- coding: utf-8 -*-
"""
Application flow controller for PyQt6.
"""
from typing import Optional, List, Tuple, Any, Dict
import sys
import os
from PyQt6 import QtCore
from PyQt6.QtWidgets import QMessageBox, QApplication
from utils.logging_config import get_logger
from .initializer import Initializer

logger = get_logger(__name__)

class AppController:
    """Controls the login -> loading -> main app flow in PyQt6."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.login_data: Optional[Dict[str, Any]] = None
        self.ocr_reader: Optional[object] = None
        self.login_window: Optional[Any] = None
        self.loading_window: Optional[Any] = None
        self.thread: Optional[QtCore.QThread] = None
        self.initializer: Optional[Initializer] = None
        self.init_issues: List[Tuple[str, str, str]] = []

    def start(self) -> None:
        from ui.windows.login_window import Login
        self.login_window = Login()
        self.login_window.controller = self
        self.login_window.show()

    def get_current_version(self) -> str:
        """Read version from version.json"""
        import json
        try:
            # Handle both dev (src root) and frozen (MEIPASS) paths
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.getcwd()
                
            version_path = os.path.join(base_path, "version.json")
            if os.path.exists(version_path):
                with open(version_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("version", "1.0.0")
        except Exception as e:
            logger.error(f"Failed to read version: {e}")
        return "1.0.0"

    def check_for_updates(self) -> None:
        """Check server for new version"""
        import requests
        
        # 개발 환경에서는 업데이트 체크 건너뛰기 (무한 재시작 방지)
        if not getattr(sys, 'frozen', False):
            logger.info("Development mode: Skipping update check")
            return
        
        # URL Configuration
        base_url = "https://ssmaker-auth-api-1049571775048.us-central1.run.app"
        
        current_version = self.get_current_version()
        logger.info(f"Checking for updates. Current version: {current_version}")
        
        try:
            response = requests.get(f"{base_url}/app/version/check", params={"current_version": current_version}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("update_available"):
                    self.handle_update_available(data)
        except Exception as e:
            logger.warning(f"Update server unreachable: {e}")

    def handle_update_available(self, update_data: Dict[str, Any]) -> None:
        """Prompt user and start update process"""
        latest_version = update_data.get("latest_version")
        download_url = update_data.get("download_url")
        is_mandatory = update_data.get("is_mandatory")
        release_notes = update_data.get("release_notes", "")
        
        msg = f"새로운 버전({latest_version})이 있습니다.\n\n{release_notes}\n\n지금 업데이트 하시겠습니까?"
        
        if is_mandatory:
            QMessageBox.warning(None, "필수 업데이트", "중요한 업데이트가 있어 프로그램을 업데이트해야 합니다.")
            self.perform_update(download_url)
        else:
            reply = QMessageBox.question(None, "업데이트 확인", msg, 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.perform_update(download_url)

    def perform_update(self, download_url: str) -> None:
        """Download and run updater with progress UI"""
        from PyQt6.QtWidgets import QProgressDialog
        
        if not download_url:
            QMessageBox.critical(None, "오류", "업데이트 파일 경로가 잘못되었습니다.")
            return

        import tempfile
        temp_dir = tempfile.gettempdir()
        new_exe_path = os.path.join(temp_dir, "new_ssmaker.exe")
        
        # Create progress dialog
        self.progress_dialog = QProgressDialog("업데이트 다운로드 중...", "취소", 0, 100)
        self.progress_dialog.setWindowTitle("실시간 업데이트")
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.show()

        self.download_worker = DownloadWorker(download_url, new_exe_path)
        self.download_worker.progress.connect(self.progress_dialog.setValue)
        
        def on_download_finished(success, result):
            if success:
                self._run_updater(result)
            else:
                QMessageBox.critical(None, "다운로드 실패", f"업데이트 파일 다운로드 중 오류가 발생했습니다:\n{result}")
                self.progress_dialog.close()

        self.download_worker.finished.connect(on_download_finished)
        self.download_worker.start()

    def _run_updater(self, new_exe_path: str) -> None:
        """Launch the separate updater process and exit"""
        import subprocess
        import shutil
        
        try:
            if getattr(sys, 'frozen', False):
                # EXE 환경: updater.exe 사용
                base_dir = os.path.dirname(sys.executable)
                current_exe = sys.executable
                updater_exe = os.path.join(base_dir, "updater.exe")
                
                if not os.path.exists(updater_exe):
                    QMessageBox.critical(None, "오류", "updater.exe를 찾을 수 없습니다. 다시 설치해 주세요.")
                    return

                args = [
                    updater_exe,
                    new_exe_path,
                    current_exe,
                    current_exe,
                    str(os.getpid())
                ]
                
                logger.info(f"Launching updater: {args}")
                subprocess.Popen(args)
                sys.exit(0)
            else:
                # 개발 환경: Python 프로세스 직접 재시작
                base_dir = os.getcwd()
                
                # 다운로드된 파일이 있으면 version.json 업데이트가 필요할 수 있음
                # 개발 환경에서는 소스코드가 이미 최신이므로 바로 재시작
                logger.info("Development mode: Restarting application...")
                
                # 현재 앱 종료 후 재시작
                python_exe = sys.executable
                script_path = os.path.join(base_dir, "ssmaker.py")
                
                # 새 프로세스로 앱 실행
                subprocess.Popen([python_exe, script_path], cwd=base_dir)
                
                # 현재 프로세스 종료
                logger.info("Exiting current process for restart...")
                sys.exit(0)

        except Exception as e:
            logger.error(f"Update launch failed: {e}", exc_info=True)
            QMessageBox.critical(None, "업데이트 실행 오류", f"업데이트 실행 중 오류가 발생했습니다:\n{e}")

    def on_login_success(self, login_data: Dict[str, Any]) -> None:
        from ui.windows.process_window import ProcessWindow
        self.login_data = login_data
        
        # Check for updates after successful login
        self.check_for_updates()
        
        self.loading_window = ProcessWindow()
        self.login_window.hide()
        self.loading_window.show()

        self.initializer = Initializer()
        self.thread = QtCore.QThread()
        self.initializer.moveToThread(self.thread)
        self.initializer.progressChanged.connect(self.loading_window.setProgress)
        self.initializer.statusChanged.connect(self.loading_window.statusLabel.setText)
        self.initializer.checkItemChanged.connect(self.loading_window.updateCheckItem)
        self.initializer.ocrReaderReady.connect(self._on_ocr_ready)
        self.initializer.finished.connect(self._on_loading_finished)
        self.thread.started.connect(self.initializer.run)
        self.thread.start()

    def _on_ocr_ready(self, ocr_reader: Optional[object]) -> None:
        self.ocr_reader = ocr_reader

    def _on_loading_finished(self) -> None:
        if self.thread: self.thread.quit()
        if self.loading_window: self.loading_window.close()
        self.launch_main_app()

    def launch_main_app(self):
        """Launch the main PyQt6 application."""
        from main import VideoAnalyzerGUI
        self.main_gui = VideoAnalyzerGUI(login_data=self.login_data, preloaded_ocr=self.ocr_reader)
        self.main_gui.show()

class DownloadWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal(bool, str) # success, file_path_or_error

    def __init__(self, url, dest_path):
        super().__init__()
        self.url = url
        self.dest_path = dest_path

    def run(self):
        import requests
        try:
            with requests.get(self.url, stream=True, timeout=10) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                with open(self.dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                prog = int((downloaded / total_size) * 100)
                                self.progress.emit(prog)
            self.finished.emit(True, self.dest_path)
        except Exception as e:
            self.finished.emit(False, str(e))
