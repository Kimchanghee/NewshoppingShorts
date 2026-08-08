import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.login_ui_modern import PRIVACY_POLICY_URL, TERMS_OF_SERVICE_URL, RegistrationRequestDialog


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
