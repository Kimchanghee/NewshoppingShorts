from types import SimpleNamespace

import startup.app_controller as app_controller


def _controller_with_main(*, batch=False, dynamic=False):
    controller = app_controller.AppController(object())
    controller.main_gui = SimpleNamespace(
        batch_processing=batch,
        dynamic_processing=dynamic,
    )
    return controller


def test_runtime_update_monitor_uses_a_bounded_periodic_interval():
    assert 60 * 60 * 1000 <= app_controller.RUNTIME_UPDATE_CHECK_INTERVAL_MS <= 12 * 60 * 60 * 1000
    assert app_controller.RUNTIME_UPDATE_DEFER_POLL_MS <= 60 * 1000


def test_runtime_update_is_deferred_while_a_video_job_is_active(monkeypatch):
    controller = _controller_with_main(batch=True)
    calls = []
    update = {
        "latest_version": "1.5.50",
        "download_url": "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v1.5.50/SSMaker_Setup_v1.5.50.exe",
        "file_hash": "a" * 64,
        "release_notes": "runtime update",
    }
    monkeypatch.setattr(controller, "perform_update", lambda *_args: calls.append("install"))
    monkeypatch.setattr(controller, "_show_runtime_update_ready", lambda: calls.append("notice"))

    controller._on_runtime_update_available(update)

    assert calls == ["notice"]
    assert controller._deferred_runtime_update == update


def test_deferred_runtime_update_installs_once_app_becomes_idle(monkeypatch):
    controller = _controller_with_main(batch=False, dynamic=False)
    update_url = "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v1.5.50/SSMaker_Setup_v1.5.50.exe"
    controller._deferred_runtime_update = {
        "latest_version": "1.5.50",
        "download_url": update_url,
        "file_hash": "b" * 64,
        "release_notes": "runtime update",
    }
    calls = []
    monkeypatch.setattr(controller, "perform_update", lambda url, digest: calls.append((url, digest)))

    controller._apply_deferred_runtime_update_if_idle()
    controller._apply_deferred_runtime_update_if_idle()

    assert calls == [(update_url, "b" * 64)]
    assert controller._deferred_runtime_update is None


def test_store_runtime_update_metadata_is_ignored(monkeypatch):
    controller = _controller_with_main()
    calls = []
    update = {
        "latest_version": "1.5.50",
        "download_url": "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v1.5.50/SSMaker_Setup_v1.5.50.exe",
        "file_hash": "c" * 64,
    }
    monkeypatch.setattr(app_controller, "is_msix_package", lambda: True)
    monkeypatch.setattr(controller, "perform_update", lambda *_args: calls.append("legacy"))

    controller._on_runtime_update_available(update)

    assert calls == []
    assert not hasattr(controller, "_store_runtime_update_data")
def test_store_package_never_starts_runtime_installer_monitor(monkeypatch):
    controller = _controller_with_main()
    monkeypatch.setattr(app_controller.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_controller, "is_msix_package", lambda: True)

    controller._start_runtime_update_monitor()

    assert controller.runtime_update_timer is None
    assert controller.runtime_update_defer_timer is None
    assert controller._runtime_update_check_worker is None


def test_packaged_controller_checks_for_updates_after_login(monkeypatch):
    controller = _controller_with_main()
    calls = []
    monkeypatch.setattr(app_controller.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_controller, "is_msix_package", lambda: False)
    monkeypatch.setattr(controller, "_check_update_after_login", lambda: calls.append("check"))
    monkeypatch.setattr(controller, "_proceed_to_loading", lambda: calls.append("load"))

    controller.on_login_success({"id": "test-user"})

    assert calls == ["check"]
