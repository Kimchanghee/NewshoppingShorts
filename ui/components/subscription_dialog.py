"""
구독 다이얼로그 (PyQt6)
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame, QPushButton, QHBoxLayout
from ui.design_system_v2 import get_design_system, get_color


class SubscriptionDialog(QDialog):
    def __init__(self, parent=None, user_id=None, work_used=0, work_count=0):
        super().__init__(parent)
        self.ds = get_design_system()
        self.user_id = user_id
        self.work_used = work_used
        self.work_count = work_count

        self.setWindowTitle("구독 신청")
        self.setModal(True)
        self.setMinimumWidth(460)

        bg_main = get_color("background")
        card_bg = get_color("surface")
        border = get_color("border_light")

        # QDialog 기본 배경이 흰색(플랫폼 기본)이라 다크 토큰과 충돌하면
        # 텍스트가 거의 보이지 않습니다. 디자인 시스템 배경을 명시합니다.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"QDialog {{ background-color: {bg_main}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            self.ds.spacing.space_4,
            self.ds.spacing.space_4,
            self.ds.spacing.space_4,
            self.ds.spacing.space_4,
        )
        outer.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            f"""
            QFrame#card {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: {self.ds.radius.md}px;
            }}
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
        )
        layout.setSpacing(self.ds.spacing.space_4)

        base_style = f"""
            color: {get_color('text_primary')};
            font-size: {self.ds.typography.size_base}px;
            font-family: {self.ds.typography.font_family_primary};
        """

        title = QLabel("체험판 사용량 소진", self)
        title.setStyleSheet(f"""
            QLabel {{
                {base_style}
                font-size: {self.ds.typography.size_lg}px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(title)

        info = QLabel(
            f"사용: {work_used}회 / 총 {work_count}회\n\n"
            "체험판 무료 횟수를 모두 사용하셨습니다.\n"
            "프로 플랜을 구독하시면 무제한으로 이용할 수 있습니다.\n\n"
            "구독 관리 페이지에서 결제를 진행해주세요.\n\n"
            "이미 결제를 완료하셨다면:\n"
            "1) 구독 관리 페이지에서 상태를 새로고침하거나\n"
            "2) 앱을 재시작 후 다시 시도해주세요.",
            self
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"QLabel {{ {base_style} }}")
        layout.addWidget(info)

        # Actions
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        open_btn = QPushButton("구독 관리 열기", self)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {get_color('primary')};
                color: {get_color('text_on_primary')};
                border: none;
                border-radius: {self.ds.radius.sm}px;
                padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_5}px;
                font-weight: {self.ds.typography.weight_bold};
            }}
            QPushButton:hover {{
                background-color: {get_color('primary_hover')};
            }}
            """
        )
        open_btn.clicked.connect(self._open_subscription)
        btn_row.addWidget(open_btn)

        close_btn = QPushButton("닫기", self)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {get_color('surface_variant')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border_light')};
                border-radius: {self.ds.radius.sm}px;
                padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_5}px;
            }}
            QPushButton:hover {{
                background-color: {get_color('border')};
            }}
            """
        )
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        outer.addWidget(card)

    def _open_subscription(self):
        """Navigate to subscription panel if possible, then close."""
        try:
            p = self.parent()
            if p is not None:
                if hasattr(p, "_show_subscription_panel"):
                    p._show_subscription_panel()
                elif hasattr(p, "_on_step_selected"):
                    p._on_step_selected("subscription")
        finally:
            self.accept()
