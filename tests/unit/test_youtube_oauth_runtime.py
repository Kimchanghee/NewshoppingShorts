import json
from pathlib import Path

from managers.youtube_manager import (
    YouTubeManager,
    get_youtube_runtime_diagnostics,
)


ROOT = Path(__file__).resolve().parents[2]


def _desktop_config():
    return {
        "installed": {
            "client_id": "test.apps.googleusercontent.com",
            "client_secret": "test-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def test_offline_youtube_runtime_is_complete():
    report = get_youtube_runtime_diagnostics()

    assert report["ok"] is True, report
    assert Path(report["discovery_document"]).is_file()


def test_desktop_oauth_json_is_accepted(tmp_path):
    oauth_file = tmp_path / "client_secret.json"
    oauth_file.write_text(json.dumps(_desktop_config()), encoding="utf-8")

    valid, message = YouTubeManager.validate_client_secrets_file(str(oauth_file))

    assert valid is True
    assert message == ""


def test_web_oauth_json_is_rejected_with_desktop_instruction(tmp_path):
    web_config = _desktop_config()["installed"]
    oauth_file = tmp_path / "web_client.json"
    oauth_file.write_text(json.dumps({"web": web_config}), encoding="utf-8")

    valid, message = YouTubeManager.validate_client_secrets_file(str(oauth_file))

    assert valid is False
    assert "웹 애플리케이션" in message
    assert "데스크톱 앱" in message


def test_incomplete_oauth_json_names_missing_fields(tmp_path):
    oauth_file = tmp_path / "incomplete.json"
    oauth_file.write_text(
        json.dumps({"installed": {"client_id": "only-an-id"}}),
        encoding="utf-8",
    )

    valid, message = YouTubeManager.validate_client_secrets_file(str(oauth_file))

    assert valid is False
    assert "client_secret" in message
    assert "auth_uri" in message
    assert "token_uri" in message


def test_oauth_json_with_non_google_endpoints_is_rejected(tmp_path):
    config = _desktop_config()
    config["installed"]["token_uri"] = "https://example.test/token"
    oauth_file = tmp_path / "phishing.json"
    oauth_file.write_text(json.dumps(config), encoding="utf-8")

    valid, message = YouTubeManager.validate_client_secrets_file(str(oauth_file))

    assert valid is False
    assert "Google 공식 OAuth 주소" in message


def test_release_build_runs_source_and_frozen_youtube_smoke_checks():
    build_script = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")

    assert "validate_youtube_runtime.py" in build_script
    assert "--youtube-runtime-smoke" in build_script
    assert "googleapiclient\\discovery_cache\\documents\\youtube.v3.json" in build_script
    for package in (
        "google_auth_oauthlib",
        "google_auth_httplib2",
        "httplib2",
        "requests_oauthlib",
        "oauthlib",
    ):
        assert f'"{package}"' in build_script


def test_oauth_transport_dependencies_are_explicit_requirements():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    for distribution in (
        "google-api-python-client",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "httplib2",
        "requests-oauthlib",
        "oauthlib",
    ):
        assert any(
            line.strip().lower().startswith(distribution)
            for line in requirements.splitlines()
        )
