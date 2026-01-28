# -*- coding: utf-8 -*-

import traceback
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog,
    QMessageBox, QFileDialog, QInputDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QSpinBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QListWidget,
    QFrame, QGroupBox, QTabWidget, QScrollArea,
    QSizePolicy, QSpacerItem
)
from PyQt5.QtGui import QIcon, QFont, QColor, QPixmap, QPalette
import configparser
from datetime import datetime, timedelta
import json
import os

from utils.logging_config import get_logger

logger = get_logger(__name__)

def userLoadInfo(self):
    config = configparser.ConfigParser(interpolation=None)
    try:
        with open('./info.on', 'r', encoding='utf-8') as f:
            config.read_file(f)
    except Exception as e:
        logger.warning("Failed to load user info: %s", e)
        return

    self.version = str(config['Config']['version'])
    saveConfig = config['User']['save']
    if saveConfig == 't':
        saveid = str(config['User']['id'])
        savepw = str(config['User']['pw'])
        self.idpw_checkbox.toggle()
        self.idEdit.setText(saveid)
        self.pwEdit.setText(savepw)


def userSaveInfo(self, checkState, loginid, loginpw, version):
    if checkState == True:
        saveCheck = 't'
        config = configparser.ConfigParser(interpolation=None)
        try:
            with open('./info.on', 'r', encoding='utf-8') as f:
                config.read_file(f)
        except Exception as e:
            logger.warning("Failed to read info.on for saving: %s", e)
            return

        config['User']['id'] = loginid
        config['User']['pw'] = loginpw
        config['User']['save'] = saveCheck
        config['Config']['version'] = version
        with open('./info.on', 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    
    elif checkState == False:
        saveCheck = 'f'
        config = configparser.ConfigParser(interpolation=None)
        try:
            with open('./info.on', 'r', encoding='utf-8') as f:
                config.read_file(f)
        except Exception as e:
            logger.warning("Failed to read info.on for clearing: %s", e)
            return

        config['User']['id'] = ""
        config['User']['pw'] = ""
        config['User']['save'] = saveCheck
        config['Config']['version'] = version
        with open('./info.on', 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    return loginid, loginpw

def accountLoadInfo(self):
    config = configparser.ConfigParser(interpolation=None)
    try:
        with open('./set.on', 'r', encoding='utf-8') as f:
            config.read_file(f)

    except Exception as e:
        logger.warning("Failed to load account info, using defaults: %s", e)
        config['Account'] = {}
    
    onFie_defaults(self, config)
    
    self.idEdit.setText(str(config['Account']['id']))
    self.pwEdit.setText(str(config['Account']['pw']))
    
    self.workCountEdit.setText(config['Account']['work'])
    self.delayCountEdit.setText(config['Account']['delay'])

    follow = int(config['Account']['isfollow'])
    self.cb_option_postFollow.setChecked(follow == 0)
    
    like = int(config['Account']['islike'])
    self.cb_option_postLike.setChecked(like == 0)
    
    comment = int(config['Account']['iscomment'])
    self.cb_option_postComment.setChecked(comment == 0)

    loaded_keywords = json.loads(config['Account'].get('keyword', '[]'))
    loaded_comments = json.loads(config['Account'].get('comment', '[]'))

    self.keywordList.clear()
    self.commentList.clear()
        
    self.keyword_table.setRowCount(0)
    self.comment_table.setRowCount(0)
    self.keywordTableCount = 0
    self.commentTableCount = 0

    for keyword in loaded_keywords:
        self.keywordEdit.setText(keyword)
        self.updateKeywordList(0)

    # 댓글 로드
    for comment in loaded_comments:
        self.commentEdit.setText(comment)
        self.updateKeywordList(1)
    

def accountSaveInfo(self, id, pw, work, delay, follow, like, comment, keywordList, commentList):

    config = configparser.ConfigParser(interpolation=None)
    try:
        with open('./set.on', 'r', encoding='utf-8') as f:
            config.read_file(f)

    except Exception as e:
        logger.warning("Failed to read set.on for saving, creating new: %s", e)
        config['Account'] = {}
    
    config['Account']['id'] = id
    config['Account']['pw'] = pw
    config['Account']['work'] = work
    config['Account']['delay'] = delay
    
    config['Account']['isfollow'] = str(follow)
    config['Account']['islike'] = str(like)
    config['Account']['iscomment'] = str(comment)
    
    config['Account']['keyword'] = json.dumps(keywordList, ensure_ascii=False)
    config['Account']['comment'] = json.dumps(commentList, ensure_ascii=False)
    with open('./set.on', 'w', encoding='utf-8') as configfile:
        config.write(configfile)
            
    return id, pw

def onFie_defaults(self, config):
    if 'Account' not in config:
        config['Account'] = {}

    account_defaults = {
        'id': '',
        'pw': '',
        'work': '20',
        'delay': '120',
        'isfollow' : 0,
        'islike' : 0,
        'iscomment' : 0,
        'keyword': '[]',
        'comment': '[]'
    }

    updated = False
    for key, default_value in account_defaults.items():
        if key not in config['Account']:
            logger.debug("Adding missing config key: %s", key)
            config['Account'][key] = str(default_value)
            updated = True

    if updated:
        try:
            with open('./set.on', 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            logger.info("기본값이 추가되어 set.on 파일 저장 완료.")
        except Exception as e:
            logger.error("기본값 저장 중 오류: %s", e)        
            
            
def errorLoadInfo(self):
    
    log_dir = './log'
    today_str = datetime.now().strftime('%Y%m%d')
    today_filename = f"{today_str}_error.on"
    today_filepath = os.path.join(log_dir, today_filename)

    today = datetime.now()
    keep_dates = [(today - timedelta(days=i)).strftime('%Y%m%d') for i in range(14)]
    
    # 1. log 폴더가 없으면 생성
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        logger.info("log 폴더 생성됨.")

    # 2. log 폴더 내 .on 파일 목록 확인
    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        if filename.endswith('.on'):
            try:
                date_part = filename.split('_')[0]
                if date_part not in keep_dates:
                    os.remove(filepath)
                    logger.info("%s 삭제됨.", filename)
            except Exception as e:
                logger.error("%s 삭제 중 오류 발생: %s", filename, e)
            
    config = configparser.ConfigParser(interpolation=None)

    if not os.path.exists(today_filepath):
        config['Error'] = {}
        try:
            with open(today_filepath, 'w', encoding='utf-8') as f:
                config.write(f)
            logger.info("%s 생성됨.", today_filename)
        except Exception as e:
            logger.error("파일 생성 실패: %s", e)
            return
    else:
        try:
            with open(today_filepath, 'r', encoding='utf-8') as f:
                config.read_file(f)
            logger.debug("%s 이미 존재하며 로드됨.", today_filename)
        except Exception as e:
            logger.error("파일 읽기 실패: %s", e)
            return
        
    # 4. 오늘 날짜 파일이 없다면 생성
    if not os.path.exists(today_filepath):
        config = configparser.ConfigParser(interpolation=None)
        try:
            with open(today_filepath, 'w', encoding='utf-8') as f:
                config.write(f)

        except Exception as e:
            logger.error("Failed to create error log file: %s", e)
            config['Error'] = {}
        logger.info("%s 생성됨.", today_filename)
    else:
        logger.debug("%s 이미 존재함.", today_filename)

def errorSaveInfo (self, message: str):
    log_dir = './log'
    today_str = datetime.now().strftime('%Y%m%d')
    today_filename = f"{today_str}_error.on"
    today_filepath = os.path.join(log_dir, today_filename)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"{timestamp} - {message}"

    # 파일이 없다면 먼저 [Error] 헤더 추가
    if not os.path.exists(today_filepath):
        with open(today_filepath, 'w', encoding='utf-8') as f:
            f.write("[Error]\n")

    # 에러 메시지 추가
    with open(today_filepath, 'a', encoding='utf-8') as f:
        f.write(log_entry + '\n')
        
def write_error_log(error: Exception):
    import traceback
    from datetime import datetime
    import os

    log_dir = "./logs"
    os.makedirs(log_dir, exist_ok=True)

    filename = datetime.now().strftime("%Y_%m_%d_log.txt")
    filepath = os.path.join(log_dir, filename)

    current_time = datetime.now().strftime("%H:%M:%S")
    separator = "-" * 90
    trace = traceback.format_exc()

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"[{current_time}] {separator}\n")
        f.write(trace + "\n\n")

    # print(f"[ErrorLog] 오류 저장됨: {filepath}")