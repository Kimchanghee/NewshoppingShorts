from ui.panels.settings_tab import SettingsTab, classify_linktree_setup_status


def test_linktree_profile_only_is_not_reported_as_connected():
    assert classify_linktree_setup_status(True, False, False) == (
        False,
        True,
        "Webhook 미설정 · 자동 등록 꺼짐",
    )


def test_linktree_webhook_without_auto_publish_is_incomplete():
    assert classify_linktree_setup_status(True, False, True) == (
        False,
        True,
        "자동 등록 꺼짐",
    )


def test_linktree_full_auto_connection_requires_profile_webhook_and_toggle():
    assert classify_linktree_setup_status(True, True, True) == (
        True,
        False,
        "자동 등록",
    )


def test_linktree_only_setup_does_not_require_gemini_precheck():
    assert SettingsTab._build_setup_steps(object(), "linktree") == [
        "linktree_user_setup",
        "linktree_save_verify",
        "final_verify",
    ]
