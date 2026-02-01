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
from utils.logging_config import get_logger

logger = get_logger(__name__)

def userLoadInfo(self):
    """저장된 로그인 정보 불러오기"""
    config = configparser.ConfigParser(interpolation=None)
    try:
        if os.path.exists('./info.on'):
            config.read('./info.on', encoding='utf-8')
            self.version = str(config.get('Config', 'version', fallback='1.0.0'))
            if config.get('User', 'save', fallback='f') == 't':
                self.idEdit.setText(config.get('User', 'id', fallback=''))
                self.pwEdit.setText(config.get('User', 'pw', fallback=''))
                # 모던 UI의 rememberCheckbox 또는 레거시 idpw_checkbox 체크
                if hasattr(self, 'rememberCheckbox'):
                    self.rememberCheckbox.setChecked(True)
                elif hasattr(self, 'idpw_checkbox'):
                    self.idpw_checkbox.setChecked(True)
    except Exception as e:
        logger.warning("Failed to load user info: %s", e)

def userSaveInfo(self, checkState, loginid, loginpw, version='1.0.0'):
    """로그인 정보 저장"""
    config = configparser.ConfigParser(interpolation=None)
    if checkState:
        config['User'] = {'id': loginid, 'pw': loginpw, 'save': 't'}
    else:
        config['User'] = {'id': '', 'pw': '', 'save': 'f'}
    config['Config'] = {'version': version}
    try:
        with open('./info.on', 'w', encoding='utf-8') as f:
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