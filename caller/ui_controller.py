# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog,
    QMessageBox, QFileDialog, QInputDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QSpinBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QListWidget,
    QFrame, QGroupBox, QTabWidget, QScrollArea,
    QSizePolicy, QSpacerItem
)
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPalette
import configparser
import json
import os
import sys
from pathlib import Path
from utils.logging_config import get_logger

logger = get_logger(__name__)
SAVED_LOGIN_PASSWORD_KEY = "saved_login_pw"


def _get_secrets_manager():
    """Return SecretsManager class when available."""
    try:
        from utils.secrets_manager import SecretsManager

        return SecretsManager
    except ImportError:
        logger.warning("SecretsManager not available")
        return None


def _get_info_on_paths() -> tuple[Path, Path]:
    """
    Return (primary, legacy) paths for info.on.

    - In frozen builds, use per-user location.
    - Legacy path exists only for migration from old installs.
    """
    is_frozen = bool(getattr(sys, "frozen", False))
    if is_frozen:
        base_dir = Path.home() / ".newshopping"
        primary = base_dir / "info.on"
        legacy = Path(sys.executable).resolve().parent / "info.on"
        return primary, legacy

    primary = Path("./info.on").resolve()
    return primary, primary


def _clear_saved_password(config_obj: configparser.ConfigParser) -> None:
    """Remove legacy password fields from both secure storage and config."""
    sm = _get_secrets_manager()
    if sm:
        try:
            sm.delete_api_key(SAVED_LOGIN_PASSWORD_KEY)
        except Exception:
            pass

    if config_obj.has_section("User"):
        config_obj.set("User", "pw", "")


def _load_saved_password() -> str:
    """Return the saved login password from secure storage, if available."""
    sm = _get_secrets_manager()
    if not sm:
        return ""
    try:
        return sm.get_api_key(SAVED_LOGIN_PASSWORD_KEY) or ""
    except Exception as e:
        logger.warning("Failed to load saved login password: %s", e)
        return ""


def _save_login_password(password: str) -> bool:
    """Save the login password to secure storage."""
    sm = _get_secrets_manager()
    if not sm:
        return False
    try:
        return sm.store_api_key(SAVED_LOGIN_PASSWORD_KEY, password)
    except Exception as e:
        logger.warning("Failed to save login password: %s", e)
        return False


def _delete_login_password() -> None:
    """Delete the login password from secure storage."""
    sm = _get_secrets_manager()
    if not sm:
        return
    try:
        sm.delete_api_key(SAVED_LOGIN_PASSWORD_KEY)
    except Exception:
        pass


def userLoadInfo(self):
    """Load saved login info."""
    config = configparser.ConfigParser(interpolation=None)
    self.auto_login_enabled = False
    try:
        primary_path, legacy_path = _get_info_on_paths()
        read_path: Path | None = None

        if primary_path.exists():
            read_path = primary_path
        elif legacy_path != primary_path and legacy_path.exists():
            read_path = legacy_path

        if read_path:
            config.read(str(read_path), encoding="utf-8")
            self.version = str(config.get("Config", "version", fallback="1.0.0"))
            config_changed = False

            if config.get("User", "save", fallback="f") == "t":
                self.idEdit.setText(config.get("User", "id", fallback=""))

                legacy_pw = config.get("User", "pw", fallback="")
                saved_pw = _load_saved_password()
                if not saved_pw and legacy_pw:
                    if _save_login_password(legacy_pw):
                        saved_pw = legacy_pw
                    config.set("User", "pw", "")
                    config_changed = True

                self.pwEdit.setText(saved_pw)
                if hasattr(self, "rememberCheckbox"):
                    self.rememberCheckbox.setChecked(True)
                elif hasattr(self, "idpw_checkbox"):
                    self.idpw_checkbox.setChecked(True)

                auto_login = config.get("User", "auto_login", fallback="f") == "t"
                self.auto_login_enabled = bool(auto_login and saved_pw and self.idEdit.text())
                if hasattr(self, "autoLoginCheckbox"):
                    self.autoLoginCheckbox.setChecked(self.auto_login_enabled)
            else:
                _delete_login_password()
                if config.has_section("User") and config.get("User", "pw", fallback=""):
                    config.set("User", "pw", "")
                    config_changed = True

            # If we loaded from legacy, persist migrated content to primary.
            if read_path == legacy_path and legacy_path != primary_path:
                try:
                    primary_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(str(primary_path), "w", encoding="utf-8") as f:
                        config.write(f)
                except Exception as e:
                    logger.warning("Failed to persist migrated info.on to primary path: %s", e)
            elif read_path == primary_path and config_changed:
                # Persist cleanup of password remnants.
                try:
                    with open(str(primary_path), "w", encoding="utf-8") as f:
                        config.write(f)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Failed to load user info: %s", e)


def userSaveInfo(self, checkState, loginid, loginpw, version="1.0.0", autoLogin=False):
    """Save login info and optional auto-login preference."""
    config = configparser.ConfigParser(interpolation=None)
    password_saved = False
    if checkState:
        if loginpw:
            password_saved = _save_login_password(loginpw)
        if not password_saved:
            _delete_login_password()
        config["User"] = {
            "id": loginid,
            "pw": "",
            "save": "t",
            "auto_login": "t" if autoLogin and password_saved else "f",
        }
    else:
        _delete_login_password()
        config["User"] = {"id": "", "pw": "", "save": "f", "auto_login": "f"}

    config["Config"] = {"version": version}
    try:
        primary_path, _legacy_path = _get_info_on_paths()
        primary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(primary_path), "w", encoding="utf-8") as f:
            config.write(f)
        logger.info(
            "User info saved: remember=%s auto_login=%s password_saved=%s",
            checkState,
            autoLogin,
            password_saved,
        )
    except Exception as e:
        logger.warning("Failed to save user info: %s", e)
    return loginid, loginpw


def accountLoadInfo(self):
    pass  # logic as before but with PyQt6 safety


def accountSaveInfo(*args):
    pass


def errorSaveInfo(self, message):
    pass


def write_error_log(error):
    """Write error log from processing pipelines."""
    try:
        logger.error(f"[ErrorLog] {type(error).__name__}: {error}")
    except Exception:
        pass
