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
from datetime import datetime, timezone
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QFrame, QProgressBar,
    QSpacerItem, QSizePolicy, QTextEdit, QLineEdit,
    QStackedWidget, QScrollArea,
    QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer

import config
from utils.logging_config import get_logger
from utils.payment_client import PaymentClient
from ui.design_system_v2 import get_design_system, get_color, ds

logger = get_logger(__name__)

PAYMENT_INFO_VBANK_TEXT = "가상계좌 발급 후 입금 시 자동 활성화."
PAYMENT_INFO_CARD_TEXT = "카드번호는 새 창 결제 페이지에서 입력하세요."

# Plan definitions with features
def format_price_korean(amount: int) -> str:
    """
    Format price in Korean style with 만원 units
    Examples:
        190000 -> "19만원"
        161500 -> "161,500원"
        133000 -> "133,000원"
        50000 -> "5만원"
    """
    if amount == 0:
        return "무료"

    if amount >= 10000:
        # If clean 만원 unit (no remainder), use 만원
        if amount % 10000 == 0:
            man = amount // 10000
            return f"{man}만원"
        # Otherwise use full number with comma separator
        return f"{amount:,}원"
    else:
        # For amounts less than 10,000
        return f"{amount:,}원"


def parse_utc_datetime(value):
    """Parse an ISO datetime to timezone-aware UTC datetime."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(value, datetime):
            dt = value
        else:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


PLANS = {
    "trial": {
        "id": "trial",
        "name": "무료계정",
        "price": 0,
        "price_text": "무료",
        "period": "",
        "months": 0,
        "description": "기본 기능을 무료로 체험하세요",
        "features": [
            "총 2개 영상 생성",
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
    "pro_1month": {
        "id": "pro_1month",
        "name": "프로 1개월",
        "price": 190000,
        "price_text": format_price_korean(190000),
        "period": "월",
        "months": 1,
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
        "popular": False,
        "badge": "정기 결제",
    },
    "pro_6months": {
        "id": "pro_6months",
        "price": 969000,
        "name": "프로 6개월",
        "price_text": format_price_korean(161500),  # Show per-month price
        "price_per_month": 161500,
        "original_price_per_month": 190000,
        "original_price": 1140000,
        "discount_percent": 15,
        "period": "6개월",
        "months": 6,
        "description": "15% 할인 혜택",
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
        "badge": "인기",
    },
    "pro_12months": {
        "id": "pro_12months",
        "name": "프로 12개월",
        "price": 1596000,
        "price_text": format_price_korean(133000),  # Show per-month price
        "price_per_month": 133000,
        "original_price_per_month": 190000,
        "original_price": 2280000,
        "discount_percent": 30,
        "period": "12개월",
        "months": 12,
        "description": "30% 할인 혜택",
        "features": [
            "무제한 영상 생성",
            "모든 음성 프로필 사용",
            "AI 콘텐츠 분석",
            "커스텀 자막 스타일",
            "1080p 해상도",
            "우선 처리",
            "최대 절약 플랜!",
        ],
        "not_included": [],
        "color": "#E31639",
        "popular": False,
        "badge": "최고 할인",
    },
}

# Legacy support: map "pro" to "pro_1month"
PLANS["pro"] = PLANS["pro_1month"]


class PlanCard(QFrame):
    """Modern plan card component"""
    
    def __init__(self, plan_data, parent=None, on_select=None):
        super().__init__(parent)
        self.plan_data = plan_data
        self.on_select = on_select
        self.ds = get_design_system()
        self._selected = False
        self._build_ui()
        
    def _build_ui(self):
        # Card styling
        self.setObjectName("plan_card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            ds.spacing.space_3,
            ds.spacing.space_3,
            ds.spacing.space_3,
            ds.spacing.space_3
        )
        layout.setSpacing(ds.spacing.space_2)
        
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
        price_container = QWidget()
        price_layout = QVBoxLayout(price_container)
        price_layout.setContentsMargins(0, 0, 0, 0)
        price_layout.setSpacing(ds.spacing.space_1)
        price_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Original price (strikethrough) if discount exists
        original_price_text = self._get_original_price_text()
        if original_price_text:
            original_row = QHBoxLayout()
            original_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

            original_price = QLabel(original_price_text)
            original_price.setObjectName("plan_price_original")
            original_row.addWidget(original_price)

            if self.plan_data.get("discount_percent"):
                discount_badge = QLabel(f"-{self.plan_data.get('discount_percent', 0)}%")
                discount_badge.setObjectName("discount_badge")
                original_row.addWidget(discount_badge)

            price_layout.addLayout(original_row)

        # Current price with "월" prefix
        current_price_row = QHBoxLayout()
        current_price_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Show "월" prefix
        if self.plan_data["price"] > 0:
            self.month_prefix = QLabel("월")
            self.month_prefix.setObjectName("plan_month_prefix")
            current_price_row.addWidget(self.month_prefix)

        self.price_label = QLabel(self.plan_data["price_text"])
        self.price_label.setObjectName("plan_price")
        current_price_row.addWidget(self.price_label)

        price_layout.addLayout(current_price_row)

        layout.addWidget(price_container)
        
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

    def _get_original_price_text(self) -> str:
        """Return strike-through price text for comparison."""
        original_per_month = self.plan_data.get("original_price_per_month")
        if original_per_month:
            return f"월 {format_price_korean(original_per_month)}"

        original_total = self.plan_data.get("original_price")
        if original_total:
            return f"{original_total:,}원"

        return ""
    
    def _on_select(self):
        if self.on_select:
            self.on_select(self.plan_data)

    def set_selected(self, selected: bool):
        """Update selected visual state."""
        self._selected = bool(selected)
        if hasattr(self, "select_btn"):
            self.select_btn.setText("선택됨" if self._selected else "선택하기")
        self._apply_styles()

    def mousePressEvent(self, event):
        """Allow selecting plan by clicking anywhere on the card."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_select()
        super().mousePressEvent(event)
    
    def _apply_styles(self):
        is_popular = self.plan_data.get("popular", False)
        primary_color = self.plan_data.get("color", ds.colors.primary)
        selected = self._selected
        
        # Card base style
        self.setStyleSheet(f"""
            #plan_card {{
                background-color: {ds.colors.surface};
                border: 2px solid {
                    primary_color if (selected or is_popular) else ds.colors.border
                };
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
                font-size: {ds.typography.size_lg}px;
                font-weight: {ds.typography.weight_bold};
            }}

            #plan_month_prefix {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_md}px;
                font-weight: {ds.typography.weight_semibold};
                margin-right: {ds.spacing.space_1}px;
            }}

            #plan_price {{
                color: {primary_color};
                font-size: {ds.typography.size_2xl}px;
                font-weight: {ds.typography.weight_extrabold};
            }}

            #plan_price_original {{
                color: {ds.colors.text_muted};
                font-size: {ds.typography.size_sm}px;
                text-decoration: line-through;
            }}

            #discount_badge {{
                background-color: #FEE2E2;
                color: #DC2626;
                padding: {ds.spacing.space_1}px {ds.spacing.space_2}px;
                border-radius: {ds.radius.sm}px;
                font-size: {ds.typography.size_xs}px;
                font-weight: {ds.typography.weight_bold};
                margin-left: {ds.spacing.space_2}px;
            }}
            
            #plan_description {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_xs}px;
            }}

            #feature_check {{
                color: {ds.colors.success};
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_bold};
            }}

            #feature_x {{
                color: {ds.colors.text_muted};
                font-size: {ds.typography.size_sm}px;
            }}

            #feature_text {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_xs}px;
            }}

            #feature_text_disabled {{
                color: {ds.colors.text_muted};
                font-size: {ds.typography.size_xs}px;
                text-decoration: line-through;
            }}
            
            #select_button {{
                background: {
                    'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E31639, stop:1 #FF4D6A)'
                    if (is_popular or selected)
                    else ds.colors.surface_variant
                };
                color: {'white' if (is_popular or selected) else ds.colors.text_primary};
                border: none;
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_2}px {ds.spacing.space_4}px;
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_semibold};
                min-height: {ds.button_sizes['sm'].height}px;
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
        self.usage_total = 2
        self._build_ui()
        
    def _build_ui(self):
        self.setObjectName("current_plan_card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            ds.spacing.space_4,
            ds.spacing.space_4,
            ds.spacing.space_4,
            ds.spacing.space_4
        )
        layout.setSpacing(ds.spacing.space_3)
        
        # Header with plan name and refresh button
        header_layout = QHBoxLayout()

        self.plan_label = QLabel("현재 플랜")
        self.plan_label.setObjectName("current_plan_label")
        header_layout.addWidget(self.plan_label)

        header_layout.addStretch()

        # Refresh button
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setObjectName("refresh_button")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setToolTip("구독 상태 새로고침")
        header_layout.addWidget(self.refresh_btn)

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
        
        self.usage_text = QLabel("0 / 2")
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
        self.usage_hint = QLabel("남은 영상 생성 횟수: 2회")
        self.usage_hint.setObjectName("usage_hint")
        layout.addWidget(self.usage_hint)

        # Cumulative usage from server
        self.usage_cumulative = QLabel("누적 작업 수: 0회")
        self.usage_cumulative.setObjectName("usage_cumulative")
        layout.addWidget(self.usage_cumulative)
        
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
        
    def update_plan(self, plan_id: str, used: int = 0, total: int = 2, expires_at_str: str = None):
        """Update current plan display

        Args:
            plan_id: Plan identifier (e.g., "pro_1month", "pro_6months", "trial")
            used: Number of works used
            total: Total work count (-1 for unlimited)
            expires_at_str: ISO format expiry date string for dynamic plan detection
        """
        self.current_plan = plan_id
        self.usage_used = used
        self.usage_total = total
        try:
            used_num = max(int(used), 0)
        except (TypeError, ValueError):
            used_num = 0

        # Try to determine specific plan from expiry date if generic "pro" is passed
        if plan_id == "pro" and expires_at_str:
            expires_dt = parse_utc_datetime(expires_at_str)
            if expires_dt is not None:
                now = datetime.now(timezone.utc)
                days_remaining = (expires_dt - now).days

                # Determine plan based on days remaining (with some tolerance)
                if days_remaining >= 335:  # ~11 months (12개월 plan)
                    plan_id = "pro_12months"
                elif days_remaining >= 155:  # ~5 months (6개월 plan)
                    plan_id = "pro_6months"
                elif days_remaining >= 15:  # ~1 month (1개월 plan)
                    plan_id = "pro_1month"
                # else: keep as "pro"

        plan_data = PLANS.get(plan_id, PLANS["trial"])

        self.status_badge.setText(plan_data["name"])
        self.plan_name.setText(plan_data["name"])

        is_unlimited = (total < 0) or str(plan_id).startswith("pro")
        if is_unlimited:
            self.usage_text.setText("무제한")
            self.progress_bar.setMaximum(1)
            self.progress_bar.setValue(1)
            self.usage_hint.setText("무제한 영상 생성 가능")
        else:
            self.usage_text.setText(f"{used_num} / {total}")
            self.progress_bar.setMaximum(max(total, 1))
            self.progress_bar.setValue(used_num)
            remaining = max(total - used_num, 0)
            self.usage_hint.setText(f"남은 영상 생성 횟수: {remaining}회")
        self.usage_cumulative.setText(f"누적 작업 수: {used_num}회")
        
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

            #refresh_button {{
                background-color: {ds.colors.surface_variant};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.full}px;
                font-size: 14px;
            }}

            #refresh_button:hover {{
                background-color: {ds.colors.border};
                border-color: {ds.colors.text_muted};
            }}

            #refresh_button:pressed {{
                background-color: {ds.colors.text_muted};
            }}
            
            #current_plan_name {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_xl}px;
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

            #usage_cumulative {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_xs}px;
                font-weight: {ds.typography.weight_medium};
            }}
            
            #upgrade_button {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #E31639, stop:1 #FF4D6A);
                color: white;
                border: none;
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_2}px {ds.spacing.space_4}px;
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_semibold};
                min-height: {ds.button_sizes['md'].height}px;
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
                padding: {ds.spacing.space_2}px {ds.spacing.space_4}px;
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_medium};
                min-height: {ds.button_sizes['md'].height}px;
            }}
            
            #contact_button:hover {{
                background-color: {ds.colors.border};
                border-color: {ds.colors.text_muted};
            }}
        """)


