import json
from pathlib import Path

from managers.youtube_manager import YouTubeManager


class _RecoveryYouTubeManager(YouTubeManager):
    def __init__(self, user_dir: Path, app_dir: Path):
        self._test_user_dir = str(user_dir)
        self._test_app_dir = str(app_dir)
        super().__init__(gui=None, settings_file="youtube_settings.json")

    def _get_user_data_dir(self) -> str:
        return self._test_user_dir

    def _get_app_base_dir(self) -> str:
        return self._test_app_dir


def test_corrupt_youtube_settings_are_isolated_and_reported(tmp_path):
    user_dir = tmp_path / "user"
    app_dir = tmp_path / "app"
    user_dir.mkdir()
    app_dir.mkdir()
    (user_dir / "youtube_settings.json").write_text("{broken", encoding="utf-8")

    manager = _RecoveryYouTubeManager(user_dir, app_dir)

    issues = manager.get_startup_issues()
    assert manager.get_upload_settings().interval_minutes == 30
    assert issues[0]["code"] == "ST-Y001"
    assert issues[0]["component"] == "settings.youtube"
    assert Path(issues[0]["recovery_path"]).read_text(encoding="utf-8") == "{broken"
    repaired = json.loads((user_dir / "youtube_settings.json").read_text(encoding="utf-8"))
    assert repaired["upload_settings"]["interval_minutes"] == 30

    reloaded = _RecoveryYouTubeManager(user_dir, app_dir)
    assert reloaded.get_startup_issues() == []


def test_legacy_string_youtube_values_are_normalized(tmp_path):
    user_dir = tmp_path / "user"
    app_dir = tmp_path / "app"
    user_dir.mkdir()
    app_dir.mkdir()
    (user_dir / "youtube_settings.json").write_text(
        json.dumps(
            {
                "upload_settings": {
                    "enabled": "true",
                    "interval_minutes": "60",
                    "max_hashtags": "12",
                    "made_for_kids": "false",
                }
            }
        ),
        encoding="utf-8",
    )

    manager = _RecoveryYouTubeManager(user_dir, app_dir)
    settings = manager.get_upload_settings()

    assert settings.enabled is True
    assert settings.interval_minutes == 60
    assert settings.max_hashtags == 12
    assert settings.made_for_kids is False
    assert manager.get_startup_issues() == []
