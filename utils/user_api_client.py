# -*- coding: utf-8 -*-
"""
User Dashboard API Client
중앙 사용자 관리 서비스 (project-user-dashboard) 연동 클라이언트

Usage:
    from utils.user_api_client import UserDashboardClient

    client = UserDashboardClient(
        base_url="https://your-dashboard-api.run.app",
        program_type="ssmaker"
    )

    # Login
    result = client.login(username="user", password="pass", ip="1.2.3.4")

    # Session check
    session = client.check_session(user_id="user", token="jwt-token", ip="1.2.3.4")

    # Work management
    available = client.check_work(user_id="user", token="jwt-token")
    used = client.use_work(user_id="user", token="jwt-token")
"""

import os
import logging
from typing import Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Default API URL (override with USER_DASHBOARD_API_URL env var)
DEFAULT_API_URL = os.getenv(
    "USER_DASHBOARD_API_URL",
    "https://ssmaker-auth-api-1049571775048.us-central1.run.app"
)


class UserDashboardClient:
    """
    REST API client for the User Dashboard service.
    모든 프로젝트에서 공통으로 사용하는 사용자 관리 API 클라이언트.

    Handles:
    - Authentication (login/logout/session check)
    - Registration
    - Work count management
    - Subscription status
    - Payment sessions
    - User logging
    """

    def __init__(
        self,
        base_url: str = DEFAULT_API_URL,
        program_type: str = "ssmaker",
        timeout: tuple = (10, 30),
        max_retries: int = 3,
    ):
        """
        Initialize the API client.

        Args:
            base_url: User Dashboard API server URL
            program_type: Program identifier (ssmaker, stmaker, etc.)
            timeout: (connect_timeout, read_timeout) in seconds
            max_retries: Maximum retry attempts for transient errors
        """
        self.base_url = base_url.rstrip("/")
        self.program_type = program_type
        self.timeout = timeout

        # Configure session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _url(self, path: str) -> str:
        """Build full URL from path."""
        return f"{self.base_url}{path}"

    def _headers(self, token: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if user_id:
            headers["X-User-ID"] = str(user_id)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        token: Optional[str] = None,
        user_id: Optional[str] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """
        Make an API request with error handling.

        Returns:
            Response JSON dict on success, or error dict on failure.
        """
        url = self._url(path)
        headers = self._headers(token=token, user_id=user_id)

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=timeout or self.timeout,
            )

            if response.status_code == 429:
                logger.warning(f"[API] Rate limited: {path}")
                return {"success": False, "error": {"code": "RATE_LIMIT", "message": "요청이 너무 많습니다."}}

            data = response.json()

            if response.status_code >= 400:
                logger.warning(f"[API] {method} {path} -> {response.status_code}: {data}")

            return data

        except requests.exceptions.ConnectionError:
            logger.error(f"[API] Connection failed: {url}")
            return {"success": False, "error": {"code": "CONNECTION_ERROR", "message": "서버에 연결할 수 없습니다."}}
        except requests.exceptions.Timeout:
            logger.error(f"[API] Timeout: {url}")
            return {"success": False, "error": {"code": "TIMEOUT", "message": "서버 응답 시간 초과."}}
        except requests.exceptions.RequestException as e:
            logger.error(f"[API] Request error: {e}")
            return {"success": False, "error": {"code": "REQUEST_ERROR", "message": str(e)}}
        except ValueError:
            logger.error(f"[API] Invalid JSON response from {url}")
            return {"success": False, "error": {"code": "PARSE_ERROR", "message": "서버 응답을 파싱할 수 없습니다."}}

    # =========================================================================
    # Authentication
    # =========================================================================

    def login(
        self,
        username: str,
        password: str,
        ip: str = "unknown",
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Login user.

        Args:
            username: User ID
            password: User password
            ip: Client IP address
            force: Force login (kick existing session)

        Returns:
            Login response with token on success.
        """
        return self._request("POST", "/user/login/god", json_data={
            "id": username,
            "pw": password,
            "ip": ip,
            "force": force,
        })

    def logout(self, user_id: str, token: str) -> Dict[str, Any]:
        """
        Logout user.

        Args:
            user_id: User ID
            token: JWT token

        Returns:
            Logout result.
        """
        return self._request("POST", "/user/logout/god", json_data={
            "id": user_id,
            "key": token,
        })

    def check_session(
        self,
        user_id: str,
        token: str,
        ip: str = "unknown",
        current_task: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check session validity (heartbeat).

        Args:
            user_id: User ID
            token: JWT token
            ip: Client IP
            current_task: Current task description
            app_version: Client app version

        Returns:
            Session status with valid/invalid and error codes.
        """
        return self._request("POST", "/user/login/god/check", json_data={
            "id": user_id,
            "key": token,
            "ip": ip,
            "current_task": current_task,
            "app_version": app_version,
        }, timeout=(3, 10))

    # =========================================================================
    # Registration
    # =========================================================================

    def register(
        self,
        username: str,
        password: str,
        name: str,
        phone: str,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit registration request.

        Args:
            username: Desired username
            password: Password
            name: Full name
            phone: Phone number
            email: Email address (optional)

        Returns:
            Registration result.
        """
        data = {
            "username": username,
            "password": password,
            "name": name,
            "phone": phone,
            "program_type": self.program_type,
        }
        if email:
            data["email"] = email
        return self._request("POST", "/user/register/request", json_data=data)

    def check_username(self, username: str) -> Dict[str, Any]:
        """
        Check if username is available.

        Args:
            username: Username to check

        Returns:
            {"available": bool, "message": str}
        """
        return self._request("GET", f"/user/check-username/{username}")

    # =========================================================================
    # Work Count Management
    # =========================================================================

    def check_work(self, user_id: str, token: str) -> Dict[str, Any]:
        """
        Check if user can perform work (has remaining count).

        Args:
            user_id: User ID
            token: JWT token

        Returns:
            Work availability status.
        """
        return self._request("POST", "/user/work/check", json_data={
            "user_id": user_id,
            "token": token,
        })

    def use_work(self, user_id: str, token: str) -> Dict[str, Any]:
        """
        Record work usage (increment work_used).

        Args:
            user_id: User ID
            token: JWT token

        Returns:
            Updated work count.
        """
        return self._request("POST", "/user/work/use", json_data={
            "user_id": user_id,
            "token": token,
        })

    # =========================================================================
    # Subscription
    # =========================================================================

    def get_subscription_status(self, user_id: int, token: str) -> Dict[str, Any]:
        """
        Get user's subscription status.

        Args:
            user_id: User ID (integer)
            token: JWT token

        Returns:
            Subscription details (type, remaining, expiry, etc.)
        """
        return self._request(
            "GET",
            f"/user/subscription/my-status?user_id={user_id}",
            token=token,
            user_id=str(user_id),
        )

    def request_subscription(
        self,
        user_id: int,
        plan_type: str = "pro_monthly",
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit subscription request.

        Args:
            user_id: User ID
            plan_type: Subscription plan (pro_monthly, trial, etc.)
            token: JWT token

        Returns:
            Subscription request result.
        """
        return self._request("POST", "/user/subscription/request", json_data={
            "user_id": user_id,
            "plan_type": plan_type,
            "program_type": self.program_type,
        }, token=token, user_id=str(user_id))

    # =========================================================================
    # Payment
    # =========================================================================

    def create_payment_session(
        self,
        user_id: int,
        plan_type: str,
        amount: int,
        buyer_name: str,
        buyer_tel: str,
        method: str = "payapp",
    ) -> Dict[str, Any]:
        """
        Create a payment checkout session.

        Args:
            user_id: User ID
            plan_type: Subscription plan
            amount: Amount in KRW
            buyer_name: Buyer name
            buyer_tel: Buyer phone
            method: Payment method (payapp, simple)

        Returns:
            Payment session with checkout URL.
        """
        if method == "payapp":
            return self._request("POST", "/payments/payapp/create", json_data={
                "user_id": user_id,
                "plan_type": plan_type,
                "amount": amount,
                "buyer_name": buyer_name,
                "buyer_tel": buyer_tel,
            })
        else:
            return self._request("POST", "/payments/create", json_data={
                "user_id": user_id,
                "plan_type": plan_type,
                "amount": amount,
                "buyer_name": buyer_name,
                "buyer_tel": buyer_tel,
            })

    def check_payment_status(self, session_id: str) -> Dict[str, Any]:
        """
        Check payment session status.

        Args:
            session_id: Payment session ID

        Returns:
            Payment status details.
        """
        return self._request("GET", f"/payments/status?session_id={session_id}")

    # =========================================================================
    # Logging
    # =========================================================================

    def log_action(
        self,
        user_id: int,
        action: str,
        content: Optional[str] = None,
        level: str = "INFO",
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Log user action to server.

        Args:
            user_id: User ID
            action: Action description
            content: Additional content/details
            level: Log level (INFO, WARNING, ERROR)
            token: JWT token

        Returns:
            Log creation result.
        """
        return self._request("POST", "/user/logs", json_data={
            "user_id": user_id,
            "action": action,
            "content": content,
            "level": level,
        }, token=token, user_id=str(user_id))

    # =========================================================================
    # Health
    # =========================================================================

    def health_check(self) -> Dict[str, Any]:
        """Check if the API server is healthy."""
        return self._request("GET", "/health", timeout=(3, 5))

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
