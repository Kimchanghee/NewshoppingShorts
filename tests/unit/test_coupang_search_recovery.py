# -*- coding: utf-8 -*-
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QLineEdit


QT_APP = QApplication.instance() or QApplication([])


def test_search_failure_hides_provider_diagnostics_from_customer_copy():
    from core.sourcing.platform_pipeline import (
        describe_platform_search_failure,
        format_failure_message,
    )

    failure = describe_platform_search_failure(
        {"counts": {"access_challenge": 2}, "platforms": {"douyin": {"access_challenge": 2}}}
    )

    assert failure["code"] == "platform_access_blocked"
    assert failure["retriable"] is True
    assert "로그인" in failure["cause"]
    message = format_failure_message("상품 영상 검색에 실패했어요.", failure)
    assert message == (
        "상품 영상을 찾지 못했어요.\n"
        "잠시 후 다시 시도하거나 다른 상품 링크를 사용해 주세요."
    )
    assert "로그인" not in message
    assert "안티봇" not in message
    assert "douyin" not in message.lower()


def test_search_failure_distinguishes_network_relevance_and_download():
    from core.sourcing.platform_pipeline import describe_platform_search_failure

    assert describe_platform_search_failure(
        {"counts": {"page_open_timeout": 1}}
    )["code"] == "platform_search_unavailable"
    assert describe_platform_search_failure(
        {"counts": {"relevance_rejected": 3}}
    )["code"] == "no_relevant_video"
    assert describe_platform_search_failure(
        {"counts": {"download_failed": 2}}
    )["code"] == "candidate_download_failed"
    assert describe_platform_search_failure({"counts": {}})["code"] == "no_search_results"


def test_sourcing_input_explains_why_normal_coupang_link_is_blocked():
    from ui.panels.sourcing_panel import SourcingPanel

    message = SourcingPanel._partner_link_error_message(
        "https://www.coupang.com/vp/products/123"
    )

    assert "일반 쿠팡 상품 링크는 사용할 수 없습니다" in message
    assert "수익 추적 정보가 없습니다" in message
    assert "https://link.coupang.com/" in message


def test_platform_start_stops_before_work_for_normal_coupang_url():
    from ui.panels.sourcing_panel import SourcingPanel

    panel = SimpleNamespace(
        url_input=QLineEdit(),
        results_label=QLabel(),
        _partner_link_error_message=SourcingPanel._partner_link_error_message,
    )
    panel.url_input.setText("https://www.coupang.com/vp/products/123")

    SourcingPanel._on_start_platform_video(panel)

    assert "일반 쿠팡 상품 링크는 사용할 수 없습니다" in panel.results_label.text()


def test_platform_start_normalizes_invisible_clipboard_prefix_before_validation():
    from ui.panels.sourcing_panel import SourcingPanel

    panel = SimpleNamespace(
        url_input=QLineEdit(),
        results_label=QLabel(),
        _partner_link_error_message=SourcingPanel._partner_link_error_message,
        _running=True,
    )
    expected = "https://link.coupang.com/a/f8i3PuVSqi"
    panel.url_input.setText(f"\ufeff\u200b {expected}")

    SourcingPanel._on_start_platform_video(panel)

    assert panel.url_input.text() == expected
    assert panel.results_label.text() == ""


def test_full_automation_accepts_all_reported_links_from_decorated_paste():
    from ui.panels.sourcing_panel import SourcingPanel

    expected = [
        "https://link.coupang.com/a/f8i3PuVSqi",
        "https://link.coupang.com/a/f8i6WhHkK4",
        "https://link.coupang.com/a/f8jcQoPoke",
        "https://link.coupang.com/a/f8jex1jVcG",
        "https://link.coupang.com/a/f8jkHwLWaO",
    ]
    pasted = "\n".join(
        f"{index}. 상품 링크: [{url}]" for index, url in enumerate(expected, 1)
    )

    assert SourcingPanel._extract_partner_links(pasted) == expected


def test_recovery_actions_retry_same_or_select_next_product():
    from ui.panels.sourcing_panel import SourcingPanel

    events = []
    panel = SimpleNamespace(
        _running=False,
        _set_search_recovery_visible=lambda visible: events.append(("visible", visible)),
        _on_start_clicked=lambda: events.append(("retry", True)),
    )
    SourcingPanel._retry_last_search(panel)
    assert events == [("visible", False), ("retry", True)]

    product_input = QLineEdit()
    result_label = QLabel()
    chooser = SimpleNamespace(
        _running=False,
        _pop_next_sourcing_url=lambda: "https://link.coupang.com/a/next",
        url_input=product_input,
        results_label=result_label,
        _set_search_recovery_visible=lambda visible: events.append(("chooser", visible)),
    )
    SourcingPanel._choose_other_product(chooser)
    assert product_input.text() == "https://link.coupang.com/a/next"
    assert "다음 상품" in result_label.text()


def test_structured_failure_hides_internal_cause_and_shows_recovery_controls():
    from ui.panels.sourcing_panel import SourcingPanel

    result_label = QLabel()
    recovery = QFrame()
    recovery.setVisible(False)
    panel = SimpleNamespace(
        results_label=result_label,
        search_recovery_frame=recovery,
    )
    panel._set_search_recovery_visible = lambda visible: SourcingPanel._set_search_recovery_visible(
        panel, visible
    )

    SourcingPanel._set_platform_failure(
        panel,
        {
            "error": "상품 영상 검색에 실패했어요.",
            "failure": {"cause": "검색 서버 시간초과", "action": "다시 검색해 주세요."},
            "report_path": r"C:\Users\tester\.ssmaker\output\report_platform_failed.json",
        },
    )

    assert "상품 영상을 찾지 못했어요" in result_label.text()
    assert "검색 서버 시간초과" not in result_label.text()
    assert "다시 검색해 주세요" not in result_label.text()
    assert "오류 기록:" not in result_label.text()
    assert "report_platform_failed.json" not in result_label.text()
    assert recovery.isHidden() is False


def test_coupang_manager_reports_server_outage_cause(monkeypatch):
    from managers.coupang_manager import CoupangManager

    manager = object.__new__(CoupangManager)
    manager.settings = SimpleNamespace(
        get_coupang_keys=lambda: {"access_key": "access", "secret_key": "secret"}
    )
    manager.last_error_message = ""
    response = SimpleNamespace(status_code=503)
    monkeypatch.setattr("managers.coupang_manager.requests.post", lambda *args, **kwargs: response)

    assert manager.generate_deep_link("https://www.coupang.com/vp/products/123") is None
    assert "서버 장애" in manager.get_last_error_message()
    assert "HTTP 503" in manager.get_last_error_message()
