from managers.settings_manager import SettingsManager


def test_remote_sync_seeds_account_with_portable_secret_values(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    manager = SettingsManager("prefs.json")
    manager.set_linktree_settings(
        webhook_url="https://example.com/linktree-hook",
        api_key="secret-token",
        profile_url="https://linktr.ee/example",
        auto_publish=True,
        account_email="k931103@gmail.com",
        expected_account_email="k931103@gmail.com",
    )
    manager.set_youtube_expected_account_email("ympartners.uk@gmail.com")
    manager.set_youtube_account_email("ympartners.uk@gmail.com")

    captured = {}

    from caller import rest

    monkeypatch.setattr(rest, "fetch_user_settings", lambda: {"success": True, "settings": {}})

    def _fake_save(payload):
        captured.update(payload)
        return {"success": True}

    monkeypatch.setattr(rest, "save_user_settings", _fake_save)

    assert manager.sync_with_remote({}) is True
    assert captured["linktree_webhook_url"] == "https://example.com/linktree-hook"
    assert captured["linktree_api_key"] == "secret-token"
    assert captured["linktree_profile_url"] == "https://linktr.ee/example"
    assert captured["linktree_account_email"] == "k931103@gmail.com"
    assert captured["linktree_expected_account_email"] == "k931103@gmail.com"
    assert captured["linktree_auto_publish"] is True
    assert captured["youtube_account_email"] == "ympartners.uk@gmail.com"
    assert captured["youtube_expected_account_email"] == "ympartners.uk@gmail.com"


def test_remote_sync_loads_account_settings_and_reencrypts_locally(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    manager = SettingsManager("prefs.json")

    from caller import rest

    remote_settings = {
        "cta_id": "remote-cta",
        "linktree_webhook_url": "https://example.com/remote-hook",
        "linktree_api_key": "remote-secret",
        "linktree_profile_url": "https://linktr.ee/remote",
        "linktree_account_email": "k931103@gmail.com",
        "linktree_expected_account_email": "k931103@gmail.com",
        "linktree_auto_publish": True,
        "youtube_account_email": "ympartners.uk@gmail.com",
        "youtube_expected_account_email": "ympartners.uk@gmail.com",
        "cookies_1688": {"session": "abc"},
    }

    monkeypatch.setattr(
        rest,
        "fetch_user_settings",
        lambda: {"success": True, "settings": remote_settings},
    )
    monkeypatch.setattr(
        rest,
        "save_user_settings",
        lambda payload: (_ for _ in ()).throw(AssertionError("unexpected save")),
    )

    assert manager.sync_with_remote({}) is True
    assert manager.get_cta_id() == "remote-cta"
    assert manager.get_linktree_settings()["webhook_url"] == "https://example.com/remote-hook"
    assert manager.get_linktree_settings()["api_key"] == "remote-secret"
    assert manager.get_linktree_settings()["profile_url"] == "https://linktr.ee/remote"
    assert manager.get_linktree_settings()["account_email"] == "k931103@gmail.com"
    assert manager.get_linktree_settings()["expected_account_email"] == "k931103@gmail.com"
    assert manager.get_linktree_auto_publish() is True
    assert manager.get_youtube_account_verification()["ok"] is True
    assert manager.get_1688_cookies() == {"session": "abc"}
    assert manager.get_all_settings()["linktree_webhook_url"].startswith("fernet:")
