"""Strict URL validation shared by sourcing and download code."""
from __future__ import annotations

from bisect import bisect_right
import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Collection, List, Optional
from urllib.parse import ParseResult, urlparse, urlsplit


COUPANG_HOSTS = frozenset({"coupang.com", "coupa.ng"})
COUPANG_PARTNER_LINK_HOSTS = frozenset({"link.coupang.com", "link.coupa.ng"})
_URL_EDGE_FORMAT_CHARS = "\ufeff\u200b\u200c\u200d\u2060"
_HTTP_SCHEME_PATTERN = re.compile(r"https?://", re.IGNORECASE)
_URL_HARD_BOUNDARIES = frozenset("<>[]{}()\"'`")
_URL_TRAILING_SENTENCE_PUNCTUATION = ".,;:!，。；：！"
_PARTNER_PATH_PATTERN = re.compile(r"/a/[A-Za-z0-9_-]+/?")
_PARTNER_CODE_CONTINUATION_PATTERN = re.compile(r"[A-Za-z0-9_-]{2,}")

MAX_PARTNER_LINK_INPUT_LENGTH = 65_536
MAX_PARTNER_LINK_HTTP_TOKENS = 100
COUPANG_PARTNER_LINK_CONTRACT_SCHEMA_VERSION = 1
COUPANG_PARTNER_LINK_CONTRACT_ID = "coupang-partner-link-v1"

PARTNER_LINK_REASON_OK = "ok"
PARTNER_LINK_REASON_EMPTY = "empty"
PARTNER_LINK_REASON_NORMAL_PRODUCT = "normal_coupang_product"
PARTNER_LINK_REASON_INVALID = "invalid_partner_link"
PARTNER_LINK_REASON_MIXED = "mixed_http_urls"
PARTNER_LINK_REASON_UNSUPPORTED = "unsupported_url"
PARTNER_LINK_REASON_INPUT_TOO_LARGE = "input_too_large"
PARTNER_LINK_REASON_TOO_MANY = "too_many_links"


@dataclass(frozen=True)
class PartnerLinkParseResult:
    """Immutable result shared by every Coupang partner-link entry point."""

    links: tuple[str, ...]
    reason_code: str
    raw_length: int
    boundary_format_character_count: int


@dataclass(frozen=True)
class _HttpToken:
    value: str
    has_safe_left_boundary: bool
    has_safe_right_boundary: bool


def _normalized_url_input(url: str) -> str:
    """Normalize clipboard-only edge characters without rewriting the URL.

    KakaoTalk, web mail and rich-text editors can place a BOM or zero-width
    formatting character before a copied URL.  Those characters are invisible
    in ``QLineEdit`` but make ``urlparse`` miss the HTTPS scheme.  Only boundary
    format characters are removed.  Embedded whitespace is rejected so several
    pasted links can never be misread as one valid URL.
    """
    text = str(url or "")
    previous = None
    while text != previous:
        previous = text
        text = text.strip().strip(_URL_EDGE_FORMAT_CHARS)
    if any(char.isspace() for char in text):
        return ""
    return text


def _strip_partner_input_boundaries(value: object) -> tuple[str, int, int]:
    """Strip only harmless outer clipboard characters and report what changed."""
    raw = str(value or "")
    start = 0
    end = len(raw)
    format_character_count = 0
    while start < end and (
        raw[start].isspace() or raw[start] in _URL_EDGE_FORMAT_CHARS
    ):
        if raw[start] in _URL_EDGE_FORMAT_CHARS:
            format_character_count += 1
        start += 1
    while end > start and (
        raw[end - 1].isspace() or raw[end - 1] in _URL_EDGE_FORMAT_CHARS
    ):
        if raw[end - 1] in _URL_EDGE_FORMAT_CHARS:
            format_character_count += 1
        end -= 1
    return raw[start:end], len(raw), format_character_count


def _is_safe_http_token_left_boundary(text: str, start: int) -> bool:
    if start <= 0:
        return True
    previous = text[start - 1]
    if previous.isspace():
        return True
    if previous in _URL_EDGE_FORMAT_CHARS:
        return False
    return not (previous.isalnum() or previous in "_/@?&=#")


def _looks_like_split_partner_code(text: str, token_end: int) -> bool:
    """Catch a partner code split by an embedded whitespace run."""
    cursor = token_end
    saw_space = False
    while cursor < len(text) and text[cursor].isspace():
        saw_space = True
        cursor += 1
    if not saw_space:
        return False
    if text[cursor : cursor + 7].lower() in {"http://", "https:/"}:
        return False
    match = _PARTNER_CODE_CONTINUATION_PATTERN.match(text, cursor)
    # Any bare ASCII continuation immediately after whitespace is ambiguous:
    # it may be the rest of a split, case-sensitive partner code.  Reject it
    # regardless of later prose or links instead of forwarding the truncated
    # prefix downstream.
    return match is not None


