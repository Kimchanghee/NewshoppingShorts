# -*- coding: utf-8 -*-
"""
Subscription Request UI
구독 신청 다이얼로그 - Stitch 스타일 모던 디자인 (PyQt6)
"""
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QWidget, QLabel, QTextEdit, QPushButton, QMessageBox
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QPalette, QBrush

FONT_FAMILY = "맑은 고딕"

class SubscriptionRequestDialog(QDialog):
    """구독 신청 다이얼로그"""
    
    subscriptionRequested = pyqtSignal(str)  # message

    def __init__(self, parent=None, work_used=0, work_count=2):
        super().__init__(parent)
        self.work_used = work_used
        self.work_count = work_count
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("구독 신청")
        self.setFixedSize(500, 600)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main Layout (Rounded with Gradient)
        self.main_frame = QWidget(self)
        self.main_frame.setGeometry(0, 0, 500, 600)
        self.main_frame.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #f8f9fa);
                border-radius: 20px;
                border: 1px solid #e0e0e0;
            }
        """)

        # Title Bar (Custom)
        self.title_bar = QLabel("쇼핑 숏폼 메이커", self.main_frame)
        self.title_bar.setGeometry(30, 30, 300, 30)
        self.title_bar.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        self.title_bar.setStyleSheet("color: #e31639; background: transparent; border: none;")

        # Close Button
        self.close_btn = QPushButton("✕", self.main_frame)
        self.close_btn.setGeometry(450, 20, 30, 30)
        self.close_btn.setFont(QFont(FONT_FAMILY, 12))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888;
                border: none;
            }
            QPushButton:hover {
                color: #333;
            }
        """)
        self.close_btn.clicked.connect(self.close)

        # Header Image / Icon Area
        self.icon_label = QLabel("💎", self.main_frame) # Gem icon
        self.icon_label.setGeometry(0, 80, 500, 80)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont("Segoe UI Emoji", 60))
        self.icon_label.setStyleSheet("background: transparent; border: none;")

        # Main Title
        self.main_title = QLabel("체험판 사용이 완료되었습니다", self.main_frame)
        self.main_title.setGeometry(0, 170, 500, 40)
        self.main_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_title.setFont(QFont(FONT_FAMILY, 18, QFont.Weight.Bold))
        self.main_title.setStyleSheet("color: #333; background: transparent; border: none;")

        # Sub Title (Usage Stats)
        self.sub_title = QLabel(f"현재 사용량: {self.work_used} / {self.work_count}회", self.main_frame)
        self.sub_title.setGeometry(0, 215, 500, 30)
        self.sub_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_title.setFont(QFont(FONT_FAMILY, 11))
        self.sub_title.setStyleSheet("color: #666; background: transparent; border: none;")

        # Description
        desc_text = """
        더 많은 영상을 제작하시려면 구독이 필요합니다.
        아래 양식을 작성하여 구독을 신청해 주세요.
        관리자가 확인 후 승인해 드립니다.
        """
        self.desc_label = QLabel(desc_text.strip(), self.main_frame)
        self.desc_label.setGeometry(50, 260, 400, 60)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setFont(QFont(FONT_FAMILY, 10))
        self.desc_label.setStyleSheet("color: #555; background: transparent; border: none;")

        # Message Input
        self.msg_label = QLabel("신청 메시지 (선택)", self.main_frame)
        self.msg_label.setGeometry(50, 330, 200, 20)
        self.msg_label.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
        self.msg_label.setStyleSheet("color: #333; background: transparent; border: none;")

        self.message_edit = QTextEdit(self.main_frame)
        self.message_edit.setGeometry(50, 360, 400, 100)
        self.message_edit.setPlaceholderText("관리자에게 전달할 메모를 입력하세요 (예: 연락 가능한 시간, 요금제 문의 등)")
        self.message_edit.setFont(QFont(FONT_FAMILY, 10))
        self.message_edit.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 10px;
                color: #333;
            }
            QTextEdit:focus {
                border: 2px solid #e31639;
                background-color: #fff;
            }
        """)

        # Submit Button
        self.submit_btn = QPushButton("구독 신청하기", self.main_frame)
        self.submit_btn.setGeometry(50, 490, 400, 50)
        self.submit_btn.setFont(QFont(FONT_FAMILY, 12, QFont.Weight.Bold))
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e31639, stop:1 #ff4081);
                color: white;
                border: none;
                border-radius: 25px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c21532, stop:1 #e0356f);
                margin-top: 2px;
            }
            QPushButton:pressed {
                background: #a01028;
            }
        """)
        self.submit_btn.clicked.connect(self._on_submit)

        # Footer
        self.footer = QLabel("문의: help@ssmaker.com", self.main_frame)
        self.footer.setGeometry(0, 560, 500, 20)
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setFont(QFont(FONT_FAMILY, 9))
        self.footer.setStyleSheet("color: #999; background: transparent; border: none;")

    def _on_submit(self):
        msg = self.message_edit.toPlainText().strip()
        self.subscriptionRequested.emit(msg)
        self.accept()

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QtCore.QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()
