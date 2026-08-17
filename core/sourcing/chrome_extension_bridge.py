# -*- coding: utf-8 -*-
"""Small, local-only bridge between SSMaker and its Chrome extension.

The extension never receives cookies, passwords, or arbitrary Python commands.
SSMaker sends only a platform plus a search phrase, and accepts only canonical
short-video page links in return.  Communication is bound to 127.0.0.1 and is
protected by a one-time pairing code and a persistent random bearer token.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_CHROME_BRIDGE_PORT = 38471
MAX_REQUEST_BYTES = 128 * 1024
CONNECTION_FRESH_SECONDS = 75.0
MAX_TASK_WAIT_SECONDS = 25.0

_EXTENSION_ORIGIN_RE = re.compile(r"^chrome-extension://[a-p]{32}$")
_VIDEO_LINK_PATTERNS = {
    "douyin": re.compile(r"^https://www\.douyin\.com/video/\d{10,25}(?:[/?#].*)?$"),
    "kuaishou": re.compile(
        r"^https://www\.kuaishou\.com/short-video/[0-9A-Za-z_-]{8,}(?:[/?#].*)?$"
    ),
    "xiaohongshu": re.compile(
        r"^https://www\.xiaohongshu\.com/explore/[0-9a-f]{20,}(?:[/?#].*)?$"
    ),
}


class _ExclusiveLoopbackServer(ThreadingHTTPServer):
    """Prevent two SSMaker processes from both claiming the bridge port."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_EXCLUSIVEADDRUSE,
                1,
            )
        super().server_bind()


def _default_storage_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".ssmaker"


