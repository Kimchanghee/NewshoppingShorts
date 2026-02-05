# -*- coding: utf-8 -*-
"""
Login UI for Shopping Shorts Maker
쇼핑 숏폼 메이커 로그인 UI

모던 UI를 기본으로 사용합니다.
기존 호환성을 위해 Ui_LoginWindow 클래스 이름을 유지합니다.

설정 변경:
- USE_MODERN_UI = True: 새로운 모던 UI 사용 (기본값)
- USE_MODERN_UI = False: 기존 레거시 UI 사용
"""

# 모던 UI 사용 여부 설정
USE_MODERN_UI = True

if USE_MODERN_UI:
    # 모던 UI 사용 (STITCH 디자인 기반)
    from ui.login_ui_modern import ModernLoginUi as Ui_LoginWindow
else:
    # 기존 UI 사용 (레거시 호환)
    from PyQt6 import QtCore, QtGui, QtWidgets

    class Ui_LoginWindow(object):
        def setupUi(self, LoginWindow):
            LoginWindow.setObjectName("LoginWindow")
            LoginWindow.resize(700, 500)
            LoginWindow.setMinimumSize(QtCore.QSize(700, 500))
            LoginWindow.setMaximumSize(QtCore.QSize(700, 500))
            LoginWindow.setUnifiedTitleAndToolBarOnMac(False)

            self.centralwidget = QtWidgets.QWidget(LoginWindow)
            self.centralwidget.setObjectName("centralwidget")

            self.rightFrame = QtWidgets.QFrame(self.centralwidget)
            self.rightFrame.setGeometry(QtCore.QRect(300, 0, 400, 500))
            self.rightFrame.setStyleSheet("background-color: #ffffff;")
            self.rightFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
            self.rightFrame.setFrameShadow(QtWidgets.QFrame.Raised)
            self.rightFrame.setObjectName("rightFrame")

            self.minimumButton = QtWidgets.QPushButton(self.rightFrame)
            self.minimumButton.setGeometry(QtCore.QRect(330, 10, 20, 20))
            self.minimumButton.setStyleSheet("""
                QPushButton {
                    color: #ffffff;
                    background-color: #020202;
                    border: 0px;
                }
                QPushButton:hover {
                    background-color: #5E616A;
                }
            """)
            self.minimumButton.setText("")
            icon1 = QtGui.QIcon()
            icon1.addPixmap(QtGui.QPixmap("resource/Minimize_icon.png"), QtGui.QIcon.Normal, QtGui.QIcon.On)
            self.minimumButton.setIcon(icon1)
            self.minimumButton.setIconSize(QtCore.QSize(13, 13))
            self.minimumButton.setObjectName("minimumButton")

            self.exitButton = QtWidgets.QPushButton(self.rightFrame)
            self.exitButton.setGeometry(QtCore.QRect(360, 10, 20, 20))
            self.exitButton.setStyleSheet("""
                QPushButton {
                    color: #ffffff;
                    background-color: #020202;
                    border: 0px;
                }
                QPushButton:hover {
                    background-color: #5E616A;
                }
            """)
            self.exitButton.setText("")
            icon2 = QtGui.QIcon()
            icon2.addPixmap(QtGui.QPixmap("resource/Close_icon.png"), QtGui.QIcon.Normal, QtGui.QIcon.On)
            self.exitButton.setIcon(icon2)
            self.exitButton.setIconSize(QtCore.QSize(13, 13))
            self.exitButton.setObjectName("exitButton")

            self.label_id = QtWidgets.QLabel(self.rightFrame)
            self.label_id.setGeometry(QtCore.QRect(30, 207, 70, 25))
            self.label_id.setStyleSheet("color: #020202; border: 0px;")
            self.label_id.setObjectName("label_id")

            self.idFrame = QtWidgets.QFrame(self.rightFrame)
            self.idFrame.setGeometry(QtCore.QRect(100, 200, 250, 40))
            self.idFrame.setStyleSheet("""
                background-color: #ffffff;
                border: 1px solid #020202;
                border-radius: 3px;
            """)
            self.idFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
            self.idFrame.setFrameShadow(QtWidgets.QFrame.Raised)
            self.idFrame.setObjectName("idFrame")

            self.idEdit = QtWidgets.QLineEdit(self.idFrame)
            self.idEdit.setGeometry(QtCore.QRect(10, 10, 230, 20))
            self.idEdit.setCursor(QtGui.QCursor(QtCore.Qt.IBeamCursor))
            self.idEdit.setStyleSheet("background-color: #ffffff; color: #020202; border: 0px;")
            self.idEdit.setObjectName("idEdit")

            self.label_pw = QtWidgets.QLabel(self.rightFrame)
            self.label_pw.setGeometry(QtCore.QRect(30, 257, 70, 25))
            self.label_pw.setStyleSheet("color: #020202; border: 0px;")
            self.label_pw.setObjectName("label_pw")

            self.pwFrame = QtWidgets.QFrame(self.rightFrame)
            self.pwFrame.setGeometry(QtCore.QRect(100, 250, 250, 40))
            self.pwFrame.setStyleSheet("""
                background-color: #ffffff;
                border: 1px solid #020202;
                border-radius: 3px;
            """)
            self.pwFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
            self.pwFrame.setFrameShadow(QtWidgets.QFrame.Raised)
            self.pwFrame.setObjectName("pwFrame")

            self.pwEdit = QtWidgets.QLineEdit(self.pwFrame)
            self.pwEdit.setGeometry(QtCore.QRect(10, 10, 230, 20))
            self.pwEdit.setCursor(QtGui.QCursor(QtCore.Qt.IBeamCursor))
            self.pwEdit.setStyleSheet("background-color: #ffffff; color: #020202; border: 0px;")
            self.pwEdit.setEchoMode(QtWidgets.QLineEdit.Password)
            self.pwEdit.setObjectName("pwEdit")

            self.idpw_checkbox = QtWidgets.QCheckBox(self.rightFrame)
            self.idpw_checkbox.setGeometry(QtCore.QRect(200, 290, 150, 25))
            self.idpw_checkbox.setStyleSheet("QCheckBox { color: #020202; }")
            self.idpw_checkbox.setObjectName("idpw_checkbox")

            self.loginButton = QtWidgets.QPushButton(self.rightFrame)
            self.loginButton.setGeometry(QtCore.QRect(120, 340, 200, 35))
            self.loginButton.setStyleSheet("""
                QPushButton {
                    color: rgb(255,255,255);
                    background-color: #020202;
                    text-align: center;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background-color: #5E616A;
                }
            """)
            self.loginButton.setIconSize(QtCore.QSize(16, 16))
            self.loginButton.setObjectName("loginButton")

            self.remoteButton = QtWidgets.QPushButton(self.rightFrame)
            self.remoteButton.setGeometry(QtCore.QRect(120, 385, 200, 35))
            self.remoteButton.setStyleSheet("""
                QPushButton {
                    color: rgb(255,255,255);
                    background-color: #020202;
                    text-align: center;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background-color: #5E616A;
                }
            """)
            self.remoteButton.setIconSize(QtCore.QSize(50, 50))
            self.remoteButton.setObjectName("remoteButton")

            self.leftFrame = QtWidgets.QFrame(self.centralwidget)
            self.leftFrame.setGeometry(QtCore.QRect(0, 0, 300, 500))
            self.leftFrame.setStyleSheet("background-color: #FFFFFF;")
            self.leftFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
            self.leftFrame.setFrameShadow(QtWidgets.QFrame.Raised)
            self.leftFrame.setObjectName("leftFrame")

            self.logoFrame = QtWidgets.QFrame(self.leftFrame)
            self.logoFrame.setGeometry(QtCore.QRect(50, 150, 200, 200))
            self.logoFrame.setStyleSheet("""
                image: url(resource/main_logo.png);
                background-color: rgba(255, 255, 255, 0);
                border: 0px;
            """)
            self.logoFrame.setFrameShape(QtWidgets.QFrame.NoFrame)
            self.logoFrame.setFrameShadow(QtWidgets.QFrame.Raised)
            self.logoFrame.setObjectName("logoFrame")

            LoginWindow.setCentralWidget(self.centralwidget)
            self.retranslateUi(LoginWindow)
            QtCore.QMetaObject.connectSlotsByName(LoginWindow)

        def retranslateUi(self, LoginWindow):
            _translate = QtCore.QCoreApplication.translate
            LoginWindow.setWindowTitle(_translate("LoginWindow", "Login"))
            self.idpw_checkbox.setText(_translate("LoginWindow", "ID/PW 저장"))
            self.loginButton.setText(_translate("LoginWindow", "로그인"))
            self.remoteButton.setText(_translate("LoginWindow", "원격지원"))
            self.label_id.setText(_translate("LoginWindow", "아이디"))
            self.label_pw.setText(_translate("LoginWindow", "비밀번호"))
