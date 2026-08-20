# -*- coding: utf-8 -*-
"""Consistent trial-limit dialog built on the production alert surface."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog

from ui.components.custom_dialog import CustomDialog


class TrialLimitDialog(CustomDialog):
    subscription_requested = pyqtSignal()

    def __init__(self, parent=None, used: int = 5, total: int = 5, theme_manager=None):
        self.used = used
        self.total = total
        message = (
            f"현재 사용량: {used}회 / {total}회\n\n"
            "체험판 무료 제작 횟수를 모두 사용했습니다.\n"
            "추가 영상을 제작하려면 구독 관리에서 플랜을 선택해 주세요."
        )
        super().__init__(
            parent,
            "체험판 사용량 소진",
            message,
            "warning",
            buttons=[
                ("닫기", self.reject),
                ("구독 관리 열기", self._on_subscribe_clicked),
            ],
            theme_manager=theme_manager,
        )

    def _on_subscribe_clicked(self):
        self.subscription_requested.emit()
        self.accept()

    def show_and_wait(self) -> bool:
        return self.exec() == QDialog.DialogCode.Accepted


def show_trial_limit_dialog(parent=None, used: int = 5, total: int = 5) -> bool:
    return TrialLimitDialog(parent, used, total).show_and_wait()
