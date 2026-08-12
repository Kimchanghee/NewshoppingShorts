import json
import os
from pathlib import Path

import pytest

from managers.settings_manager import SettingsManager


def _isolated_locations(monkeypatch, tmp_path):
    home = tmp_path / "home"
    current_dir = home / ".ssmaker"
    install_path = tmp_path / "install" / "ui_preferences.json"
    appdata = tmp_path / "appdata"
    local_appdata = tmp_path / "local-appdata"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setattr(SettingsManager, "_get_settings_dir", lambda self: str(current_dir))
    monkeypatch.setattr(
        SettingsManager,
        "_get_legacy_settings_path",
        lambda self: str(install_path),
    )
    return {
        "home": home,
        "current": current_dir / "ui_preferences.json",
        "install": install_path,
        "newshopping": home / ".newshopping" / "ui_preferences.json",
        "appdata": appdata / "SSMaker" / "ui_preferences.json",
    }


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_current_settings_win_and_v1552_types_migrate_idempotently(monkeypatch, tmp_path):
    paths = _isolated_locations(monkeypatch, tmp_path)
    _write_json(paths["install"], {"cta_id": "legacy-cta", "youtube_upload_interval": 60})
    _write_json(
        paths["current"],
        {
            "cta_id": "current-cta",
            "youtube_upload_interval": "240",
            "launch_on_startup": "false",
            "selected_voices": '["voice-a", "voice-a", "voice-b"]',
            "platform_video_sources": "Douyin, invalid, xiaohongshu, douyin",
            "linktree_profile_url": {"wrong": "type"},
            "linktree_auto_publish": "off",
            "cookies_inpock": '{"session": "cookie-value"}',
            "cookies_1688": ["wrong-type"],
            "future_plugin_setting": {"kept": [1, True, None]},
        },
    )

    manager = SettingsManager()
    settings = manager.get_all_settings()

    assert settings["cta_id"] == "current-cta"
    assert settings["youtube_upload_interval"] == 240
    assert settings["launch_on_startup"] is False
    assert settings["selected_voices"] == ["voice-a", "voice-b"]
    assert settings["platform_video_sources"] == ["douyin", "xiaohongshu"]
    assert settings["linktree_profile_url"] == ""
    assert settings["linktree_auto_publish"] is False
    assert settings["cookies_inpock"] == {"session": "cookie-value"}
    assert settings["cookies_1688"] == {}
    assert settings["future_plugin_setting"] == {"kept": [1, True, None]}
    assert settings["settings_schema_version"] == SettingsManager.CURRENT_SETTINGS_SCHEMA_VERSION
    assert json.loads(paths["install"].read_text(encoding="utf-8"))["cta_id"] == "legacy-cta"

    issue_components = {issue["component"] for issue in manager.get_recovery_issues()}
    assert issue_components == {"settings.core", "settings.linktree", "settings.youtube"}
    assert {issue["code"] for issue in manager.get_recovery_issues()} == {"ST-S002"}
    copied_issues = manager.get_recovery_issues()
    copied_issues[0]["code"] = "changed-by-caller"
    assert "changed-by-caller" not in {
        issue["code"] for issue in manager.get_recovery_issues()
    }

    migrated_bytes = paths["current"].read_bytes()
    unexpected_replaces = []
    monkeypatch.setattr(
        "managers.settings_manager.os.replace",
        lambda *args: unexpected_replaces.append(args),
    )
    reloaded = SettingsManager()
    assert paths["current"].read_bytes() == migrated_bytes
    assert unexpected_replaces == []
    assert reloaded.get_youtube_upload_interval() == 240


