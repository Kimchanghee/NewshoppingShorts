from managers.settings_manager import SettingsManager


def _settings_in_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(SettingsManager, "_get_settings_dir", lambda self: str(tmp_path))
    monkeypatch.setattr(
        SettingsManager,
        "_get_legacy_settings_path",
        lambda self: str(tmp_path / "legacy_ui_preferences.json"),
    )


def test_launch_on_startup_defaults_enabled(monkeypatch, tmp_path):
    _settings_in_tmp(monkeypatch, tmp_path)

    settings = SettingsManager()

    assert settings.get_launch_on_startup() is True


def test_launch_on_startup_setting_saves_and_syncs(monkeypatch, tmp_path):
    _settings_in_tmp(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(
        "utils.autostart.sync_launch_on_startup",
        lambda enabled: calls.append(enabled) or True,
    )

    settings = SettingsManager()

    assert settings.set_launch_on_startup(False) is True
    assert settings.get_launch_on_startup() is False
    assert calls == [False]

    reloaded = SettingsManager()
    assert reloaded.get_launch_on_startup() is False
