import os
import stat
from pathlib import Path

from managers.youtube_manager import YouTubeManager


class _TestYouTubeManager(YouTubeManager):
    def __init__(self, user_dir: Path, app_dir: Path):
        self._test_user_dir = str(user_dir)
        self._test_app_dir = str(app_dir)
        super().__init__(gui=None, settings_file="youtube_settings_test.json")

    def _get_user_data_dir(self) -> str:
        return self._test_user_dir

    def _get_app_base_dir(self) -> str:
        return self._test_app_dir


def test_install_client_secrets_replaces_readonly_destination(tmp_path):
    user_dir = tmp_path / "user"
    app_dir = tmp_path / "app"
    user_dir.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)

    manager = _TestYouTubeManager(user_dir=user_dir, app_dir=app_dir)

    source = tmp_path / "client_secrets_source.json"
    source.write_text('{"installed": {"client_id": "new"}}', encoding="utf-8")

    destination = Path(manager._get_client_secrets_path())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('{"installed": {"client_id": "old"}}', encoding="utf-8")
    os.chmod(destination, stat.S_IREAD)

    installed_path = manager.install_client_secrets(str(source))

    assert Path(installed_path) == destination
    installed_content = Path(installed_path).read_text(encoding="utf-8")
    assert '"client_id": "new"' in installed_content


def test_migrate_legacy_oauth_files_to_user_profile(tmp_path):
    user_dir = tmp_path / "user"
    app_dir = tmp_path / "app"
    user_dir.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)

    manager = _TestYouTubeManager(user_dir=user_dir, app_dir=app_dir)

    legacy_token = app_dir / "youtube_token.json"
    legacy_token.write_text('{"token": "legacy"}', encoding="utf-8")

    legacy_secret_dir = app_dir / ".ssmaker_credentials" / "youtube"
    legacy_secret_dir.mkdir(parents=True, exist_ok=True)
    legacy_secret = legacy_secret_dir / "client_secrets.json"
    legacy_secret.write_text('{"installed": {"client_id": "legacy"}}', encoding="utf-8")

    token_path = Path(manager._get_token_path())
    secret_path = Path(manager._get_client_secrets_path())
    if token_path.exists():
        token_path.unlink()
    if secret_path.exists():
        secret_path.unlink()

    manager._migrate_legacy_oauth_files()

    assert token_path.exists()
    assert secret_path.exists()
    assert '"token": "legacy"' in token_path.read_text(encoding="utf-8")
    assert '"client_id": "legacy"' in secret_path.read_text(encoding="utf-8")
