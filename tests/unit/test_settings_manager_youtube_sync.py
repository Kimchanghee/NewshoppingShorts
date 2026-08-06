import json

from managers.settings_manager import SettingsManager


def test_youtube_connection_syncs_from_secure_token_and_channel_file(monkeypatch, tmp_path):
    monkeypatch.setattr(SettingsManager, "_get_settings_dir", lambda self: str(tmp_path))
    monkeypatch.setattr(
        SettingsManager,
        "_get_legacy_settings_path",
        lambda self: str(tmp_path / "legacy_ui_preferences.json"),
    )

    secure_store = type(
        "SecureStore",
        (),
        {"get_credential": lambda self, key: '{"token":"demo"}'},
    )()
    monkeypatch.setattr(
        "managers.settings_manager.get_secrets_manager",
        lambda: secure_store,
    )
    (tmp_path / "youtube_settings.json").write_text(
        json.dumps(
            {
                "channel": {
                    "channel_id": "UC-demo",
                    "channel_name": "오늘의 쇼핑",
                    "account_email": "ympartners.uk@gmail.com",
                },
                "upload_settings": {
                    "enabled": True,
                    "interval_minutes": 240,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    settings = SettingsManager()

    assert settings.get_youtube_connected() is True
    assert settings.get_youtube_channel_info() == {
        "channel_id": "UC-demo",
        "channel_name": "오늘의 쇼핑",
        "account_email": "ympartners.uk@gmail.com",
        "expected_account_email": "ympartners.uk@gmail.com",
    }
    assert settings.get_youtube_auto_upload() is True
    assert settings.get_youtube_upload_interval() == 240
