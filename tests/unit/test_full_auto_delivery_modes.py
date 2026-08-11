import inspect
import os
from types import SimpleNamespace

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
