# -*- coding: utf-8 -*-
"""
Update Dialog UI
업데이트 알림 다이얼로그

업데이트가 있을 때 사용자에게 알리고,
다운로드/설치를 진행할 수 있는 UI를 제공합니다.
"""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QWidget,
    QFrame,
)
from PyQt6.QtGui import QFont

from typing import Optional, Dict, Any, Callable
from pathlib import Path

from utils.logging_config import get_logger
from utils.auto_updater import UpdateChecker, get_current_version

logger = get_logger(__name__)

# 폰트 설정
FONT_FAMILY = "맑은 고딕"


class DownloadWorker(QThread):
    """백그라운드 다운로드 워커"""
    
    progress = pyqtSignal(int, int)  # downloaded, total
    finished = pyqtSignal(object)  # Path or None
    error = pyqtSignal(str)
    
    def __init__(self, checker: UpdateChecker, download_url: str):
        super().__init__()
        self.checker = checker
        self.download_url = download_url
    
    def run(self):
        try:
            def on_progress(downloaded: int, total: int):
                self.progress.emit(downloaded, total)
            
            path = self.checker.download_update(
                self.download_url,
                progress_callback=on_progress
            )
            self.finished.emit(path)
        except Exception as e:
            logger.exception(f"Download worker error: {e}")
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    """
    업데이트 알림 다이얼로그
    
    사용자에게 새 버전이 있음을 알리고,
    다운로드/설치 옵션을 제공합니다.
    """
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        update_info: Optional[Dict[str, Any]] = None
    ):
        super().__init__(parent)
        self.update_info = update_info or {}
        self._checker = UpdateChecker()
        self._download_worker: Optional[DownloadWorker] = None
        self._downloaded_path: Optional[Path] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """UI 설정"""
        self.setWindowTitle("업데이트 알림")
        self.setFixedSize(420, 300)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        # 스타일
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #1F2937;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)
        
        # 제목
        title_label = QLabel("새로운 버전이 있습니다!")
        title_label.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #e31639;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 버전 정보
        current_version = get_current_version()
        latest_version = self.update_info.get("latest_version", "?")
        
        version_frame = QFrame()
        version_frame.setStyleSheet("""
            QFrame {
                background-color: #F3F4F6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        version_layout = QHBoxLayout(version_frame)
        version_layout.setContentsMargins(20, 15, 20, 15)
        
        current_label = QLabel(f"현재 버전: {current_version}")
        current_label.setFont(QFont(FONT_FAMILY, 11))
        current_label.setStyleSheet("color: #6B7280;")
        
        arrow_label = QLabel("→")
        arrow_label.setFont(QFont(FONT_FAMILY, 14))
        arrow_label.setStyleSheet("color: #9CA3AF;")
        arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        latest_label = QLabel(f"최신 버전: {latest_version}")
        latest_label.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        latest_label.setStyleSheet("color: #10B981;")
        
        version_layout.addWidget(current_label)
        version_layout.addStretch()
        version_layout.addWidget(arrow_label)
        version_layout.addStretch()
        version_layout.addWidget(latest_label)
        
        layout.addWidget(version_frame)
        
        # 릴리스 노트
        release_notes = self.update_info.get("release_notes", "")
        if release_notes:
            notes_label = QLabel(release_notes)
            notes_label.setFont(QFont(FONT_FAMILY, 10))
            notes_label.setStyleSheet("color: #6B7280;")
            notes_label.setWordWrap(True)
            notes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(notes_label)
        
        # 진행률 바 (처음엔 숨김)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 5px;
                background-color: #E5E7EB;
                height: 10px;
            }
            QProgressBar::chunk {
                background-color: #e31639;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 상태 라벨
        self.status_label = QLabel("")
        self.status_label.setFont(QFont(FONT_FAMILY, 9))
        self.status_label.setStyleSheet("color: #6B7280;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        # 나중에 버튼
        self.later_btn = QPushButton("나중에")
        self.later_btn.setFont(QFont(FONT_FAMILY, 11))
        self.later_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.later_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #374151;
                border: none;
                border-radius: 8px;
                padding: 12px 25px;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
            }
        """)
        self.later_btn.clicked.connect(self.reject)
        
        # 업데이트 버튼
        self.update_btn = QPushButton("업데이트")
        self.update_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #e31639;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 25px;
            }
            QPushButton:hover {
                background-color: #c41231;
            }
            QPushButton:disabled {
                background-color: #D1D5DB;
            }
        """)
        self.update_btn.clicked.connect(self._on_update_clicked)
        
        button_layout.addWidget(self.later_btn)
        button_layout.addWidget(self.update_btn)
        
        layout.addLayout(button_layout)
        
        # 필수 업데이트 처리
        if self.update_info.get("is_mandatory"):
            self.later_btn.setVisible(False)
            title_label.setText("필수 업데이트가 있습니다!")
    
    def _on_update_clicked(self):
        """업데이트 버튼 클릭"""
        download_url = self.update_info.get("download_url")
        
        if not download_url:
            self.status_label.setText("다운로드 URL이 없습니다.")
            self.status_label.setStyleSheet("color: #EF4444;")
            self.status_label.setVisible(True)
            return
        
        # UI 업데이트
        self.update_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("다운로드 중...")
        self.status_label.setVisible(True)
        
        # 다운로드 시작
        self._download_worker = DownloadWorker(self._checker, download_url)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()
    
    def _on_download_progress(self, downloaded: int, total: int):
        """다운로드 진행률 업데이트"""
        if total > 0:
            percent = int(downloaded / total * 100)
            self.progress_bar.setValue(percent)
            
            # 크기 표시
            downloaded_mb = downloaded / 1024 / 1024
            total_mb = total / 1024 / 1024
            self.status_label.setText(f"다운로드 중... {downloaded_mb:.1f} / {total_mb:.1f} MB")
    
    def _on_download_finished(self, path: Optional[Path]):
        """다운로드 완료"""
        if path:
            self._downloaded_path = path
            self.progress_bar.setValue(100)
            self.status_label.setText("다운로드 완료! 설치를 시작합니다...")
            self.status_label.setStyleSheet("color: #10B981;")
            
            # 설치 시작
            QtCore.QTimer.singleShot(1000, self._start_install)
        else:
            self.status_label.setText("다운로드 실패")
            self.status_label.setStyleSheet("color: #EF4444;")
            self.update_btn.setEnabled(True)
            self.later_btn.setEnabled(True)
    
    def _on_download_error(self, error: str):
        """다운로드 에러"""
        self.status_label.setText(f"오류: {error[:50]}")
        self.status_label.setStyleSheet("color: #EF4444;")
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
    
    def _start_install(self):
        """설치 시작"""
        if self._downloaded_path:
            success = self._checker.install_update(self._downloaded_path)
            if success:
                self.status_label.setText("설치 프로그램이 시작되었습니다. 프로그램을 종료합니다...")
                QtCore.QTimer.singleShot(2000, self._exit_app)
            else:
                self.status_label.setText("설치 시작 실패")
                self.status_label.setStyleSheet("color: #EF4444;")
                self.update_btn.setEnabled(True)
                self.later_btn.setEnabled(True)
    
    def _exit_app(self):
        """앱 종료"""
        QtCore.QCoreApplication.quit()


def show_update_dialog_if_needed(
    parent: Optional[QWidget] = None,
    on_complete: Optional[Callable[[], None]] = None,
    check_async: bool = True
) -> None:
    """
    업데이트 확인 후 필요하면 다이얼로그 표시.
    
    Args:
        parent: 부모 위젯
        on_complete: 확인 완료 후 콜백 (업데이트 없거나 스킵한 경우)
        check_async: True면 비동기로 확인
    """
    from utils.auto_updater import get_update_checker
    
    def on_update_checked(result: Dict[str, Any]):
        if result.get("update_available"):
            dialog = UpdateDialog(parent=parent, update_info=result)
            dialog_result = dialog.exec()
            
            if dialog_result == QDialog.DialogCode.Rejected and on_complete:
                on_complete()
        else:
            if on_complete:
                on_complete()
    
    checker = get_update_checker()
    
    if check_async:
        checker.check_async(on_update_checked)
    else:
        result = UpdateChecker().check_for_updates()
        on_update_checked(result)
