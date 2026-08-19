from types import SimpleNamespace

import pytest

from core.video.batch import processor
from app.video_helpers import VideoHelpers
from managers.generated_video_manager import GeneratedVideoManager
from managers.output_manager import OutputManager
from managers import queue_manager as queue_module
from managers.queue_manager import QueueManager


class DummyGUI:
    def __init__(self):
        self.url_queue = []
        self.url_status = {}
        self.url_status_message = {}
        self.url_timestamps = {}
        self.url_remarks = {}
        self.mix_jobs = {}
        self.url_auto_upload_status = {}
        self.state = SimpleNamespace(mix_jobs=self.mix_jobs)


def _manager(monkeypatch):
    monkeypatch.setattr(queue_module.QueueManager, "update_url_listbox", lambda self: None)
    monkeypatch.setattr(queue_module.QueueManager, "update_queue_count", lambda self: None)
    gui = DummyGUI()
    return QueueManager(gui), gui


def test_mix_job_requires_two_distinct_valid_sources(monkeypatch):
    manager, gui = _manager(monkeypatch)

    with pytest.raises(ValueError, match="서로 다른 영상"):
        manager.add_mix_job(
            ["https://video.example/source", "https://video.example/source"]
        )

    assert gui.url_queue == []
    assert gui.mix_jobs == {}


def test_mix_job_rejects_invalid_remote_url_before_queueing(monkeypatch):
    manager, gui = _manager(monkeypatch)

    with pytest.raises(ValueError, match="올바른 영상 링크"):
        manager.add_mix_job(["not-a-url", "https://video.example/source"])

    assert gui.url_queue == []
    assert gui.mix_jobs == {}


def test_mix_job_rejects_computer_video_files(monkeypatch, tmp_path):
    manager, gui = _manager(monkeypatch)
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mov"
    first.write_bytes(b"video-one")
    second.write_bytes(b"video-two")

    with pytest.raises(ValueError, match="영상 링크만 입력"):
        manager.add_mix_job([f"local://{first}", f"local://{second}"])

    assert gui.url_queue == []
    assert gui.mix_jobs == {}


def test_restored_mix_sources_are_deduplicated():
    key = "mix://job/restored"
    app = SimpleNamespace(
        mix_jobs={
            key: [
                "https://video.example/one",
                "https://video.example/one",
                "https://video.example/two",
            ]
        }
    )

    assert processor._get_mix_job_urls(app, key) == [
        "https://video.example/one",
        "https://video.example/two",
    ]


def test_incomplete_restored_mix_job_fails_with_recovery_instruction():
    key = "mix://job/incomplete"
    app = SimpleNamespace(mix_jobs={key: ["https://video.example/one"]})

    with pytest.raises(RuntimeError, match="영상을 다시 선택"):
        processor._prepare_mix_source_video(app, key)


def test_source_state_is_reset_between_manual_jobs():
    state = SimpleNamespace(video_source="local", local_file_path="old.mp4")
    app = SimpleNamespace(
        video_source="local", local_file_path="old.mp4", state=state
    )

    processor._set_active_source_state(app, "remote")

    assert app.video_source == "remote"
    assert app.local_file_path == ""
    assert state.video_source == "remote"
    assert state.local_file_path == ""


def test_cleanup_preserves_user_selected_local_source(tmp_path):
    source = tmp_path / "original.mp4"
    source.write_bytes(b"user-owned-video")
    app = SimpleNamespace(
        _temp_downloaded_file=str(source),
        _temp_downloaded_file_owned=False,
        _temp_downloaded_files=[],
    )

    VideoHelpers(app).cleanup_temp_files()

    assert source.read_bytes() == b"user-owned-video"
    assert app._temp_downloaded_file is None


