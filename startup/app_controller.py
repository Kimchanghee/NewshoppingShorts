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
import re
import subprocess
from PyQt6 import QtCore
from PyQt6.QtWidgets import QMessageBox
from utils.logging_config import get_logger
from utils.auto_updater import compare_versions
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
PAYMENT_API_BASE_URL = os.getenv("PAYMENT_API_BASE_URL", "").strip().rstrip("/")
GITHUB_RELEASE_API_URL = os.getenv(
    "GITHUB_RELEASE_API_URL",
    "https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases/latest",
).strip()


def _verify_authenticode_signature(file_path: str, thumbprints_env: str) -> tuple[bool, str]:
    """
    Verify Windows Authenticode signature for a file.

    - Requires signature Status == Valid
    - If `<thumbprints_env>` is configured, signer thumbprint must match allowlist.
    """
    if not file_path or not os.path.exists(file_path):
        return False, "File not found"
    if sys.platform != "win32":
        return True, "Signature check skipped (non-Windows)"

    escaped_path = file_path.replace("'", "''")
    ps_script = (
        f"$sig = Get-AuthenticodeSignature -FilePath '{escaped_path}'; "
        "if ($null -eq $sig) { Write-Output 'unknown|'; exit 0 }; "
        "$thumb=''; if ($sig.SignerCertificate) { $thumb=$sig.SignerCertificate.Thumbprint }; "
        "Write-Output (($sig.Status.ToString().ToLower()) + '|' + $thumb)"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as e:
        return False, f"Signature check invocation failed: {e}"

    output = (result.stdout or "").strip().splitlines()
    last_line = output[-1].strip() if output else ""
    status, thumb = (last_line.split("|", 1) + [""])[:2] if "|" in last_line else (last_line, "")
    status = (status or "").strip().lower()
    thumb = (thumb or "").replace(" ", "").strip().lower()

    if status != "valid":
        stderr = (result.stderr or "").strip()
        return False, f"Invalid signature status: {status or 'unknown'} {stderr}".strip()

    allow_raw = (os.getenv(thumbprints_env, "") or "").strip()
    if allow_raw:
        allowed = {
            item.replace(" ", "").strip().lower()
            for item in allow_raw.split(",")
            if item.strip()
        }
        if not thumb:
            return False, "Missing signer thumbprint"
        if thumb not in allowed:
            return False, "Signer thumbprint not allowed"

    return True, "Signature verified"


class UpdateCheckWorker(QtCore.QThread):
    """Background worker to check for updates after login."""
    update_available = QtCore.pyqtSignal(dict)
    no_update = QtCore.pyqtSignal()
    check_failed = QtCore.pyqtSignal(str)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = (current_version or "").strip() or "0.0.0"

    def run(self):
        import requests
        try:
            result = self._check_with_fallback(requests)
            if result.get("update_available"):
                self.update_available.emit(result)
                return
            self.no_update.emit()
        except Exception as e:
            self.check_failed.emit(str(e))

    def _check_with_fallback(self, requests_module):
        best_no_update: Optional[Dict[str, Any]] = None

        for base_url in self._candidate_base_urls():
            by_check = self._query_version_check(requests_module, base_url)
            if by_check is None:
                by_check = self._query_version_info(requests_module, base_url)

            if by_check is None:
                continue

            if by_check.get("update_available"):
                if self._has_required_update_metadata(by_check):
                    return by_check
                logger.warning(
                    "Server reported update but metadata is incomplete at %s; trying fallback sources",
                    base_url,
                )
            else:
                best_no_update = self._pick_newer_result(best_no_update, by_check)

        by_github = self._query_github_latest_release(requests_module)
        if by_github is not None:
            if by_github.get("update_available"):
                if self._has_required_update_metadata(by_github):
                    return by_github
                logger.warning("GitHub release fallback metadata is incomplete")
            else:
                best_no_update = self._pick_newer_result(best_no_update, by_github)

        if best_no_update is not None:
            return best_no_update

        return {
            "update_available": False,
            "current_version": self.current_version,
            "latest_version": self.current_version,
        }

    @staticmethod
    def _has_required_update_metadata(update_data: Dict[str, Any]) -> bool:
        download_url = str(update_data.get("download_url", "")).strip()
        file_hash = str(update_data.get("file_hash", "")).strip()
        return bool(download_url and file_hash)

    def _pick_newer_result(
        self,
        current_best: Optional[Dict[str, Any]],
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        if current_best is None:
            return candidate

        best_version = str(
            current_best.get("latest_version") or current_best.get("version") or "0.0.0"
        ).strip()
        candidate_version = str(
            candidate.get("latest_version") or candidate.get("version") or "0.0.0"
        ).strip()

        try:
            if compare_versions(best_version, candidate_version) < 0:
                return candidate
        except Exception:
            if best_version < candidate_version:
                return candidate
        return current_best

    @staticmethod
    def _normalize_base_url(raw: str) -> str:
        return (raw or "").strip().rstrip("/")

    def _candidate_base_urls(self) -> List[str]:
        candidates: List[str] = []
        for raw in (PAYMENT_API_BASE_URL, API_SERVER_URL):
            base = self._normalize_base_url(raw)
            if base and base not in candidates:
                candidates.append(base)
        return candidates

    def _query_version_check(self, requests_module, base_url: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests_module.get(
                f"{base_url}/app/version/check",
                params={"current_version": self.current_version},
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                latest_version = str(
                    data.get("latest_version")
                    or data.get("version")
                    or self.current_version
                ).strip()
                is_mandatory = bool(data.get("is_mandatory", False))
                return {
                    "update_available": bool(data.get("update_available")),
                    "current_version": self.current_version,
                    "latest_version": latest_version,
                    "download_url": data.get("download_url"),
                    "release_notes": data.get("release_notes", ""),
                    "is_mandatory": is_mandatory,
                    "file_hash": data.get("file_hash", ""),
                }
            if response.status_code in (404, 405, 422):
                return None
            logger.warning(
                "Version check endpoint returned %s at %s",
                response.status_code,
                base_url,
            )
            return None
        except Exception as e:
            logger.debug("Version check endpoint failed at %s: %s", base_url, e)
            return None

    def _query_version_info(self, requests_module, base_url: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests_module.get(f"{base_url}/app/version", timeout=5)
            if response.status_code != 200:
                if response.status_code not in (404, 405):
                    logger.warning(
                        "Version metadata endpoint returned %s at %s",
                        response.status_code,
                        base_url,
                    )
                return None

            data = response.json()
            latest_version = str(data.get("version", "")).strip()
            if not latest_version:
                logger.warning("Version metadata missing version at %s", base_url)
                return None

            update_available = compare_versions(self.current_version, latest_version) < 0
            min_required = str(data.get("min_required_version", "")).strip()
            is_mandatory = bool(data.get("is_mandatory", False))
            if min_required:
                is_mandatory = is_mandatory or (
                    compare_versions(self.current_version, min_required) < 0
                )

            return {
                "update_available": update_available,
                "current_version": self.current_version,
                "latest_version": latest_version,
                "download_url": data.get("download_url"),
                "release_notes": data.get("release_notes", ""),
                "is_mandatory": is_mandatory,
                "file_hash": data.get("file_hash", ""),
            }
        except Exception as e:
            logger.debug("Version metadata endpoint failed at %s: %s", base_url, e)
            return None

    def _query_github_latest_release(self, requests_module) -> Optional[Dict[str, Any]]:
        if not GITHUB_RELEASE_API_URL:
            return None

        try:
            response = requests_module.get(
                GITHUB_RELEASE_API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"SSMaker/{self.current_version}",
                },
                timeout=6,
            )
            if response.status_code != 200:
                logger.warning(
                    "GitHub release fallback returned %s",
                    response.status_code,
                )
                return None

            data = response.json()
            latest_version = str(data.get("tag_name", "")).strip().lstrip("vV")
            if not latest_version:
                logger.warning("GitHub release fallback missing tag_name")
                return None

            update_available = compare_versions(self.current_version, latest_version) < 0
            if not update_available:
                return {
                    "update_available": False,
                    "current_version": self.current_version,
                    "latest_version": latest_version,
                }

            assets = data.get("assets", []) or []
            preferred_pattern = re.compile(
                rf"^SSMaker_Setup_v{re.escape(latest_version)}\.exe$",
                re.IGNORECASE,
            )
            installer_asset = next(
                (
                    asset
                    for asset in assets
                    if preferred_pattern.match(str(asset.get("name", "")))
                ),
                None,
            )
            if installer_asset is None:
                installer_asset = next(
                    (
                        asset
                        for asset in assets
                        if str(asset.get("name", "")).lower().endswith(".exe")
                    ),
                    None,
                )
            if installer_asset is None:
                logger.warning("GitHub release fallback found no installer asset")
                return {
                    "update_available": False,
                    "current_version": self.current_version,
                    "latest_version": latest_version,
                }

            digest = str(installer_asset.get("digest", "")).strip()
            file_hash = ""
            if digest.lower().startswith("sha256:"):
                file_hash = digest.split(":", 1)[1].strip()
            if not file_hash:
                file_hash = self._extract_sha256(data.get("body", ""))

            return {
                "update_available": True,
                "current_version": self.current_version,
                "latest_version": latest_version,
                "download_url": installer_asset.get("browser_download_url"),
                "release_notes": data.get("body", ""),
                "is_mandatory": False,
                "file_hash": file_hash,
            }
        except Exception as e:
            logger.debug("GitHub release fallback failed: %s", e)
            return None

    @staticmethod
    def _extract_sha256(text: str) -> str:
        match = re.search(r"\b([a-fA-F0-9]{64})\b", str(text or ""))
        return match.group(1).lower() if match else ""


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
        if getattr(sys, "frozen", False) and sys.platform == "win32":
            ok, reason = _verify_authenticode_signature(
                sys.executable,
                "APP_SIGNER_THUMBPRINTS",
            )
            if not ok:
                logger.error("Executable signature verification failed: %s", reason)
                QMessageBox.critical(
                    None,
                    "보안 오류",
                    "앱 서명 검증에 실패했습니다. 실행을 중단합니다.",
                )
                sys.exit(1)
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
        from utils.auto_updater import get_current_version
        return get_current_version()

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
                self._build_launch_error_message(e),
            )

    @staticmethod
    def _build_launch_error_message(exc: Exception) -> str:
        """Return a user-friendly launch error message for known runtime issues."""
        detail = f"{type(exc).__name__}: {exc}"
        lowered = detail.lower()
        numpy_signature = (
            "numpy" in lowered
            and (
                "_multiarray_umath" in lowered
                or "importing the numpy c-extensions failed" in lowered
                or "numpy c-extensions failed" in lowered
            )
        )

        if numpy_signature:
            return (
                "메인 앱을 시작할 수 없습니다.\n\n"
                "원인: 업데이트 중 이전 버전 파일이 남아 라이브러리 충돌이 발생했습니다.\n\n"
                "해결 방법\n"
                "1) 최신 설치 파일을 다시 실행하세요.\n"
                "2) 설치 모드에서 '재설치(Reinstall)'를 선택하세요.\n"
                "3) 설치 완료 후 앱을 다시 실행하세요.\n\n"
                f"기술 정보: {detail}"
            )

        return f"메인 앱을 시작할 수 없습니다:\n{detail}"

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
        self.update_complete_dialog.confirmed.connect(self._transition_to_main)
        self.update_complete_dialog.show()

        # Pre-import heavy main module while dialog countdown is visible.
        # This caches ~20+ module imports so launch_main_app is near-instant.
        QtCore.QTimer.singleShot(500, self._preload_main_module)

    def _preload_main_module(self) -> None:
        """Pre-import main module during update dialog to reduce transition lag."""
        try:
            import main  # noqa: F401
            logger.debug("Main module pre-imported during update dialog")
        except Exception as e:
            logger.warning(f"Failed to pre-import main module: {e}")

    def _transition_to_main(self) -> None:
        """Smooth transition from update dialog to main app."""
        dialog = getattr(self, "update_complete_dialog", None)
        if dialog and hasattr(dialog, "countdown_label"):
            dialog.countdown_label.setText("메인 화면을 준비하고 있습니다...")
            self.app.processEvents()

        self.launch_main_app()

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

            # Verify installer code signature before execution.
            # If UPDATE_SIGNER_THUMBPRINTS is set, signer must match allowlist.
            ok, reason = _verify_authenticode_signature(
                self.dest_path,
                "UPDATE_SIGNER_THUMBPRINTS",
            )
            if not ok:
                raise ValueError(f"Installer signature verification failed: {reason}")
                
            self.finished.emit(True, self.dest_path)
        except Exception as e:
            self.finished.emit(False, str(e))
