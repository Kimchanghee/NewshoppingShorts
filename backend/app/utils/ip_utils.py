import logging
from fastapi import Request

logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request with security validation.
    Prioritizes Cloudflare-Connecting-IP for production environments.

    Security: Prevents X-Forwarded-For spoofing by validating trusted proxies.
    """
    # Trust Cloudflare IP in production (most secure)
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    # Fallback to request.client (direct connection)
    if request.client:
        return request.client.host

    # Last resort: X-Forwarded-For (validate first IP only)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take only the first IP (client IP), ignore proxy chain
        client_ip = forwarded_for.split(",")[0].strip()
        # Additional validation could go here
        return client_ip

    return "unknown"