@pytest.mark.parametrize("legacy_key", ["newshopping", "appdata"])
def test_historical_user_locations_migrate_when_current_is_missing(
    monkeypatch, tmp_path, legacy_key
):
    paths = _isolated_locations(monkeypatch, tmp_path)
    _write_json(
        paths[legacy_key],
        {
            "settings_schema_version": SettingsManager.CURRENT_SETTINGS_SCHEMA_VERSION,
            "cta_id": f"from-{legacy_key}",
        },
    )

    manager = SettingsManager()

    assert manager.get_cta_id() == f"from-{legacy_key}"
    assert paths["current"].is_file()
    assert paths[legacy_key].is_file()
    assert any(
        issue["code"] == "ST-S002"
        and issue["source_path"] == os.path.abspath(paths[legacy_key])
        for issue in manager.get_recovery_issues()
    )


def test_corrupt_current_is_copied_to_recovery_and_replaced_with_safe_defaults(
    monkeypatch, tmp_path
):
    paths = _isolated_locations(monkeypatch, tmp_path)
    corrupt_bytes = b'{"youtube_upload_interval": "secret-fragment"'
    paths["current"].parent.mkdir(parents=True, exist_ok=True)
    paths["current"].write_bytes(corrupt_bytes)

    manager = SettingsManager()

    issues = manager.get_recovery_issues()
    parse_issue = next(issue for issue in issues if issue["code"] == "ST-S001")
    recovery_path = Path(parse_issue["recovery_path"])
    assert recovery_path.parent == paths["current"].parent / "recovery"
    assert recovery_path.read_bytes() == corrupt_bytes
    assert paths["current"].is_file()
    persisted = json.loads(paths["current"].read_text(encoding="utf-8"))
    assert persisted["youtube_upload_interval"] == 60
    assert persisted["settings_schema_version"] == SettingsManager.CURRENT_SETTINGS_SCHEMA_VERSION
    assert "secret-fragment" not in parse_issue["message"]


def test_non_object_json_is_a_schema_recovery_issue(monkeypatch, tmp_path):
    paths = _isolated_locations(monkeypatch, tmp_path)
    _write_json(paths["current"], ["not", "an", "object"])

    manager = SettingsManager()

    assert manager.get_cta_id() == SettingsManager.DEFAULT_SETTINGS["cta_id"]
    assert any(
        issue["code"] == "ST-S002" and issue["component"] == "settings.core"
        for issue in manager.get_recovery_issues()
    )


def test_saves_replace_a_same_directory_temporary_file(monkeypatch, tmp_path):
    paths = _isolated_locations(monkeypatch, tmp_path)
    replace_calls = []
    real_replace = os.replace

    def recording_replace(source, destination):
        replace_calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr("managers.settings_manager.os.replace", recording_replace)
    manager = SettingsManager()

    assert manager.set_theme("dark") is True
    assert len(replace_calls) == 1
    temporary_path, destination_path = replace_calls[0]
    assert temporary_path.parent == destination_path.parent == paths["current"].parent
    assert destination_path == paths["current"]
    assert not temporary_path.exists()
    assert json.loads(paths["current"].read_text(encoding="utf-8"))["theme"] == "dark"


def test_corrupt_linktree_cipher_isolated_without_blocking_startup(monkeypatch, tmp_path):
    paths = _isolated_locations(monkeypatch, tmp_path)
    _write_json(
        paths["current"],
        {
            "settings_schema_version": SettingsManager.CURRENT_SETTINGS_SCHEMA_VERSION,
            "linktree_webhook_url": "fernet:not-valid",
            "linktree_api_key": "fernet:also-not-valid",
            "linktree_auto_publish": True,
            "linktree_profile_url": "https://linktr.ee/example",
        },
    )

    manager = SettingsManager()
    recovered = manager.get_linktree_settings()

    assert recovered["webhook_url"] == ""
    assert recovered["api_key"] == ""
    assert recovered["auto_publish"] is False
    assert recovered["profile_url"] == "https://linktr.ee/example"
    assert any(
        issue["code"] == "ST-S001"
        and issue["component"] == "settings.linktree"
        for issue in manager.get_recovery_issues()
    )
