"""
Payment client for web-based checkout + status polling + PayApp 가상계좌/카드/정기결제.
Server endpoints expected:
  POST /payments/create -> {payment_id, checkout_url}
  POST /payments/payapp/create -> {payment_id, payurl, mul_no}
  GET  /payments/status?payment_id=... -> {status, ...}
  POST /payments/payapp/card/register -> {success, card_id, ...}
  POST /payments/payapp/card/pay -> {success, payment_id, mul_no}
  POST /payments/payapp/card/delete -> {success, message}
  GET  /payments/payapp/card/list -> {success, cards: [...]}
  POST /payments/payapp/subscribe -> {success, rebill_no, payurl}
  POST /payments/payapp/subscribe/cancel -> {success, message}
  POST /payments/payapp/subscribe/stop -> {success, message}
  POST /payments/payapp/subscribe/start -> {success, message}
  GET  /payments/payapp/subscribe/status -> {success, subscriptions: [...]}
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

    def create_checkout(
        self, plan_id: str, user_id: str | None = None, token: str | None = None
    ) -> dict:
        if not user_id or not token:
            raise RuntimeError("결제 세션 생성에는 사용자 인증 정보가 필요합니다.")
        payload = {"plan_id": plan_id, "user_id": user_id}
        headers = {}
        headers["X-User-ID"] = str(user_id)
        headers["Authorization"] = f"Bearer {token}"
        resp = requests.post(
            f"{self.base_url}/payments/create", json=payload, headers=headers, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        if "payment_id" not in data or "checkout_url" not in data:
            raise RuntimeError("payment_id or checkout_url missing in response")
        return data

    def create_payapp_checkout(
        self, user_id: str, phone: str, plan_id: str = "pro_1month", token: str = ""
    ) -> dict:
        """PayApp 가상계좌 결제 요청 생성.

        Returns dict with keys: success, payment_id, payurl, mul_no, message.
        Raises RuntimeError on server/network failure.
        """
        if not token:
            raise RuntimeError("결제 생성에는 인증 토큰이 필요합니다.")
        payload = {"user_id": user_id, "phone": phone, "plan_id": plan_id}
        headers = self._auth_headers(user_id, token)
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
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    def get_status(self, payment_id: str, user_id: str = "", token: str = "") -> dict:
        headers = {}
        if user_id and token:
            headers = self._auth_headers(user_id, token)
        resp = requests.get(
            f"{self.base_url}/payments/status",
            params={"payment_id": payment_id},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    # ─────────────────────────────────────────────
    # 카드 결제 API (Card Payment API)
    # ─────────────────────────────────────────────

    def _auth_headers(self, user_id: str, token: str) -> dict:
        """인증 헤더 생성 헬퍼"""
        return {
            "X-User-ID": str(user_id),
            "Authorization": f"Bearer {token}",
        }

    def register_card(
        self,
        user_id: str,
        card_no: str,
        exp_month: str,
        exp_year: str,
        buyer_auth_no: str,
        card_pw: str,
        buyer_phone: str,
        buyer_name: str,
        token: str,
    ) -> dict:
        """카드 등록 (빌링키 발급).

        Returns dict with keys: success, card_id, card_no_masked, card_name.
        Raises RuntimeError on server/network failure.
        """
        payload = {
            "user_id": user_id,
            "card_no": card_no,
            "exp_month": exp_month,
            "exp_year": exp_year,
            "buyer_auth_no": buyer_auth_no,
            "card_pw": card_pw,
            "buyer_phone": buyer_phone,
            "buyer_name": buyer_name,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/payments/payapp/card/register",
                json=payload,
                headers=self._auth_headers(user_id, token),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "카드 등록 실패"))
            return data
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    def pay_with_card(
        self, user_id: str, card_id: int, plan_id: str, phone: str, token: str
    ) -> dict:
        """등록된 카드로 결제.

        Returns dict with keys: success, payment_id, mul_no.
        Raises RuntimeError on server/network failure.
        """
        payload = {
            "user_id": user_id,
            "card_id": card_id,
            "plan_id": plan_id,
            "phone": phone,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/payments/payapp/card/pay",
                json=payload,
                headers=self._auth_headers(user_id, token),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "카드 결제 실패"))
            return data
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    def delete_card(self, user_id: str, card_id: int, token: str) -> dict:
        """등록된 카드 삭제.

        Returns dict with keys: success, message.
        Raises RuntimeError on server/network failure.
        """
        payload = {"user_id": user_id, "card_id": card_id}
        try:
            resp = requests.post(
                f"{self.base_url}/payments/payapp/card/delete",
                json=payload,
                headers=self._auth_headers(user_id, token),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "카드 삭제 실패"))
            return data
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    def list_cards(self, user_id: str, token: str) -> dict:
        """등록된 카드 목록 조회.

        Returns dict with keys: success, cards (list).
        Raises RuntimeError on server/network failure.
        """
        try:
            resp = requests.get(
                f"{self.base_url}/payments/payapp/card/list",
                headers=self._auth_headers(user_id, token),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    # ─────────────────────────────────────────────
    # 정기결제 API (Recurring Subscription API)
    # ─────────────────────────────────────────────

    def create_subscription(
        self,
        user_id: str,
        phone: str,
        plan_id: str,
        cycle_type: str = "Month",
        cycle_day: int = 1,
        expire_date: str | None = None,
        token: str | None = None,
    ) -> dict:
        """정기결제 구독 생성.

        Returns dict with keys: success, rebill_no, payurl.
        Raises RuntimeError on server/network failure.
        """
        if not token:
            raise RuntimeError("정기결제 생성에는 인증 토큰이 필요합니다.")
        payload = {
            "user_id": user_id,
            "phone": phone,
            "plan_id": plan_id,
            "cycle_type": cycle_type,
            "cycle_day": cycle_day,
        }
        if expire_date:
            payload["expire_date"] = expire_date
        try:
            resp = requests.post(
                f"{self.base_url}/payments/payapp/subscribe",
                json=payload,
                headers=self._auth_headers(user_id, token),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "정기결제 등록 실패"))
            return data
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    def cancel_subscription(self, user_id: str, rebill_no: str, token: str) -> dict:
        """정기결제 취소.

        Returns dict with keys: success, message.
        Raises RuntimeError on server/network failure.
        """
        payload = {"user_id": user_id, "rebill_no": rebill_no}
        try:
            resp = requests.post(
                f"{self.base_url}/payments/payapp/subscribe/cancel",
                json=payload,
                headers=self._auth_headers(user_id, token),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "정기결제 취소 실패"))
            return data
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    def stop_subscription(self, user_id: str, rebill_no: str, token: str) -> dict:
        """정기결제 일시중지.

        Returns dict with keys: success, message.
        Raises RuntimeError on server/network failure.
        """
        payload = {"user_id": user_id, "rebill_no": rebill_no}
        try:
            resp = requests.post(
                f"{self.base_url}/payments/payapp/subscribe/stop",
                json=payload,
                headers=self._auth_headers(user_id, token),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "정기결제 중지 실패"))
            return data
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    def start_subscription(self, user_id: str, rebill_no: str, token: str) -> dict:
        """정기결제 재개.

        Returns dict with keys: success, message.
        Raises RuntimeError on server/network failure.
        """
        payload = {"user_id": user_id, "rebill_no": rebill_no}
        try:
            resp = requests.post(
                f"{self.base_url}/payments/payapp/subscribe/start",
                json=payload,
                headers=self._auth_headers(user_id, token),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(data.get("message", "정기결제 재개 실패"))
            return data
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")

    def get_subscription_status(self, user_id: str, token: str) -> dict:
        """정기결제 구독 상태 조회.

        Returns dict with keys: success, subscriptions (list).
        Raises RuntimeError on server/network failure.
        """
        try:
            resp = requests.get(
                f"{self.base_url}/payments/payapp/subscribe/status",
                headers=self._auth_headers(user_id, token),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 오류가 발생했습니다. 다시 시도해주세요.")
