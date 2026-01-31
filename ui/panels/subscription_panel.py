"""
Subscription purchase panel (PyQt6) with web checkout + status polling.
Products: Monthly and Yearly (20% off).
"""
import webbrowser
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
import config
from utils.logging_config import get_logger
from utils.payment_client import PaymentClient

logger = get_logger(__name__)

PLANS = [
    ("monthly", "월 구독 (₩9,000)", 9000),
    ("yearly", "연간 구독 (20% 할인, ₩86,400)", 86400),
]


class SubscriptionPanel(QWidget):
    def __init__(self, parent=None, gui=None):
        super().__init__(parent)
        self.gui = gui
        self.payment = PaymentClient()
        self.current_payment_id: str | None = None
        self.poll_tries = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_status)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("구독 플랜 선택")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel("브라우저에서 결제 후 상태를 자동 조회합니다.")
        desc.setStyleSheet("color: #64748b;")
        layout.addWidget(desc)

        self.plan_combo = QComboBox()
        for pid, label, price in PLANS:
            self.plan_combo.addItem(label, (pid, price))
        layout.addWidget(self.plan_combo)

        btn_row = QHBoxLayout()
        pay_btn = QPushButton("결제하기")
        pay_btn.clicked.connect(self._checkout)
        btn_row.addWidget(pay_btn)

        cancel_btn = QPushButton("조회 중단")
        cancel_btn.clicked.connect(self._stop_poll)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self.status_label = QLabel("대기 중")
        layout.addWidget(self.status_label)

    def _checkout(self):
        plan_id, price = self.plan_combo.currentData()
        user_id = getattr(self.gui, "login_data", {}).get("user_id") if self.gui else None
        try:
            data = self.payment.create_checkout(plan_id, user_id)
            self.current_payment_id = data["payment_id"]
            checkout_url = data["checkout_url"]
            self.status_label.setText("결제 페이지 오픈…")
            webbrowser.open(checkout_url)
            self._start_poll()
        except Exception as e:
            logger.error(f"[Subscription] checkout create failed: {e}")
            QMessageBox.critical(self, "오류", f"결제 세션 생성 실패:\n{e}")

    def _start_poll(self):
        self.poll_tries = 0
        interval_ms = int(config.CHECKOUT_POLL_INTERVAL * 1000)
        self.timer.start(interval_ms)
        self.status_label.setText("결제 상태 조회 중…")

    def _stop_poll(self):
        self.timer.stop()
        self.status_label.setText("조회 중단")

    def _poll_status(self):
        if not self.current_payment_id:
            self._stop_poll()
            return
        if self.poll_tries >= config.CHECKOUT_POLL_MAX_TRIES:
            self._stop_poll()
            QMessageBox.information(self, "타임아웃", "결제 확인 시간이 초과되었습니다.")
            return
        self.poll_tries += 1
        try:
            data = self.payment.get_status(self.current_payment_id)
            status = data.get("status", "pending")
            self.status_label.setText(f"상태: {status}")
            if status in ("paid", "success", "succeeded"):
                self._stop_poll()
                QMessageBox.information(self, "완료", "결제가 완료되었습니다.")
            elif status in ("failed", "canceled", "cancelled"):
                self._stop_poll()
                QMessageBox.warning(self, "실패", "결제가 실패/취소되었습니다.")
        except Exception as e:
            logger.error(f"[Subscription] status poll failed: {e}")
            self.status_label.setText(f"상태 조회 오류: {e}")
