"""
Modern Subscription Panel - SaaS-style pricing page design

Features:
- Card-based modern layout
- Current plan display with usage progress
- Feature list with checkmarks
- Modern payment form
- Responsive design using design_system_v2 tokens
"""

import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox, QFrame, QProgressBar,
    QSpacerItem, QSizePolicy, QTextEdit, QLineEdit,
    QGridLayout, QStackedWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

import config
from utils.logging_config import get_logger
from utils.payment_client import PaymentClient
from ui.design_system_v2 import get_design_system, get_color, ds

logger = get_logger(__name__)

# Plan definitions with features
PLANS = {
    "trial": {
        "id": "trial",
        "name": "무료계정",
        "price": 0,
        "price_text": "무료",
        "period": "",
        "description": "기본 기능을 무료로 체험하세요",
        "features": [
            "월 2개 영상 생성",
            "기본 음성 합성",
            "기본 자막 스타일",
            "720p 해상도",
        ],
        "not_included": [
            "무제한 영상 생성",
            "고급 음성 프로필",
            "우선 처리",
        ],
        "color": "#9A9A9A",
        "popular": False,
    },
    "pro": {
        "id": "pro",
        "name": "프로 (유료계정)",
        "price": 190000,
        "price_text": "190,000",
        "period": "월",
        "description": "무제한 영상 생성 + 모든 기능 해제",
        "features": [
            "무제한 영상 생성",
            "모든 음성 프로필 사용",
            "AI 콘텐츠 분석",
            "커스텀 자막 스타일",
            "1080p 해상도",
            "우선 처리",
        ],
        "not_included": [],
        "color": "#E31639",
        "popular": True,
    },
}


