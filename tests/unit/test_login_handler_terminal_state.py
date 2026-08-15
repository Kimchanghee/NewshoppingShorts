from types import SimpleNamespace

from app import login_handler


def _handler():
    app = SimpleNamespace(
        login_data={"data": {"data": {"id": 1}, "token": "token"}},
        _login_watch_stop=False,
    )
    return login_handler.LoginHandler(app)


def test_session_expiry_warning_and_exit_are_one_shot(monkeypatch):
    handler = _handler()
    calls = []
    handler.app.exit_handler = SimpleNamespace(
        logout_to_login=lambda: calls.append("login")
    )
    monkeypatch.setattr(login_handler, "show_warning", lambda *_args: calls.append("warning"))

    handler._on_auth_required()
    handler._on_auth_required()

    assert calls == ["warning", "login"]
    assert handler.app._login_watch_stop is True


def test_duplicate_login_warning_and_exit_are_one_shot(monkeypatch):
    handler = _handler()
    calls = []
    monkeypatch.setattr(login_handler, "show_warning", lambda *_args: calls.append("warning"))
    monkeypatch.setattr(handler, "_safe_exit", lambda: calls.append("exit"))

    handler.exit_program_other_place("EU003")
    handler.exit_program_other_place("EU003")

    assert calls == ["warning", "exit"]


def test_force_close_dialog_is_suppressed_after_terminal_state(monkeypatch):
    handler = _handler()
    calls = []
    monkeypatch.setattr(login_handler, "show_error", lambda *_args: calls.append("error"))
    monkeypatch.setattr(handler, "_safe_exit", lambda: calls.append("exit"))

    handler.error_program_force_close("EU004")
    handler.error_program_force_close("EU004")

    assert calls == ["error", "exit"]
