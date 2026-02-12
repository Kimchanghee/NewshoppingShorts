# -*- coding: utf-8 -*-
"""
Application flow controller for PyQt6.
Game-like auto-update: login ??check ??download ??replace ??restart (no user interaction).
After restart: show update-complete dialog with release notes + 5s countdown.
"""
from typing import Optional, List, Tuple, Any, Dict
import sys
import os
import json
from PyQt6 import QtCore
from PyQt6.QtWidgets import QMessageBox
from utils.logging_config import get_logger
from .initializer import Initializer

logger = get_logger(__name__)

# Path for persisting update info across restart
_PENDING_UPDATE_PATH = os.path.join(
    os.path.expanduser("~"), ".ssmaker", "pending_update.json"
)

# Keep API endpoint overridable in local/dev network environments.
API_SERVER_URL = os.getenv(
    "API_SERVER_URL",
    "https://ssmaker-auth-api-1049571775048.us-central1.run.app",
).rstrip("/")


class UpdateCheckWorker(QtCore.QThread):
    """Background worker to check for updates after login."""
    update_available = QtCore.pyqtSignal(dict)
    no_update = QtCore.pyqtSignal()
    check_failed = QtCore.pyqtSignal(str)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        import requests
        try:
            response = requests.get(
                f"{API_SERVER_URL}/app/version/check",
                params={"current_version": self.current_version},
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("update_available"):
                    self.update_available.emit(data)
                    return
                self.no_update.emit()
            else:
                self.check_failed.emit(f"Server returned {response.status_code}")
        except Exception as e:
            self.check_failed.emit(str(e))


class AppController:
    """Controls the login -> update check -> loading -> main app flow."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.login_data: Optional[Dict[str, Any]] = None
        self.ocr_reader: Optional[object] = None
        self.login_window: Optional[Any] = None
        self.loading_window: Optional[Any] = None
        self.thread: Optional[QtCore.QThread] = None
        self.initializer: Optional[Initializer] = None
        self.init_issues: List[Tuple[str, str, str]] = []
        self.splash: Optional[Any] = None
        self.ocr_init_attempted: bool = False
        self._update_is_mandatory: bool = False
        self._latest_version: str = ""
        self._release_notes: str = ""
        self._main_launched: bool = False
        self._pending_update_info: Optional[Dict[str, Any]] = None  # ?낅뜲?댄듃 ?댁뿭 ??μ슜

    # ?? Entry point ??

    def start(self) -> None:
        """Start the app ??show login first."""
        self._show_login()

    # ?? Splash management ??

    def _close_splash(self) -> None:
        if self.splash:
            self.splash.close()
            self.splash = None

    # ?? Login ??

    def _show_login(self) -> None:
        from ui.windows.login_window import Login
        self.login_window = Login()
        self.login_window.controller = self

        if self.splash:
            self.login_window.window_ready.connect(self._close_splash)

        self.login_window.show()

    def on_login_success(self, login_data: Dict[str, Any]) -> None:
        """After login: check for updates, then proceed to main app."""
        self.login_data = login_data

        if getattr(sys, "frozen", False):
            self._check_update_after_login()
        else:
            logger.info("Development mode: Skipping update check")
            self._proceed_to_loading()

    # ?? Post-login update check (game-like auto-update) ??

    def _check_update_after_login(self) -> None:
        current_version = self.get_current_version()
        logger.info(f"Post-login update check. Current version: {current_version}")
        self.update_check_worker = UpdateCheckWorker(current_version)
        self.update_check_worker.update_available.connect(self._on_update_available)
        self.update_check_worker.no_update.connect(self._proceed_to_loading)
        self.update_check_worker.check_failed.connect(self._on_update_check_failed)
        self.update_check_worker.start()

    def _on_update_available(self, update_data: dict) -> None:
        """Auto-download update without user confirmation (game-like)."""
        download_url = update_data.get("download_url")
        self._update_is_mandatory = update_data.get("is_mandatory", False)
        self._latest_version = update_data.get("latest_version", "")
        self._release_notes = update_data.get("release_notes", "")
        file_hash = update_data.get("file_hash", "")

        if not download_url:
            logger.warning("Update available but no download URL provided")
            if self._update_is_mandatory:
                QMessageBox.critical(
                    None,
                    "업데이트 오류",
                    "필수 업데이트를 다운로드할 수 없습니다.\n프로그램을 종료합니다.",
                )
                sys.exit(1)
            self._proceed_to_loading()
            return
            
        if not file_hash:
            logger.error("No file_hash provided by server - refusing unsafe update")
            if self._update_is_mandatory:
                QMessageBox.critical(
                    None,
                    "업데이트 오류",
                    "필수 업데이트 검증 정보(file_hash)가 없습니다.\n프로그램을 종료합니다.",
                )
                sys.exit(1)
            self._proceed_to_loading()
            return

        logger.info(f"Auto-updating to version {self._latest_version} (Hash: {file_hash})")
        if self.login_window:
            self.login_window.hide()
        self.perform_update(download_url, file_hash)

    def _on_update_check_failed(self, error: str) -> None:
        logger.warning(f"Update check failed: {error}")
        self._proceed_to_loading()

    # ?? Version ??

    def get_current_version(self) -> str:
        try:
            if getattr(sys, "frozen", False):
                base_path = sys._MEIPASS
            else:
                base_path = os.getcwd()

            version_path = os.path.join(base_path, "version.json")
            if os.path.exists(version_path):
                with open(version_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("version", "1.0.0")
        except Exception as e:
            logger.error(f"Failed to read version: {e}")
        return "1.0.0"

    # ?? Loading & Main App ??

    def _proceed_to_loading(self) -> None:
        """Continue to ProcessWindow and main app (no update needed)."""
        from ui.windows.process_window import ProcessWindow

        self.loading_window = ProcessWindow()
        if self.login_window:
            self.login_window.hide()
        self.loading_window.show()

        self.initializer = Initializer()
        self.thread = QtCore.QThread()
        self.initializer.moveToThread(self.thread)
        self.initializer.progressChanged.connect(self.loading_window.setProgress)
        self.initializer.statusChanged.connect(self.loading_window.statusLabel.setText)
        self.initializer.checkItemChanged.connect(self.loading_window.updateCheckItem)
        self.initializer.ocrReaderReady.connect(self._on_ocr_ready)
        self.initializer.updateInfoReady.connect(self._on_update_info_ready)
        self.initializer.finished.connect(self._on_loading_finished)
        self.thread.started.connect(self.initializer.run)
        self.thread.start()

    def _on_ocr_ready(self, ocr_reader: Optional[object]) -> None:
        self.ocr_init_attempted = True
        self.ocr_reader = ocr_reader

    def _on_update_info_ready(self, update_info: Dict[str, Any]) -> None:
        """Store update info for showing popup after main app launches."""
        self._pending_update_info = update_info
        logger.debug(f"Update info received: {update_info}")

    def _on_loading_finished(self) -> None:
        try:
            if self.thread:
                self.thread.quit()
                self.thread.wait()

            # OCR init step was executed during loading even if reader is None.
            self.ocr_init_attempted = True

            # Check for pending update notification (saved before restart)
            pending = self._consume_pending_update()
            if pending:
                # Show dialog BEFORE closing loading window to prevent
                # quitOnLastWindowClosed from terminating the app.
                self._show_update_complete(pending)
                if self.loading_window:
                    self.loading_window.close()
            else:
                self.launch_main_app()
        except Exception as e:
            logger.error(f"Loading finished handler failed: {e}", exc_info=True)
            if self.loading_window:
                self.loading_window.close()
            QMessageBox.critical(
                None,
                "시작 오류",
                f"초기화 중 오류가 발생했습니다:\n{e}",
            )

    def launch_main_app(self) -> None:
        if self._main_launched:
            return
        self._main_launched = True
        try:
            logger.info("Launching main application...")
            from main import VideoAnalyzerGUI
            logger.info("VideoAnalyzerGUI imported successfully")
            self.main_gui = VideoAnalyzerGUI(
                login_data=self.login_data,
                preloaded_ocr=self.ocr_reader,
                ocr_init_attempted=self.ocr_init_attempted,
            )
            logger.info("VideoAnalyzerGUI created successfully")
            self.main_gui.show()
            logger.info("Main window shown")
            # Close loading window AFTER main window is shown
            if self.loading_window:
                self.loading_window.close()

            # Log application start
            try:
                from caller.rest import log_user_action
                log_user_action("앱 실행", "애플리케이션이 성공적으로 실행되었습니다.")
            except Exception:
                pass

            # 업데이트 내역 팝업 표시 (새 버전일 때만)
            self._show_update_notes_if_needed()

        except Exception as e:
            logger.error(f"Failed to launch main app: {e}", exc_info=True)
            if self.loading_window:
                self.loading_window.close()
            QMessageBox.critical(
                None,
                "시작 오류",
                f"메인 앱을 시작할 수 없습니다:\n{type(e).__name__}: {e}",
            )

    def _show_update_notes_if_needed(self) -> None:
        """업데이트 내역 팝업 표시 (새 버전이고 릴리즈노트가 있을 때)."""
        if not self._pending_update_info:
            return

        has_notes = self._pending_update_info.get("has_update_notes", False)
        is_new_version = self._pending_update_info.get("is_new_version", False)
        version = self._pending_update_info.get("version", "")
        release_notes = self._pending_update_info.get("release_notes", "")

        # 새 버전이고 릴리즈노트가 있을 때만 팝업 표시
        if is_new_version and has_notes and release_notes:
            try:
                from ui.windows.update_dialog import UpdateNotesDialog

                self.update_notes_dialog = UpdateNotesDialog(
                    version=version,
                    release_notes=release_notes,
                )
                self.update_notes_dialog.show()
                logger.info(f"Showing update notes for v{version}")
            except Exception as e:
                logger.warning(f"Failed to show update notes dialog: {e}")

    # ?? Pending update persistence ??

    @staticmethod
    def _save_pending_update(version: str, release_notes: str) -> None:
        """Save update info so the next launch can show the complete dialog."""
        try:
            os.makedirs(os.path.dirname(_PENDING_UPDATE_PATH), exist_ok=True)
            with open(_PENDING_UPDATE_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {"version": version, "release_notes": release_notes},
                    f,
                    ensure_ascii=False,
                )
            logger.info("Pending update info saved")
        except Exception as e:
            logger.warning(f"Failed to save pending update info: {e}")

    @staticmethod
    def _consume_pending_update() -> Optional[Dict[str, str]]:
        """Read and delete pending update info. Returns dict or None."""
        try:
            if os.path.exists(_PENDING_UPDATE_PATH):
                with open(_PENDING_UPDATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                os.remove(_PENDING_UPDATE_PATH)
                logger.info(f"Consumed pending update info: v{data.get('version')}")
                return data
        except Exception as e:
            logger.warning(f"Failed to read pending update info: {e}")
            try:
                os.remove(_PENDING_UPDATE_PATH)
            except OSError:
                pass
        return None

    # ?? Update-complete dialog ??

    def _show_update_complete(self, pending: Dict[str, str]) -> None:
        """Show update-complete dialog with 5s countdown, then launch main app."""
        from ui.windows.update_dialog import UpdateCompleteDialog

        version = pending.get("version", "")
        notes = pending.get("release_notes", "")

        self.update_complete_dialog = UpdateCompleteDialog(
            version=version, release_notes=notes,
        )
        self.update_complete_dialog.confirmed.connect(self.launch_main_app)
        self.update_complete_dialog.show()

    # ?? Update download & install ??

    @staticmethod
    def _windows_creation_flags() -> int:
        """Return safe detached creation flags on Windows."""
        import subprocess

        flags = 0
        flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        flags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
        return flags

    def perform_update(self, download_url: str, file_hash: str) -> None:
        """Auto-download and install update (game-like, no confirmation).

        The server now provides an Inno Setup installer as the download artifact.
        After downloading and verifying the hash, the installer is launched in
        silent mode (/VERYSILENT) which handles closing the app, replacing files,
        and restarting automatically.
        """
        from ui.windows.update_dialog import UpdateProgressDialog

        if not download_url:
            if self._update_is_mandatory:
                QMessageBox.critical(
                    None,
                    "오류",
                    "업데이트 파일 경로가 올바르지 않습니다.\n프로그램을 종료합니다.",
                )
                sys.exit(1)
            self._proceed_to_loading()
            return

        import tempfile
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "SSMaker_Setup_update.exe")

        self.update_progress_dialog = UpdateProgressDialog(
            version=self._latest_version,
            release_notes=self._release_notes,
        )
        self.update_progress_dialog.show()

        self.download_worker = DownloadWorker(download_url, installer_path, file_hash)
        self.download_worker.progress.connect(self.update_progress_dialog.set_progress)

        def on_download_finished(success: bool, result: str):
            if success:
                self.update_progress_dialog.set_status("설치 준비 중...")
                self.update_progress_dialog.set_progress(100)
                QtCore.QTimer.singleShot(500, lambda: self._run_installer(result))
            else:
                self.update_progress_dialog.close()
                logger.error(f"Update verification failed: {result}")
                if self._update_is_mandatory:
                    QMessageBox.critical(
                        None,
                        "업데이트 실패",
                        f"업데이트 검증 실패:\n{result}\n\n프로그램을 종료합니다.",
                    )
                    sys.exit(1)
                self._proceed_to_loading()

        self.download_worker.finished.connect(on_download_finished)
        self.download_worker.start()

    def _run_installer(self, installer_path: str) -> None:
        """Launch Inno Setup installer in silent mode and exit the app.

        The installer handles:
        1. Closing any remaining running instances (CloseApplications=force)
        2. Replacing all files in the install directory
        3. Restarting the app after installation (skipifnotsilent Run entry)
        """
        import subprocess

        if hasattr(self, "update_progress_dialog") and self.update_progress_dialog:
            self.update_progress_dialog.set_status("설치 프로그램 실행 중...")

        try:
            # Save update info BEFORE restarting so post-restart can show complete dialog
            self._save_pending_update(self._latest_version, self._release_notes)

            if getattr(sys, "frozen", False):
                creation_flags = self._windows_creation_flags()

                logger.info(f"Launching Inno Setup installer (silent): {installer_path}")
                subprocess.Popen(
                    [
                        installer_path,
                        "/VERYSILENT",
                        "/SUPPRESSMSGBOXES",
                        "/CLOSEAPPLICATIONS",
                        "/SP-",
                    ],
                    creationflags=creation_flags,
                    shell=False,
                    close_fds=True,
                )

                # Exit the app so the installer can replace files.
                # The installer's [Run] section will restart ssmaker.exe after install.
                logger.info("Installer launched. Exiting app for update...")
                QtCore.QTimer.singleShot(500, lambda: os._exit(0))

            else:
                # Development mode: just restart
                base_dir = os.getcwd()
                logger.info("Development mode: Restarting application...")

                python_exe = sys.executable
                script_path = os.path.join(base_dir, "ssmaker.py")
                subprocess.Popen([python_exe, script_path], cwd=base_dir)
                logger.info("Exiting current process for restart...")
                sys.exit(0)

        except Exception as e:
            logger.error(f"Update launch failed: {e}", exc_info=True)
            if hasattr(self, "update_progress_dialog"):
                self.update_progress_dialog.close()
            QMessageBox.critical(
                None,
                "업데이트 실행 오류",
                f"업데이트 실행 중 오류가 발생했습니다:\n{e}",
            )
            if self._update_is_mandatory:
                sys.exit(1)
            self._proceed_to_loading()


class DownloadWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal(bool, str)  # success, file_path_or_error

    def __init__(self, url: str, dest_path: str, expected_hash: str):
        super().__init__()
        self.url = url
        self.dest_path = dest_path
        self.expected_hash = expected_hash

    def run(self):
        import requests
        import hashlib
        try:
            if not self.expected_hash:
                raise ValueError("Missing expected hash for update package")

            sha256 = hashlib.sha256()
            with requests.get(self.url, stream=True, timeout=(10, 120)) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(self.dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            sha256.update(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                prog = int((downloaded / total_size) * 100)
                                self.progress.emit(prog)
            
            # Verify hash
            file_hash = sha256.hexdigest().lower()
            if file_hash != self.expected_hash.lower():
                raise ValueError(f"Hash mismatch! Expected {self.expected_hash}, got {file_hash}")
                
            self.finished.emit(True, self.dest_path)
        except Exception as e:
            self.finished.emit(False, str(e))

