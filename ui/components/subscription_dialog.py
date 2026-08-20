# -*- coding: utf-8 -*-
"""Subscription prompt using the same production alert hierarchy."""
from __future__ import annotations

from ui.components.custom_dialog import CustomDialog


class SubscriptionDialog(CustomDialog):
    def __init__(self, parent=None, user_id=None, work_used=0, work_count=0):
        self.user_id = user_id
        self.work_used = work_used
        self.work_count = work_count
        message = (
            f"현재 사용량: {work_used}회 / {work_count}회\n\n"
            "체험판 무료 횟수를 모두 사용했습니다.\n"
            "프로 플랜을 구독하면 제작 횟수 제한 없이 이용할 수 있습니다.\n\n"
            "이미 결제했다면 구독 관리에서 상태를 새로고침하거나 앱을 다시 시작해 주세요."
        )
        super().__init__(
            parent,
            "체험판 사용량 소진",
            message,
            "warning",
            buttons=[
                ("닫기", self.reject),
                ("구독 관리 열기", self._open_subscription),
            ],
        )

    def _open_subscription(self):
        try:
            parent = self.parent()
            if parent is not None:
                if hasattr(parent, "_show_subscription_panel"):
                    parent._show_subscription_panel()
                elif hasattr(parent, "_on_step_selected"):
                    parent._on_step_selected("subscription")
        finally:
            self.accept()
