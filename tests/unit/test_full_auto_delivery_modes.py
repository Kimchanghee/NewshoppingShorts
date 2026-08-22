import inspect
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


QT_APP = QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self, youtube_connected=False):
        self.youtube_connected = youtube_connected

    def get_automation_sourcing_method(self):
        return "platform_video"

    def get_sourcing_match_policy(self):
        return {
            "min_similarity_percent": 90,
            "min_similarity_score": 0.9,
            "auto_skip_low_similarity": False,
        }

    def get_youtube_upload_interval(self):
        return 240

    def get_youtube_connected(self):
        return self.youtube_connected

    def get_youtube_account_verification(self):
        return {}

    def get_youtube_channel_info(self):
        return {"channel_name": "테스트 채널"}

    def get_coupang_keys(self):
        return {}


class _Linktree:
    def require_connected_for_publish(self):
        return False, "Linktree 미연결"

    def is_connected(self):
        return False


def _build_panel(monkeypatch, settings):
    from ui.panels.sourcing_panel import SourcingPanel

    monkeypatch.setattr(
        "managers.settings_manager.get_settings_manager",
        lambda: settings,
    )
    monkeypatch.setattr(
        "managers.linktree_manager.get_linktree_manager",
        lambda: _Linktree(),
    )
    gui = SimpleNamespace(
        state=SimpleNamespace(),
        genai_client=object(),
        model_provider=None,
        youtube_manager=None,
    )
    return SourcingPanel(None, gui)


def test_file_only_is_safe_default_and_upload_mode_explains_blocker(monkeypatch):
    from ui.panels.sourcing_panel import DELIVERY_FILE_ONLY, DELIVERY_YOUTUBE

    settings = _Settings(youtube_connected=False)
    panel = _build_panel(monkeypatch, settings)

    assert panel._delivery_mode == DELIVERY_FILE_ONLY
    assert panel.delivery_file_card.radio.isChecked()
    assert not panel.chk_upload.isChecked()
    assert not panel.chk_linktree.isChecked()
    assert panel.delivery_options_frame.isHidden()
    assert panel.btn_start.isEnabled()
    assert panel.btn_start.text() == "영상 파일 만들기 시작"

    panel.delivery_youtube_card.radio.setChecked(True)

    assert panel._delivery_mode == DELIVERY_YOUTUBE
    assert not panel.delivery_options_frame.isHidden()
    assert not panel.btn_start.isEnabled()
    assert panel.btn_start.text() == "YouTube 연결 후 시작 가능"
    assert "연결" in panel.delivery_outcome_label.text()

    settings.youtube_connected = True
    panel._sync_delivery_ui()

    assert panel.btn_start.isEnabled()
    assert panel.btn_start.text() == "영상 만들고 YouTube에 올리기"
    assert "테스트 채널" in panel.delivery_status_label.text()


def test_full_auto_ui_accepts_multiple_partner_links_without_internal_controls(monkeypatch):
    panel = _build_panel(monkeypatch, _Settings(youtube_connected=False))
    first = "https://link.coupang.com/a/first"
    second = "https://link.coupang.com/a/second"

    panel.partner_links_input.setPlainText(f"{first}\n{first}\n{second}")
    QT_APP.processEvents()

    assert panel.url_input.text() == first
    assert panel._extract_next_links() == [second]
    assert panel.next_links_count_label.text() == "2개"
    assert not hasattr(panel, "match_threshold_spin")
    assert not hasattr(panel, "chk_auto_skip_low_similarity")
    assert not hasattr(panel, "radio_method_platform")
    assert "한 줄에 하나씩" in panel.partner_links_input.accessibleDescription()


def test_partner_text_change_shares_one_parse_result_for_display_and_count(monkeypatch):
    from ui.panels import sourcing_panel

    panel = _build_panel(monkeypatch, _Settings(youtube_connected=False))
    first = "https://link.coupang.com/a/FirstCase"
    second = "https://link.coupa.ng/a/SecondCase"
    raw = f"첫 상품: [{first}]\n둘째 상품: {second}"
    calls = []
    real_parser = sourcing_panel.parse_coupang_partner_links

    def recording_parser(value):
        calls.append(value)
        return real_parser(value)

    monkeypatch.setattr(sourcing_panel, "parse_coupang_partner_links", recording_parser)

    panel.partner_links_input.setPlainText(raw)
    QT_APP.processEvents()

    assert calls == [raw]
    assert panel.url_input.text() == first
    assert panel._extract_next_links() == [second]
    assert panel.next_links_count_label.text() == "2개"


