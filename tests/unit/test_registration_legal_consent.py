import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from caller import rest
import ui.login_ui_modern as login_ui_modern

from ui.login_ui_modern import (
    PRIVACY_DOCUMENT_VERSION,
    PRIVACY_POLICY_URL,
    TERMS_DOCUMENT_VERSION,
    TERMS_OF_SERVICE_URL,
    RegistrationRequestDialog,
)


QT_APP = QApplication.instance() or QApplication([])


def _dialog():
    return RegistrationRequestDialog()


def test_registration_requires_separate_terms_and_privacy_consent():
    dialog = _dialog()

    assert dialog.termsConsentCheckBox.isChecked() is False
    assert dialog.privacyConsentCheckBox.isChecked() is False
    issues = dialog._collect_form_issues()
    issue_names = [issue[0] for issue in issues]
    assert "서비스 이용약관 동의" in issue_names
    assert "개인정보 수집·이용 동의" in issue_names


def test_registration_legal_links_use_public_https_pages():
    assert TERMS_OF_SERVICE_URL == "https://newshopping-shorts-auth.vercel.app/terms"
    assert PRIVACY_POLICY_URL == "https://newshopping-shorts-auth.vercel.app/privacy"


def test_registration_shows_calm_revenue_and_connected_account_notice():
    dialog = _dialog()

    notice = dialog.responsibilityNoticeBody.text()
    assert "조회수·판매·제휴 수익을 보장하지 않습니다" in notice
    assert "연결한 계정과 게시물은 직접 확인" in notice
    assert "외부 플랫폼의 정책·심사·장애" in notice
    assert dialog.responsibilityNotice.accessibleName() == "이용 전 확인"
    assert dialog.responsibilityNoticeBody.accessibleName() == "수익 및 연결 계정 운영 안내"


def test_terms_and_privacy_versions_are_recorded_independently():
    assert TERMS_DOCUMENT_VERSION == "2026-08-13"
    assert PRIVACY_DOCUMENT_VERSION == "2026-08-08"


def test_username_check_ignores_result_for_text_that_has_since_changed():
    dialog = _dialog()
    dialog.usernameEdit.setText("new_name")

    dialog._on_username_check_done(
        "old_name", True, "사용 가능한 아이디입니다."
    )

    assert dialog._username_available is False
    assert dialog.usernameStatusLabel.text() == ""


def test_registration_submit_keeps_ui_responsive_while_request_runs(monkeypatch):
    dialog = _dialog()
    dialog.nameEdit.setText("테스트 사용자")
    dialog.emailEdit.setText("async@example.com")
    dialog.usernameEdit.setText("async_user")
    dialog.passwordEdit.setText("Password123")
    dialog.passwordConfirmEdit.setText("Password123")
    dialog.contactEdit.setText("01012345678")
    dialog.termsConsentCheckBox.setChecked(True)
    dialog.privacyConsentCheckBox.setChecked(True)
    dialog._username_available = True

    def slow_registration(**_kwargs):
        time.sleep(0.2)
        return {
            "success": True,
            "data": {"user_id": 7, "username": "async_user", "token": "token"},
        }

    monkeypatch.setattr(rest, "submitRegistrationRequest", slow_registration)
    monkeypatch.setattr(login_ui_modern, "show_success", lambda *_args, **_kwargs: None)

    started_at = time.perf_counter()
    dialog._on_submit()
    returned_after = time.perf_counter() - started_at

    assert returned_after < 0.1
    assert dialog.submitButton.isEnabled() is False

    deadline = time.monotonic() + 2
    while not dialog.registration_result and time.monotonic() < deadline:
        QT_APP.processEvents()
        time.sleep(0.01)

    assert dialog.registration_result["success"] is True