class PlanCard(QFrame):
    """Modern plan card component"""
    
    def __init__(self, plan_data, parent=None, on_select=None):
        super().__init__(parent)
        self.plan_data = plan_data
        self.on_select = on_select
        self.ds = get_design_system()
        self._build_ui()
        
    def _build_ui(self):
        # Card styling
        self.setObjectName("plan_card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            ds.spacing.space_5,
            ds.spacing.space_5, 
            ds.spacing.space_5,
            ds.spacing.space_5
        )
        layout.setSpacing(ds.spacing.space_4)
        
        # Popular badge
        if self.plan_data.get("popular"):
            self.badge = QLabel("가장 인기있는")
            self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.badge.setObjectName("popular_badge")
            layout.addWidget(self.badge)
        elif self.plan_data.get("badge"):
            self.badge = QLabel(self.plan_data["badge"])
            self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.badge.setObjectName("plan_badge")
            layout.addWidget(self.badge)
        else:
            layout.addSpacing(ds.spacing.space_6)
        
        # Plan name
        self.name_label = QLabel(self.plan_data["name"])
        self.name_label.setObjectName("plan_name")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        
        # Price section
        price_layout = QHBoxLayout()
        price_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.price_label = QLabel(self.plan_data["price_text"])
        self.price_label.setObjectName("plan_price")
        price_layout.addWidget(self.price_label)
        
        if self.plan_data["price"] > 0:
            self.currency_label = QLabel("원")
            self.currency_label.setObjectName("plan_currency")
            price_layout.addWidget(self.currency_label)
            
            self.period_label = QLabel(f"/{self.plan_data['period']}")
            self.period_label.setObjectName("plan_period")
            price_layout.addWidget(self.period_label)
        
        layout.addLayout(price_layout)
        
        # Description
        self.desc_label = QLabel(self.plan_data["description"])
        self.desc_label.setObjectName("plan_description")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)
        
        # Separator
        layout.addSpacing(ds.spacing.space_2)
        
        # Features list
        features_container = QWidget()
        features_layout = QVBoxLayout(features_container)
        features_layout.setContentsMargins(0, 0, 0, 0)
        features_layout.setSpacing(ds.spacing.space_3)
        
        # Included features
        for feature in self.plan_data["features"]:
            feature_row = self._create_feature_row(feature, included=True)
            features_layout.addWidget(feature_row)
        
        # Not included features (grayed out)
        for feature in self.plan_data.get("not_included", []):
            feature_row = self._create_feature_row(feature, included=False)
            features_layout.addWidget(feature_row)
        
        layout.addWidget(features_container)
        layout.addStretch()
        
        # Select button
        self.select_btn = QPushButton("선택하기")
        self.select_btn.setObjectName("select_button")
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(self._on_select)
        layout.addWidget(self.select_btn)
        
        self._apply_styles()
        
    def _create_feature_row(self, text, included=True):
        """Create a feature row with checkmark or x mark"""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.spacing.space_3)
        
        # Icon
        if included:
            icon = QLabel("✓")
            icon.setObjectName("feature_check")
        else:
            icon = QLabel("✕")
            icon.setObjectName("feature_x")
        icon.setFixedWidth(ds.spacing.space_5)
        layout.addWidget(icon)
        
        # Text
        label = QLabel(text)
        if included:
            label.setObjectName("feature_text")
        else:
            label.setObjectName("feature_text_disabled")
        label.setWordWrap(True)
        layout.addWidget(label, 1)
        
        return row
    
    def _on_select(self):
        if self.on_select:
            self.on_select(self.plan_data)
    
    def _apply_styles(self):
        is_popular = self.plan_data.get("popular", False)
        primary_color = self.plan_data.get("color", ds.colors.primary)
        
        # Card base style
        self.setStyleSheet(f"""
            #plan_card {{
                background-color: {ds.colors.surface};
                border: 2px solid {primary_color if is_popular else ds.colors.border};
                border-radius: {ds.radius.lg}px;
            }}
            #plan_card:hover {{
                border-color: {primary_color};
            }}
            
            #popular_badge {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #E31639, stop:1 #FF4D6A);
                color: white;
                padding: {ds.spacing.space_1}px {ds.spacing.space_3}px;
                border-radius: {ds.radius.full}px;
                font-size: {ds.typography.size_xs}px;
                font-weight: {ds.typography.weight_bold};
            }}
            
            #plan_badge {{
                background-color: {ds.colors.surface_variant};
                color: {ds.colors.text_secondary};
                padding: {ds.spacing.space_1}px {ds.spacing.space_3}px;
                border-radius: {ds.radius.full}px;
                font-size: {ds.typography.size_xs}px;
                font-weight: {ds.typography.weight_medium};
            }}
            
            #plan_name {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_xl}px;
                font-weight: {ds.typography.weight_bold};
            }}
            
            #plan_price {{
                color: {primary_color};
                font-size: {ds.typography.size_2xl}px;
                font-weight: {ds.typography.weight_extrabold};
            }}
            
            #plan_currency, #plan_period {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_lg}px;
                font-weight: {ds.typography.weight_medium};
            }}
            
            #plan_description {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
            }}
            
            #feature_check {{
                color: {ds.colors.success};
                font-size: {ds.typography.size_md}px;
                font-weight: {ds.typography.weight_bold};
            }}
            
            #feature_x {{
                color: {ds.colors.text_muted};
                font-size: {ds.typography.size_md}px;
            }}
            
            #feature_text {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_sm}px;
            }}
            
            #feature_text_disabled {{
                color: {ds.colors.text_muted};
                font-size: {ds.typography.size_sm}px;
                text-decoration: line-through;
            }}
            
            #select_button {{
                background: {'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E31639, stop:1 #FF4D6A)' if is_popular else ds.colors.surface_variant};
                color: {'white' if is_popular else ds.colors.text_primary};
                border: none;
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_3}px {ds.spacing.space_5}px;
                font-size: {ds.typography.size_base}px;
                font-weight: {ds.typography.weight_semibold};
                min-height: {ds.button_sizes['md'].height}px;
            }}
            
            #select_button:hover {{
                background: {'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #C41230, stop:1 #E63D5A)' if is_popular else ds.colors.border};
            }}
            
            #select_button:pressed {{
                background: {'#A01028' if is_popular else ds.colors.text_muted};
            }}
        """)