def test_failed_output_copy_keeps_render_for_recovery(monkeypatch, tmp_path):
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    render = render_dir / "result.mp4"
    render.write_bytes(b"completed-render")
    output = tmp_path / "output"
    app = SimpleNamespace(
        generated_videos=[{"path": str(render), "temp_dir": str(render_dir)}],
        output_folder_path=str(output),
        _current_processing_url="https://video.example/source",
        _processing_start_time=processor.datetime(2026, 8, 19, 12, 0, 0),
    )
    monkeypatch.setattr("shutil.move", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("move failed")))
    monkeypatch.setattr("shutil.copy2", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy failed")))

    saved_count = GeneratedVideoManager(app).save_locally(show_popup=False)

    assert saved_count == 0
    assert render.read_bytes() == b"completed-render"
    assert render_dir.is_dir()


def test_transient_save_failure_is_retried_before_success(tmp_path):
    saved = tmp_path / "saved.mp4"
    calls = []
    video_info = {}

    def save_generated_videos_locally(show_popup=False):
        calls.append(show_popup)
        if len(calls) == 1:
            return 0
        saved.write_bytes(b"saved-video")
        video_info["saved_path"] = str(saved)
        return 1

    app = SimpleNamespace(
        generated_videos=[video_info],
        save_generated_videos_locally=save_generated_videos_locally,
    )

    with pytest.raises(RuntimeError, match="1개 중 0개"):
        processor._save_generated_outputs_or_raise(app)

    assert processor._save_generated_outputs_or_raise(app) == [str(saved)]
    assert calls == [False, False]


def test_multi_voice_save_requires_every_requested_output(tmp_path):
    first_saved = tmp_path / "voice-one.mp4"
    second_saved = tmp_path / "voice-two.mp4"
    first_saved.write_bytes(b"voice-one")
    generated = [
        {"saved_path": str(first_saved)},
        {"path": str(tmp_path / "voice-two-temp.mp4")},
    ]
    calls = []

    def save_generated_videos_locally(show_popup=False):
        calls.append(show_popup)
        if len(calls) == 1:
            return 0
        second_saved.write_bytes(b"voice-two")
        generated[1]["saved_path"] = str(second_saved)
        return 1

    app = SimpleNamespace(
        generated_videos=generated,
        save_generated_videos_locally=save_generated_videos_locally,
    )

    with pytest.raises(RuntimeError, match="2개 중 1개"):
        processor._save_generated_outputs_or_raise(app)

    assert processor._save_generated_outputs_or_raise(app) == [
        str(first_saved),
        str(second_saved),
    ]
    assert calls == [False, False]


def test_local_output_name_uses_original_path_after_trim():
    from core.video.batch.utils import _extract_product_name

    app = SimpleNamespace(
        video_source="local",
        local_file_path="C:/temp/batch_source_trim_123.mp4",
        _original_local_file_path="C:/videos/my_product.mp4",
        video_title="",
        product_name="",
        translation_result="",
    )

    assert _extract_product_name(app) == "my_product"


def test_multi_voice_render_filenames_are_unique():
    first = processor._build_render_output_filename("product", "voice-a", 1)
    second = processor._build_render_output_filename("product", "voice-b", 2)

    assert first != second
    assert "_v01_voice-a_product.mp4" in first
    assert "_v02_voice-b_product.mp4" in second


def test_output_log_verification_never_passes_without_evidence():
    app = SimpleNamespace(_url_log_buffer=[])

    assert OutputManager(app).verify_video_log("job") == "검증 자료 없음 · 확인 필요"


def test_output_log_verification_ignores_normal_sync_progress():
    app = SimpleNamespace(
        _url_log_buffer=[
            "[다운로드] 영상 다운로드 중...\n",
            "[싱크 검증] 자막 범위 정상\n",
            "[인코딩] 렌더링 완료\n",
        ]
    )

    assert OutputManager(app).verify_video_log("job") == "통과"


def test_empty_manual_queue_finishes_worker_immediately(monkeypatch):
    events = []
    app = SimpleNamespace(
        batch_processing=True,
        dynamic_processing=True,
        url_queue=[],
        url_status={},
        session_manager=SimpleNamespace(clear_session=lambda: events.append("cleared")),
        add_log=events.append,
        update_status=events.append,
        start_batch_button=None,
        stop_batch_button=None,
    )
    monkeypatch.setattr(processor, "_dispatch_ui_callback", lambda _app, callback: callback())

    processor.dynamic_batch_processing_thread(app)

    assert app.batch_processing is False
    assert app.dynamic_processing is False
    assert "cleared" in events
    assert "등록된 수동 영상 작업을 모두 처리했습니다." in events


def test_user_interrupted_processing_job_becomes_resumable():
    key = "https://video.example/interrupted"
    events = []
    app = SimpleNamespace(
        batch_processing=False,
        url_status={key: "processing"},
        url_status_message={},
        add_log=events.append,
    )

    assert processor._restore_interrupted_job(app, key) is True
    assert app.url_status[key] == "waiting"
    assert app.url_status_message[key] == "사용자 중지 · 다시 시작 가능"
    assert events


def test_failed_job_is_not_requeued_by_interruption_cleanup():
    key = "https://video.example/failed"
    app = SimpleNamespace(
        batch_processing=False,
        url_status={key: "failed"},
        url_status_message={key: "download failed"},
        add_log=lambda _message: None,
    )

    assert processor._restore_interrupted_job(app, key) is False
    assert app.url_status[key] == "failed"


def test_final_batch_counts_are_derived_from_terminal_statuses():
    app = SimpleNamespace(
        url_status={
            "completed": "completed",
            "recovered-delivery": "failed",
            "authentication": "failed",
        }
    )

    assert processor._count_batch_results(
        app, {"completed", "recovered-delivery", "authentication"}
    ) == (1, 2)


def test_unexpected_worker_error_preserves_session_and_avoids_success(monkeypatch):
    class FlakyQueue(list):
        def __init__(self, values):
            super().__init__(values)
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            if self.iterations == 1:
                raise RuntimeError("unexpected queue failure")
            return super().__iter__()

    events = []
    dialogs = []
    key = "https://video.example/preserved"
    app = SimpleNamespace(
        batch_processing=True,
        dynamic_processing=True,
        url_queue=FlakyQueue([key]),
        url_status={key: "waiting"},
        url_status_message={},
        add_log=events.append,
        update_status=events.append,
        start_batch_button=None,
        stop_batch_button=None,
        session_manager=SimpleNamespace(clear_session=lambda: events.append("cleared")),
        _auto_save_session=lambda: events.append("saved"),
    )
    monkeypatch.setattr(
        processor, "_dispatch_ui_callback", lambda _app, callback: callback()
    )
    monkeypatch.setattr(
        processor,
        "show_error",
        lambda _app, title, message: dialogs.append((title, message)),
    )
    monkeypatch.setattr(
        processor,
        "show_success",
        lambda *_args, **_kwargs: dialogs.append(("success", "unexpected")),
    )
    monkeypatch.setattr(processor.ui_controller, "write_error_log", lambda _error: None)

    processor.dynamic_batch_processing_thread(app)

    assert "saved" in events
    assert "cleared" not in events
    assert dialogs and dialogs[0][0] == "작업 중단"
    assert all(title != "success" for title, _message in dialogs)
    assert app.url_status[key] == "waiting"
