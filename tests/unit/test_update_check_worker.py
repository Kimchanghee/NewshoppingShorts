from startup.app_controller import UpdateCheckWorker


def test_update_check_falls_back_to_github_when_server_version_is_stale(monkeypatch):
    worker = UpdateCheckWorker("1.4.9")

    monkeypatch.setattr(worker, "_candidate_base_urls", lambda: ["https://api.example.com"])
    monkeypatch.setattr(
        worker,
        "_query_version_check",
        lambda _requests, _base_url: {
            "update_available": False,
            "current_version": "1.4.9",
            "latest_version": "1.4.0",
        },
    )
    monkeypatch.setattr(worker, "_query_version_info", lambda _requests, _base_url: None)
    monkeypatch.setattr(
        worker,
        "_query_github_latest_release",
        lambda _requests: {
            "update_available": True,
            "current_version": "1.4.9",
            "latest_version": "1.4.12",
            "download_url": "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v1.4.12/SSMaker_Setup_v1.4.12.exe",
            "file_hash": "a" * 64,
            "release_notes": "notes",
            "is_mandatory": False,
        },
    )

    result = worker._check_with_fallback(object())

    assert result["update_available"] is True
    assert result["latest_version"] == "1.4.12"
    assert result["file_hash"] == "a" * 64


def test_update_check_ignores_server_update_without_hash_and_uses_github(monkeypatch):
    worker = UpdateCheckWorker("1.4.9")

    monkeypatch.setattr(worker, "_candidate_base_urls", lambda: ["https://api.example.com"])
    monkeypatch.setattr(
        worker,
        "_query_version_check",
        lambda _requests, _base_url: {
            "update_available": True,
            "current_version": "1.4.9",
            "latest_version": "1.4.13",
            "download_url": "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v1.4.13/SSMaker_Setup_v1.4.13.exe",
            "file_hash": "",
            "release_notes": "broken metadata",
            "is_mandatory": False,
        },
    )
    monkeypatch.setattr(worker, "_query_version_info", lambda _requests, _base_url: None)
    monkeypatch.setattr(
        worker,
        "_query_github_latest_release",
        lambda _requests: {
            "update_available": True,
            "current_version": "1.4.9",
            "latest_version": "1.4.12",
            "download_url": "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v1.4.12/SSMaker_Setup_v1.4.12.exe",
            "file_hash": "b" * 64,
            "release_notes": "valid metadata",
            "is_mandatory": False,
        },
    )

    result = worker._check_with_fallback(object())

    assert result["update_available"] is True
    assert result["latest_version"] == "1.4.12"
    assert result["file_hash"] == "b" * 64


def test_update_check_rejects_untrusted_download_url(monkeypatch):
    worker = UpdateCheckWorker("1.4.9")

    monkeypatch.setattr(worker, "_candidate_base_urls", lambda: ["https://api.example.com"])
    monkeypatch.setattr(
        worker,
        "_query_version_check",
        lambda _requests, _base_url: {
            "update_available": True,
            "current_version": "1.4.9",
            "latest_version": "1.4.14",
            "download_url": "https://evil.example/SSMaker_Setup_v1.4.14.exe",
            "file_hash": "c" * 64,
            "release_notes": "bad host",
            "is_mandatory": True,
        },
    )
    monkeypatch.setattr(worker, "_query_version_info", lambda _requests, _base_url: None)
    monkeypatch.setattr(worker, "_query_github_latest_release", lambda _requests: None)

    result = worker._check_with_fallback(object())

    assert result["update_available"] is False
    assert result["latest_version"] == "1.4.9"


def test_update_check_returns_newest_no_update_result_when_everything_is_up_to_date(monkeypatch):
    worker = UpdateCheckWorker("1.4.12")

    monkeypatch.setattr(
        worker,
        "_candidate_base_urls",
        lambda: ["https://api1.example.com", "https://api2.example.com"],
    )

    server_responses = {
        "https://api1.example.com": {
            "update_available": False,
            "current_version": "1.4.12",
            "latest_version": "1.4.11",
        },
        "https://api2.example.com": {
            "update_available": False,
            "current_version": "1.4.12",
            "latest_version": "1.4.12",
        },
    }

    monkeypatch.setattr(
        worker,
        "_query_version_check",
        lambda _requests, base_url: server_responses.get(base_url),
    )
    monkeypatch.setattr(worker, "_query_version_info", lambda _requests, _base_url: None)
    monkeypatch.setattr(
        worker,
        "_query_github_latest_release",
        lambda _requests: {
            "update_available": False,
            "current_version": "1.4.12",
            "latest_version": "1.4.12",
        },
    )

    result = worker._check_with_fallback(object())

    assert result["update_available"] is False
    assert result["latest_version"] == "1.4.12"


def test_auto_updater_uses_github_when_server_version_is_stale(monkeypatch):
    from utils import auto_updater

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "version": "1.4.39",
                "download_url": "https://github.com/example/old.exe",
                "release_notes": "old",
                "file_hash": "1" * 64,
                "is_mandatory": False,
            }

    checker = auto_updater.UpdateChecker("https://api.example.com/app/version")
    checker.current_version = "1.4.41"
    monkeypatch.setattr(auto_updater.requests, "get", lambda *_args, **_kwargs: FakeResponse())
    monkeypatch.setattr(
        checker,
        "_query_github_latest_release",
        lambda: {
            "update_available": True,
            "current_version": "1.4.41",
            "latest_version": "1.4.43",
            "download_url": "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v1.4.43/SSMaker_Setup_v1.4.43.exe",
            "release_notes": "new",
            "file_hash": "a" * 64,
            "is_mandatory": False,
            "error": None,
        },
    )

    result = checker.check_for_updates()

    assert result["update_available"] is True
    assert result["latest_version"] == "1.4.43"
    assert result["file_hash"] == "a" * 64


def test_store_package_update_check_never_calls_legacy_update_server(monkeypatch):
    from utils import auto_updater

    monkeypatch.setattr(auto_updater, "is_msix_package", lambda: True)
    monkeypatch.setattr(
        auto_updater.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Store package must not call legacy updater")
        ),
    )

    checker = auto_updater.UpdateChecker("https://api.example.com/app/version")
    result = checker.check_for_updates()

    assert result["update_available"] is False
    assert result["latest_version"] == checker.current_version


def test_store_package_controller_skips_pre_login_installer_update(monkeypatch):
    import startup.app_controller as app_controller

    controller = app_controller.AppController(object())
    calls = []
    monkeypatch.setattr(app_controller, "is_msix_package", lambda: True)
    monkeypatch.setattr(app_controller, "get_package_full_name", lambda: "SSMaker.Package")
    monkeypatch.setattr(app_controller.sys, "frozen", True, raising=False)
    monkeypatch.setattr(controller, "_show_login", lambda: calls.append("login"))
    monkeypatch.setattr(
        controller,
        "_check_update_before_login",
        lambda: calls.append("legacy-update"),
    )

    controller.start()

    assert calls == ["login"]


def test_store_package_controller_skips_post_login_installer_update(monkeypatch):
    import startup.app_controller as app_controller

    controller = app_controller.AppController(object())
    calls = []
    monkeypatch.setattr(app_controller, "is_msix_package", lambda: True)
    monkeypatch.setattr(app_controller.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        controller,
        "_check_update_after_login",
        lambda: calls.append("legacy-update"),
    )
    monkeypatch.setattr(controller, "_proceed_to_loading", lambda: calls.append("loading"))

    controller.on_login_success({"id": "store-user"})

    assert calls == ["loading"]