def _token_digest(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _valid_extension_origin(origin: str) -> bool:
    return bool(_EXTENSION_ORIGIN_RE.fullmatch(str(origin or "").strip()))


def _canonical_links(platform: str, values: Iterable[Any]) -> List[str]:
    pattern = _VIDEO_LINK_PATTERNS.get(str(platform or "").lower())
    if pattern is None:
        return []
    out: List[str] = []
    seen = set()
    for raw in values or []:
        value = str(raw or "").strip()
        if not pattern.fullmatch(value):
            continue
        canonical = value.split("?", 1)[0].split("#", 1)[0].rstrip("/")
        if canonical in seen:
            continue
        seen.add(canonical)
        out.append(canonical)
        if len(out) >= 30:
            break
    return out


class ChromeExtensionBridge:
    """Thread-safe localhost task broker used by the MV3 extension."""

    def __init__(self, storage_dir: Optional[Path] = None, port: Optional[int] = None):
        self.storage_dir = Path(storage_dir or _default_storage_dir())
        self.port = int(
            port
            if port is not None
            else os.getenv("SSMAKER_CHROME_BRIDGE_PORT", DEFAULT_CHROME_BRIDGE_PORT)
        )
        self._state_path = self.storage_dir / "chrome_extension_pairing.json"
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._tasks: Deque[Dict[str, Any]] = deque()
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._paired_origin = ""
        self._token_hash = ""
        self._client_token = ""
        self._proxy_mode = False
        self._last_seen = 0.0
        self._pairing_code = f"{secrets.randbelow(1_000_000):06d}"
        self._load_state()

    @property
    def pairing_code(self) -> str:
        return self._pairing_code

    def extension_directory(self) -> Path:
        candidates: List[Path] = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "browser-extension")
            bundle_root = getattr(sys, "_MEIPASS", "")
            if bundle_root:
                candidates.append(Path(bundle_root) / "browser-extension")
        candidates.append(Path(__file__).resolve().parents[2] / "browser-extension")
        return next((path for path in candidates if path.is_dir()), candidates[-1])

    def _load_state(self) -> None:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            origin = str(payload.get("origin") or "").strip()
            token_hash = str(payload.get("token_hash") or "").strip().lower()
            client_token = str(payload.get("client_token") or "").strip()
            if _valid_extension_origin(origin) and re.fullmatch(r"[0-9a-f]{64}", token_hash):
                self._paired_origin = origin
                self._token_hash = token_hash
            if re.fullmatch(r"[A-Za-z0-9_-]{32,}", client_token):
                self._client_token = client_token
        except (OSError, ValueError, TypeError):
            return

    def _save_state(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self._state_path.with_suffix(".tmp")
        payload = {
            "origin": self._paired_origin,
            "token_hash": self._token_hash,
            # This token is for same-user localhost worker processes only.  It
            # never grants extension access and never leaves 127.0.0.1.
            "client_token": self._client_token,
            "updated_at": int(time.time()),
        }
        temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, self._state_path)

    def pair(self, origin: str, code: str) -> Optional[str]:
        origin = str(origin or "").strip()
        if not _valid_extension_origin(origin):
            return None
        if not hmac.compare_digest(str(code or "").strip(), self._pairing_code):
            return None
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._paired_origin = origin
            self._token_hash = _token_digest(token)
            self._last_seen = time.monotonic()
            self._pairing_code = f"{secrets.randbelow(1_000_000):06d}"
            self._save_state()
        return token

    def authenticate(self, origin: str, authorization: str) -> bool:
        if not self._paired_origin or str(origin or "").strip() != self._paired_origin:
            return False
        prefix = "Bearer "
        if not str(authorization or "").startswith(prefix):
            return False
        supplied = _token_digest(str(authorization)[len(prefix):].strip())
        return bool(self._token_hash) and hmac.compare_digest(supplied, self._token_hash)

    def authenticate_local_client(self, authorization: str) -> bool:
        prefix = "Bearer "
        supplied = str(authorization or "")
        if not supplied.startswith(prefix) or not self._client_token:
            return False
        return hmac.compare_digest(supplied[len(prefix):].strip(), self._client_token)

    def touch(self) -> None:
        with self._lock:
            self._last_seen = time.monotonic()

    def is_connected(self) -> bool:
        if self._proxy_mode:
            response = self._proxy_request("/v1/client/status", timeout=3.0)
            return bool(response and response.get("connected"))
        with self._lock:
            return bool(
                self._paired_origin
                and self._token_hash
                and self._last_seen
                and time.monotonic() - self._last_seen <= CONNECTION_FRESH_SECONDS
            )

    def status(self, origin: str = "") -> Dict[str, Any]:
        with self._lock:
            return {
                "ok": True,
                "paired": bool(self._paired_origin and origin == self._paired_origin),
                "connected": self.is_connected(),
                "version": 1,
            }

    def start(self) -> bool:
        with self._lock:
            if self._server is not None:
                return True
            bridge = self

            class Handler(BaseHTTPRequestHandler):
                server_version = "SSMakerChromeBridge/1"

                def log_message(self, _format: str, *_args: Any) -> None:
                    return

                @property
                def origin(self) -> str:
                    return str(self.headers.get("Origin") or "").strip()

                def _cors(self) -> None:
                    if _valid_extension_origin(self.origin):
                        self.send_header("Access-Control-Allow-Origin", self.origin)
                        self.send_header("Vary", "Origin")

                def _json(self, status: int, payload: Dict[str, Any]) -> None:
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    self.send_response(status)
                    self._cors()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)

                def _read_json(self) -> Optional[Dict[str, Any]]:
                    try:
                        length = int(self.headers.get("Content-Length") or 0)
                    except ValueError:
                        return None
                    if length <= 0 or length > MAX_REQUEST_BYTES:
                        return None
                    try:
                        value = json.loads(self.rfile.read(length).decode("utf-8"))
                    except (UnicodeDecodeError, ValueError):
                        return None
                    return value if isinstance(value, dict) else None

                def _authorized(self) -> bool:
                    return bridge.authenticate(
                        self.origin, str(self.headers.get("Authorization") or "")
                    )

                def _local_client_authorized(self) -> bool:
                    remote_host = str(self.client_address[0] or "")
                    return (
                        remote_host in {"127.0.0.1", "::1"}
                        and bridge.authenticate_local_client(
                            str(self.headers.get("Authorization") or "")
                        )
                    )

                def do_OPTIONS(self) -> None:  # noqa: N802
                    if not _valid_extension_origin(self.origin):
                        self._json(403, {"ok": False})
                        return
                    self.send_response(204)
                    self._cors()
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                    self.send_header("Access-Control-Max-Age", "600")
                    self.end_headers()

                def do_GET(self) -> None:  # noqa: N802
                    parsed = urlsplit(self.path)
                    if parsed.path == "/v1/client/status":
                        if not self._local_client_authorized():
                            self._json(401, {"ok": False})
                            return
                        self._json(
                            200,
                            {"ok": True, "connected": bridge.is_connected(), "version": 1},
                        )
                        return
                    if parsed.path == "/v1/status":
                        if not _valid_extension_origin(self.origin):
                            self._json(403, {"ok": False})
                            return
                        self._json(200, bridge.status(self.origin))
                        return
                    if parsed.path != "/v1/tasks" or not self._authorized():
                        self._json(401, {"ok": False})
                        return
                    bridge.touch()
                    try:
                        requested_wait = float(parse_qs(parsed.query).get("wait", ["20"])[0])
                    except (TypeError, ValueError):
                        requested_wait = 20.0
                    task = bridge.next_task(max(0.0, min(MAX_TASK_WAIT_SECONDS, requested_wait)))
                    if task is None:
                        self.send_response(204)
                        self._cors()
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        return
                    self._json(200, task)

                def do_POST(self) -> None:  # noqa: N802
                    parsed = urlsplit(self.path)
                    payload = self._read_json()
                    if payload is None:
                        self._json(400, {"ok": False})
                        return
                    if parsed.path == "/v1/pair":
                        token = bridge.pair(self.origin, str(payload.get("code") or ""))
                        if token is None:
                            self._json(403, {"ok": False, "error": "pairing_failed"})
                            return
                        self._json(200, {"ok": True, "token": token, "version": 1})
                        return
                    if parsed.path == "/v1/client/search":
                        if not self._local_client_authorized():
                            self._json(401, {"ok": False})
                            return
                        try:
                            wait_seconds = max(
                                1.0, min(60.0, float(payload.get("timeout") or 35.0))
                            )
                        except (TypeError, ValueError):
                            wait_seconds = 35.0
                        links = bridge._search_index_local(
                            str(payload.get("platform") or ""),
                            str(payload.get("query") or ""),
                            wait_seconds,
                        )
                        self._json(200, {"ok": True, "links": links})
                        return
                    if not self._authorized():
                        self._json(401, {"ok": False})
                        return
                    bridge.touch()
                    if parsed.path == "/v1/heartbeat":
                        self._json(200, {"ok": True})
                        return
                    if parsed.path == "/v1/results":
                        accepted = bridge.submit_result(
                            task_id=str(payload.get("task_id") or ""),
                            links=payload.get("links") or [],
                            error=str(payload.get("error") or "")[:240],
                        )
                        self._json(200 if accepted else 404, {"ok": accepted})
                        return
                    self._json(404, {"ok": False})

            if not self._client_token:
                self._client_token = secrets.token_urlsafe(32)
            try:
                server = _ExclusiveLoopbackServer(("127.0.0.1", self.port), Handler)
                server.daemon_threads = True
            except OSError as exc:
                # Queue runs in a child process while the GUI owns the bridge
                # port.  Reuse that authenticated localhost broker instead of
                # silently falling back to a logged-out automation browser.
                self._load_state()
                self._proxy_mode = bool(
                    self._client_token
                    and self._proxy_request("/v1/client/status", timeout=3.0)
                )
                if self._proxy_mode:
                    logger.info("[ChromeBridge] GUI의 Chrome 연결을 작업 프로세스에서 재사용")
                    return True
                logger.warning("[ChromeBridge] 로컬 연결 포트를 열 수 없음: %s", exc)
                return False
            self.port = int(server.server_address[1])
            self._proxy_mode = False
            self._server = server
            self._save_state()
            self._thread = threading.Thread(
                target=server.serve_forever,
                name="SSMakerChromeBridge",
                daemon=True,
            )
            self._thread.start()
            logger.info("[ChromeBridge] Chrome 연결 대기 시작 (127.0.0.1:%d)", self.port)
            return True

    def stop(self) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
            self._proxy_mode = False
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except OSError:
                pass
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def next_task(self, timeout: float = 20.0) -> Optional[Dict[str, Any]]:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            while True:
                while self._tasks:
                    task = self._tasks.popleft()
                    pending = self._pending.get(str(task.get("task_id") or ""))
                    if pending is not None and not pending.get("cancelled"):
                        return dict(task)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)

    def submit_result(self, task_id: str, links: Iterable[Any], error: str = "") -> bool:
        with self._condition:
            pending = self._pending.get(str(task_id or ""))
            if pending is None or pending.get("cancelled"):
                return False
            platform = str(pending.get("platform") or "")
            pending["links"] = _canonical_links(platform, links)
            pending["error"] = str(error or "")[:240]
            pending["event"].set()
            return True

    def _proxy_request(
        self,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 5.0,
    ) -> Optional[Dict[str, Any]]:
        if not self._client_token:
            return None
        body = None
        method = "GET"
        headers = {"Authorization": f"Bearer {self._client_token}"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            method = "POST"
            headers["Content-Type"] = "application/json"
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=max(1.0, float(timeout))) as response:
                value = json.loads(response.read().decode("utf-8"))
                return value if isinstance(value, dict) else None
        except (OSError, HTTPError, URLError, ValueError, TypeError):
            return None

    def _search_index_local(
        self, platform: str, query: str, timeout: float = 35.0
    ) -> List[str]:
        platform = str(platform or "").lower()
        query = " ".join(str(query or "").split())[:180]
        if platform not in _VIDEO_LINK_PATTERNS or not query or not self.is_connected():
            return []
        task_id = uuid.uuid4().hex
        event = threading.Event()
        pending = {
            "event": event,
            "platform": platform,
            "links": [],
            "error": "",
            "cancelled": False,
        }
        task = {
            "task_id": task_id,
            "action": "google_index_search",
            "platform": platform,
            "query": query,
        }
        with self._condition:
            self._pending[task_id] = pending
            self._tasks.append(task)
            self._condition.notify_all()
        completed = event.wait(max(1.0, min(60.0, float(timeout))))
        with self._condition:
            current = self._pending.pop(task_id, pending)
            if not completed:
                current["cancelled"] = True
                return []
            return list(current.get("links") or [])

    def search_index(self, platform: str, query: str, timeout: float = 35.0) -> List[str]:
        if self._proxy_mode:
            response = self._proxy_request(
                "/v1/client/search",
                payload={"platform": platform, "query": query, "timeout": timeout},
                timeout=max(5.0, min(65.0, float(timeout) + 3.0)),
            )
            if not response:
                return []
            return _canonical_links(platform, response.get("links") or [])
        return self._search_index_local(platform, query, timeout)


_bridge: Optional[ChromeExtensionBridge] = None
_bridge_lock = threading.Lock()


def get_chrome_extension_bridge() -> ChromeExtensionBridge:
    global _bridge
    if _bridge is None:
        with _bridge_lock:
            if _bridge is None:
                _bridge = ChromeExtensionBridge()
    return _bridge
