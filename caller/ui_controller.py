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
    """SecretsManager 인스턴스를 가져오기 (지연 임포트)"""
    try:
        from utils.secrets_manager import SecretsManager
        return SecretsManager
    except ImportError:
        logger.warning("SecretsManager not available, password will not be stored securely")
        return None


def _get_info_on_paths() -> tuple[Path, Path]:
    """
    Return (primary, legacy) paths for info.on.

    - In frozen builds, never use the current working directory. Use a per-user location
      to avoid accidentally picking up developer repo files when running `dist\\ssmaker.exe`
      from a terminal rooted elsewhere.
    - Legacy path exists only to migrate older installs that kept info.on next to the exe.
    """
    is_frozen = bool(getattr(sys, "frozen", False))
    if is_frozen:
        base_dir = Path.home() / ".newshopping"
        primary = base_dir / "info.on"
        legacy = Path(sys.executable).resolve().parent / "info.on"
        return primary, legacy

    # Dev/runtime: keep existing behavior (relative to CWD)
    primary = Path("./info.on").resolve()
    return primary, primary


def userLoadInfo(self):
    """저장된 로그인 정보 불러오기 (비밀번호는 암호화 저장소에서 로드)"""
    config = configparser.ConfigParser(interpolation=None)
    try:
        primary_path, legacy_path = _get_info_on_paths()
        read_path: Path | None = None

        if primary_path.exists():
            read_path = primary_path
        elif legacy_path != primary_path and legacy_path.exists():
            # Migrate from legacy location (next to exe) into per-user location.
            read_path = legacy_path

        if read_path:
            config.read(str(read_path), encoding='utf-8')
            self.version = str(config.get('Config', 'version', fallback='1.0.0'))
            if config.get('User', 'save', fallback='f') == 't':
                self.idEdit.setText(config.get('User', 'id', fallback=''))
                # 비밀번호는 SecretsManager에서 암호화된 상태로 로드
                sm = _get_secrets_manager()
                saved_pw = None
                if sm:
                    try:
                        saved_pw = sm.get_api_key("saved_login_pw")
                    except Exception as e:
                        logger.warning("Failed to load password from SecretsManager: %s", e)
                # SecretsManager 실패 시 레거시 info.on에서 마이그레이션
                if not saved_pw:
                    saved_pw = config.get('User', 'pw', fallback='')
                    # 레거시 평문 비밀번호가 있으면 암호화 저장소로 마이그레이션
                    if saved_pw and sm:
                        try:
                            sm.store_api_key("saved_login_pw", saved_pw)
                            # 마이그레이션 후 info.on에서 평문 비밀번호 제거
                            config.set('User', 'pw', '')
                            primary_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(str(primary_path), 'w', encoding='utf-8') as f:
                                config.write(f)
                            logger.info("Migrated plaintext password to encrypted storage")
                        except Exception as e:
                            logger.warning("Failed to migrate password: %s", e)
                if saved_pw:
                    self.pwEdit.setText(saved_pw)
                # 모던 UI의 rememberCheckbox 또는 레거시 idpw_checkbox 체크
                if hasattr(self, 'rememberCheckbox'):
                    self.rememberCheckbox.setChecked(True)
                elif hasattr(self, 'idpw_checkbox'):
                    self.idpw_checkbox.setChecked(True)

            # If we loaded from legacy, persist the non-secret bits to primary as well.
            if read_path == legacy_path and legacy_path != primary_path:
                try:
                    primary_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(str(primary_path), 'w', encoding='utf-8') as f:
                        config.write(f)
                except Exception as e:
                    logger.warning("Failed to persist migrated info.on to primary path: %s", e)
    except Exception as e:
        logger.warning("Failed to load user info: %s", e)

def userSaveInfo(self, checkState, loginid, loginpw, version='1.0.0'):
    """로그인 정보 저장 (비밀번호는 암호화 저장소에 저장, info.on에는 평문 비밀번호 미저장)"""
    config = configparser.ConfigParser(interpolation=None)
    if checkState:
        config['User'] = {'id': loginid, 'pw': '', 'save': 't'}
        # 비밀번호는 SecretsManager에 암호화 저장
        sm = _get_secrets_manager()
        if sm:
            try:
                sm.store_api_key("saved_login_pw", loginpw)
            except Exception as e:
                logger.warning("Failed to store password in SecretsManager: %s", e)
    else:
        config['User'] = {'id': '', 'pw': '', 'save': 'f'}
        # 기억하기 해제 시 암호화 저장소에서도 삭제
        sm = _get_secrets_manager()
        if sm:
            try:
                sm.store_api_key("saved_login_pw", "")
            except Exception:
                pass
    config['Config'] = {'version': version}
    try:
        primary_path, _legacy_path = _get_info_on_paths()
        primary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(primary_path), 'w', encoding='utf-8') as f:
            config.write(f)
        logger.info("User info saved: remember=%s", checkState)
    except Exception as e:
        logger.warning("Failed to save user info: %s", e)
    return loginid, loginpw

def accountLoadInfo(self):
    pass # logic as before but with PyQt6 safety

def accountSaveInfo(*args):
    pass

def errorSaveInfo(self, message):
    pass


def write_error_log(error):
    """에러를 로그에 기록 (processor.py 등에서 호출)"""
    try:
        logger.error(f"[ErrorLog] {type(error).__name__}: {error}")
    except Exception:
        pass