def _collect_http_tokens(text: str) -> list[_HttpToken]:
    """Collect every HTTP(S) occurrence before validating any allowlisted URL.

    Starts are intentionally allowed to overlap an earlier URL token.  That
    makes a nested value such as ``evil/?next=https://link.coupang.com/...``
    visible as mixed input instead of accepting the allowlisted substring.
    """
    tokens: list[_HttpToken] = []
    boundary_positions = [
        index
        for index, character in enumerate(text)
        if character.isspace() or character in _URL_HARD_BOUNDARIES
    ]
    boundary_positions.append(len(text))
    split_code_cache: dict[int, bool] = {}
    for match in _HTTP_SCHEME_PATTERN.finditer(text):
        start = match.start()
        end = boundary_positions[bisect_right(boundary_positions, start)]
        candidate = text[start:end].rstrip(_URL_TRAILING_SENTENCE_PUNCTUATION)
        if not candidate:
            continue
        if end not in split_code_cache:
            split_code_cache[end] = _looks_like_split_partner_code(text, end)
        tokens.append(
            _HttpToken(
                value=candidate,
                has_safe_left_boundary=_is_safe_http_token_left_boundary(text, start),
                has_safe_right_boundary=not split_code_cache[end],
            )
        )
        # The caller only needs to distinguish inputs up to the public token
        # limit.  Stop at the first overflow sentinel so a malicious string
        # containing thousands of nested ``https://`` markers cannot make the
        # UI rescan the same 65 KiB token thousands of times.
        if len(tokens) > MAX_PARTNER_LINK_HTTP_TOKENS:
            break
    return tokens


def _split_host(token: str) -> tuple[object, str]:
    parsed = urlsplit(token)
    try:
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
    except UnicodeError:
        host = ""
    return parsed, host


def _is_valid_partner_http_token(token: _HttpToken) -> bool:
    if not token.has_safe_left_boundary or not token.has_safe_right_boundary:
        return False
    try:
        parsed, host = _split_host(token.value)
        if (
            parsed.scheme.lower() != "https"
            or host not in COUPANG_PARTNER_LINK_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or "?" in token.value
            or "#" in token.value
            or parsed.query
            or parsed.fragment
        ):
            return False
        return _PARTNER_PATH_PATTERN.fullmatch(str(parsed.path or "")) is not None
    except (TypeError, ValueError):
        return False


def _classify_single_http_token(token: _HttpToken) -> str:
    if _is_valid_partner_http_token(token):
        return PARTNER_LINK_REASON_OK
    try:
        _parsed, host = _split_host(token.value)
    except (TypeError, ValueError):
        return PARTNER_LINK_REASON_UNSUPPORTED
    if host in COUPANG_PARTNER_LINK_HOSTS:
        return PARTNER_LINK_REASON_INVALID
    if _host_matches(host, COUPANG_HOSTS):
        return PARTNER_LINK_REASON_NORMAL_PRODUCT
    return PARTNER_LINK_REASON_UNSUPPORTED


def parse_coupang_partner_links(value: object) -> PartnerLinkParseResult:
    """Parse partner links using the shared, fail-closed input contract."""
    text, raw_length, boundary_format_count = _strip_partner_input_boundaries(value)

    def result(links: tuple[str, ...], reason_code: str) -> PartnerLinkParseResult:
        return PartnerLinkParseResult(
            links=links,
            reason_code=reason_code,
            raw_length=raw_length,
            boundary_format_character_count=boundary_format_count,
        )

    if not text:
        return result((), PARTNER_LINK_REASON_EMPTY)
    if raw_length > MAX_PARTNER_LINK_INPUT_LENGTH:
        return result((), PARTNER_LINK_REASON_INPUT_TOO_LARGE)

    tokens = _collect_http_tokens(text)
    if len(tokens) > MAX_PARTNER_LINK_HTTP_TOKENS:
        return result((), PARTNER_LINK_REASON_TOO_MANY)
    if not tokens:
        return result((), PARTNER_LINK_REASON_UNSUPPORTED)

    classifications = [_classify_single_http_token(token) for token in tokens]
    if len(tokens) == 1:
        if classifications[0] != PARTNER_LINK_REASON_OK:
            return result((), classifications[0])
    elif any(reason != PARTNER_LINK_REASON_OK for reason in classifications):
        return result((), PARTNER_LINK_REASON_MIXED)

    links: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token.value in seen:
            continue
        seen.add(token.value)
        links.append(token.value)
    return result(tuple(links), PARTNER_LINK_REASON_OK)


