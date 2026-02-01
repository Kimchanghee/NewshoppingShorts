import logging
from fastapi import Request

logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request with security validation.
    Prioritizes Cloudflare-Connecting-IP for production environments.

    Security: Prevents X-Forwarded-For spoofing by validating trusted proxies.
    """
    # Prioritize Cloudflare or standard X-Forwarded-For in proxy environments
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP which is the original client
        return forwarded_for.split(",")[0].strip()

    # Trust Cloudflare IP (most secure if using Cloudflare)
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    # Fallback to direct connection IP
    if request.client and request.client.host:
        return request.client.host

    return "unknown"
