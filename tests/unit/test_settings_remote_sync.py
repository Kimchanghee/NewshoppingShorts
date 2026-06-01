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
    )

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
    assert captured["linktree_auto_publish"] is True


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
        "linktree_auto_publish": True,
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
    assert manager.get_linktree_auto_publish() is True
    assert manager.get_1688_cookies() == {"session": "abc"}
    assert manager.get_all_settings()["linktree_webhook_url"].startswith("fernet:")
