import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials

from managers.queue_manager import QueueManager
from managers.youtube_manager import YouTubeChannel, YouTubeManager
from ui.panels.upload_panel import _YouTubeOAuthWorker


ROOT = Path(__file__).resolve().parents[2]


class _MemorySecrets:
    def __init__(self):
        self.values = {}

    def set_credential(self, key, value):
        self.values[key] = value
        return True

    def get_credential(self, key):
        return self.values.get(key)

    def delete_credential(self, key):
        return self.values.pop(key, None) is not None


def _manager(tmp_path: Path) -> YouTubeManager:
    manager = object.__new__(YouTubeManager)
    manager._secrets_manager = _MemorySecrets()
    manager._get_user_data_dir = lambda: str(tmp_path)
    app_dir = tmp_path / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    manager._get_app_base_dir = lambda: str(app_dir)
    return manager


def _credentials() -> Credentials:
    return Credentials(
        token="access-token-must-stay-secret",
        refresh_token="refresh-token-must-stay-secret",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="test.apps.googleusercontent.com",
        client_secret="client-secret-must-stay-secret",
        scopes=YouTubeManager.SCOPES,
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )


def test_oauth_token_round_trips_through_secure_store_without_plaintext_file(tmp_path):
    manager = _manager(tmp_path)

    assert manager._store_credentials_securely(_credentials()) is True

    token_path = Path(manager._get_token_path())
    assert not token_path.exists()
    assert manager._has_stored_credentials() is True

    stored_payload = manager._secrets_manager.values[manager.OAUTH_TOKEN_KEY]
    assert json.loads(stored_payload)["refresh_token"] == "refresh-token-must-stay-secret"

    restored = manager._load_stored_credentials()
    assert restored is not None
    assert restored.refresh_token == "refresh-token-must-stay-secret"


def test_legacy_plaintext_token_is_migrated_then_deleted(tmp_path):
    manager = _manager(tmp_path)
    legacy_path = Path(manager._get_legacy_token_path())
    legacy_path.write_text(_credentials().to_json(), encoding="utf-8")

    manager._migrate_legacy_oauth_files()

    assert manager._has_stored_credentials() is True
    assert not legacy_path.exists()
    assert not Path(manager._get_token_path()).exists()
    restored = manager._load_stored_credentials()
    assert restored is not None
    assert restored.refresh_token == "refresh-token-must-stay-secret"


