# -*- coding: utf-8 -*-
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
            sm.store_api_key("saved_login_pw", "")
        except Exception:
            pass

    if config_obj.has_section("User"):
        config_obj.set("User", "pw", "")


def userLoadInfo(self):
    """Load saved login info (ID only)."""
    config = configparser.ConfigParser(interpolation=None)
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

            if config.get("User", "save", fallback="f") == "t":
                self.idEdit.setText(config.get("User", "id", fallback=""))
                self.pwEdit.setText("")
                _clear_saved_password(config)
                if hasattr(self, "rememberCheckbox"):
                    self.rememberCheckbox.setChecked(True)
                elif hasattr(self, "idpw_checkbox"):
                    self.idpw_checkbox.setChecked(True)

            # If we loaded from legacy, persist migrated content to primary.
            if read_path == legacy_path and legacy_path != primary_path:
                try:
                    primary_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(str(primary_path), "w", encoding="utf-8") as f:
                        config.write(f)
                except Exception as e:
                    logger.warning("Failed to persist migrated info.on to primary path: %s", e)
            elif read_path == primary_path:
                # Persist cleanup of password remnants.
                try:
                    with open(str(primary_path), "w", encoding="utf-8") as f:
                        config.write(f)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Failed to load user info: %s", e)


def userSaveInfo(self, checkState, loginid, loginpw, version="1.0.0"):
    """Save login info (ID only)."""
    config = configparser.ConfigParser(interpolation=None)
    if checkState:
        config["User"] = {"id": loginid, "pw": "", "save": "t"}
    else:
        config["User"] = {"id": "", "pw": "", "save": "f"}

    _clear_saved_password(config)
    config["Config"] = {"version": version}
    try:
        primary_path, _legacy_path = _get_info_on_paths()
        primary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(primary_path), "w", encoding="utf-8") as f:
            config.write(f)
        logger.info("User info saved: remember=%s", checkState)
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
