from types import SimpleNamespace

from caller import rest


def _submit(monkeypatch, response):
    monkeypatch.setattr(rest, "_check_https_security", lambda: True)
    monkeypatch.setattr(rest, "_candidate_api_servers", lambda: ["https://auth.example"])
    monkeypatch.setattr(
        rest,
        "_secure_session",
        SimpleNamespace(post=lambda *_args, **_kwargs: response),
    )
    return rest.submitRegistrationRequest(
        "테스트",
        "test_user",
        "Password123!",
        "01012345678",
        "test@example.com",
        terms_accepted=True,
        privacy_accepted=True,
        terms_version="1",
        privacy_version="1",
    )


def test_registration_local_validation_is_localized(monkeypatch):
    monkeypatch.setattr(rest, "_check_https_security", lambda: True)

    result = rest.submitRegistrationRequest(
        "A",
        "bad id",
        "short",
        "1",
        "invalid",
    )

    assert result == {"success": False, "message": "이름은 2자 이상 입력해 주세요."}


def test_registration_conflict_does_not_expose_server_text(monkeypatch):
    response = SimpleNamespace(status_code=409, text="Username already exists")

    result = _submit(monkeypatch, response)

    assert result["success"] is False
    assert result["message"] == "이미 사용 중인 아이디입니다. 다른 아이디를 입력해 주세요."
    assert "Username" not in result["message"]


def test_registration_rate_limit_is_readable_korean(monkeypatch):
    response = SimpleNamespace(
        status_code=429,
        text='{"error":{"retry_after":"12"}}',
        json=lambda: {"error": {"retry_after": "12"}},
    )

    result = _submit(monkeypatch, response)

    assert result["success"] is False
    assert result["message"] == "회원가입 요청이 잠시 많습니다.\n약 12초 뒤 다시 시도해 주세요."
    assert "?" not in result["message"]


def test_registration_validation_never_shows_framework_message(monkeypatch):
    response = SimpleNamespace(
        status_code=422,
        text="validation failed",
        json=lambda: {
            "detail": [
                {
                    "loc": ["body", "username"],
                    "msg": "String should have at least 4 characters",
                }
            ]
        },
    )

    result = _submit(monkeypatch, response)

    assert result == {"success": False, "message": "회원가입 입력값을 확인해 주세요."}
    assert "String" not in result["message"]
