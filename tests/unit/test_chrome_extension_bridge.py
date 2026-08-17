# -*- coding: utf-8 -*-
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.sourcing.chrome_extension_bridge import ChromeExtensionBridge


EXTENSION_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


def _json_request(url, *, method="GET", payload=None, token="", origin=EXTENSION_ORIGIN):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Origin": origin}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=5) as response:
        data = response.read()
        return response.status, json.loads(data.decode("utf-8")) if data else None


def test_local_bridge_pairs_and_returns_only_canonical_platform_links(tmp_path):
    bridge = ChromeExtensionBridge(storage_dir=tmp_path, port=0)
    assert bridge.start() is True
    base = f"http://127.0.0.1:{bridge.port}"
    try:
        status, paired = _json_request(
            f"{base}/v1/pair",
            method="POST",
            payload={"code": bridge.pairing_code},
        )
        assert status == 200
        token = paired["token"]
        assert bridge.is_connected() is True

        result = {}

        def run_search():
            result["links"] = bridge.search_index(
                "douyin", "旋转 喷泉 水枪", timeout=4
            )

        worker = threading.Thread(target=run_search)
        worker.start()
        status, task = _json_request(f"{base}/v1/tasks?wait=2", token=token)
        assert status == 200
        assert task["action"] == "google_index_search"
        assert task["query"] == "旋转 喷泉 水枪"

        valid = "https://www.douyin.com/video/7658326682089144783?from=google"
        status, response = _json_request(
            f"{base}/v1/results",
            method="POST",
            token=token,
            payload={
                "task_id": task["task_id"],
                "links": [valid, valid, "https://example.com/not-a-video"],
            },
        )
        assert status == 200 and response["ok"] is True
        worker.join(timeout=5)
        assert result["links"] == [
            "https://www.douyin.com/video/7658326682089144783"
        ]
    finally:
        bridge.stop()


def test_local_bridge_rejects_non_extension_origin(tmp_path):
    bridge = ChromeExtensionBridge(storage_dir=tmp_path, port=0)
    assert bridge.start() is True
    try:
        base = f"http://127.0.0.1:{bridge.port}"
        try:
            _json_request(
                f"{base}/v1/pair",
                method="POST",
                payload={"code": bridge.pairing_code},
                origin="https://example.com",
            )
        except HTTPError as exc:
            assert exc.code == 403
        else:
            raise AssertionError("non-extension origins must not be paired")
    finally:
        bridge.stop()


def test_queue_process_proxies_search_through_gui_bridge(tmp_path):
    gui_bridge = ChromeExtensionBridge(storage_dir=tmp_path, port=0)
    assert gui_bridge.start() is True
    token = gui_bridge.pair(EXTENSION_ORIGIN, gui_bridge.pairing_code)
    assert token

    queue_bridge = ChromeExtensionBridge(
        storage_dir=tmp_path,
        port=gui_bridge.port,
    )
    assert queue_bridge.start() is True
    assert queue_bridge.is_connected() is True

    result = {}

    def run_search():
        result["links"] = queue_bridge.search_index(
            "douyin", "鲨鱼水枪玩具", timeout=4
        )

    worker = threading.Thread(target=run_search)
    worker.start()
    task = gui_bridge.next_task(timeout=2)
    assert task and task["query"] == "鲨鱼水枪玩具"
    assert gui_bridge.submit_result(
        task["task_id"],
        ["https://www.douyin.com/video/7383327980765973779?from=google"],
    )
    worker.join(timeout=5)

    assert result["links"] == [
        "https://www.douyin.com/video/7383327980765973779"
    ]
    queue_bridge.stop()
    gui_bridge.stop()