def test_invalid_partner_input_never_populates_hidden_delivery_fields(monkeypatch):
    panel = _build_panel(monkeypatch, _Settings(youtube_connected=False))

    panel.partner_links_input.setPlainText(
        "https://link.coupang.com/a/good?query=1"
    )
    QT_APP.processEvents()

    assert panel.url_input.text() == ""
    assert panel.next_links_input.toPlainText() == ""
    assert panel.next_links_count_label.text() == "0개"

    panel._on_start_platform_video()

    assert "단축 링크 형식" in panel.results_label.text()
    assert panel._running is False


def test_missing_ai_client_disables_start_and_never_consumes_partner_queue(monkeypatch):
    settings = _Settings(youtube_connected=False)
    panel = _build_panel(monkeypatch, settings)
    panel.gui.genai_client = None
    panel.gui.model_provider = SimpleNamespace(gemini_client=None)
    links = [
        "https://link.coupang.com/a/first",
        "https://link.coupang.com/a/second",
        "https://link.coupang.com/a/third",
    ]
    panel.partner_links_input.setPlainText("\n".join(links))
    QT_APP.processEvents()
    panel._sync_delivery_ui()

    assert panel.btn_start.isEnabled() is False
    assert panel.btn_start.text() == "Gemini API 키 설정 후 시작 가능"

    panel._on_start_platform_video()

    assert panel._running is False
    assert panel._partner_batch_active is False
    assert panel.partner_links_input.toPlainText() == "\n".join(links)
    assert panel.next_links_count_label.text() == "3개"
    assert "실제로 등록되지 않았습니다" in panel.results_label.text()


def test_readiness_does_not_treat_empty_provider_placeholder_as_vertex(monkeypatch):
    from ui.components.automation_readiness import AutomationReadinessCard

    panel = _build_panel(monkeypatch, _Settings(youtube_connected=False))
    panel.gui.genai_client = None
    panel.gui.model_provider = SimpleNamespace(gemini_client=None)

    ready, detail = AutomationReadinessCard(
        gui=panel.gui
    )._ai_status()

    assert ready is False
    assert "Gemini API 키" in detail
    assert "Vertex AI 엔진이 준비" not in detail


def test_partner_link_batch_advances_to_the_next_item_automatically(monkeypatch):
    panel = _build_panel(monkeypatch, _Settings(youtube_connected=False))
    links = [
        "https://link.coupang.com/a/first",
        "https://link.coupang.com/a/second",
        "https://link.coupang.com/a/third",
    ]
    panel.partner_links_input.setPlainText("\n".join(links))
    QT_APP.processEvents()
    panel._partner_batch_active = True
    panel._partner_batch_total = len(links)
    panel._partner_batch_completed = 0
    panel._platform_batch_can_continue = True
    panel._platform_item_succeeded = True
    panel.partner_links_input.setEnabled(False)
    starts = []
    monkeypatch.setattr(panel, "_on_start_clicked", lambda: starts.append(True))
    monkeypatch.setattr(
        "ui.panels.sourcing_panel.QTimer.singleShot",
        lambda _delay, callback: callback(),
    )

    panel._reset_platform_controls()

    assert starts == [True]
    assert panel.url_input.text() == links[1]
    assert panel._extract_next_links() == [links[2]]
    assert panel.partner_links_input.toPlainText() == "\n".join(links[1:])
    assert panel._partner_batch_completed == 1
    assert panel._partner_batch_active is True


