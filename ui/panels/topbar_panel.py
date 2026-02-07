# -*- coding: utf-8 -*-
"""
Top bar panel - user status, credits, subscription badge.

Builds the application header with user info display and
subscription status badge. Assigns widgets to gui.X for
backward compatibility with existing cross-references.
"""

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from caller import rest
from utils.logging_config import get_logger

logger = get_logger(__name__)


class TopBarPanel(QFrame):
    """Top header bar with user info, credits, and subscription badge.

    Builds widgets and assigns them onto ``gui.credits_label``,
    ``gui.username_label``, ``gui.last_login_label``, ``gui.sub_badge``,
    ``gui.subscription_time_label`` so that existing cross-references
    in other components continue to work.
    """

    def __init__(self, gui, design_system):
        super().__init__()
        self.gui = gui
        self.design = design_system
        self._build()

    def _build(self):
        """Build topbar UI."""
        d = self.design
        c = d.colors

        self.setObjectName("TopBar")
        self.setFixedHeight(68)
        self.setStyleSheet(f"""
            #TopBar {{
                background-color: {c.bg_header};
                border-bottom: 1px solid {c.border_light};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(16)

        # Title
        app_title = QLabel("쇼핑 숏폼 메이커 - 스튜디오")
        app_title.setFont(QFont(
            d.typography.font_family_heading,
            d.typography.size_sm,
            QFont.Weight.Bold,
        ))
        app_title.setStyleSheet(f"color: {c.text_primary}; letter-spacing: -0.5px;")
        layout.addWidget(app_title)

        layout.addStretch()

        # Credits Button
        self.gui.credits_label = QPushButton("")
        self.gui.credits_label.setFont(
            QFont(d.typography.font_family_body, d.typography.size_xs, QFont.Weight.Bold)
        )
        self.gui.credits_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gui.credits_label.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                padding: 8px 16px;
                border-radius: {d.radius.md}px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
            }}
        """)
        self.gui.credits_label.clicked.connect(self.show_subscription_panel)
        layout.addWidget(self.gui.credits_label)

        # Username
        self.gui.username_label = QLabel("사용자")
        self.gui.username_label.setFont(
            QFont(d.typography.font_family_body, d.typography.size_xs)
        )
        self.gui.username_label.setStyleSheet(f"color: {c.text_secondary};")
        layout.addWidget(self.gui.username_label)

        # Last login
        self.gui.last_login_label = QLabel("")
        self.gui.last_login_label.setFont(
            QFont(d.typography.font_family_body, d.typography.size_2xs)
        )
        self.gui.last_login_label.setStyleSheet(f"color: {c.text_muted};")
        layout.addWidget(self.gui.last_login_label)

        # Subscription Badge
        self.gui.sub_badge = QPushButton("게스트")
        self.gui.sub_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gui.sub_badge.setFont(
            QFont(d.typography.font_family_body, d.typography.size_2xs, QFont.Weight.Bold)
        )
        self.gui.sub_badge.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.05);
                color: {c.text_secondary};
                padding: 6px 12px;
                border-radius: {d.radius.base}px;
                border: 1px solid {c.border_light};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                border-color: {c.primary};
            }}
        """)
        self.gui.sub_badge.clicked.connect(self.show_subscription_panel)
        layout.addWidget(self.gui.sub_badge)

        # Subscription time remaining label
        self.gui.subscription_time_label = QLabel("")
        self.gui.subscription_time_label.setFont(
            QFont(d.typography.font_family_body, d.typography.size_2xs)
        )
        self.gui.subscription_time_label.setStyleSheet(
            f"color: {c.success}; font-weight: bold;"
        )
        self.gui.subscription_time_label.hide()
        layout.addWidget(self.gui.subscription_time_label)

        # Subscribe button (shown for free accounts instead of countdown)
        self.gui.subscribe_btn = QPushButton("구독 하기")
        self.gui.subscribe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gui.subscribe_btn.setFont(
            QFont(d.typography.font_family_body, d.typography.size_2xs, QFont.Weight.Bold)
        )
        self.gui.subscribe_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #E31639, stop:1 #FF4D6A);
                color: white;
                padding: 6px 14px;
                border-radius: {d.radius.base}px;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #C41230, stop:1 #E63D5A);
            }}
        """)
        self.gui.subscribe_btn.clicked.connect(self.show_subscription_panel)
        self.gui.subscribe_btn.hide()
        layout.addWidget(self.gui.subscribe_btn)

    def show_subscription_panel(self):
        """Navigate to subscription panel."""
        if hasattr(self.gui, "_on_step_selected"):
            self.gui._on_step_selected("subscription")

    def refresh_user_status(self):
        """Update user subscription status, credits, and user info from server."""
        if not self.gui.login_data:
            self.gui.sub_badge.setText("게스트")
            self.gui.username_label.setText("게스트")
            self.gui.last_login_label.setText("최근 로그인: -")
            return

        try:
            data_part = self.gui.login_data.get("data", {})
            if isinstance(data_part, dict):
                inner_data = data_part.get("data", {})
                user_id = inner_data.get("id")
                username = (
                    inner_data.get("username")
                    or data_part.get("username")
                    or "사용자"
                )
                last_login = inner_data.get("last_login_at", None)
            else:
                user_id = None
                username = "사용자"
                last_login = None

            if not user_id:
                user_id = self.gui.login_data.get("userId")

            # Update username and last login labels
            self.gui.username_label.setText(username or "사용자")
            if last_login:
                try:
                    if isinstance(last_login, str):
                        dt = datetime.fromisoformat(
                            last_login.replace("Z", "+00:00")
                        )
                        formatted = dt.strftime("%Y-%m-%d %H:%M")
                    else:
                        formatted = str(last_login)[:16]
                    self.gui.last_login_label.setText(f"최근 로그인: {formatted}")
                except (ValueError, TypeError):
                    self.gui.last_login_label.setText(
                        f"최근 로그인: {str(last_login)[:10]}"
                    )
            else:
                self.gui.last_login_label.setText("최근 로그인: 오늘")

            if user_id:
                info = rest.check_work_available(user_id)

                if not info.get("success", True):
                    # Token missing/expired or server verification failed.
                    # Do not mislead the user with fake "0/5" credits.
                    self.gui.credits_label.setText("로그인 필요")
                    self.gui.sub_badge.setText("로그인")
                    d = self.design
                    c = d.colors
                    self.gui.sub_badge.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {c.bg_card};
                            color: {c.text_secondary};
                            padding: 6px 12px;
                            border-radius: 6px;
                            font-weight: bold;
                            border: 1px solid {c.border_light};
                        }}
                    """)
                    return

                remaining = info.get("remaining", 0)
                total = info.get("total", 0)

                top_data = self.gui.login_data.get("data", {}).get("data", {})

                # login_data의 user_type은 결제/웹훅으로 구독이 활성화된 뒤 stale(갱신 안 됨)일 수 있습니다.
                # 배지/표시는 구독 상태 API(/user/subscription/my-status)를 기준으로 결정합니다.
                login_user_type = top_data.get("user_type", "trial")
                user_type = login_user_type

                # admin은 그대로 유지
                if login_user_type != "admin":
                    sub_status = rest.getSubscriptionStatus(str(user_id))
                    has_expiry = bool(sub_status.get("subscription_expires_at"))
                    is_unlimited = sub_status.get("work_count") == -1
                    is_trial_flag = sub_status.get("is_trial")
                    is_subscriber = has_expiry or is_unlimited or (is_trial_flag is False)
                    user_type = "subscriber" if is_subscriber else "trial"

                    # NOTE: login_data는 공유 상태이므로 직접 변경하지 않음.
                    # 백엔드 auto-heal이 다음 요청 시 DB를 갱신함.

                # 구독자는 "구독중", 그 외는 크레딧 표시
                if user_type == "subscriber":
                    self.gui.credits_label.setText("구독중")
                else:
                    self.gui.credits_label.setText(f"크레딧: {remaining}/{total}")

                d = self.design
                c = d.colors

                badge_text = user_type.upper()
                badge_bg = c.bg_card
                badge_color = c.text_secondary

                if user_type == "subscriber":
                    badge_text = "유료계정"
                    badge_bg = c.primary_light
                    badge_color = c.primary
                elif user_type == "admin":
                    badge_text = "관리자"
                    badge_bg = "#374151"
                    badge_color = "#FFFFFF"
                else:  # trial
                    badge_text = "무료계정"
                    if remaining <= 0:
                        badge_bg = "#FEF2F2"
                        badge_color = "#EF4444"

                self.gui.sub_badge.setText(badge_text)
                self.gui.sub_badge.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {badge_bg};
                        color: {badge_color};
                        padding: 6px 12px;
                        border-radius: 6px;
                        font-weight: bold;
                        border: 1px solid {c.border_light};
                    }}
                    QPushButton:hover {{
                        background-color: {c.bg_hover};
                        opacity: 0.9;
                    }}
                """)

                logger.info(
                    f"User status refreshed: {user_id} | {user_type} | "
                    f"{remaining}/{total}"
                )
            else:
                logger.warning(
                    "Could not extract user_id from login_data for status refresh"
                )
        except (KeyError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse user status: {e}")
        except Exception as e:
            logger.error(f"Failed to refresh user status: {e}")
