import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

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
