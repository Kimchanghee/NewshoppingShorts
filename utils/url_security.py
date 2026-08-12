"""Strict URL validation shared by sourcing and download code."""
from __future__ import annotations

import ipaddress
import socket
from typing import Collection, Optional
from urllib.parse import ParseResult, urlparse


COUPANG_HOSTS = frozenset({"coupang.com", "coupa.ng"})
COUPANG_PARTNER_LINK_HOSTS = frozenset({"link.coupang.com", "link.coupa.ng"})


def _normalized_host(url: str) -> tuple[object, str]:
    parsed = urlparse(str(url or "").strip())
    try:
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError:
        host = ""
    return parsed, host


def _host_matches(host: str, allowed_domains: Collection[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def is_official_coupang_url(url: str, *, allow_shortlinks: bool = True) -> bool:
    """Return whether *url* is an official HTTPS Coupang URL.

    Credentials, IP literals, lookalike suffixes and non-standard ports are
    rejected before a browser is allowed to navigate.
    """
    try:
        parsed, host = _normalized_host(url)
        allowed = COUPANG_HOSTS if allow_shortlinks else frozenset({"coupang.com"})
        if parsed.scheme.lower() != "https" or not host or not _host_matches(host, allowed):
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        if parsed.port not in (None, 443):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            return True
    except (TypeError, ValueError):
        return False


def is_coupang_partner_link(url: str) -> bool:
    """Return whether *url* is a Coupang Partners tracking short link.

    A normal ``www.coupang.com`` product page is an official Coupang URL, but
    it is not an affiliate link and must not be accepted by inputs that promise
    commission tracking.  Keep this stricter check separate from
    :func:`is_official_coupang_url`, which is still used for product scraping.
    """
    try:
        parsed, host = _normalized_host(url)
        if (
            parsed.scheme.lower() != "https"
            or host not in COUPANG_PARTNER_LINK_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            return False
        path = str(parsed.path or "").strip("/")
        return bool(path)
    except (TypeError, ValueError):
        return False


def is_public_http_url(
    url: str,
    *,
    allowed_domains: Optional[Collection[str]] = None,
    resolve_dns: bool = True,
) -> bool:
    """Validate a network URL against SSRF and optional domain restrictions."""
    try:
        resolve_public_http_url(
            url,
            allowed_domains=allowed_domains,
            resolve_dns=resolve_dns,
        )
        return True
    except (OSError, TypeError, ValueError, UnicodeError):
        return False


def resolve_public_http_url(
    url: str,
    *,
    allowed_domains: Optional[Collection[str]] = None,
    resolve_dns: bool = True,
) -> tuple[ParseResult, tuple[str, ...]]:
    """Validate *url* and return the exact public IPs approved for connection.

    Callers that open sockets should connect to one of the returned addresses
    while retaining the original hostname for HTTP Host and TLS SNI. This
    prevents a second DNS lookup from turning validation into a rebinding gap.
    """
    parsed, host = _normalized_host(url)
    try:
        if parsed.scheme.lower() not in {"http", "https"} or not host:
            raise ValueError("URL must use HTTP(S) and include a hostname")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URL credentials are not allowed")
        expected_port = 443 if parsed.scheme.lower() == "https" else 80
        if parsed.port not in (None, expected_port):
            raise ValueError("Non-standard ports are not allowed")
        if allowed_domains and not _host_matches(host, {d.lower().rstrip(".") for d in allowed_domains}):
            raise ValueError("URL hostname is not allowlisted")

        addresses: set[str] = set()
        try:
            addresses.add(str(ipaddress.ip_address(host)))
        except ValueError:
            if resolve_dns:
                for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80)):
                    addresses.add(str(info[4][0]).split("%", 1)[0])

        if resolve_dns and not addresses:
            raise ValueError("URL hostname did not resolve")
        for value in addresses:
            address = ipaddress.ip_address(value)
            if not address.is_global:
                raise ValueError("URL resolved to a non-public address")
        return parsed, tuple(sorted(addresses))
    except (OSError, TypeError, ValueError, UnicodeError):
        raise


def require_public_http_url(
    url: str,
    *,
    allowed_domains: Optional[Collection[str]] = None,
    resolve_dns: bool = True,
) -> str:
    if not is_public_http_url(url, allowed_domains=allowed_domains, resolve_dns=resolve_dns):
        raise ValueError(f"안전하지 않거나 허용되지 않은 URL입니다: {str(url or '')[:120]}")
    return str(url).strip()


def is_trusted_service_url(url: str, trusted_base_urls: Collection[str]) -> bool:
    """Check that a URL has the exact HTTPS origin of a trusted service."""
    try:
        candidate = urlparse(str(url or "").strip())
        if (
            candidate.scheme.lower() != "https"
            or not candidate.hostname
            or candidate.username
            or candidate.password
            or candidate.query
            or candidate.fragment
            or candidate.port not in (None, 443)
        ):
            return False
        candidate_origin = ("https", candidate.hostname.lower().rstrip("."), 443)
    except (TypeError, ValueError):
        return False

    for trusted in trusted_base_urls:
        try:
            parsed = urlparse(str(trusted or "").strip())
            if (
                parsed.scheme.lower() != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.port not in (None, 443)
            ):
                continue
            trusted_origin = ("https", parsed.hostname.lower().rstrip("."), 443)
        except (TypeError, ValueError):
            continue
        if candidate_origin == trusted_origin:
            return True
    return False