def build_coupang_partner_link_contract_report() -> dict:
    """Build the stable source/frozen/installed parser smoke projection."""
    cases = (
        (
            "reported_partner_link",
            "https://link.coupang.com/a/f8i3PuVSqi",
            True,
            ("https://link.coupang.com/a/f8i3PuVSqi",),
            PARTNER_LINK_REASON_OK,
        ),
        (
            "partner_code_case_preserved",
            "\ufeff https://link.coupang.com/a/AbC_9-xYz \u200b",
            True,
            ("https://link.coupang.com/a/AbC_9-xYz",),
            PARTNER_LINK_REASON_OK,
        ),
        (
            "decorated_markdown_link",
            "상품 보기: [링크](https://link.coupang.com/a/Markdown9).",
            True,
            ("https://link.coupang.com/a/Markdown9",),
            PARTNER_LINK_REASON_OK,
        ),
        (
            "multiple_links_order_and_deduplication",
            (
                "첫째 https://link.coupang.com/a/First9, 둘째 "
                "https://link.coupa.ng/a/Second8 그리고 중복 "
                "https://link.coupang.com/a/First9"
            ),
            True,
            (
                "https://link.coupang.com/a/First9",
                "https://link.coupa.ng/a/Second8",
            ),
            PARTNER_LINK_REASON_OK,
        ),
        (
            "normal_coupang_product_rejected",
            "https://www.coupang.com/vp/products/123",
            False,
            (),
            PARTNER_LINK_REASON_NORMAL_PRODUCT,
        ),
        (
            "http_partner_link_rejected",
            "http://link.coupang.com/a/good",
            False,
            (),
            PARTNER_LINK_REASON_INVALID,
        ),
        (
            "lookalike_host_rejected",
            "https://link.coupang.com.evil.example/a/good",
            False,
            (),
            PARTNER_LINK_REASON_UNSUPPORTED,
        ),
        (
            "nested_partner_link",
            "https://evil.example/?next=https://link.coupang.com/a/good",
            False,
            (),
            PARTNER_LINK_REASON_MIXED,
        ),
        (
            "partner_query_rejected",
            "https://link.coupang.com/a/good?next=1",
            False,
            (),
            PARTNER_LINK_REASON_INVALID,
        ),
        (
            "partner_fragment_rejected",
            "https://link.coupang.com/a/good#fragment",
            False,
            (),
            PARTNER_LINK_REASON_INVALID,
        ),
        (
            "partner_path_suffix_rejected",
            "https://link.coupang.com/a/good.evil",
            False,
            (),
            PARTNER_LINK_REASON_INVALID,
        ),
        (
            "internal_zero_width_rejected",
            "https://link.coupang.com/a/go\u200bod",
            False,
            (),
            PARTNER_LINK_REASON_INVALID,
        ),
        (
            "mixed_http_urls_rejected",
            "https://link.coupang.com/a/good https://example.com/other",
            False,
            (),
            PARTNER_LINK_REASON_MIXED,
        ),
    )
    report_cases = []
    contract_ok = True
    for case_id, raw, expected_accepted, expected_links, expected_reason in cases:
        parsed = parse_coupang_partner_links(raw)
        accepted = parsed.reason_code == PARTNER_LINK_REASON_OK
        report_cases.append(
            {
                "id": case_id,
                "accepted": accepted,
                "links": list(parsed.links),
                "reason_code": parsed.reason_code,
            }
        )
        contract_ok = contract_ok and (
            accepted == expected_accepted
            and parsed.links == expected_links
            and parsed.reason_code == expected_reason
        )
    return {
        "schema_version": COUPANG_PARTNER_LINK_CONTRACT_SCHEMA_VERSION,
        "contract_id": COUPANG_PARTNER_LINK_CONTRACT_ID,
        "ok": contract_ok,
        "cases": report_cases,
    }


def _normalized_host(url: str) -> tuple[object, str]:
    parsed = urlparse(_normalized_url_input(url))
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
    normalized = _normalized_url_input(url)
    return bool(
        normalized
        and _is_valid_partner_http_token(
            _HttpToken(normalized, True, True)
        )
    )


def normalize_coupang_partner_link(url: str) -> str:
    """Return one clipboard-safe partner link, or an empty string.

    A copied link is often wrapped in a messenger label, Markdown, brackets,
    or punctuation.  Accept that common single-link form while continuing to
    reject input containing more than one URL.  The short-link code is never
    lower-cased or rewritten because it is case-sensitive.
    """
    parsed = parse_coupang_partner_links(url)
    return parsed.links[0] if len(parsed.links) == 1 else ""


def extract_coupang_partner_links(value: str) -> List[str]:
    """Extract valid Partners links from pasted plain or decorated text.

    This intentionally recognizes only the official ``/a/{code}`` short-link
    shape.  It is suitable for multi-line clipboard input and preserves both
    input order and the exact case of every link code.
    """
    return list(parse_coupang_partner_links(value).links)


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