class PaymentForm(QWidget):
    """Payment form with virtual-account and card modes."""

    def __init__(
        self,
        parent=None,
        on_submit=None,
        on_cancel=None,
        on_method_changed=None,
    ):
        super().__init__(parent)
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        self.on_method_changed = on_method_changed
        self.ds = get_design_system()
        self._payment_method = "vbank"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.spacing.space_4)

        title = QLabel("결제 정보")
        title.setObjectName("form_title")
        layout.addWidget(title)

        form_container = QFrame()
        form_container.setObjectName("form_container")
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(
            ds.spacing.space_4,
            ds.spacing.space_4,
            ds.spacing.space_4,
            ds.spacing.space_4,
        )
        form_layout.setSpacing(ds.spacing.space_3)

        plan_card = QFrame()
        plan_card.setObjectName("selected_plan_card")
        plan_card_layout = QVBoxLayout(plan_card)
        plan_card_layout.setContentsMargins(
            ds.spacing.space_3,
            ds.spacing.space_3,
            ds.spacing.space_3,
            ds.spacing.space_3,
        )
        plan_card_layout.setSpacing(ds.spacing.space_2)

        plan_header = QLabel("선택한 플랜")
        plan_header.setObjectName("plan_card_header")
        plan_card_layout.addWidget(plan_header)

        self.selected_plan_label = QLabel("플랜을 선택해주세요")
        self.selected_plan_label.setObjectName("selected_plan_value")
        self.selected_plan_label.setWordWrap(True)
        plan_card_layout.addWidget(self.selected_plan_label)
        form_layout.addWidget(plan_card)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("form_separator")
        form_layout.addWidget(separator)

        method_label = QLabel("결제 수단")
        method_label.setObjectName("field_label")
        form_layout.addWidget(method_label)

        method_row = QHBoxLayout()
        method_row.setSpacing(ds.spacing.space_2)
        self.method_vbank_btn = QPushButton("가상계좌")
        self.method_vbank_btn.setObjectName("method_button")
        self.method_vbank_btn.setCheckable(True)
        self.method_vbank_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        method_row.addWidget(self.method_vbank_btn)

        self.method_card_btn = QPushButton("카드결제")
        self.method_card_btn.setObjectName("method_button")
        self.method_card_btn.setCheckable(True)
        self.method_card_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        method_row.addWidget(self.method_card_btn)
        form_layout.addLayout(method_row)

        self.method_group = QButtonGroup(self)
        self.method_group.setExclusive(True)
        self.method_group.addButton(self.method_vbank_btn)
        self.method_group.addButton(self.method_card_btn)
        self.method_vbank_btn.clicked.connect(lambda: self.set_payment_method("vbank"))
        self.method_card_btn.clicked.connect(lambda: self.set_payment_method("card"))

        self.method_stack = QStackedWidget()
        self.method_stack.setObjectName("method_stack")
        self.method_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        vbank_page = QWidget()
        vbank_layout = QVBoxLayout(vbank_page)
        vbank_layout.setContentsMargins(0, 0, 0, 0)
        self.vbank_info_label = QLabel(PAYMENT_INFO_VBANK_TEXT)
        self.vbank_info_label.setObjectName("info_label")
        self.vbank_info_label.setWordWrap(True)
        vbank_layout.addWidget(self.vbank_info_label)
        self.method_stack.addWidget(vbank_page)
        form_layout.addWidget(self.method_stack)

        phone_label = QLabel("전화번호 (결제 안내 수신)")
        phone_label.setObjectName("field_label")
        form_layout.addWidget(phone_label)

        self.phone_input = QLineEdit()
        self.phone_input.setObjectName("phone_input")
        self.phone_input.setPlaceholderText("010-0000-0000")
        self.phone_input.setMaxLength(13)
        form_layout.addWidget(self.phone_input)

        self.status_label = QLabel("결제 대기 중")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(self.status_label)

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

        QTimer.singleShot(0, self._sync_method_stack_height)
        self.set_payment_method("vbank", notify=False)
        self._apply_styles()

    def set_plan(self, plan_data: dict):
        """Set the selected plan."""
        plan_name = plan_data["name"]
        price = plan_data["price"]
        months = plan_data.get("months", 1)

        price_text = f"{price:,}원"
        if months > 1:
            price_text += f" ({months}개월분)"

        per_month_price = plan_data.get("price_per_month", price)
        per_month_text = f"월 {format_price_korean(per_month_price)}"

        discount_info = ""
        if plan_data.get("discount_percent"):
            discount_info = f"\n할인율: {plan_data['discount_percent']}%"

        full_text = f"{plan_name}\n{per_month_text}\n총액: {price_text}{discount_info}"
        self.selected_plan_label.setText(full_text)

    def reset_selection(self):
        """Reset selected plan display."""
        self.selected_plan_label.setText("플랜을 선택해주세요")
        self.set_payment_method("vbank")

    def set_submit_enabled(self, enabled: bool):
        """Enable/disable submit button based on plan selection."""
        self.pay_btn.setEnabled(enabled)

    def set_status(self, status: str):
        self.status_label.setText(status)

    def set_payment_method(self, method: str, notify: bool = True):
        normalized = "card" if method == "card" else "vbank"
        self._payment_method = normalized
        self.method_vbank_btn.setChecked(normalized == "vbank")
        self.method_card_btn.setChecked(normalized == "card")
        # Keep UI minimal: both methods use same phone-only web checkout flow.
        self.method_stack.setCurrentIndex(0)
        if normalized == "card":
            self.vbank_info_label.setText(PAYMENT_INFO_CARD_TEXT)
        else:
            self.vbank_info_label.setText(PAYMENT_INFO_VBANK_TEXT)
        self._sync_method_stack_height()
        self.status_label.setText("결제 대기 중")
        if notify and callable(self.on_method_changed):
            self.on_method_changed(normalized)

    def get_payment_method(self) -> str:
        return self._payment_method

    def _on_submit(self):
        if self.on_submit:
            self.on_submit()

    def _on_cancel(self):
        if self.on_cancel:
            self.on_cancel()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_method_stack_height()

    def _sync_method_stack_height(self):
        """Keep method info area compact based on wrapped label height."""
        if not hasattr(self, "method_stack") or not hasattr(self, "vbank_info_label"):
            return

        content_width = max(220, self.method_stack.width() - ds.spacing.space_2)
        text_height = self.vbank_info_label.heightForWidth(content_width)
        if text_height <= 0:
            text_height = self.vbank_info_label.sizeHint().height()

        target_height = max(38, min(72, text_height + ds.spacing.space_1))
        if self.method_stack.height() != target_height:
            self.method_stack.setFixedHeight(target_height)

    def _apply_styles(self):
        self.setStyleSheet(f"""
            #form_title {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_md}px;
                font-weight: {ds.typography.weight_bold};
                letter-spacing: 0.4px;
            }}

            #form_container {{
                background-color: {ds.colors.surface};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.lg}px;
            }}

            #selected_plan_card {{
                background-color: {ds.colors.surface_variant};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
            }}

            #plan_card_header {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_xs}px;
                font-weight: {ds.typography.weight_bold};
                letter-spacing: 0.3px;
            }}

            #field_label {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_medium};
            }}

            #selected_plan_value {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_semibold};
            }}

            #form_separator {{
                color: {ds.colors.border};
            }}

            #method_button {{
                background-color: {ds.colors.surface_variant};
                color: {ds.colors.text_secondary};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_2}px {ds.spacing.space_4}px;
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_medium};
            }}

            #method_button:checked {{
                color: white;
                background-color: {ds.colors.primary};
                border-color: {ds.colors.primary};
            }}

            #method_stack {{
                border: none;
                background: transparent;
            }}

            #card_input_container {{
                background-color: {ds.colors.surface_variant};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
            }}

            #info_label {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
            }}

            #status_label {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
                padding: {ds.spacing.space_3}px;
                background-color: {ds.colors.surface_variant};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
            }}

            #pay_button {{
                background-color: {ds.colors.primary};
                color: white;
                border: none;
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_2}px {ds.spacing.space_4}px;
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_semibold};
                min-height: {ds.button_sizes['sm'].height}px;
            }}

            #pay_button:hover {{
                background-color: #C41230;
            }}

            #pay_button:disabled {{
                background: {ds.colors.surface_variant};
                color: {ds.colors.text_muted};
                border: 1px solid {ds.colors.border};
            }}

            #cancel_button {{
                background-color: {ds.colors.surface_variant};
                color: {ds.colors.text_primary};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_2}px {ds.spacing.space_4}px;
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_medium};
                min-height: {ds.button_sizes['sm'].height}px;
            }}

            #cancel_button:hover {{
                background-color: {ds.colors.border};
                border-color: {ds.colors.text_muted};
            }}

            #phone_input, #card_select, #card_input {{
                background-color: {ds.colors.surface_variant};
                color: {ds.colors.text_primary};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_2}px {ds.spacing.space_3}px;
                font-size: {ds.typography.size_sm}px;
            }}

            #phone_input:focus, #card_select:focus, #card_input:focus {{
                border-color: {ds.colors.primary};
            }}

            #card_refresh_btn {{
                background-color: {ds.colors.surface_variant};
                color: {ds.colors.text_primary};
                border: 1px solid {ds.colors.border};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_2}px {ds.spacing.space_3}px;
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_medium};
            }}

            #card_refresh_btn:hover {{
                border-color: {ds.colors.primary};
                color: {ds.colors.primary};
            }}

            #card_field_label {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
                font-weight: {ds.typography.weight_medium};
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
        self._polling = False  # Prevent overlapping status poll requests.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_status)
        self.selected_plan = None
        self._default_plan_id = "pro_1month"
        self.ds = get_design_system()
        
        self._build_ui()
        
    def _build_ui(self):
        # Scroll area: keep the main window size stable and allow tall content to be reachable.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Set proper background color for the panel
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        scroll = self.scroll_area = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {ds.colors.background};
                border: none;
            }}
        """)

        page = QWidget()
        page.setObjectName("subscription_page")
        page.setStyleSheet(f"""
            QWidget#subscription_page {{
                background-color: {ds.colors.background};
            }}
        """)

        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(
            ds.spacing.space_4,
            ds.spacing.space_4,
            ds.spacing.space_4,
            ds.spacing.space_4
        )
        main_layout.setSpacing(ds.spacing.space_4)

        # Subtitle (removed duplicate title)
        subtitle = QLabel("숏폼 메이커의 모든 기능을 해제하세요")
        subtitle.setObjectName("page_subtitle")
        main_layout.addWidget(subtitle)
        
        main_layout.addSpacing(ds.spacing.space_4)
        
        # Current plan card
        self.current_plan_card = CurrentPlanCard()
        self.current_plan_card.upgrade_btn.clicked.connect(self._show_plans)
        self.current_plan_card.contact_btn.clicked.connect(self._contact_support)
        self.current_plan_card.refresh_btn.clicked.connect(self._manual_refresh)
        main_layout.addWidget(self.current_plan_card)
        
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
        
        # Create plan cards for all pro tiers
        self.plan_cards = []
        pro_plan_ids = ["pro_1month", "pro_6months", "pro_12months"]
        for plan_id in pro_plan_ids:
            if plan_id in PLANS:
                plan_data = PLANS[plan_id]
                card = PlanCard(plan_data, on_select=self._on_plan_selected)
                self.plan_cards.append(card)
                plans_row.addWidget(card)
        
        plans_layout.addLayout(plans_row)
        self.plans_container.hide()
        main_layout.addWidget(self.plans_container)

        # Payment form under plans (no right-side split layout)
        self.payment_form = PaymentForm(
            on_submit=self._checkout,
            on_cancel=self._cancel_payment,
            on_method_changed=self._on_payment_method_changed,
        )
        self.payment_form.hide()
        self.payment_form.set_submit_enabled(False)
        main_layout.addWidget(self.payment_form)
        main_layout.addStretch()

        scroll.setWidget(page)
        outer_layout.addWidget(scroll)
        
        self._apply_styles()
        
    def _apply_styles(self):
        self.setStyleSheet(f"""
            #page_title {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_2xl}px;
                font-weight: {ds.typography.weight_bold};
            }}

            #page_subtitle {{
                color: {ds.colors.text_secondary};
                font-size: {ds.typography.size_sm}px;
            }}

            #section_title {{
                color: {ds.colors.text_primary};
                font-size: {ds.typography.size_md}px;
                font-weight: {ds.typography.weight_semibold};
            }}
        """)
        
    def _show_plans(self):
        """Show plan selection"""
        self.plans_container.show()
        self.payment_form.show()
        # Keep payment controls interactive when the section is opened.
        self.payment_form.method_vbank_btn.setEnabled(True)
        self.payment_form.method_card_btn.setEnabled(True)
        self.payment_form.phone_input.setEnabled(True)
        self.payment_form.cancel_btn.setEnabled(True)
        # Auto-select default plan once for smoother checkout UX.
        if not self.selected_plan and self._default_plan_id in PLANS:
            self._on_plan_selected(PLANS[self._default_plan_id])
        # Ensure the newly revealed section is reachable without resizing the window.
        QTimer.singleShot(
            0,
            lambda: getattr(self, "scroll_area", None)
            and self.scroll_area.ensureWidgetVisible(self.plans_container, 0, ds.spacing.space_6),
        )
        
    def _on_plan_selected(self, plan_data: dict):
        """Handle plan selection"""
        self.selected_plan = plan_data
        self._update_plan_card_selection(plan_data.get("id"))
        self.payment_form.set_plan(plan_data)
        self.payment_form.set_submit_enabled(True)
        self.payment_form.method_vbank_btn.setEnabled(True)
        self.payment_form.method_card_btn.setEnabled(True)
        self.payment_form.phone_input.setEnabled(True)
        self.payment_form.cancel_btn.setEnabled(True)
        self.payment_form.set_status("결제 대기 중")

    def _update_plan_card_selection(self, selected_plan_id: str | None):
        """Sync plan card selected visuals with current selection."""
        for card in self.plan_cards:
            plan_id = card.plan_data.get("id")
            card.set_selected(plan_id == selected_plan_id)

    def _on_payment_method_changed(self, method: str):
        """Payment method switched (UI is unified phone-only checkout)."""
        _ = method

    def _contact_support(self):
        """Open support contact"""
        webbrowser.open("https://open.kakao.com/o/sVkZPsfi")

    def _manual_refresh(self):
        """Manually refresh subscription status"""
        self.current_plan_card.refresh_btn.setEnabled(False)
        self.current_plan_card.refresh_btn.setText("⏳")

        def _do_refresh():
            success = self.refresh_from_server()

            def _restore_button():
                self.current_plan_card.refresh_btn.setEnabled(True)
                self.current_plan_card.refresh_btn.setText("🔄")
                if success:
                    QMessageBox.information(self, "완료", "구독 상태가 새로고침되었습니다.")
                else:
                    QMessageBox.warning(self, "오류", "구독 상태를 새로고침하지 못했습니다.")

            # Run in main thread
            cb_signal = getattr(self.gui, 'ui_callback_signal', None) if self.gui else None
            if cb_signal is not None:
                cb_signal.emit(_restore_button)
            else:
                QTimer.singleShot(0, _restore_button)

        # Run refresh in background thread
        import threading
        threading.Thread(target=_do_refresh, daemon=True).start()
        
    def _checkout(self):
        """Start PayApp checkout process."""
        if not self.selected_plan:
            QMessageBox.warning(self, "알림", "플랜을 먼저 선택해주세요.")
            return

        import re as _re

        phone = self.payment_form.phone_input.text().strip()
        phone_digits = _re.sub(r"[^0-9]", "", phone)
        if not phone_digits or len(phone_digits) < 10 or len(phone_digits) > 11:
            QMessageBox.warning(self, "알림", "전화번호를 정확히 입력해주세요.")
            return
        if not _re.match(r"^01[016789]\d{7,8}$", phone_digits):
            QMessageBox.warning(self, "알림", "올바른 휴대폰 번호를 입력해주세요.\n(예: 010-1234-5678)")
            return

        user_id = self._extract_user_id()
        auth_token = self._extract_auth_token()

        if not user_id:
            QMessageBox.warning(self, "알림", "로그인 사용자 정보를 찾을 수 없습니다.")
            return
        if not auth_token:
            QMessageBox.warning(self, "로그인 필요", "결제를 위해 다시 로그인해주세요.")
            return

        try:
            plan_id = self.selected_plan.get("id", "pro_1month")
            payment_method = self.payment_form.get_payment_method()

            status_text = "카드 결제창 준비 중..." if payment_method == "card" else "가상계좌 결제창 준비 중..."
            self.payment_form.set_status(status_text)

            # Unified web checkout flow:
            # app collects only phone number, and all sensitive payment info is entered on web.
            try:
                data = self.payment.create_payapp_checkout(
                    str(user_id),
                    phone_digits,
                    plan_id=plan_id,
                    token=auth_token,
                    payment_type=payment_method,
                )
            except RuntimeError as e:
                # Backward compatibility for servers that do not support payment_type.
                logger.warning(
                    "[Subscription] checkout with payment_type=%s failed, retrying legacy create: %s",
                    payment_method,
                    e,
                )
                data = self.payment.create_payapp_checkout(
                    str(user_id),
                    phone_digits,
                    plan_id=plan_id,
                    token=auth_token,
                )

            self.current_payment_id = data.get("payment_id", "")
            if not self.current_payment_id:
                raise RuntimeError("결제 응답에 payment_id가 없습니다.")
            payurl = data.get("payurl", "")

            self.payment_form.set_status("결제 페이지를 여는 중...")
            if payurl:
                webbrowser.open(payurl)
            self._start_poll()
        except RuntimeError as e:
            message = str(e).strip() or "결제 요청에 실패했습니다. 잠시 후 다시 시도해주세요."
            logger.error("[Subscription] PayApp checkout failed: %s", message)
            QMessageBox.critical(self, "오류", message)
            self.payment_form.set_status(message)
        except Exception as e:
            logger.exception("[Subscription] PayApp checkout failed unexpectedly")
            QMessageBox.critical(self, "오류", "결제 요청에 실패했습니다.\n잠시 후 다시 시도해주세요.")
            self.payment_form.set_status("결제 요청 오류")

    def _cancel_payment(self):
        """Cancel current payment flow and reset form state."""
        self._stop_poll()
        self.current_payment_id = None
        self.selected_plan = None
        self._update_plan_card_selection(None)
        self.payment_form.reset_selection()
        self.payment_form.set_submit_enabled(False)
        self.payment_form.set_status("결제 대기 중")
        
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
        user_id = self._extract_user_id()
        auth_token = self._extract_auth_token()

        def _do_poll():
            try:
                data = self.payment.get_status(payment_id, user_id=user_id or "", token=auth_token or "")
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

    def _extract_auth_token(self):
        """login_data에서 인증 토큰을 안전하게 추출"""
        if not self.gui or not getattr(self.gui, "login_data", None):
            try:
                from caller import rest
                getter = getattr(rest, "_get_auth_token", None)
                if callable(getter):
                    return getter()
            except Exception:
                pass
            return None
        data_part = self.gui.login_data.get("data", {})
        if isinstance(data_part, dict):
            token = data_part.get("token")
            if token:
                return token
        try:
            from caller import rest
            getter = getattr(rest, "_get_auth_token", None)
            if callable(getter):
                return getter()
        except Exception:
            pass
        return None

    def _verify_subscription_server(self):
        """결제 완료 후 서버에서 구독 상태를 재확인하여 UI 업데이트"""
        try:
            user_id = self._extract_user_id()
            if not user_id:
                # 서버 확인 불가 시 trial로 표시
                self.current_plan_card.update_plan("trial", used=0, total=0, expires_at_str=None)
                return
            from caller import rest
            status = rest.getSubscriptionStatus(user_id)
            if status.get("success", True):
                work_count = status.get("work_count", -1)
                work_used = status.get("work_used", 0)

                # Check if subscription is actually active
                expires_at_str = status.get("subscription_expires_at") or status.get("data", {}).get("subscription_expires_at")
                expires_dt = parse_utc_datetime(expires_at_str)
                is_active_subscription = bool(
                    expires_dt and expires_dt > datetime.now(timezone.utc)
                )

                is_pro = (work_count == -1) and is_active_subscription

                if is_pro:
                    self.current_plan_card.update_plan("pro", used=work_used, total=-1, expires_at_str=expires_at_str)
                else:
                    remaining = max(work_count - work_used, 0)
                    self.current_plan_card.update_plan("trial", used=work_used, total=work_count, expires_at_str=None)
                logger.info(f"[Subscription] Server verification complete: pro={is_pro}")
            else:
                # 서버 확인 실패 시 trial로 표시 (권한 불일치 방지)
                self.current_plan_card.update_plan("trial", used=0, total=0, expires_at_str=None)
        except Exception as e:
            logger.error(f"[Subscription] Server verification failed: {e}")
            self.current_plan_card.update_plan("trial", used=0, total=0, expires_at_str=None)

    def update_usage(self, used: int, total: int, plan_id: str = "trial", expires_at_str: str = None):
        """Update current usage display"""
        self.current_plan_card.update_plan(plan_id, used, total, expires_at_str=expires_at_str)

    def refresh_from_server(self):
        """Force refresh subscription status from server"""
        try:
            user_id = self._extract_user_id()
            if not user_id:
                logger.warning("[Subscription] Cannot refresh - no user_id")
                return

            from caller import rest
            status = rest.getSubscriptionStatus(user_id)

            if status.get("success", True):
                work_count = status.get("work_count", -1)
                work_used = status.get("work_used", 0)

                # Check if subscription is actually active
                expires_at_str = status.get("subscription_expires_at") or status.get("data", {}).get("subscription_expires_at")
                expires_dt = parse_utc_datetime(expires_at_str)
                is_active_subscription = bool(
                    expires_dt and expires_dt > datetime.now(timezone.utc)
                )

                is_pro = (work_count == -1) and is_active_subscription

                if is_pro:
                    self.current_plan_card.update_plan("pro", used=work_used, total=-1, expires_at_str=expires_at_str)
                    logger.info(f"[Subscription] Refreshed: PRO account (expires_at={expires_at_str})")
                else:
                    remaining = max(work_count - work_used, 0)
                    self.current_plan_card.update_plan("trial", used=work_used, total=work_count, expires_at_str=None)
                    logger.info(f"[Subscription] Refreshed: TRIAL account ({work_used}/{work_count})")

                # Update parent GUI if available
                if self.gui:
                    # Update credits label
                    credits_lbl = getattr(self.gui, "credits_label", None)
                    if credits_lbl is not None:
                        if is_pro:
                            credits_lbl.setText(f"구독중 | 누적 {work_used}회")
                        else:
                            credits_lbl.setText(f"크레딧 {remaining}/{work_count} | 누적 {work_used}회")

                return True
            else:
                logger.warning(f"[Subscription] Server returned failure: {status}")
                return False

        except Exception as e:
            logger.error(f"[Subscription] Refresh failed: {e}")
            return False

    def showEvent(self, event):
        """Called when panel becomes visible - refresh subscription status"""
        super().showEvent(event)
        # Refresh subscription status when panel is shown
        QTimer.singleShot(100, self.refresh_from_server)


