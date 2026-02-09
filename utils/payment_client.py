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
import re

import requests
import config
from utils.logging_config import get_logger

logger = get_logger(__name__)

PAYAPP_OPENPAY_TYPES = frozenset(
    {
        "card",   # 신용카드
        "phone",  # 휴대전화
        "vbank",  # 가상계좌
        "kpay",   # 카카오페이
        "npay",   # 네이버페이
        "sapay",  # 스마일페이
        "apay",   # 애플페이
        "tpay",   # 토스페이
    }
)


class CardApiNotSupportedError(RuntimeError):
    """Raised when server does not provide /payments/payapp/card/* endpoints."""


def _looks_like_missing_card_api(message: str) -> bool:
    """Heuristic check for backend responses indicating missing card billing APIs."""
    text = (message or "").strip().lower()
    if not text:
        return False
    markers = (
        "카드결제 api",
        "카드 결제 api",
        "카드 api",
        "card api",
        "card payment api",
        "card billing api",
        "/payments/payapp/card/",
    )
    if any(marker in text for marker in markers):
        return True
    if "api" not in text:
        return False
    availability_markers = (
        "없",
        "not available",
        "unsupported",
        "missing",
        "unavailable",
        "지원하지",
    )
    return any(marker in text for marker in availability_markers)


def _sanitize_api_message(message: str) -> str:
    """Drop known mojibake patterns so users don't see unreadable text."""
    text = (message or "").strip()
    if not text:
        return ""
    mojibake_markers = (
        "??",
        "野껉퀣",
        "寃곗젣",
        "移대뱶",
        "?붿껌",
        "?ㅽ뙣",
    )
    if any(marker in text for marker in mojibake_markers):
        return ""
    return text


def _normalize_business_error(message: str, fallback: str) -> str:
    """Normalize business-level API errors returned with HTTP 200."""
    clean = _sanitize_api_message(message)
    if clean:
        return clean

    raw = (message or "").strip()
    if raw:
        code_match = re.search(r"PayApp\s*([A-Za-z0-9_-]+)", raw, flags=re.IGNORECASE)
        code_hint = f" (PayApp {code_match.group(1)})" if code_match else ""
        return (
            f"{fallback}{code_hint}. PayApp 응답 메시지를 해석하지 못했습니다. "
            "서버 로그의 errorCode/errorMessage 및 feedbackurl 연결 상태를 확인해주세요."
        )
    return fallback


