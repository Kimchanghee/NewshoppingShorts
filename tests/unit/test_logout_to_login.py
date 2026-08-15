from types import SimpleNamespace

from app.exit_handler import ExitHandler
from startup.app_controller import AppController


class _QtApp:
    def __init__(self):
        self.login_data = {"token": "old"}
        self.quit_on_last_window_closed = True

    def quitOnLastWindowClosed(self):
        return self.quit_on_last_window_closed

    def setQuitOnLastWindowClosed(self, value):
        self.quit_on_last_window_closed = bool(value)


class _Window:
    def __init__(self):
        self.shown = False
        self.closed = False
        self.prepared = False

    def prepare_for_reauthentication(self):
        self.prepared = True

    def show(self):
        self.shown = True

    def raise_(self):
        pass

    def activateWindow(self):
        pass

    def hide(self):
        self.shown = False

    def close(self):
        self.closed = True


def test_controller_reuses_login_window_without_quitting_application():
    qt_app = _QtApp()
    controller = AppController(qt_app)
    login_window = _Window()
    main_window = _Window()
    controller.login_window = login_window
    controller.main_gui = main_window
    controller.login_data = {"data": {"token": "old"}}
    controller._main_launched = True
    controller._loading_started = True

    controller.return_to_login(main_window)

    assert main_window.closed is True
    assert main_window._closing is True
    assert login_window.prepared is True
    assert login_window.shown is True
    assert controller.main_gui is None
    assert controller.login_data is None
    assert controller._main_launched is False
    assert controller._loading_started is False
    assert qt_app.login_data is None
    assert qt_app.quit_on_last_window_closed is True


def test_exit_handler_logs_out_then_delegates_to_controller(monkeypatch):
    calls = []
    controller = SimpleNamespace(return_to_login=lambda window: calls.append(("login", window)))
    app = SimpleNamespace(
        login_data={"data": {"data": {"id": 7}, "token": "jwt-token"}},
        batch_processing=False,
        dynamic_processing=False,
        _login_watch_stop=False,
        subscription_manager=SimpleNamespace(stop=lambda: calls.append(("stop", None))),
        controller=controller,
    )
    monkeypatch.setattr(
        "app.exit_handler.rest.logOut",
        lambda **data: calls.append(("logout", data)) or "success",
    )

    ExitHandler(app).logout_to_login()

    assert app._login_watch_stop is True
    assert calls[0] == ("stop", None)
    assert calls[1] == (
        "logout",
        {"userId": 7, "key": "jwt-token"},
    )
    assert calls[2] == ("login", app)
