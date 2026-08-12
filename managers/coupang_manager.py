"""
Coupang Partners Manager
쿠팡 파트너스 API 연동 및 딥링크 생성 관리자
"""

import hmac
import hashlib
import time
import requests
from typing import Optional
from utils.logging_config import get_logger
from utils.url_security import is_coupang_partner_link, is_official_coupang_url
from managers.settings_manager import get_settings_manager

logger = get_logger(__name__)

class CoupangManager:
    """
    Manages Coupang Partners API interactions.
    Handles HMAC signature generation and Deep Link creation.
    """

    BASE_URL = "https://api-gateway.coupang.com"
    
    def __init__(self):
        self.settings = get_settings_manager()
        self.last_error_message = ""

    def _set_error(self, message: str) -> None:
        self.last_error_message = str(message or "").strip()
        logger.error("[Coupang] %s", self.last_error_message)

    def get_last_error_message(self) -> str:
        """Return a safe, user-facing explanation for the latest API failure."""
        return self.last_error_message or "쿠팡 파트너스 API가 응답하지 않았습니다. 잠시 후 다시 시도해 주세요."

    def _generate_signature(self, method: str, url: str, secret_key: str) -> str:
        """
        Generate HMAC signature for Coupang API authorization.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: API endpoint URL (path only)
            secret_key: Coupang Secret Key
            
        Returns:
            Authorization header string
        """
        date_gmt = time.strftime('%y%m%d', time.gmtime())
        time_gmt = time.strftime('%H%M%S', time.gmtime())
        datetime_msg = date_gmt + 'T' + time_gmt + 'Z'
        
        message = datetime_msg + method + url
        
        signature = hmac.new(
            secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"CEA algorithm=HmacSHA256, access-key={self.settings.get_coupang_keys()['access_key']}, signed-date={datetime_msg}, signature={signature}"

    def generate_deep_link(self, product_url: str) -> Optional[str]:
        """
        Generate a Coupang Partners deep link for a given product URL.
        
        Args:
            product_url: Original Coupang product URL
            
        Returns:
            Shortened Deep Link URL (e.g., https://link.coupang.com/...) or None if failed
        """
        self.last_error_message = ""
        if is_coupang_partner_link(product_url):
            return str(product_url).strip()
        if not is_official_coupang_url(product_url, allow_shortlinks=False):
            self._set_error(
                "입력한 주소가 공식 HTTPS 쿠팡 상품 링크가 아닙니다. "
                "www.coupang.com 상품 주소를 확인해 주세요."
            )
            return None

        keys = self.settings.get_coupang_keys()
        if not keys['access_key'] or not keys['secret_key']:
            self._set_error(
                "쿠팡 파트너스 Access Key 또는 Secret Key가 없습니다. "
                "설정에서 두 키를 모두 저장해 주세요."
            )
            return None

        # API Endpoint for Deep Link
        # Note: The actual endpoint might be /v2/providers/affiliate_sdp/sa/colink for generic links
        # or specific product link generation. Using generic deep link generation here.
        
        api_path = "/v2/providers/affiliate_sdp/sa/deep_link"
        target_url = self.BASE_URL + api_path
        
        # Payload
        payload = {
            "coupangUrls": [product_url]
        }
        
        try:
            auth_header = self._generate_signature("POST", api_path, keys['secret_key'])
            headers = {
                "Authorization": auth_header,
                "Content-Type": "application/json"
            }
            
            response = requests.post(target_url, headers=headers, json=payload, timeout=30)
            if response.status_code in (401, 403):
                self._set_error(
                    "쿠팡 파트너스 인증 또는 API 사용 권한이 거부되었습니다. "
                    "Access/Secret Key와 파트너스 최종 승인 상태를 확인해 주세요."
                )
                return None
            if response.status_code == 429:
                self._set_error(
                    "쿠팡 파트너스 API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."
                )
                return None
            if response.status_code >= 500:
                self._set_error(
                    f"쿠팡 파트너스 서버 장애로 딥링크를 만들지 못했습니다 (HTTP {response.status_code}). "
                    "잠시 후 다시 시도해 주세요."
                )
                return None
            if response.status_code >= 400:
                self._set_error(
                    f"쿠팡 파트너스 요청이 거부되었습니다 (HTTP {response.status_code}). "
                    "상품 링크와 API 설정을 확인해 주세요."
                )
                return None
            
            result = response.json()
            
            # Parse response
            # Response format example: {"rCode": "0", "rMessage": "", "data": [{"originalUrl": "...", "shortenUrl": "..."}]}
            if result.get("rCode") == "0" and result.get("data"):
                short_url = result["data"][0].get("shortenUrl")
                if is_coupang_partner_link(short_url):
                    logger.info("[Coupang] Deep link generated successfully.")
                    return short_url
                self._set_error("쿠팡 파트너스 응답에 유효한 추적 링크가 없습니다. 잠시 후 다시 시도해 주세요.")
                return None
            else:
                code = str(result.get("rCode") or "알 수 없음")
                message = str(result.get("rMessage") or "응답 데이터 없음").strip()[:160]
                self._set_error(f"쿠팡 파트너스 API 오류 ({code}): {message}")
                return None

        except requests.Timeout:
            self._set_error("쿠팡 파트너스 서버 응답 시간이 초과되었습니다. 네트워크를 확인하고 다시 시도해 주세요.")
            return None
        except requests.ConnectionError:
            self._set_error("쿠팡 파트너스 서버에 연결할 수 없습니다. 인터넷 연결 또는 서비스 장애를 확인해 주세요.")
            return None
        except (ValueError, KeyError, TypeError) as e:
            self._set_error(f"쿠팡 파트너스 응답 형식을 해석하지 못했습니다: {type(e).__name__}")
            return None
        except requests.RequestException as e:
            self._set_error(f"쿠팡 파트너스 요청 처리 중 네트워크 오류가 발생했습니다: {type(e).__name__}")
            return None
        except Exception as e:
            self._set_error(f"쿠팡 파트너스 딥링크 생성 중 오류가 발생했습니다: {type(e).__name__}")
            return None

    def check_connection(self) -> bool:
        """
        Check if API keys are valid by making a test request.
        """
        # Test with a generic page (e.g., Goldbox)
        test_url = "https://www.coupang.com/np/goldbox"
        link = self.generate_deep_link(test_url)
        return link is not None

    def is_connected(self) -> bool:
        """Return whether Coupang credentials are configured."""
        keys = self.settings.get_coupang_keys()
        return bool(keys["access_key"] and keys["secret_key"])

# Global instance
_coupang_manager: Optional[CoupangManager] = None

def get_coupang_manager() -> CoupangManager:
    global _coupang_manager
    if _coupang_manager is None:
        _coupang_manager = CoupangManager()
    return _coupang_manager