class CurrentPlanCard(QFrame):
    """Current plan status card with usage indicator"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ds = get_design_system()
        self.current_plan = "trial"  # Default
        self.usage_used = 0
        self.usage_total = 3
        self._build_ui()
        
    def _build_ui(self):
        self.setObjectName("current_plan_card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            ds.spacing.space_6,
            ds.spacing.space_6,
            ds.spacing.space_6,
            ds.spacing.space_6
        )
        layout.setSpacing(ds.spacing.space_4)
        
        # Header with plan name
        header_layout = QHBoxLayout()
        
        self.plan_label = QLabel("현재 플랜")
        self.plan_label.setObjectName("current_plan_label")
        header_layout.addWidget(self.plan_label)
        
        header_layout.addStretch()
        
        self.status_badge = QLabel("무료계정")
        self.status_badge.setObjectName("status_badge")
        header_layout.addWidget(self.status_badge)

        layout.addLayout(header_layout)

        # Plan name (large)
        self.plan_name = QLabel("무료계정")
        self.plan_name.setObjectName("current_plan_name")
        layout.addWidget(self.plan_name)
        
        # Usage section
        usage_header = QHBoxLayout()
        
        self.usage_label = QLabel("사용량")
        self.usage_label.setObjectName("usage_label")
        usage_header.addWidget(self.usage_label)
        
        usage_header.addStretch()
        
        self.usage_text = QLabel("0 / 3")
        self.usage_text.setObjectName("usage_text")
        usage_header.addWidget(self.usage_text)
        
        layout.addLayout(usage_header)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("usage_progress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(self.usage_total)
        self.progress_bar.setValue(self.usage_used)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)
        
        # Usage hint
        self.usage_hint = QLabel("이번 달 남은 영상 생성 횟수: 3회")
        self.usage_hint.setObjectName("usage_hint")
        layout.addWidget(self.usage_hint)
        
        layout.addSpacing(ds.spacing.space_4)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(ds.spacing.space_3)
        
        self.upgrade_btn = QPushButton("구독 신청")
        self.upgrade_btn.setObjectName("upgrade_button")
        self.upgrade_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons_layout.addWidget(self.upgrade_btn)
        
        self.contact_btn = QPushButton("문의하기")
        self.contact_btn.setObjectName("contact_button")
        self.contact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons_layout.addWidget(self.contact_btn)
        
        layout.addLayout(buttons_layout)
        
        self._apply_styles()
        
    def update_plan(self, plan_id: str, used: int = 0, total: int = 3):
        """Update current plan display"""
        self.current_plan = plan_id
        self.usage_used = used
        self.usage_total = total

        plan_data = PLANS.get(plan_id, PLANS["trial"])

        self.status_badge.setText(plan_data["name"])
        self.plan_name.setText(plan_data["name"])

        is_unlimited = (total < 0) or (plan_id == "pro")
        if is_unlimited:
            self.usage_text.setText("무제한")
            self.progress_bar.setMaximum(1)
            self.progress_bar.setValue(1)
            self.usage_hint.setText("무제한 영상 생성 가능")
        else:
            self.usage_text.setText(f"{used} / {total}")
            self.progress_bar.setMaximum(max(total, 1))
            self.progress_bar.setValue(used)
            remaining = max(total - used, 0)
            self.usage_hint.setText(f"이번 달 남은 영상 생성 횟수: {remaining}회")
        
        # Update badge color
        if plan_id == "trial":
            self.status_badge.setStyleSheet(f"""
                #status_badge {{
                    background-color: {ds.colors.surface_variant};
                    color: {ds.colors.text_secondary};
                    padding: {ds.spacing.space_1}px {ds.spacing.space_3}px;
                    border-radius: {ds.radius.full}px;
                    font-size: {ds.typography.size_xs}px;
                    font-weight: {ds.typography.weight_medium};
                }}
            """)
        else:
            self.status_badge.setStyleSheet(f"""
                #status_badge {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #E31639, stop:1 #FF4D6A);
                    color: white;
                    padding: {ds.spacing.space_1}px {ds.spacing.space_3}px;
                    border-radius: {ds.radius.full}px;
                    font-size: {ds.typography.size_xs}px;
                    font-weight: {ds.typography.weight_bold};
                }}
            """)
    
    def _apply_styles(self):
        self.setStyleSheet(f"""
            #current_plan_card {{
                background-color: {ds.colors.surface};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.lg}px;
            }}
            
            #current_plan_label {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_medium};
            }}
            
            #current_plan_name {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_2xl}px;
                font-weight: {ds.typography.weight_bold};
            }}
            
            #usage_label {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
            }}
            
            #usage_text {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_semibold};
            }}
            
            #usage_progress {{
                border: none;
                border-radius: {ds.radius.full}px;
                background-color: {ds.colors.surface_variant};
            }}
            
            #usage_progress::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #E31639, stop:1 #FF4D6A);
                border-radius: {ds.radius.full}px;
            }}
            
            #usage_hint {{
                color: {ds.colors.text_muted};
                font-size: {ds.typography.size_xs}px;
            }}
            
            #upgrade_button {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #E31639, stop:1 #FF4D6A);
                color: white;
                border: none;
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_3}px {ds.spacing.space_5}px;
                font-size: {ds.typography.size_base}px;
                font-weight: {ds.typography.weight_semibold};
                min-height: {ds.button_sizes['lg'].height}px;
            }}
            
            #upgrade_button:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #C41230, stop:1 #E63D5A);
            }}
            
            #contact_button {{
                background-color: {ds.colors.surface_variant};
                color: {ds.colors.text_primary};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_3}px {ds.spacing.space_5}px;
                font-size: {ds.typography.size_base}px;
                font-weight: {ds.typography.weight_medium};
                min-height: {ds.button_sizes['lg'].height}px;
            }}
            
            #contact_button:hover {{
                background-color: {ds.colors.border};
                border-color: {ds.colors.text_muted};
            }}
        """)


class PaymentForm(QWidget):
    """Modern payment form"""
    
    def __init__(self, parent=None, on_submit=None, on_cancel=None):
        super().__init__(parent)
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        self.ds = get_design_system()
        self._build_ui()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.spacing.space_5)

        # Title
        title = QLabel("결제 정보")
        title.setObjectName("form_title")
        layout.addWidget(title)

        # Form fields container
        form_container = QFrame()
        form_container.setObjectName("form_container")
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(
            ds.spacing.space_5,
            ds.spacing.space_5,
            ds.spacing.space_5,
            ds.spacing.space_5
        )
        form_layout.setSpacing(ds.spacing.space_4)

        # Selected plan display
        plan_row = QHBoxLayout()
        plan_label = QLabel("선택한 플랜")
        plan_label.setObjectName("field_label")
        plan_row.addWidget(plan_label)

        self.selected_plan_label = QLabel("-")
        self.selected_plan_label.setObjectName("selected_plan_value")
        plan_row.addWidget(self.selected_plan_label)

        form_layout.addLayout(plan_row)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("form_separator")
        form_layout.addWidget(separator)

        # Phone number input (PayApp 필수)
        phone_label = QLabel("전화번호 (가상계좌 안내 수신용)")
        phone_label.setObjectName("field_label")
        form_layout.addWidget(phone_label)

        self.phone_input = QLineEdit()
        self.phone_input.setObjectName("phone_input")
        self.phone_input.setPlaceholderText("010-0000-0000")
        self.phone_input.setMaxLength(13)
        form_layout.addWidget(self.phone_input)

        # Status info
        info_label = QLabel(
            "가상계좌가 발급되며, 입금 완료 시 자동으로 구독이 활성화됩니다."
        )
        info_label.setObjectName("info_label")
        info_label.setWordWrap(True)
        form_layout.addWidget(info_label)

        # Status
        self.status_label = QLabel("결제 대기 중")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(self.status_label)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(ds.spacing.space_3)

        self.pay_btn = QPushButton("결제 진행하기")
        self.pay_btn.setObjectName("pay_button")
        self.pay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pay_btn.clicked.connect(self._on_submit)
        buttons_layout.addWidget(self.pay_btn)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setObjectName("cancel_button")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_cancel)
        buttons_layout.addWidget(self.cancel_btn)

        form_layout.addLayout(buttons_layout)

        layout.addWidget(form_container)
        layout.addStretch()

        self._apply_styles()
        
    def set_plan(self, plan_data: dict):
        """Set the selected plan"""
        price_text = f"{plan_data['price_text']}원"
        if plan_data['price'] > 0:
            price_text += f"/{plan_data['period']}"
        self.selected_plan_label.setText(f"{plan_data['name']} - {price_text}")
        
    def set_status(self, status: str):
        """Update status text"""
        self.status_label.setText(status)
        
    def _on_submit(self):
        if self.on_submit:
            self.on_submit()
            
    def _on_cancel(self):
        if self.on_cancel:
            self.on_cancel()
    
    def _apply_styles(self):
        self.setStyleSheet(f"""
            #form_title {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_xl}px;
                font-weight: {ds.typography.weight_bold};
            }}
            
            #form_container {{
                background-color: {ds.colors.surface};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.lg}px;
            }}
            
            #field_label {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
            }}
            
            #selected_plan_value {{
                color: {ds.colors.primary};
                font-size: {ds.typography.size_base}px;
                font-weight: {ds.typography.weight_semibold};
            }}
            
            #form_separator {{
                color: {ds.colors.border};
            }}
            
            #info_label {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
            }}
            
            #status_label {{
                color: {ds.colors.text_muted};
                font-size: {ds.typography.size_sm}px;
                padding: {ds.spacing.space_3}px;
                background-color: {ds.colors.surface_variant};
                border-radius: {ds.radius.md}px;
            }}
            
            #pay_button {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #E31639, stop:1 #FF4D6A);
                color: white;
                border: none;
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_3}px {ds.spacing.space_5}px;
                font-size: {ds.typography.size_base}px;
                font-weight: {ds.typography.weight_semibold};
                min-height: {ds.button_sizes['md'].height}px;
            }}
            
            #pay_button:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #C41230, stop:1 #E63D5A);
            }}
            
            #cancel_button {{
                background-color: {ds.colors.surface_variant};
                color: {ds.colors.text_primary};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_3}px {ds.spacing.space_5}px;
                font-size: {ds.typography.size_base}px;
                font-weight: {ds.typography.weight_medium};
                min-height: {ds.button_sizes['md'].height}px;
            }}
            
            #cancel_button:hover {{
                background-color: {ds.colors.border};
            }}

            #phone_input {{
                background-color: {ds.colors.surface_variant};
                color: {ds.colors.text_primary};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_3}px {ds.spacing.space_4}px;
                font-size: {ds.typography.size_base}px;
            }}
            #phone_input:focus {{
                border-color: {ds.colors.primary};
            }}
        """)


class SubscriptionPanel(QWidget):
    """
    Modern Subscription Panel with SaaS-style pricing page
    
    Features:
    - Card-based plan selection
    - Current plan status with usage
    - Modern payment form
    - Real-time payment status polling
    """
    
    def __init__(self, parent=None, gui=None):
        super().__init__(parent)
        self.gui = gui
        self.payment = PaymentClient()
        self.current_payment_id: str | None = None
        self.poll_tries = 0
        self._polling = False  # 중복 폴링 방지 플래그
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_status)
        self.selected_plan = None
        self.ds = get_design_system()
        
        self._build_ui()
        
    def _build_ui(self):
        # Scroll area: keep the main window size stable and allow tall content to be reachable.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = self.scroll_area = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(
            ds.spacing.space_6,
            ds.spacing.space_6,
            ds.spacing.space_6,
            ds.spacing.space_6
        )
        main_layout.setSpacing(ds.spacing.space_6)
        
        # Page title
        title = QLabel("구독 관리")
        title.setObjectName("page_title")
        main_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("쇼핑 숏츠 메이커의 모든 기능을 해제하세요")
        subtitle.setObjectName("page_subtitle")
        main_layout.addWidget(subtitle)
        
        main_layout.addSpacing(ds.spacing.space_4)
        
        # Content container
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(ds.spacing.space_6)
        
        # Left side: Current plan + Plans
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(ds.spacing.space_6)
        
        # Current plan card
        self.current_plan_card = CurrentPlanCard()
        self.current_plan_card.upgrade_btn.clicked.connect(self._show_plans)
        self.current_plan_card.contact_btn.clicked.connect(self._contact_support)
        left_layout.addWidget(self.current_plan_card)
        
        # Plans section (hidden by default, shown when upgrade clicked)
        self.plans_container = QWidget()
        plans_layout = QVBoxLayout(self.plans_container)
        plans_layout.setContentsMargins(0, 0, 0, 0)
        plans_layout.setSpacing(ds.spacing.space_4)
        
        plans_title = QLabel("플랜 선택")
        plans_title.setObjectName("section_title")
        plans_layout.addWidget(plans_title)
        
        # Plan cards row
        plans_row = QHBoxLayout()
        plans_row.setSpacing(ds.spacing.space_4)
        
        # Create plan cards
        self.plan_cards = []
        for plan_id, plan_data in PLANS.items():
            if plan_id != "trial":  # Don't show trial in selection
                card = PlanCard(plan_data, on_select=self._on_plan_selected)
                self.plan_cards.append(card)
                plans_row.addWidget(card)
        
        plans_layout.addLayout(plans_row)
        self.plans_container.hide()
        left_layout.addWidget(self.plans_container)
        
        left_layout.addStretch()
        content_layout.addWidget(left_panel, 2)
        
        # Right side: Payment form
        self.payment_form = PaymentForm(
            on_submit=self._checkout,
            on_cancel=self._cancel_payment
        )
        self.payment_form.hide()
        content_layout.addWidget(self.payment_form, 1)
        
        main_layout.addWidget(content)

        scroll.setWidget(page)
        outer_layout.addWidget(scroll)
        
        self._apply_styles()
        
    def _apply_styles(self):
        self.setStyleSheet(f"""
            #page_title {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_3xl}px;
                font-weight: {ds.typography.weight_bold};
            }}
            
            #page_subtitle {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_md}px;
            }}
            
            #section_title {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_lg}px;
                font-weight: {ds.typography.weight_semibold};
            }}
        """)
        
    def _show_plans(self):
        """Show plan selection"""
        self.plans_container.show()
        self.payment_form.hide()
        # Ensure the newly revealed section is reachable without resizing the window.
        QTimer.singleShot(
            0,
            lambda: getattr(self, "scroll_area", None)
            and self.scroll_area.ensureWidgetVisible(self.plans_container, 0, ds.spacing.space_6),
        )
        
    def _on_plan_selected(self, plan_data: dict):
        """Handle plan selection"""
        self.selected_plan = plan_data
        self.payment_form.set_plan(plan_data)
        self.payment_form.show()
        
    def _contact_support(self):
        """Open support contact"""
        webbrowser.open("mailto:support@shoppingmaker.com")
        
    def _checkout(self):
        """Start PayApp checkout process"""
        if not self.selected_plan:
            QMessageBox.warning(self, "알림", "플랜을 먼저 선택해주세요.")
            return

        # Get phone number from form and validate Korean mobile format
        import re as _re
        phone = self.payment_form.phone_input.text().strip()
        phone_digits = _re.sub(r'[^0-9]', '', phone)
        if not phone_digits or len(phone_digits) < 10 or len(phone_digits) > 11:
            QMessageBox.warning(self, "알림", "전화번호를 정확히 입력해주세요.")
            return
        if not _re.match(r'^01[016789]\d{7,8}$', phone_digits):
            QMessageBox.warning(self, "알림", "올바른 휴대폰 번호를 입력해주세요.\n(예: 010-1234-5678)")
            return

        # Extract user_id from login_data
        user_id = self._extract_user_id()

        if not user_id:
            QMessageBox.warning(self, "알림", "로그인 정보를 찾을 수 없습니다.")
            return

        try:
            data = self.payment.create_payapp_checkout(user_id, phone)
            self.current_payment_id = data.get("payment_id", "")
            payurl = data.get("payurl", "")

            self.payment_form.set_status("결제 페이지를 여는 중...")
            if payurl:
                webbrowser.open(payurl)
            self._start_poll()
        except Exception as e:
            logger.error(f"[Subscription] PayApp checkout failed: {e}")
            QMessageBox.critical(self, "오류", "결제 요청에 실패했습니다.\n잠시 후 다시 시도해주세요.")
            self.payment_form.set_status("결제 요청 오류")
            
    def _cancel_payment(self):
        """Cancel payment and hide form"""
        self._stop_poll()
        self.payment_form.hide()
        self.selected_plan = None
        
    def _start_poll(self):
        """Start payment status polling"""
        self.poll_tries = 0
        interval_ms = int(config.CHECKOUT_POLL_INTERVAL * 1000)
        self.timer.start(interval_ms)
        self.payment_form.set_status("결제 상태 확인 중...")
        
    def _stop_poll(self):
        """Stop payment status polling"""
        self.timer.stop()
        
    def _poll_status(self):
        """Poll payment status (비동기 - UI 프리즈 방지)"""
        if not self.current_payment_id:
            self._stop_poll()
            return

        if self._polling:
            return  # 이전 요청이 진행 중이면 스킵

        if self.poll_tries >= config.CHECKOUT_POLL_MAX_TRIES:
            self._stop_poll()
            QMessageBox.information(
                self, "타임아웃",
                "결제 확인 시간이 초과되었습니다.\n"
                "입금을 완료하셨다면 잠시 후 앱을 재시작하면 구독이 자동으로 반영됩니다.\n"
                "문제가 지속되면 고객센터에 문의해주세요."
            )
            self.payment_form.set_status("시간 초과")
            return

        self.poll_tries += 1
        self._polling = True

        import threading
        payment_id = self.current_payment_id

        def _do_poll():
            try:
                data = self.payment.get_status(payment_id)
                status = data.get("status", "pending")
                # UI 콜백 (메인 스레드)
                cb_signal = getattr(self.gui, 'ui_callback_signal', None) if self.gui else None
                if cb_signal is not None:
                    cb_signal.emit(lambda: self._handle_poll_result(status))
                else:
                    QTimer.singleShot(0, lambda: self._handle_poll_result(status))
            except Exception as e:
                logger.error(f"[Subscription] status poll failed: {e}")
                cb_signal = getattr(self.gui, 'ui_callback_signal', None) if self.gui else None
                if cb_signal is not None:
                    cb_signal.emit(lambda: self._handle_poll_error())
                else:
                    QTimer.singleShot(0, self._handle_poll_error)
            finally:
                self._polling = False

        threading.Thread(target=_do_poll, daemon=True).start()

    def _handle_poll_result(self, status: str):
        """폴링 결과 처리 (메인 스레드에서 호출)"""
        status_text = f"상태: {status}"
        self.payment_form.set_status(status_text)

        if status in ("paid", "success", "succeeded"):
            self._stop_poll()
            QMessageBox.information(self, "완료", "결제가 완료되었습니다! 구독이 활성화됩니다.")
            self.payment_form.hide()
            self.plans_container.hide()
            self._verify_subscription_server()
        elif status in ("failed", "canceled", "cancelled"):
            self._stop_poll()
            QMessageBox.warning(self, "실패", "결제가 실패/취소되었습니다.")
            self.payment_form.set_status("결제 실패/취소")

    def _handle_poll_error(self):
        """폴링 오류 처리 (메인 스레드에서 호출)"""
        self.payment_form.set_status("상태 조회 오류")

    def _extract_user_id(self):
        """login_data에서 user_id를 안전하게 추출"""
        if not self.gui or not getattr(self.gui, "login_data", None):
            return None
        data_part = self.gui.login_data.get("data", {})
        if isinstance(data_part, dict):
            inner = data_part.get("data", {})
            user_id = inner.get("id")
            if user_id:
                return user_id
        return self.gui.login_data.get("userId")

    def _verify_subscription_server(self):
        """결제 완료 후 서버에서 구독 상태를 재확인하여 UI 업데이트"""
        try:
            user_id = self._extract_user_id()
            if not user_id:
                # 서버 확인 불가 시 일단 pro로 표시
                self.current_plan_card.update_plan("pro", used=0, total=999)
                return
            from caller import rest
            status = rest.getSubscriptionStatus(user_id)
            if status.get("success", True):
                work_count = status.get("work_count", -1)
                work_used = status.get("work_used", 0)
                is_pro = (work_count == -1) or status.get("user_type") == "subscriber"
                if is_pro:
                    self.current_plan_card.update_plan("pro", used=work_used, total=999)
                else:
                    remaining = max(work_count - work_used, 0)
                    self.current_plan_card.update_plan("trial", used=work_used, total=work_count)
                logger.info(f"[Subscription] Server verification complete: pro={is_pro}")
            else:
                # 서버 확인 실패 시 일단 pro로 표시
                self.current_plan_card.update_plan("pro", used=0, total=999)
        except Exception as e:
            logger.error(f"[Subscription] Server verification failed: {e}")
            self.current_plan_card.update_plan("pro", used=0, total=999)

    def update_usage(self, used: int, total: int, plan_id: str = "trial"):
        """Update current usage display"""
        self.current_plan_card.update_plan(plan_id, used, total)
