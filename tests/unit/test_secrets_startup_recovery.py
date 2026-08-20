from pathlib import Path

from utils.secrets_manager import SecretsManager


def _reset_issues():
    SecretsManager._startup_issues = []
    SecretsManager._reported_issue_sources = set()


def test_corrupt_gemini_secret_store_is_copied_and_reported(monkeypatch, tmp_path):
    _reset_issues()
    app_dir = tmp_path / ".ssmaker"
    app_dir.mkdir()
    secret_file = app_dir / ".secrets"
    secret_file.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(
        SecretsManager, "_candidate_base_dirs", classmethod(lambda cls: [app_dir])
    )
    monkeypatch.setattr(
        SecretsManager, "_candidate_secret_files", classmethod(lambda cls: [secret_file])
    )

    assert SecretsManager._read_secrets_file() == {}

    issues = SecretsManager.get_startup_issues()
    assert issues[0]["code"] == "ST-G001"
    assert issues[0]["component"] == "settings.gemini"
    assert Path(issues[0]["recovery_path"]).read_text(encoding="utf-8") == "{broken"
    assert "broken" not in issues[0]["message"]

    # Repeated key lookups must not create an unbounded set of backup copies.
    assert SecretsManager._read_secrets_file() == {}
    assert len(list((app_dir / "recovery").glob("secrets.*.corrupt"))) == 1


def test_bad_gemini_cipher_isolated_without_exception(monkeypatch, tmp_path):
    _reset_issues()
    secret_file = tmp_path / ".secrets"
    secret_file.write_text('{"gemini_api_1": "fernet:not-valid"}', encoding="utf-8")
    monkeypatch.setattr(
        SecretsManager, "_candidate_secret_files", classmethod(lambda cls: [secret_file])
    )

    assert SecretsManager._read_from_file("gemini_api_1") is None
    issue = SecretsManager.get_startup_issues()[0]
    assert issue["code"] == "ST-G002"
    assert issue["component"] == "settings.gemini"


def test_frozen_windows_refuses_recoverable_file_fallback(monkeypatch):
    _reset_issues()
    monkeypatch.setattr("utils.secrets_manager.sys.frozen", True, raising=False)
    monkeypatch.setattr(SecretsManager, "_use_keyring", True)
    monkeypatch.setattr(
        SecretsManager,
        "_init_keyring",
        classmethod(lambda cls: False),
    )

    def _unexpected_store(cls, _name, _value):
        raise AssertionError("packaged Windows must not use file fallback")

    def _unexpected_read(cls, _name):
        raise AssertionError("packaged Windows must not read fallback without keyring")

    monkeypatch.setattr(
        SecretsManager,
        "_store_to_file",
        classmethod(_unexpected_store),
    )
    monkeypatch.setattr(
        SecretsManager,
        "_read_from_file",
        classmethod(_unexpected_read),
    )

    assert SecretsManager.store_api_key("gemini_api_1", "secret-value") is False
    assert SecretsManager.get_api_key("gemini_api_1") is None
    assert any(
        issue["code"] == "ST-G003"
        for issue in SecretsManager.get_startup_issues()
    )
