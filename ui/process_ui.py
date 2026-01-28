# -*- coding: utf-8 -*-
"""
Process UI for Shopping Shorts Maker
쇼핑 숏폼 메이커 시작 점검 UI

모던 UI를 기본으로 사용합니다.
기존 호환성을 위해 Process_Ui 클래스 이름을 유지합니다.

설정 변경:
- USE_MODERN_UI = True: 새로운 모던 UI 사용 (기본값)
- USE_MODERN_UI = False: 기존 레거시 UI 사용
"""

# 모던 UI 사용 여부 설정
USE_MODERN_UI = True

if USE_MODERN_UI:
    # 모던 UI 사용 (STITCH 디자인 기반)
    from ui.process_ui_modern import ModernProcessUi as Process_Ui
else:
    # 기존 UI 사용 (레거시 호환)
    from PyQt5 import QtCore, QtGui, QtWidgets

    class Process_Ui(object):
        def setupUi(self, window):
            window.setObjectName("LoginWindow")
            window.resize(600, 520)
            window.setMinimumSize(QtCore.QSize(600, 520))
            window.setMaximumSize(QtCore.QSize(600, 520))
            window.setUnifiedTitleAndToolBarOnMac(False)

            self.mainwidget = QtWidgets.QWidget(window)
            self.mainwidget.setObjectName("centralwidget")

            self.frame = QtWidgets.QFrame(self.mainwidget)
            self.frame.setGeometry(QtCore.QRect(0, 0, 600, 520))
            self.frame.setStyleSheet("background-color: #faf9fc;")
            self.frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
            self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
            self.frame.setObjectName("rightFrame")

            # 상단 헤더 영역 (보라색 그라데이션)
            self.headerFrame = QtWidgets.QFrame(self.frame)
            self.headerFrame.setGeometry(QtCore.QRect(0, 0, 600, 80))
            self.headerFrame.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e31639, stop:1 #ff4d6a);
                border-bottom-left-radius: 20px;
                border-bottom-right-radius: 20px;
            """)

            # 제목
            self.title = QtWidgets.QLabel(self.headerFrame)
            self.title.setGeometry(QtCore.QRect(0, 15, 600, 30))
            self.title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold; background: transparent; border: 0px;")
            self.title.setAlignment(QtCore.Qt.AlignCenter)
            self.title.setText("🚀 쇼핑 숏폼 메이커")

            # 현재 상태 메시지
            self.statusLabel = QtWidgets.QLabel(self.headerFrame)
            self.statusLabel.setGeometry(QtCore.QRect(0, 45, 600, 25))
            self.statusLabel.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 12px; background: transparent; border: 0px;")
            self.statusLabel.setAlignment(QtCore.Qt.AlignCenter)
            self.statusLabel.setText("시스템을 점검하고 있습니다...")

            # 체크리스트 카드
            self.checklistFrame = QtWidgets.QFrame(self.frame)
            self.checklistFrame.setGeometry(QtCore.QRect(25, 95, 550, 340))
            self.checklistFrame.setStyleSheet("""
                background-color: #ffffff;
                border-radius: 16px;
                border: 1px solid #fce8eb;
            """)

            # 체크리스트 제목
            self.checklistTitle = QtWidgets.QLabel(self.checklistFrame)
            self.checklistTitle.setGeometry(QtCore.QRect(20, 12, 200, 25))
            self.checklistTitle.setStyleSheet("color: #374151; font-size: 13px; font-weight: bold; background: transparent; border: 0px;")
            self.checklistTitle.setText("📋 시작 전 점검 항목")

            # 체크리스트 항목들
            self.checkItems = {}
            items = [
                ("system", "💻 시스템 환경", "컴퓨터 성능 확인"),
                ("fonts", "🔤 폰트 확인", "자막용 폰트"),
                ("ffmpeg", "🎬 영상 처리", "영상 변환 엔진"),
                ("internet", "🌐 인터넷 연결", "서비스 연결용"),
                ("modules", "📦 핵심 모듈", "확인 중..."),
                ("ocr", "🔍 자막 인식", "중국어 자막 인식 (첫 실행 1-2분)"),
                ("tts_dir", "📁 음성 폴더", "음성 저장 폴더 준비"),
                ("api", "🔗 서비스 준비", "서비스 연결")
            ]

            y_pos = 45
            for item_id, item_title, item_desc in items:
                item_frame = QtWidgets.QFrame(self.checklistFrame)
                item_frame.setGeometry(QtCore.QRect(12, y_pos, 526, 34))
                item_frame.setStyleSheet("background-color: #f9fafb; border-radius: 8px; border: 0px;")

                icon_label = QtWidgets.QLabel(item_frame)
                icon_label.setGeometry(QtCore.QRect(8, 0, 28, 34))
                icon_label.setStyleSheet("font-size: 13px; background: transparent; border: 0px;")
                icon_label.setText("⏳")
                icon_label.setAlignment(QtCore.Qt.AlignCenter)

                title_label = QtWidgets.QLabel(item_frame)
                title_label.setGeometry(QtCore.QRect(38, 0, 180, 34))
                title_label.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: bold; background: transparent; border: 0px;")
                title_label.setText(item_title)
                title_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

                desc_label = QtWidgets.QLabel(item_frame)
                desc_label.setGeometry(QtCore.QRect(220, 0, 220, 34))
                desc_label.setStyleSheet("color: #9ca3af; font-size: 10px; background: transparent; border: 0px;")
                desc_label.setText(item_desc)
                desc_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

                status_label = QtWidgets.QLabel(item_frame)
                status_label.setGeometry(QtCore.QRect(445, 0, 70, 34))
                status_label.setStyleSheet("color: #9ca3af; font-size: 10px; background: transparent; border: 0px;")
                status_label.setText("대기")
                status_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

                self.checkItems[item_id] = {
                    'frame': item_frame,
                    'icon': icon_label,
                    'title': title_label,
                    'desc': desc_label,
                    'status': status_label
                }

                y_pos += 36

            # 프로그레스 영역
            self.progressFrame = QtWidgets.QFrame(self.frame)
            self.progressFrame.setGeometry(QtCore.QRect(25, 448, 550, 60))
            self.progressFrame.setStyleSheet("background-color: #ffffff; border-radius: 12px; border: 1px solid #fce8eb;")

            self.progressLabel = QtWidgets.QLabel(self.progressFrame)
            self.progressLabel.setGeometry(QtCore.QRect(20, 8, 100, 18))
            self.progressLabel.setStyleSheet("color: #374151; font-size: 11px; font-weight: bold; background: transparent; border: 0px;")
            self.progressLabel.setText("진행률")

            self.percentLabel = QtWidgets.QLabel(self.progressFrame)
            self.percentLabel.setGeometry(QtCore.QRect(450, 8, 80, 18))
            self.percentLabel.setStyleSheet("color: #e31639; font-size: 12px; font-weight: bold; background: transparent; border: 0px;")
            self.percentLabel.setAlignment(QtCore.Qt.AlignRight)
            self.percentLabel.setText("0%")

            self.progressBar = QtWidgets.QProgressBar(self.progressFrame)
            self.progressBar.setGeometry(QtCore.QRect(20, 32, 510, 14))
            self.progressBar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    border-radius: 7px;
                    background-color: #fce8eb;
                    color: black;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e31639, stop:1 #ff4d6a);
                    border-radius: 7px;
                }
            """)
            self.progressBar.setProperty("value", 0)
            self.progressBar.setTextVisible(False)
            self.progressBar.setObjectName("progressBar")

            window.setCentralWidget(self.mainwidget)
            QtCore.QMetaObject.connectSlotsByName(window)

        def updateCheckItem(self, item_id, status, message=None):
            """체크리스트 항목 상태 업데이트
            status: 'checking', 'success', 'warning', 'error'
            """
            if item_id not in self.checkItems:
                return

            item = self.checkItems[item_id]

            if status == 'checking':
                item['icon'].setText("🔄")
                item['frame'].setStyleSheet("background-color: #fef2f2; border-radius: 8px; border: 1px solid #fca5a5;")
                item['title'].setStyleSheet("color: #e31639; font-size: 11px; font-weight: bold; background: transparent; border: 0px;")
                item['desc'].setStyleSheet("color: #ff6b84; font-size: 10px; background: transparent; border: 0px;")
                item['status'].setText("확인 중...")
                item['status'].setStyleSheet("color: #e31639; font-size: 10px; font-weight: bold; background: transparent; border: 0px;")
            elif status == 'success':
                item['icon'].setText("✅")
                item['frame'].setStyleSheet("background-color: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0;")
                item['title'].setStyleSheet("color: #166534; font-size: 11px; font-weight: bold; background: transparent; border: 0px;")
                item['desc'].setStyleSheet("color: #22c55e; font-size: 10px; background: transparent; border: 0px;")
                item['status'].setText(message or "완료")
                item['status'].setStyleSheet("color: #16a34a; font-size: 10px; font-weight: bold; background: transparent; border: 0px;")
            elif status == 'warning':
                item['icon'].setText("⚠️")
                item['frame'].setStyleSheet("background-color: #fffbeb; border-radius: 8px; border: 1px solid #fde68a;")
                item['title'].setStyleSheet("color: #92400e; font-size: 11px; font-weight: bold; background: transparent; border: 0px;")
                item['desc'].setStyleSheet("color: #f59e0b; font-size: 10px; background: transparent; border: 0px;")
                item['status'].setText(message or "경고")
                item['status'].setStyleSheet("color: #d97706; font-size: 10px; font-weight: bold; background: transparent; border: 0px;")
            elif status == 'error':
                item['icon'].setText("❌")
                item['frame'].setStyleSheet("background-color: #fef2f2; border-radius: 8px; border: 1px solid #fecaca;")
                item['title'].setStyleSheet("color: #991b1b; font-size: 11px; font-weight: bold; background: transparent; border: 0px;")
                item['desc'].setStyleSheet("color: #ef4444; font-size: 10px; background: transparent; border: 0px;")
                item['status'].setText(message or "실패")
                item['status'].setStyleSheet("color: #dc2626; font-size: 10px; font-weight: bold; background: transparent; border: 0px;")
