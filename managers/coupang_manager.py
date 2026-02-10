"""
Coupang Partners Manager
쿠팡 파트너스 API 연동 및 딥링크 생성 관리자
"""

import hmac
import hashlib
import time
import requests
import json
import urllib.parse
from typing import Dict, Optional
from utils.logging_config import get_logger
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
        keys = self.settings.get_coupang_keys()
        if not keys['access_key'] or not keys['secret_key']:
            logger.error("[Coupang] API keys are missing.")
            return None

        # API Endpoint for Deep Link
        # Note: The actual endpoint might be /v2/providers/affiliate_sdp/sa/colink for generic links
        # or specific product link generation. Using generic deep link generation here.
        
        # Validating URL format just in case
        if "coupang.com" not in product_url:
            logger.warning(f"[Coupang] Invalid Coupang URL: {product_url}")
            return None

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
            
            response = requests.post(target_url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Parse response
            # Response format example: {"rCode": "0", "rMessage": "", "data": [{"originalUrl": "...", "shortenUrl": "..."}]}
            if result.get("rCode") == "0" and result.get("data"):
                short_url = result["data"][0].get("shortenUrl")
                logger.info(f"[Coupang] Deep link generated: {short_url}")
                return short_url
            else:
                logger.error(f"[Coupang] API Error: {result}")
                return None
                
        except Exception as e:
            logger.error(f"[Coupang] Failed to generate deep link: {e}")
            return None

    def check_connection(self) -> bool:
        """
        Check if API keys are valid by making a test request.
        """
        # Test with a generic page (e.g., Goldbox)
        test_url = "https://www.coupang.com/np/goldbox"
        link = self.generate_deep_link(test_url)
        return link is not None

# Global instance
_coupang_manager: Optional[CoupangManager] = None

def get_coupang_manager() -> CoupangManager:
    global _coupang_manager
    if _coupang_manager is None:
        _coupang_manager = CoupangManager()
    return _coupang_manager