def test_file_only_still_starts_final_batch_render(monkeypatch, tmp_path):
    settings = _Settings(youtube_connected=False)
    panel = _build_panel(monkeypatch, settings)
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    calls = []

    panel.gui.queue_manager = SimpleNamespace(
        add_url_to_queue=lambda url: calls.append(("queue", url)) or True
    )
    panel.gui._on_step_selected = lambda step: calls.append(("step", step))
    panel.gui.start_batch_processing = lambda: calls.append(("batch", True))
    monkeypatch.setattr(
        panel,
        "_set_youtube_auto_upload_for_pipeline",
        lambda enabled: calls.append(("upload", enabled)),
    )
    monkeypatch.setattr(
        "ui.panels.sourcing_panel.QTimer.singleShot",
        lambda _delay, callback: callback(),
    )
    pipeline = SimpleNamespace(
        sourced_products=[{"video_file": str(video), "source": "douyin"}],
        deep_link="",
        coupang_url="https://www.coupang.com/vp/products/1",
        product_info={"name": "상품"},
    )

    panel._enqueue_sourced_videos(pipeline)

    assert ("upload", False) in calls
    assert ("step", "queue") in calls
    assert ("batch", True) in calls
    assert not any(call == ("step", "voice") for call in calls)


def test_upload_mode_accepts_real_flagless_marketplace_shape_after_match_gate(
    monkeypatch, tmp_path
):
    from core.sourcing.pipeline import SourcingPipeline

    panel = _build_panel(monkeypatch, _Settings(youtube_connected=True))
    video = tmp_path / "marketplace.mp4"
    video.write_bytes(b"video")
    calls = []
    panel.gui.queue_manager = SimpleNamespace(
        add_url_to_queue=lambda url: calls.append(("queue", url)) or True
    )
    panel.gui._on_step_selected = lambda step: calls.append(("step", step))
    panel.gui.start_batch_processing = lambda: calls.append(("batch", True))
    monkeypatch.setattr(panel, "_is_upload_mode", lambda: True)
    monkeypatch.setattr(panel, "_is_linktree_requested", lambda: False)
    monkeypatch.setattr(
        panel,
        "_set_youtube_auto_upload_for_pipeline",
        lambda enabled: calls.append(("upload", enabled)),
    )
    monkeypatch.setattr(
        "ui.panels.sourcing_panel.QTimer.singleShot",
        lambda _delay, callback: callback(),
    )

    pipeline = SourcingPipeline(
        coupang_url="https://www.coupang.com/vp/products/1",
        output_dir=str(tmp_path),
        min_similarity_score=0.9,
    )
    pipeline.product_info = {"name": "상품"}
    pipeline.sourced_products = [
        {
            "source": "aliexpress",
            "product": {
                "title": "Matching marketplace item",
                "url": "https://www.aliexpress.com/item/1005000000000001.html",
                "score": 0.95,
            },
            "video_url": "https://example.com/product-video.mp4",
            "video_file": str(video),
            "size_mb": 1.0,
        }
    ]

    assert pipeline.evaluate_similarity_threshold() is True
    panel._enqueue_sourced_videos(pipeline)

    item = pipeline.sourced_products[0]
    assert item["auto_publish_safe"] is True
    assert item["requires_review"] is False
    assert ("queue", f"local://{video}") in calls
    assert ("upload", True) in calls
    assert ("batch", True) in calls


def test_linktree_failure_is_warning_not_delivery_block():
    from core.video.batch import processor
    from ui.panels.sourcing_panel import SourcingPanel

    batch_source = inspect.getsource(processor._process_single_video)
    direct_source = inspect.getsource(SourcingPanel._run_platform_pipeline)

    optional_guard = batch_source.index("if linktree_publish_blocked:")
    youtube_queue = batch_source.index('"YouTube",', optional_guard)
    between = batch_source[optional_guard:youtube_queue]
    assert "logger.warning" in between
    assert "raise WorkDeliveryPendingError" not in between
    assert "링크트리 발행에 실패해 자동 업로드를 중단" not in direct_source
    assert "링크트리가 연결되지 않아 자동 업로드를 중단" not in direct_source


