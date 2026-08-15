import json
import os
import re
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
    assert report["app_version"]
    for distribution in (
        "google-api-python-client",
        "google-auth",
        "google-auth-oauthlib",
        "google-api-core",
        "google-genai",
        "requests",
        "httpx",
    ):
        assert report["package_versions"].get(distribution), report
    runtime_modules = [
        "requests",
        "httpx",
        "google.genai",
        "google.api_core",
        "keyring",
    ]
    if os.name == "nt":
        runtime_modules.append("keyring.backends.Windows")
    for module_name in runtime_modules:
        assert report["runtime_imports"].get(module_name) is True, report


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
    spec = (ROOT / "ssmaker.spec").read_text(encoding="utf-8")

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
    excludes_match = re.search(r"excludes=\[(.*?)\]", spec, re.DOTALL)
    assert excludes_match is not None
    assert "'unittest'" not in excludes_match.group(1)


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


def test_release_google_runtime_stack_is_pinned_and_actual_module_folders_are_checked():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    spec = (ROOT / "ssmaker.spec").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")

    for pinned in (
        "google-genai==2.8.0",
        "google-api-core==2.34.0",
        "google-api-python-client==2.198.0",
        "google-auth==2.56.3",
        "google-auth-oauthlib==1.4.0",
        "google-auth-httplib2==0.4.1",
        "httplib2==0.32.0",
        "requests-oauthlib==2.0.0",
        "oauthlib==3.3.1",
        "requests==2.34.2",
        "httpx==0.28.1",
        "keyring==25.7.0",
    ):
        assert pinned in requirements

    for package in (
        "google.genai",
        "google.api_core",
        "google.auth",
        "google.oauth2",
        "keyring",
    ):
        assert f"'{package}'" in spec

    assert "$mustHaveDirectories" in build_script
    directory_check = build_script[
        build_script.index("$mustHaveDirectories"):build_script.index(
            "foreach ($item in $mustContain)"
        )
    ]
    assert '"httpx"' not in directory_check
    assert '"google_auth_httplib2"' not in directory_check
    for directory in (
        r"google\genai",
        r"google\api_core",
        r"google\auth",
        r"google\oauth2",
        "googleapiclient",
        "google_auth_oauthlib",
        "keyring",
    ):
        assert f'"{directory}"' in build_script
