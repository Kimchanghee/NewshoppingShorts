from app.schemas.registration import RegistrationRequestCreate


def _base_registration_payload() -> dict:
    return {
        "name": "Tester",
        "username": "tester_01",
        "password": "Password123",
        "contact": "010-1234-5678",
        "email": "tester@example.com",
        "program_type": "ssmaker",
        "terms_accepted": True,
        "privacy_accepted": True,
        "terms_version": "2026-08-08",
        "privacy_version": "2026-08-08",
    }


def test_registration_payload_defaults_ym_news_opt_in_false():
    model = RegistrationRequestCreate(**_base_registration_payload())
    assert model.ym_news_opt_in is False


def test_registration_payload_accepts_ym_news_opt_in_true():
    payload = _base_registration_payload()
    payload["ym_news_opt_in"] = True
    model = RegistrationRequestCreate(**payload)
    assert model.ym_news_opt_in is True


def test_registration_payload_rejects_missing_required_legal_consent():
    import pytest
    from pydantic import ValidationError

    payload = _base_registration_payload()
    payload["privacy_accepted"] = False

    with pytest.raises(ValidationError):
        RegistrationRequestCreate(**payload)
