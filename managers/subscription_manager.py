# -*- coding: utf-8 -*-
"""
Subscription status auto-refresh and countdown display manager.

Polls the server every 60 seconds for subscription status and
updates the countdown display every second.
"""

from datetime import datetime, timezone

from PyQt6.QtCore import QTimer

from caller import rest
from utils.logging_config import get_logger

logger = get_logger(__name__)


class SubscriptionManager:
    """Manages subscription status polling and countdown display.

    Follows the existing manager pattern: accepts ``gui`` reference,
    accesses widgets via ``getattr()`` for safety.
    """

    def __init__(self, gui):
        self.gui = gui
        self._subscription_expires_at = None
        self._last_countdown_style = None
        self._countdown_was_active = False

        # 60-second subscription poll timer
        self._subscription_timer = QTimer(gui)
        self._subscription_timer.timeout.connect(self._auto_refresh_subscription)

        # 1-second countdown display timer
        self._countdown_timer = QTimer(gui)
        self._countdown_timer.timeout.connect(self._update_countdown_display)

    # -------------------- public API --------------------

    def start(self):
        """Start the subscription refresh cycle."""
        self._subscription_timer.start(60000)
        self._auto_refresh_subscription()

    def stop(self):
        """Stop all timers."""
        self._subscription_timer.stop()
        self._countdown_timer.stop()

    def pause_countdown(self):
        """Pause countdown during resize for performance."""
        if self._countdown_timer.isActive():
            self._countdown_timer.stop()
            self._countdown_was_active = True
        else:
            self._countdown_was_active = False

    def resume_countdown(self):
        """Resume countdown after resize."""
        if self._countdown_was_active:
            self._countdown_timer.start(1000)
            self._update_countdown_display()

    # -------------------- internal --------------------

    def _auto_refresh_subscription(self):
        """Poll server for subscription status (called every 60s)."""
        if not self.gui.login_data:
            return

        try:
            data_part = self.gui.login_data.get("data", {})
            if isinstance(data_part, dict):
                inner_data = data_part.get("data", {})
                user_id = inner_data.get("id")
            else:
                user_id = None

            if not user_id:
                user_id = self.gui.login_data.get("userId")

            if not user_id:
                return

            status = rest.getSubscriptionStatus(user_id)

            if status.get("success", True):
                expires_at = status.get("subscription_expires_at")

                if expires_at:
                    self._subscription_expires_at = expires_at
                    if not self._countdown_timer.isActive():
                        self._countdown_timer.start(1000)
                    self._update_countdown_display()
                else:
                    self._subscription_expires_at = None
                    self._countdown_timer.stop()
                    sub_label = getattr(self.gui, "subscription_time_label", None)
                    if sub_label is not None:
                        d = self.gui.design
                        sub_label.setText("체험계정")
                        sub_label.setStyleSheet(
                            f"color: {d.colors.text_muted}; font-weight: normal;"
                        )
                        sub_label.show()

                remaining = status.get("remaining", 0)
                total = status.get("work_count", 0)
                credits_lbl = getattr(self.gui, "credits_label", None)
                if credits_lbl is not None:
                    # 구독 중이면 "구독중" 표시, 아니면 크레딧 표시
                    if expires_at:
                        credits_lbl.setText("구독중")
                    else:
                        credits_lbl.setText(f"크레딧: {remaining}/{total}")

                logger.debug(
                    f"[Subscription] Auto-refresh: expires_at={expires_at}, "
                    f"remaining={remaining}/{total}"
                )

        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"[Subscription] Auto-refresh parse error: {e}")
        except Exception as e:
            logger.error(f"[Subscription] Auto-refresh failed: {e}")

    def _update_countdown_display(self):
        """Update countdown label (called every 1s)."""
        sub_label = getattr(self.gui, "subscription_time_label", None)
        if sub_label is None:
            return

        if not self._subscription_expires_at:
            d = self.gui.design
            sub_label.setText("체험계정")
            sub_label.setStyleSheet(
                f"color: {d.colors.text_muted}; font-weight: normal;"
            )
            sub_label.show()
            return

        try:
            expires_str = self._subscription_expires_at
            if expires_str.endswith("Z"):
                expires_str = expires_str[:-1] + "+00:00"

            expires_dt = datetime.fromisoformat(expires_str)

            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            diff = expires_dt - now
            total_seconds = int(diff.total_seconds())

            if total_seconds <= 0:
                sub_label.setText("구독 만료됨")
                sub_label.setStyleSheet("color: #EF4444; font-weight: bold;")
                sub_label.show()
                self._countdown_timer.stop()
                return

            years = total_seconds // (365 * 24 * 3600)
            remaining = total_seconds % (365 * 24 * 3600)

            months = remaining // (30 * 24 * 3600)
            remaining = remaining % (30 * 24 * 3600)

            days = remaining // (24 * 3600)
            remaining = remaining % (24 * 3600)

            hours = remaining // 3600
            remaining = remaining % 3600

            minutes = remaining // 60
            seconds = remaining % 60

            parts = []
            if years > 0:
                parts.append(f"{years}년")
            if months > 0:
                parts.append(f"{months}월")
            if days > 0:
                parts.append(f"{days}일")
            if hours > 0:
                parts.append(f"{hours}시간")
            if minutes > 0:
                parts.append(f"{minutes}분")
            parts.append(f"{seconds}초")

            time_str = " ".join(parts)
            sub_label.setText(f"구독 남은 시간: {time_str}")

            new_style = "warning" if total_seconds < 7 * 24 * 3600 else "normal"
            if self._last_countdown_style != new_style:
                self._last_countdown_style = new_style
                if new_style == "warning":
                    sub_label.setStyleSheet("color: #F59E0B; font-weight: bold;")
                else:
                    d = self.gui.design
                    sub_label.setStyleSheet(
                        f"color: {d.colors.success}; font-weight: bold;"
                    )

            sub_label.show()

        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(f"[Subscription] Countdown parse error: {e}")
            if sub_label is not None:
                sub_label.hide()