def test_direct_platform_upload_continues_when_optional_linktree_is_disconnected(
    monkeypatch, tmp_path
):
    from ui.panels.sourcing_panel import SourcingPanel

    video = tmp_path / "edited.mp4"
    video.write_bytes(b"video")
    events = []

    class _Reservation:
        finalized = False

        def mark_pending_finalize(self):
            return None

        def finalize(self):
            self.finalized = True
            return {"success": True, "reservation_status": "completed"}

        def complete_delivery(self):
            events.append("complete")

        def can_release(self):
            return False

    monkeypatch.setattr(
        "ui.panels.sourcing_panel.DurableWorkReservation.begin",
        lambda *_args, **_kwargs: (
            _Reservation(),
            {"success": True, "reservation_status": "reserved"},
        ),
    )

    async def _pipeline(*_args, **_kwargs):
        return {
            "ok": True,
            "product_info": {"name": "상품"},
            "hit": {"platform": "douyin"},
            "final_video": str(video),
            "auto_publish_safe": True,
            "requires_review": False,
            "deep_link": "",
            "purchase_url": "https://www.coupang.com/vp/products/1",
            "render_integrity": {"ok": True},
        }

    monkeypatch.setattr("core.sourcing.platform_pipeline.run_platform_sourcing", _pipeline)
    monkeypatch.setattr(
        "managers.linktree_manager.get_linktree_manager",
        lambda: _Linktree(),
    )

    panel = SimpleNamespace(
        _on_pipeline_progress=lambda *_args: None,
        _safe_set_results=lambda text: events.append(("result", text)),
        _reset_start_button=lambda: events.append("reset"),
    )
    youtube = SimpleNamespace(
        add_to_upload_queue=lambda **_kwargs: events.append("youtube") or True
    )

    SourcingPanel._run_platform_pipeline(
        panel,
        "https://www.coupang.com/vp/products/1",
        0.9,
        True,
        True,
        None,
        youtube,
        "42",
        "platform:https://www.coupang.com/vp/products/1",
    )

    assert "youtube" in events
    assert "complete" in events


@pytest.mark.parametrize(
    "safety_fields",
    [
        {"auto_publish_safe": False, "requires_review": True},
        {},
        {"auto_publish_safe": None, "requires_review": False},
        {"auto_publish_safe": "true", "requires_review": False},
        {"auto_publish_safe": 0, "requires_review": False},
        {"auto_publish_safe": True, "requires_review": None},
    ],
    ids=["review", "missing", "none", "string", "zero", "review-missing"],
)
def test_direct_platform_review_only_result_completes_without_publish_or_upload(
    monkeypatch, tmp_path, safety_fields
):
    from ui.panels.sourcing_panel import SourcingPanel

    video = tmp_path / "review-only.mp4"
    video.write_bytes(b"video")
    events = []

    class _Reservation:
        finalized = False

        def mark_pending_finalize(self):
            events.append("pending-finalize")

        def finalize(self):
            self.finalized = True
            events.append("finalize")
            return {"success": True, "reservation_status": "completed"}

        def complete_delivery(self):
            events.append("complete")

        def can_release(self):
            return False

    monkeypatch.setattr(
        "ui.panels.sourcing_panel.DurableWorkReservation.begin",
        lambda *_args, **_kwargs: (
            _Reservation(),
            {"success": True, "reservation_status": "reserved"},
        ),
    )

    async def _pipeline(*_args, **_kwargs):
        return {
            "ok": True,
            "product_info": {"name": "review product"},
            "hit": {"platform": "coupang_image"},
            "final_video": str(video),
            "fallback_reason": "product_image_fallback",
            "deep_link": "",
            "purchase_url": "https://www.coupang.com/vp/products/1",
            "render_integrity": {"ok": True},
            **safety_fields,
        }

    monkeypatch.setattr("core.sourcing.platform_pipeline.run_platform_sourcing", _pipeline)

    class _UnexpectedLinktree:
        def is_connected(self):
            raise AssertionError("review-only result must not publish to Linktree")

    monkeypatch.setattr(
        "managers.linktree_manager.get_linktree_manager",
        lambda: _UnexpectedLinktree(),
    )

    panel = SimpleNamespace(
        _on_pipeline_progress=lambda *args: events.append(("progress", args)),
        _safe_set_results=lambda message: events.append(("result", message)),
        _reset_start_button=lambda: events.append("reset"),
    )
    youtube = SimpleNamespace(
        add_to_upload_queue=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("review-only result must not upload to YouTube")
        )
    )

    SourcingPanel._run_platform_pipeline(
        panel,
        "https://www.coupang.com/vp/products/1",
        0.9,
        True,
        True,
        None,
        youtube,
        "42",
        "platform:https://www.coupang.com/vp/products/1",
    )

    messages = [
        event[1]
        for event in events
        if isinstance(event, tuple) and event[0] == "result"
    ]
    assert "complete" in events
    assert messages
    assert str(video) in messages[-1]
    assert "검토" in messages[-1]
