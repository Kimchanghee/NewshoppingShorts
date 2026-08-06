from managers.account_registry import (
    AccountRegistry,
    MAX_ACCOUNTS,
    secure_account_token_key,
)
from managers.youtube_manager import YouTubeChannel, YouTubeManager


ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def test_connected_youtube_channel_moves_slot_count_from_zero_to_one(tmp_path):
    registry = AccountRegistry(path=str(tmp_path / "accounts.json"))

    account = registry.upsert_connected_channel(
        platform="youtube",
        channel_id="UC123",
        name="오늘의 쇼핑",
        account_email="person@example.com",
        credential_key="youtube_oauth_token_json_v1",
    )

    assert MAX_ACCOUNTS == 5
    assert registry.count() == 1
    assert registry.slots_remaining() == 4
    assert account.connected is True
    assert account.channel_id == "UC123"
    assert account.account_email == "person@example.com"
    assert account.credential_key == "youtube_oauth_token_json_v1"

    same_account = registry.upsert_connected_channel(
        platform="youtube",
        channel_id="UC123",
        name="오늘의 쇼핑 새 이름",
        account_email="person@example.com",
        credential_key="youtube_oauth_token_json_v1",
    )
    assert same_account.id == account.id
    assert registry.count() == 1
    assert registry.get(account.id).name == "오늘의 쇼핑 새 이름"


def test_youtube_manager_registers_verified_channel_in_slot_list(monkeypatch, tmp_path):
    registry = AccountRegistry(path=str(tmp_path / "accounts.json"))
    monkeypatch.setattr("managers.account_registry.AccountRegistry", lambda: registry)
    manager = object.__new__(YouTubeManager)
    manager._channel = YouTubeChannel(
        channel_id="UC456",
        channel_name="테스트 채널",
        account_email="person@example.com",
    )
    secure_values = {manager.OAUTH_TOKEN_KEY: '{"token":"secret"}'}
    manager._secrets_manager = type(
        "SecureStore",
        (),
        {
            "get_credential": lambda self, key: secure_values.get(key),
            "set_credential": lambda self, key, value: secure_values.__setitem__(key, value) is None,
        },
    )()

    assert manager._sync_connected_account_registry() is True
    accounts = registry.by_platform("youtube")
    assert len(accounts) == 1
    assert accounts[0].channel_id == "UC456"
    expected_key = secure_account_token_key("youtube", accounts[0].id)
    assert accounts[0].credential_key == expected_key
    assert secure_values[expected_key] == '{"token":"secret"}'


def test_per_account_token_key_is_safe_bounded_and_not_a_file_path():
    key = secure_account_token_key("youtube", "yt_채널 이름/../../secret")

    assert key.startswith("youtube_oauth_")
    assert key.endswith("_v1")
    assert len(key) <= 64
    assert "/" not in key
    assert "\\" not in key
    assert ".." not in key


def test_multi_account_panel_never_copies_plaintext_youtube_tokens():
    source = (ROOT / "ui" / "panels" / "multi_account_panel.py").read_text(
        encoding="utf-8"
    )

    assert 'src_name = "youtube_token.json"' not in source
    assert "upsert_connected_channel" in source
    assert "secure_account_token_key" in source


def test_remove_connected_channel_returns_removed_secure_credentials(tmp_path):
    registry = AccountRegistry(path=str(tmp_path / "accounts.json"))
    account = registry.upsert_connected_channel(
        platform="youtube",
        channel_id="UC_REMOVE",
        name="Remove Me",
        credential_key="youtube_oauth_deadbeef_v1",
    )
    registry.add(platform="instagram", name="Keep Me", connected=True)

    removed = registry.remove_connected_channel("youtube", "UC_REMOVE")

    assert [item.id for item in removed] == [account.id]
    assert registry.by_platform("youtube") == []
    assert len(registry.by_platform("instagram")) == 1


def test_disconnect_removes_global_and_per_account_secure_tokens(monkeypatch, tmp_path):
    registry = AccountRegistry(path=str(tmp_path / "accounts.json"))
    account = registry.upsert_connected_channel(
        platform="youtube",
        channel_id="UC_REMOVE",
        name="Remove Me",
    )
    account_key = secure_account_token_key("youtube", account.id)
    registry.update(account.id, credential_key=account_key)
    monkeypatch.setattr("managers.account_registry.AccountRegistry", lambda: registry)

    manager = object.__new__(YouTubeManager)
    manager._channel = YouTubeChannel(
        channel_id="UC_REMOVE",
        channel_name="Remove Me",
    )
    manager._credentials = object()
    manager._youtube_service = object()
    manager._secrets_manager = type(
        "SecureStore",
        (),
        {
            "values": {
                YouTubeManager.OAUTH_TOKEN_KEY: '{"token":"global"}',
                account_key: '{"token":"account"}',
            },
            "delete_credential": lambda self, key: self.values.pop(key, None) is not None,
            "get_credential": lambda self, key: self.values.get(key),
        },
    )()
    manager._save_settings = lambda: None
    manager._sync_settings_manager_state = lambda: None
    manager.stop_auto_upload = lambda: None
    manager._on_connection_changed = None
    manager._get_token_path = lambda: str(tmp_path / "youtube_token.json")

    manager.disconnect_channel()

    assert registry.by_platform("youtube") == []
    assert manager._secrets_manager.values == {}
