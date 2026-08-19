from types import SimpleNamespace

from core.video.batch.api_key_recovery import is_google_drive_permission_error
from main import VideoAnalyzerGUI
from user_facing_errors import classify_error, friendly_error_title
from utils import gemini_key_probe


def test_blocked_manager_key_is_not_reused_from_config_fallback():
    fallback_calls = []

    class BlockedManager:
        def get_available_key(self):
            raise RuntimeError("all keys blocked")

    app = SimpleNamespace(
        api_key_manager=BlockedManager(),
        model_provider=SimpleNamespace(
            _get_first_api_key=lambda: fallback_calls.append(True) or "blocked-key"
        ),
    )

    assert VideoAnalyzerGUI.init_client(app) is False
    assert fallback_calls == []


def test_gemini_project_denial_is_not_misclassified_as_drive_file_error():
    message = (
        "403 PERMISSION_DENIED: Your project has been denied access. "
        "Please contact support."
    )

    assert is_google_drive_permission_error(message) is False
    assert classify_error(message) == "gemini_key_rejected"
    assert friendly_error_title(message) == "Gemini API 키를 사용할 수 없어요"


def test_drive_file_permission_requires_drive_context():
    assert is_google_drive_permission_error(
        "Google Drive: you do not have permission to access the file. Request access."
    ) is True
    assert is_google_drive_permission_error(
        "Permission denied while calling Gemini"
    ) is False


def test_live_probe_reports_status_without_returning_secret_values(monkeypatch):
    class Response:
        def __init__(self, status_code, status=""):
            self.status_code = status_code
            self._status = status

        def json(self):
            return {"error": {"status": self._status}}

    def fake_post(_url, *, params, json, timeout):
        assert timeout == 2.0
        assert json["generationConfig"]["maxOutputTokens"] == 4
        return Response(200) if params["key"] == "valid-secret" else Response(
            403, "PERMISSION_DENIED"
        )

    monkeypatch.setattr(gemini_key_probe.requests, "post", fake_post)

    result = gemini_key_probe.probe_gemini_keys(
        {"api_1": "valid-secret", "api_2": "rejected-secret"},
        timeout_seconds=2.0,
    )

    assert result["ok"] is True
    assert [item["alias"] for item in result["valid"]] == ["api_1"]
    assert [item["alias"] for item in result["rejected"]] == ["api_2"]
    assert "valid-secret" not in str(result)
    assert "rejected-secret" not in str(result)
