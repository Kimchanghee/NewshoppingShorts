"""
Payment client for web-based checkout + status polling + PayApp 가상계좌.
Server endpoints expected:
  POST /payments/create -> {payment_id, checkout_url}
  POST /payments/payapp/create -> {payment_id, payurl, mul_no}
  GET  /payments/status?payment_id=... -> {status, ...}
"""
import requests
import config
from utils.logging_config import get_logger

logger = get_logger(__name__)


class PaymentClient:
    def __init__(self):
        self.base_url = config.PAYMENT_API_BASE_URL.rstrip("/")
        # HTTPS 강제 (localhost 제외)
        if not self.base_url.startswith("https://") and "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
            logger.warning("[PaymentClient] PAYMENT_API_BASE_URL is not HTTPS: %s", self.base_url)
            raise RuntimeError("결제 서버 URL은 HTTPS를 사용해야 합니다.")

    def create_checkout(self, plan_id: str, user_id: str | None = None) -> dict:
        payload = {"plan_id": plan_id, "user_id": user_id}
        resp = requests.post(
            f"{self.base_url}/payments/create", json=payload, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        if "payment_id" not in data or "checkout_url" not in data:
            raise RuntimeError("payment_id or checkout_url missing in response")
        return data

    def create_payapp_checkout(
        self, user_id: str, phone: str, plan_id: str = "pro_1month", token: str | None = None
    ) -> dict:
        """PayApp 가상계좌 결제 요청 생성.

        Returns dict with keys: success, payment_id, payurl, mul_no, message.
        Raises RuntimeError on server/network failure.
        """
        payload = {"user_id": user_id, "phone": phone, "plan_id": plan_id}
        headers = {}
        if token:
            headers["X-User-ID"] = str(user_id)
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = requests.post(
                f"{self.base_url}/payments/payapp/create",
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "결제 요청 실패"))
            return data
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"결제 서버 오류: {e}")

    def get_status(self, payment_id: str) -> dict:
        resp = requests.get(
            f"{self.base_url}/payments/status",
            params={"payment_id": payment_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