class PaymentClient:
    def __init__(self):
        self.base_url = config.PAYMENT_API_BASE_URL.rstrip("/")
        # HTTPS 강제 (localhost 제외)
        if not self.base_url.startswith("https://") and "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
            logger.warning("[PaymentClient] PAYMENT_API_BASE_URL is not HTTPS: %s", self.base_url)
            raise RuntimeError("결제 서버 URL은 HTTPS를 사용해야 합니다.")

    def _extract_error_message(self, response: requests.Response, fallback: str) -> str:
        """Extract user-friendly error message from API response."""
        status_code = response.status_code
        detail = ""

        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = (
                    str(
                        payload.get("message")
                        or payload.get("detail")
                        or (payload.get("error") or {}).get("message")
                        or ""
                    )
                    .strip()
                )
            elif isinstance(payload, list) and payload:
                first = payload[0]
                if isinstance(first, dict):
                    detail = str(first.get("msg") or first.get("detail") or "").strip()
        except Exception:
            raw_text = (response.text or "").strip()
            if raw_text:
                detail = raw_text[:200]
        detail = _sanitize_api_message(detail)

        req_url = str(getattr(getattr(response, "request", None), "url", "") or "")
        if status_code == 404 and "/payments/payapp/card/" in req_url:
            return "결제 서버에 카드결제 API가 없습니다. 서버를 최신 버전으로 업데이트해주세요."
        if status_code in (401, 403):
            return "인증이 만료되었거나 권한이 없습니다. 다시 로그인 후 시도해주세요."
        if status_code == 422 and detail:
            return f"입력값 오류: {detail}"
        if status_code >= 500:
            return "결제 서버 내부 오류입니다. 잠시 후 다시 시도해주세요."
        return detail or fallback

    def _raise_http_error(self, err: requests.exceptions.HTTPError, fallback: str) -> None:
        """Raise RuntimeError with extracted API message."""
        response = getattr(err, "response", None)
        if response is None:
            raise RuntimeError(fallback)
        message = self._extract_error_message(response, fallback)
        req_url = str(getattr(getattr(response, "request", None), "url", "") or "")
        is_card_endpoint = "/payments/payapp/card/" in req_url
        if is_card_endpoint and response.status_code == 404:
            raise CardApiNotSupportedError(message)
        if is_card_endpoint and response.status_code in (400, 405, 501):
            if "api" in message.lower():
                raise CardApiNotSupportedError(message)
        if _looks_like_missing_card_api(message):
            raise CardApiNotSupportedError(message)
        raise RuntimeError(message)

    def _raise_business_error(self, message: str, fallback: str) -> None:
        """Raise RuntimeError for non-HTTP API failures with cleaned message."""
        raise RuntimeError(_normalize_business_error(message, fallback))

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
        self,
        user_id: str,
        phone: str,
        plan_id: str = "pro_1month",
        token: str = "",
        payment_type: str | None = None,
    ) -> dict:
        """PayApp 가상계좌 결제 요청 생성.

        Returns dict with keys: success, payment_id, payurl, mul_no, message.
        Raises RuntimeError on server/network failure.
        """
        if not token:
            raise RuntimeError("결제 생성에는 인증 토큰이 필요합니다.")
        if payment_type is not None and payment_type not in PAYAPP_OPENPAY_TYPES:
            raise RuntimeError(f"지원하지 않는 결제 수단입니다: {payment_type}")
        payload = {"user_id": user_id, "phone": phone, "plan_id": plan_id}
        if payment_type:
            payload["payment_type"] = payment_type
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
                self._raise_business_error(data.get("message", ""), "결제 요청 실패")
            return data
        except requests.exceptions.HTTPError as e:
            self._raise_http_error(e, "결제 요청 실패")
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 서버 연결 오류가 발생했습니다. 네트워크 상태를 확인해주세요.")

    def get_status(self, payment_id: str, user_id: str = "", token: str = "") -> dict:
        headers = {}
        if user_id and token:
            headers = self._auth_headers(user_id, token)
        try:
            resp = requests.get(
                f"{self.base_url}/payments/status",
                params={"payment_id": payment_id},
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            self._raise_http_error(e, "결제 상태 조회 실패")
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 상태 조회 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("결제 상태 조회 중 네트워크 오류가 발생했습니다.")

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
                self._raise_business_error(data.get("message", ""), "카드 등록 실패")
            return data
        except requests.exceptions.HTTPError as e:
            self._raise_http_error(e, "카드 등록 실패")
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("카드 등록 중 네트워크 오류가 발생했습니다.")

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
                self._raise_business_error(data.get("message", ""), "카드 결제 실패")
            return data
        except requests.exceptions.HTTPError as e:
            self._raise_http_error(e, "카드 결제 실패")
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("카드 결제 중 네트워크 오류가 발생했습니다.")

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
                self._raise_business_error(data.get("message", ""), "카드 삭제 실패")
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
        except requests.exceptions.HTTPError as e:
            self._raise_http_error(e, "카드 목록 조회 실패")
        except requests.exceptions.Timeout:
            raise RuntimeError("결제 서버 연결 시간 초과")
        except requests.exceptions.RequestException as e:
            logger.error("[PaymentClient] 서버 오류: %s", e)
            raise RuntimeError("카드 목록 조회 중 네트워크 오류가 발생했습니다.")

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
                self._raise_business_error(data.get("message", ""), "정기결제 등록 실패")
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
                self._raise_business_error(data.get("message", ""), "정기결제 취소 실패")
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
                self._raise_business_error(data.get("message", ""), "정기결제 중지 실패")
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
                self._raise_business_error(data.get("message", ""), "정기결제 재개 실패")
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
