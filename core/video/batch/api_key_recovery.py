"""
API Key Recovery Module

Shared logic for handling API key errors (429 quota, 403 permission)
with user-facing popup dialogs and key rotation.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Constants
KEY_BLOCK_DURATION_MINUTES = 30
RETRY_WAIT_MULTIPLIER_SECONDS = 15
SERVER_OVERLOAD_WAIT_MINUTES = 5


def is_google_drive_permission_error(error_msg: str) -> bool:
    """Return True only for file-sharing failures that actually mention Drive."""
    lowered = str(error_msg or "").lower()
    drive_context = any(
        marker in lowered
        for marker in (
            "google drive",
            "drive.google.com",
            "file id",
            "shared file",
        )
    )
    file_access_failure = any(
        marker in lowered
        for marker in (
            "you do not have permission to access the file",
            "file not found",
            "request access",
            "sharing settings",
        )
    )
    return drive_context and file_access_failure


def show_api_key_error_and_wait(app, step_name, key_name, error_msg, error_type="quota"):
    """
    Show an API key error popup on the main thread and wait for user response.

    Args:
        app: The main application instance (QMainWindow)
        step_name: Current processing step name (for display)
        key_name: Name of the problematic API key
        error_msg: Error message to display
        error_type: "quota" or "permission"

    Returns:
        str: "retry" | "stop"
    """
    result_holder = {"action": "stop"}
    wait_event = threading.Event()

    def _show_dialog():
        try:
            from ui.windows.api_key_error_dialog import ApiKeyErrorDialog

            prev = getattr(app, "_api_key_error_dialog", None)
            if prev is not None:
                try:
                    prev.close()
                    prev.deleteLater()
                except Exception as close_err:
                    logger.debug("Failed to close previous dialog: %s", close_err)

            dialog = ApiKeyErrorDialog(
                parent=app,
                step_name=step_name,
                key_name=key_name,
                error_msg=error_msg,
                error_type=error_type,
            )

            def _on_finished(_code=None):
                try:
                    result_holder["action"] = getattr(dialog, "result_action", "stop")
                finally:
                    try:
                        dialog.deleteLater()
                    except Exception as del_err:
                        logger.debug("Failed to delete dialog: %s", del_err)
                    if getattr(app, "_api_key_error_dialog", None) is dialog:
                        app._api_key_error_dialog = None
                    wait_event.set()

            dialog.finished.connect(_on_finished)
            dialog.show()
            try:
                dialog.raise_()
                dialog.activateWindow()
            except Exception as raise_err:
                logger.debug("Failed to raise dialog: %s", raise_err)
            app._api_key_error_dialog = dialog
        except Exception as dialog_err:
            logger.error("[ApiKeyErrorDialog] Failed to show: %s", dialog_err)
            result_holder["action"] = "stop"
            wait_event.set()

    signal = getattr(app, "ui_callback_signal", None)
    if signal is not None:
        try:
            signal.emit(_show_dialog)
        except RuntimeError:
            wait_event.set()
            return "stop"
    else:
        wait_event.set()
        return "stop"

    while not wait_event.is_set():
        if not getattr(app, "batch_processing", True):
            try:
                dlg = getattr(app, "_api_key_error_dialog", None)
                if dlg is not None and signal is not None:
                    signal.emit(lambda: dlg.close())
            except Exception as close_err:
                logger.debug("Failed to close dialog on stop: %s", close_err)
            return "stop"
        wait_event.wait(timeout=0.2)

    return result_holder["action"]


def try_rotate_key(app, block_duration=KEY_BLOCK_DURATION_MINUTES):
    """
    Attempt to block the current API key and rotate to a new one.

    Args:
        app: The main application instance
        block_duration: Minutes to block the current key

    Returns:
        tuple: (success: bool, blocked_key: str, new_key_name: str)
    """
    api_mgr = getattr(app, "api_key_manager", None)
    if api_mgr is None:
        return False, "unknown", "unknown"

    blocked_key = getattr(api_mgr, "current_key", "unknown")
    try:
        api_mgr.block_current_key(duration_minutes=block_duration)
    except Exception as block_err:
        app.add_log(f"[WARN] 키 차단 중 오류: {block_err}")

    try:
        new_key = api_mgr.get_available_key()
        new_key_name = getattr(api_mgr, "current_key", "unknown")
        if new_key and app.init_client(use_specific_key=new_key):
            return True, blocked_key, new_key_name
    except Exception as switch_err:
        app.add_log(f"[WARN] 키 교체 실패: {switch_err}")

    return False, blocked_key, "unknown"


def wait_for_user_key_retry(app, step_name, key_name, error_msg, error_type="quota"):
    """
    Show popup and wait for user to add/fix keys, then retry init_client.

    This is the shared retry loop used by both 429 and 403 handlers
    in processor.py and tts_generator.py.

    Args:
        app: The main application instance
        step_name: Current processing step name
        key_name: Name of the problematic API key
        error_msg: Error message (truncated for display)
        error_type: "quota" or "permission"

    Returns:
        bool: True if successfully resumed with a new key, False if stopped
    """
    # Detect Google Drive permission errors (file sharing issue, not API key issue)
    is_gdrive_permission_error = False
    if error_type == "permission":
        is_gdrive_permission_error = is_google_drive_permission_error(error_msg)
        if is_gdrive_permission_error:
            app.add_log(
                "[WARN] 구글 드라이브 파일 접근 권한 오류가 감지되었습니다. "
                "이는 API 키 문제가 아니라 파일 공유 설정 문제일 수 있습니다."
            )

    retry_count = 0
    max_retries = 3 if not is_gdrive_permission_error else 1

    while getattr(app, "batch_processing", True):
        # For Google Drive permission errors, show enhanced message
        display_msg = error_msg[:200]
        if is_gdrive_permission_error and retry_count == 0:
            display_msg += "\n\n💡 해결 방법: 구글 드라이브에서 해당 파일을 '링크가 있는 모든 사용자'로 공유하거나, OAuth 인증을 사용하세요."

        user_action = show_api_key_error_and_wait(
            app,
            step_name=step_name,
            key_name=key_name,
            error_msg=display_msg,
            error_type=error_type,
        )

        if user_action != "retry":
            break

        retry_count += 1

        # Prevent infinite loop for Google Drive permission errors
        if is_gdrive_permission_error and retry_count > max_retries:
            app.add_log(
                "[오류] 구글 드라이브 파일 권한 오류는 API 키로 해결할 수 없습니다. "
                "파일 공유 설정을 확인하거나 해당 URL을 건너뛰세요."
            )
            break

        api_mgr = getattr(app, "api_key_manager", None)
        if not api_mgr:
            app.add_log("[WARN] API 키 관리자 없음 - 설정에서 키를 추가한 뒤 다시 시도해주세요.")
            if retry_count >= max_retries:
                app.add_log(f"[오류] {max_retries}번 재시도 실패 - 작업을 중지합니다.")
                break
            continue

        try:
            new_key = api_mgr.get_available_key()
        except Exception as retry_err:
            app.add_log(f"[WARN] 사용 가능한 키 없음: {retry_err}")
            if retry_count >= max_retries:
                app.add_log(f"[오류] {max_retries}번 재시도 실패 - 작업을 중지합니다.")
                break
            continue

        if new_key and app.init_client(use_specific_key=new_key):
            new_name = getattr(api_mgr, "current_key", "unknown")
            app.add_log(f"작업 재개 (키: {new_name})")
            return True

        app.add_log(f"[WARN] 키 초기화 실패 ({retry_count}/{max_retries})")

        if retry_count >= max_retries:
            app.add_log(f"[오류] {max_retries}번 재시도 실패 - 작업을 중지합니다.")
            break

    return False


def handle_api_error_with_rotation(app, error_str, error_type, step_name="처리"):
    """
    Handle API key errors (429/403) in TTS or other generators with key rotation.
    Cancellation-safe sleep using 1-second intervals.

    Args:
        app: The main application instance
        error_str: The error message string
        error_type: "429" or "403"
        step_name: Current processing step for display

    Returns:
        bool: True if key was rotated successfully
    """
    block_duration = 5 if error_type == "429" else KEY_BLOCK_DURATION_MINUTES
    blocked_key = "unknown"

    api_mgr = getattr(app, "api_key_manager", None)
    if api_mgr:
        blocked_key = getattr(api_mgr, "current_key", "unknown")
        app.add_log(f"[{step_name}] API {error_type} 오류 (키: {blocked_key}) - {error_str[:80]}")
        api_mgr.block_current_key(duration_minutes=block_duration)
        if hasattr(app, "init_client") and app.init_client():
            new_key = getattr(api_mgr, "current_key", "unknown")
            app.add_log(f"[{step_name}] 키 교체: {blocked_key} -> {new_key}")
            return True
        else:
            app.add_log(f"[{step_name}] 사용 가능한 API 키 없음 - 작업을 중지합니다.")
            _show_no_key_popup_and_stop(app, step_name)
            return False
    else:
        app.add_log(f"[{step_name}] API {error_type} 오류 - 키 관리자 없음")
        _show_no_key_popup_and_stop(app, step_name)
        return False


def _show_no_key_popup_and_stop(app, step_name="처리"):
    """
    Show a popup alerting the user that no API keys are available,
    then stop batch processing.
    """
    app.batch_processing = False
    app.dynamic_processing = False

    def _show_popup():
        try:
            from ui.components.custom_dialog import show_error
            show_error(
                app,
                "API 키 오류",
                f"[{step_name}] 사용 가능한 API 키가 없습니다.\n\n"
                "모든 API 키가 차단되었거나 등록된 키가 없습니다.\n"
                "설정 페이지에서 API 키를 추가하거나 확인해주세요.\n\n"
                "작업이 중지되었습니다.",
            )
        except Exception as popup_err:
            logger.error("[ApiKeyRecovery] Failed to show no-key popup: %s", popup_err)

    signal = getattr(app, "ui_callback_signal", None)
    if signal is not None:
        try:
            signal.emit(_show_popup)
        except RuntimeError:
            pass


def interruptible_sleep(app, seconds):
    """
    Sleep for the given number of seconds, checking every second
    whether batch_processing has been stopped.

    Args:
        app: The main application instance
        seconds: Total seconds to sleep

    Returns:
        bool: True if sleep completed fully, False if interrupted
    """
    for _ in range(seconds):
        if not getattr(app, "batch_processing", True):
            return False
        time.sleep(1)
    return True
