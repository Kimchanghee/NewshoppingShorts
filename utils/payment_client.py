"""
Generic payment client for web-based checkout + status polling.
Server endpoints expected:
  POST /payments/create -> {payment_id, checkout_url}
  GET  /payments/status?payment_id=... -> {status, ...}
"""
import requests
import config
from utils.logging_config import get_logger

logger = get_logger(__name__)


class PaymentClient:
    def __init__(self):
        self.base_url = config.PAYMENT_API_BASE_URL.rstrip("/")

    def create_checkout(self, plan_id: str, user_id: str | None = None) -> dict:
        payload = {"plan_id": plan_id, "user_id": user_id}
        resp = requests.post(f"{self.base_url}/payments/create", json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "payment_id" not in data or "checkout_url" not in data:
            raise RuntimeError("payment_id or checkout_url missing in response")
        return data

    def get_status(self, payment_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/payments/status", params={"payment_id": payment_id}, timeout=10)
        resp.raise_for_status()
        return resp.json()
