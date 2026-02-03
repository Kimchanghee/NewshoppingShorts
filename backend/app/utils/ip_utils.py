"""
IP Utilities
IP 주소 추출 및 검증 유틸리티

Security:
- Validates trusted proxies before trusting X-Forwarded-For
- Prevents IP spoofing attacks for rate limiting bypass
"""
import os
import ipaddress
import logging
from typing import List
from fastapi import Request

logger = logging.getLogger(__name__)


def _get_trusted_proxies() -> List[str]:
    """
    Get list of trusted proxy IPs/CIDRs.

    Returns:
        List of trusted proxy IP addresses or CIDR ranges
    """
    env_proxies = os.environ.get("TRUSTED_PROXIES", "")
    if env_proxies:
        return [p.strip() for p in env_proxies.split(",") if p.strip()]

    # Default trusted ranges:
    # - 127.0.0.1, ::1: Localhost
    # - 10.0.0.0/8: Private network (Cloud Run internal)
    # - 172.16.0.0/12: Private network (Docker, Kubernetes)
    # - 192.168.0.0/16: Private network (local development)
    return [
        "127.0.0.1",
        "::1",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ]


def _is_trusted_proxy(ip: str) -> bool:
    """
    Check if an IP address is from a trusted proxy.

    Args:
        ip: IP address to check

    Returns:
        True if IP is in trusted proxy list
    """
    if not ip:
        return False

    try:
        client_addr = ipaddress.ip_address(ip)
        for proxy in _get_trusted_proxies():
            try:
                if "/" in proxy:
                    # CIDR notation
                    if client_addr in ipaddress.ip_network(proxy, strict=False):
                        return True
                else:
                    # Single IP
                    if client_addr == ipaddress.ip_address(proxy):
                        return True
            except ValueError:
                continue
    except ValueError:
        return False

    return False


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request with security validation.

    Security: Only trusts X-Forwarded-For from trusted proxies to prevent
    IP spoofing attacks that could bypass rate limiting.

    Priority:
    1. If direct IP is from trusted proxy -> use X-Forwarded-For (first non-proxy IP)
    2. If using Cloudflare -> trust CF-Connecting-IP
    3. Otherwise -> use direct connection IP

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address string
    """
    # Get direct connection IP
    direct_ip = request.client.host if request.client else None

    # Only trust forwarded headers if request comes from trusted proxy
    if direct_ip and _is_trusted_proxy(direct_ip):
        # Check X-Forwarded-For (standard proxy header)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For format: "client, proxy1, proxy2"
            # Find first IP that is NOT a trusted proxy (the real client)
            ips = [ip.strip() for ip in forwarded_for.split(",")]
            for ip in ips:
                if ip and not _is_trusted_proxy(ip):
                    return ip
            # If all IPs are proxies, use the first one
            if ips and ips[0]:
                return ips[0]

        # Check Cloudflare header (if using Cloudflare)
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()

    # Fallback to direct connection IP
    if direct_ip:
        return direct_ip

    return "unknown"
