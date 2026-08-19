from pathlib import Path

from managers.inpock_manager import InpockManager


def test_unverified_inpock_integration_cannot_report_success(monkeypatch):
    manager = InpockManager.__new__(InpockManager)
    manager.driver = None
    manager.settings = object()
    monkeypatch.setattr(
        manager,
        "_init_driver",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("disabled integration must not open a browser")
        ),
    )

    assert manager.is_available() is False
    assert manager.is_connected() is False
    assert manager.add_link("상품", "https://example.com/product") is False


def test_video_pipeline_has_no_fake_inpock_profile_url():
    source = Path("core/video/batch/processor.py").read_text(encoding="utf-8")

    assert "https://inpock.co.kr/..." not in source
    assert "inpock_mgr.is_available()" in source


def test_login_logs_never_serialize_account_response_or_ip():
    source = Path("caller/rest.py").read_text(encoding="utf-8")

    assert "[Login] Response body:" not in source
    assert 'log_user_action("로그인", f"로그인 성공 (IP:' not in source
    assert "[Login] Response summary:" in source
