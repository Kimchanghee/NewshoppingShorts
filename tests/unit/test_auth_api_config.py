import importlib


EXPECTED_API_URL = "https://13-124-7-65.nip.io"


def test_default_auth_api_url_points_to_reachable_server(monkeypatch):
    monkeypatch.delenv("API_SERVER_URL", raising=False)
    monkeypatch.delenv("USER_DASHBOARD_API_URL", raising=False)
    monkeypatch.delenv("PAYMENT_API_BASE_URL", raising=False)

    import caller.rest as rest
    import config

    rest = importlib.reload(rest)
    config = importlib.reload(config)

    assert rest.main_server == EXPECTED_API_URL
    assert config.PAYMENT_API_BASE_URL == EXPECTED_API_URL


def test_deprecated_cloud_run_url_is_replaced_with_reachable_server(monkeypatch):
    monkeypatch.setenv(
        "API_SERVER_URL",
        "https://ssmaker-auth-api-1049571775048.us-central1.run.app",
    )
    monkeypatch.setenv(
        "PAYMENT_API_BASE_URL",
        "https://ssmaker-auth-api-m2hewckpba-uc.a.run.app",
    )
    monkeypatch.delenv("USER_DASHBOARD_API_URL", raising=False)

    import caller.rest as rest
    import config

    rest = importlib.reload(rest)
    config = importlib.reload(config)

    assert rest.main_server == EXPECTED_API_URL
    assert rest._candidate_api_servers() == [EXPECTED_API_URL]
    assert config.PAYMENT_API_BASE_URL == EXPECTED_API_URL


def test_login_retries_stale_404_endpoint(monkeypatch):
    import caller.rest as rest

    calls = []

    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

    class FakeSession:
        def post(self, url, json, timeout):
            calls.append(url)
            if len(calls) == 1:
                return FakeResponse(404, '{"detail": "Not Found"}')
            return FakeResponse(200, '{"status": false, "message": "bad password"}')

    monkeypatch.setattr(rest, "_check_https_security", lambda: True)
    monkeypatch.setattr(rest, "_secure_session", FakeSession())
    monkeypatch.setattr(rest, "main_server", "https://stale.example.com")
    monkeypatch.delenv("USER_DASHBOARD_API_URL", raising=False)
    monkeypatch.delenv("API_SERVER_URL_FALLBACK", raising=False)

    result = rest.login(
        userId="sstale_client",
        userPw="Password123",
        key="",
        ip="127.0.0.1",
        force=False,
    )

    assert calls == [
        "https://stale.example.com/user/login/god",
        f"{EXPECTED_API_URL}/user/login/god",
    ]
    assert rest.main_server == EXPECTED_API_URL
    assert result["status"] is False


def test_registration_request_sends_ssmaker_program_type(monkeypatch):
    import caller.rest as rest

    captured = {}

    class FakeResponse:
        status_code = 200
        text = '{"success": true, "data": {"program_type": "ssmaker"}}'

        def json(self):
            return {"success": True, "data": {"program_type": "ssmaker"}}

        def raise_for_status(self):
            return None

    class FakeSession:
        def post(self, url, json, timeout):
            captured["url"] = url
            captured["json"] = json
            captured["timeout"] = timeout
            return FakeResponse()

    monkeypatch.setattr(rest, "_check_https_security", lambda: True)
    monkeypatch.setattr(rest, "_secure_session", FakeSession())
    monkeypatch.setattr(rest, "main_server", EXPECTED_API_URL)

    result = rest.submitRegistrationRequest(
        "Tester",
        "sstest_client",
        "Password123",
        "010-1234-5678",
        "tester@example.com",
    )

    assert result["success"] is True
    assert captured["url"] == f"{EXPECTED_API_URL}/user/register/request"
    assert captured["json"]["program_type"] == "ssmaker"


def test_registration_retries_stale_404_endpoint(monkeypatch):
    import caller.rest as rest

    calls = []

    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

        def json(self):
            if self.status_code == 200:
                return {"success": True, "data": {"program_type": "ssmaker"}}
            return {"detail": "Not Found"}

        def raise_for_status(self):
            return None

    class FakeSession:
        def post(self, url, json, timeout):
            calls.append(url)
            if len(calls) == 1:
                return FakeResponse(404, '{"detail": "Not Found"}')
            return FakeResponse(200, '{"success": true}')

    monkeypatch.setattr(rest, "_check_https_security", lambda: True)
    monkeypatch.setattr(rest, "_secure_session", FakeSession())
    monkeypatch.setattr(rest, "main_server", "https://stale.example.com")
    monkeypatch.delenv("USER_DASHBOARD_API_URL", raising=False)
    monkeypatch.delenv("API_SERVER_URL_FALLBACK", raising=False)

    result = rest.submitRegistrationRequest(
        "Tester",
        "sstest_client",
        "Password123",
        "010-1234-5678",
        "tester@example.com",
    )

    assert calls == [
        "https://stale.example.com/user/register/request",
        f"{EXPECTED_API_URL}/user/register/request",
    ]
    assert rest.main_server == EXPECTED_API_URL
    assert result["success"] is True
