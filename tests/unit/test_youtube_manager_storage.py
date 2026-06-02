import os
import stat
from pathlib import Path

from managers.youtube_manager import AutoUploadSettings, YouTubeChannel, YouTubeManager


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
    source.write_text('{"installed": {"client_id": "new", "client_secret": "abc"}}', encoding="utf-8")

    secure_store = {}

    def _set_credential(key, value):
        secure_store[key] = value
        return True

    def _get_credential(key):
        return secure_store.get(key)

    manager._secrets_manager.set_credential = _set_credential
    manager._secrets_manager.get_credential = _get_credential

    destination = Path(manager._get_client_secrets_path())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('{"installed": {"client_id": "old"}}', encoding="utf-8")
    os.chmod(destination, stat.S_IREAD)

    installed_path = manager.install_client_secrets(str(source))

    assert Path(installed_path) == destination
    assert '"client_id": "new"' in secure_store[manager.CLIENT_SECRETS_KEY]
    assert not Path(installed_path).exists()


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
    legacy_secret.write_text(
        '{"installed": {"client_id": "legacy", "client_secret": "secret"}}',
        encoding="utf-8",
    )

    secure_store = {}

    def _set_credential(key, value):
        secure_store[key] = value
        return True

    def _get_credential(key):
        return secure_store.get(key)

    manager._secrets_manager.set_credential = _set_credential
    manager._secrets_manager.get_credential = _get_credential

    token_path = Path(manager._get_token_path())
    secret_path = Path(manager._get_client_secrets_path())
    if token_path.exists():
        token_path.unlink()
    if secret_path.exists():
        secret_path.unlink()

    manager._migrate_legacy_oauth_files()

    assert token_path.exists()
    assert '"token": "legacy"' in token_path.read_text(encoding="utf-8")
    assert '"client_id": "legacy"' in secure_store[manager.CLIENT_SECRETS_KEY]
    assert not secret_path.exists()


class _AccountVerificationSettings:
    def __init__(self, ok, message=""):
        self.ok = ok
        self.message = message
        self.account_email = ""

    def set_youtube_account_email(self, email):
        self.account_email = email
        return True

    def get_youtube_account_verification(self):
        return {
            "required": True,
            "ok": self.ok,
            "expected": "ympartners.uk@gmail.com",
            "actual": self.account_email,
            "message": self.message,
        }


def _make_upload_manager(monkeypatch, verification_settings):
    manager = object.__new__(YouTubeManager)
    manager._upload_settings = AutoUploadSettings(enabled=False)
    manager._upload_queue = []
    manager._upload_running = False
    manager._last_error_message = ""
    manager._channel = YouTubeChannel(account_email=verification_settings.account_email)
    monkeypatch.setattr("managers.youtube_manager.get_settings_manager", lambda: verification_settings)
    return manager


def test_upload_queue_blocks_when_expected_youtube_account_not_verified(monkeypatch):
    settings = _AccountVerificationSettings(
        ok=False,
        message="YouTube 기대 계정 이메일이 설정되어 있지만 OAuth 계정 이메일이 확인되지 않았습니다.",
    )
    manager = _make_upload_manager(monkeypatch, settings)

    manager.add_to_upload_queue(
        video_path="video.mp4",
        title="title",
        render_integrity={"ok": True},
        render_integrity_required=True,
    )

    assert manager._upload_queue == []
    assert "OAuth 계정 이메일" in manager.get_last_error()


def test_upload_queue_allows_verified_youtube_account(monkeypatch):
    settings = _AccountVerificationSettings(ok=True)
    settings.account_email = "ympartners.uk@gmail.com"
    manager = _make_upload_manager(monkeypatch, settings)

    manager.add_to_upload_queue(
        video_path="video.mp4",
        title="title",
        render_integrity={"ok": True},
        render_integrity_required=True,
    )

    assert len(manager._upload_queue) == 1


class _SyncSettings:
    def __init__(self):
        self.account_email = "ympartners.uk@gmail.com"
        self.connected_calls = []
        self.auto_upload_enabled = None

    def set_youtube_connected(self, connected, channel_id="", channel_name="", account_email=None):
        self.connected_calls.append(
            {
                "connected": connected,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "account_email": account_email,
            }
        )
        if account_email is not None:
            self.account_email = account_email
        if not connected:
            self.account_email = ""
        return True

    def set_youtube_auto_upload(self, enabled):
        self.auto_upload_enabled = enabled
        return True


def test_sync_settings_preserves_existing_youtube_account_email_when_channel_email_unknown(monkeypatch, tmp_path):
    settings = _SyncSettings()
    manager = object.__new__(YouTubeManager)
    manager._channel = YouTubeChannel(
        channel_id="UCkWrhk9ooMO5BFa-syG6Qig",
        channel_name="오늘의 쇼핑",
        account_email="",
    )
    manager._upload_settings = AutoUploadSettings(enabled=True)

    token_path = tmp_path / "youtube_token.json"
    token_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(manager, "_get_token_path", lambda: str(token_path))
    monkeypatch.setattr("managers.youtube_manager.get_settings_manager", lambda: settings)

    manager._sync_settings_manager_state()

    assert settings.connected_calls[-1]["account_email"] is None
    assert settings.account_email == "ympartners.uk@gmail.com"
    assert settings.auto_upload_enabled is True