def test_secure_client_config_removes_all_managed_plaintext_legacy_copies(tmp_path):
    manager = _manager(tmp_path)
    config = {
        "installed": {
            "client_id": "test.apps.googleusercontent.com",
            "client_secret": "must-not-remain-on-disk",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    manager._secrets_manager.values[manager.CLIENT_SECRETS_KEY] = json.dumps(config)
    legacy_paths = [
        Path(manager._get_client_secrets_path()),
        Path(manager._get_legacy_managed_client_secrets_path()),
        Path(manager._get_legacy_client_secrets_path()),
    ]
    for path in legacy_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    manager._migrate_legacy_oauth_files()

    assert all(not path.exists() for path in legacy_paths)


def test_saved_connection_restores_service_without_plaintext_token(monkeypatch, tmp_path):
    manager = _manager(tmp_path)
    manager._youtube_service = None
    manager._credentials = None
    manager._channel = YouTubeChannel(channel_id="UC123", channel_name="Test Channel")
    assert manager._store_credentials_securely(_credentials()) is True

    built = object()
    monkeypatch.setattr(
        "managers.youtube_manager.build",
        lambda *args, **kwargs: built,
    )

    assert manager._ensure_youtube_service() is True
    assert manager._youtube_service is built
    assert manager._credentials is not None
    assert not Path(manager._get_token_path()).exists()


def test_oauth_url_is_published_and_can_be_reopened_in_edge(monkeypatch, tmp_path):
    manager = _manager(tmp_path)
    published = []
    opened = []
    manager.set_oauth_url_callback(published.append)
    monkeypatch.setattr(
        manager,
        "_launch_oauth_url",
        lambda url, browser="default": opened.append((url, browser)) or True,
    )
    oauth_url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=test"

    assert manager._handle_oauth_browser_open(oauth_url) is True
    assert published == [oauth_url]
    assert opened == [(oauth_url, "default")]
    assert manager.get_oauth_authorization_url() == oauth_url

    assert manager.open_oauth_authorization_url("edge") is True
    assert opened[-1] == (oauth_url, "edge")


def test_non_google_oauth_url_is_never_opened(monkeypatch, tmp_path):
    manager = _manager(tmp_path)
    opened = []
    monkeypatch.setattr(
        manager,
        "_launch_oauth_url",
        lambda url, browser="default": opened.append((url, browser)) or True,
    )

    assert manager._handle_oauth_browser_open("https://evil.example/steal") is False
    assert opened == []


def test_connect_uses_browser_bridge_and_ten_minute_timeout(monkeypatch, tmp_path):
    manager = _manager(tmp_path)
    manager._last_error_message = ""
    manager._credentials = None
    manager._youtube_service = None
    manager._channel = None
    manager._on_connection_changed = None
    manager._load_client_secret_config_securely = lambda: {
        "installed": {
            "client_id": "test.apps.googleusercontent.com",
            "client_secret": "secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    manager._fetch_oauth_account_email = lambda creds: "person@example.com"
    manager._account_guard_message = lambda: ""
    def _fetch_channel(account_email=""):
        manager._channel = YouTubeChannel(
            channel_id="UC123",
            channel_name="Test Channel",
        )
        return True

    manager._fetch_channel_info = _fetch_channel

    captured = {}

    class _Flow:
        def run_local_server(self, **kwargs):
            captured.update(kwargs)
            return _credentials()

    class _InstalledAppFlow:
        @staticmethod
        def from_client_config(config, scopes):
            return _Flow()

    monkeypatch.setattr("managers.youtube_manager.get_youtube_runtime_diagnostics", lambda: {"ok": True})
    monkeypatch.setattr("managers.youtube_manager.InstalledAppFlow", _InstalledAppFlow)
    monkeypatch.setattr("managers.youtube_manager.build", lambda *args, **kwargs: object())

    assert manager.connect_channel(force_reauth=True) is True
    assert captured["timeout_seconds"] == 600
    assert captured["authorization_prompt_message"] is None
    assert captured["browser"].startswith("ssmaker-youtube-oauth-")


def test_oauth_worker_forwards_authorization_url_and_forces_new_login():
    class _Manager:
        def __init__(self):
            self.callback = None
            self.force_reauth = None

        def set_oauth_url_callback(self, callback):
            self.callback = callback

        def install_client_secrets(self, source_path):
            return "managed-client-secrets"

        def connect_channel(self, client_secrets_file=None, force_reauth=False):
            self.force_reauth = force_reauth
            self.callback("https://accounts.google.com/o/oauth2/v2/auth?client_id=test")
            return True

        def get_channel_info(self):
            return {"id": "UC123", "title": "Test Channel"}

        def get_last_error(self):
            return ""

    manager = _Manager()
    worker = _YouTubeOAuthWorker(manager, "selected.json")
    urls = []
    results = []
    worker.authorization_url_ready.connect(urls.append)
    worker.finished.connect(lambda *args: results.append(args))

    worker.run()

    assert urls == ["https://accounts.google.com/o/oauth2/v2/auth?client_id=test"]
    assert manager.force_reauth is True
    assert manager.callback is None
    assert results == [(True, {"id": "UC123", "title": "Test Channel"}, "")]


def test_oauth_worker_rejects_success_without_channel_id_and_name():
    class _Manager:
        def set_oauth_url_callback(self, callback):
            pass

        def install_client_secrets(self, source_path):
            return "managed-client-secrets"

        def connect_channel(self, client_secrets_file=None, force_reauth=False):
            return True

        def get_channel_info(self):
            return {}

        def get_last_error(self):
            return ""

    worker = _YouTubeOAuthWorker(_Manager(), "selected.json")
    results = []
    worker.finished.connect(lambda *args: results.append(args))

    worker.run()

    assert results[0][0] is False
    assert "채널 ID" in results[0][2]


def test_oauth_worker_never_exposes_secrets_from_unexpected_errors(caplog):
    class _Manager:
        def set_oauth_url_callback(self, callback):
            pass

        def install_client_secrets(self, source_path):
            return "managed-client-secrets"

        def connect_channel(self, client_secrets_file=None, force_reauth=False):
            raise RuntimeError("access_token=must-not-leak")

        def get_last_error(self):
            return ""

    worker = _YouTubeOAuthWorker(_Manager(), "selected.json")
    results = []
    worker.finished.connect(lambda *args: results.append(args))

    worker.run()

    assert "must-not-leak" not in caplog.text
    assert "must-not-leak" not in results[0][2]
    assert results[0][0] is False


def test_youtube_connect_dialog_exposes_copy_and_browser_fallback_controls():
    source = (ROOT / "ui" / "panels" / "upload_panel.py").read_text(encoding="utf-8")

    assert "승인 링크 복사" in source
    assert "기본 브라우저로 열기" in source
    assert "Microsoft Edge로 열기" in source
    assert "authorization_url_ready.connect" in source


def test_channel_lookup_without_a_real_channel_is_not_connection_success(tmp_path):
    manager = _manager(tmp_path)
    manager._last_error_message = ""
    manager._channel = None

    class _Request:
        @staticmethod
        def execute():
            return {"items": []}

    class _Channels:
        @staticmethod
        def list(**kwargs):
            return _Request()

    class _Service:
        @staticmethod
        def channels():
            return _Channels()

    manager._youtube_service = _Service()

    assert manager._fetch_channel_info(account_email="person@example.com") is False
    assert manager._channel is None
    assert "YouTube 채널" in manager.get_last_error()


def test_failed_forced_reauth_preserves_previous_channel_and_token(monkeypatch, tmp_path):
    manager = _manager(tmp_path)
    old_credentials = _credentials()
    old_service = object()
    old_channel = YouTubeChannel(channel_id="UCOLD", channel_name="Old Channel")
    manager._last_error_message = ""
    manager._credentials = old_credentials
    manager._youtube_service = old_service
    manager._channel = old_channel
    manager._on_connection_changed = None
    assert manager._store_credentials_securely(old_credentials) is True
    old_payload = manager._secrets_manager.values[manager.OAUTH_TOKEN_KEY]
    manager._load_client_secret_config_securely = lambda: {
        "installed": {
            "client_id": "new.apps.googleusercontent.com",
            "client_secret": "new-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    manager._fetch_oauth_account_email = lambda creds: "new@example.com"

    new_credentials = Credentials(
        token="new-access",
        refresh_token="new-refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="new.apps.googleusercontent.com",
        client_secret="new-secret",
        scopes=YouTubeManager.SCOPES,
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    class _Flow:
        def run_local_server(self, **kwargs):
            return new_credentials

    class _InstalledAppFlow:
        @staticmethod
        def from_client_config(config, scopes):
            return _Flow()

    def _failed_fetch(account_email=""):
        manager._channel = YouTubeChannel(channel_id="UCNEW", channel_name="New Channel")
        manager._last_error_message = "채널 조회 실패"
        return False

    manager._fetch_channel_info = _failed_fetch
    monkeypatch.setattr("managers.youtube_manager.get_youtube_runtime_diagnostics", lambda: {"ok": True})
    monkeypatch.setattr("managers.youtube_manager.InstalledAppFlow", _InstalledAppFlow)
    monkeypatch.setattr("managers.youtube_manager.build", lambda *args, **kwargs: object())

    assert manager.connect_channel(force_reauth=True) is False
    assert manager._channel is old_channel
    assert manager._credentials is old_credentials
    assert manager._youtube_service is old_service
    assert manager._secrets_manager.values[manager.OAUTH_TOKEN_KEY] == old_payload


def test_damaged_saved_token_is_removed_with_reconnect_instruction(tmp_path):
    manager = _manager(tmp_path)
    manager._youtube_service = None
    manager._credentials = None
    manager._channel = YouTubeChannel(channel_id="UC123", channel_name="Old Channel")
    manager._last_error_message = ""
    manager._secrets_manager.values[manager.OAUTH_TOKEN_KEY] = "not-json"

    assert manager._ensure_youtube_service() is False
    assert manager._has_stored_credentials() is False
    assert "다시 연결" in manager.get_last_error()


def test_revoked_refresh_token_is_removed_and_requests_reconnection(monkeypatch, tmp_path):
    manager = _manager(tmp_path)
    manager._youtube_service = None
    manager._credentials = None
    manager._channel = YouTubeChannel(channel_id="UC123", channel_name="Old Channel")
    manager._last_error_message = ""
    manager._on_connection_changed = None
    manager._save_settings = lambda: None
    manager._sync_settings_manager_state = lambda: None
    manager._migrate_legacy_oauth_files = lambda: None
    manager._remove_connected_account_registry = lambda channel_id: True
    manager.stop_auto_upload = lambda: None
    manager._secrets_manager.values[manager.OAUTH_TOKEN_KEY] = '{"token":"stored"}'

    class _RevokedCredentials:
        valid = False
        expired = True
        refresh_token = "refresh-secret"

        @staticmethod
        def refresh(request):
            raise RuntimeError("invalid_grant access_token=must-not-be-logged")

    manager._load_stored_credentials = lambda scopes=None: _RevokedCredentials()

    assert manager._ensure_youtube_service() is False
    assert manager._channel is None
    assert manager._has_stored_credentials() is False
    assert "다시 연결" in manager.get_last_error()


def test_oauth_error_text_redacts_all_token_and_secret_values():
    raw = (
        "Bearer access-secret access_token=access-secret "
        '"refresh_token":"refresh-secret" client_secret=client-secret '
        "https://localhost/?code=auth-code&state=csrf-state"
    )

    sanitized = YouTubeManager._sanitize_oauth_error(raw)

    for secret in (
        "access-secret",
        "refresh-secret",
        "client-secret",
        "auth-code",
        "csrf-state",
    ):
        assert secret not in sanitized
    assert sanitized.count("[REDACTED]") >= 5


def test_upload_queue_detects_secure_youtube_token_without_plaintext_file(
    monkeypatch,
):
    secure_store = type(
        "SecureStore",
        (),
        {"get_credential": lambda self, key: '{"token":"stored"}'},
    )()
    monkeypatch.setattr(
        "managers.queue_manager.get_secrets_manager",
        lambda: secure_store,
    )

    assert QueueManager._youtube_upload_token_exists() is True
