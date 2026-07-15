from pathlib import Path

from caller import ui_controller


class _Field:
    def __init__(self):
        self.value = ""

    def setText(self, value):
        self.value = value

    def text(self):
        return self.value


class _Checkbox:
    def __init__(self):
        self.checked = False

    def setChecked(self, checked):
        self.checked = bool(checked)

    def isChecked(self):
        return self.checked


class _LoginForm:
    def __init__(self):
        self.idEdit = _Field()
        self.pwEdit = _Field()
        self.rememberCheckbox = _Checkbox()
        self.autoLoginCheckbox = _Checkbox()


class _Secrets:
    store = {}

    @classmethod
    def store_api_key(cls, key_name, key_value):
        cls.store[key_name] = key_value
        return True

    @classmethod
    def get_api_key(cls, key_name):
        return cls.store.get(key_name)

    @classmethod
    def delete_api_key(cls, key_name):
        cls.store.pop(key_name, None)
        return True


def _patch_storage(monkeypatch, tmp_path: Path):
    info_path = tmp_path / "info.on"
    monkeypatch.setattr(ui_controller, "_get_info_on_paths", lambda: (info_path, info_path))
    _Secrets.store = {}
    monkeypatch.setattr(ui_controller, "_get_secrets_manager", lambda: _Secrets)
    return info_path


def test_user_save_and_load_auto_login_uses_secure_password(monkeypatch, tmp_path):
    _patch_storage(monkeypatch, tmp_path)

    ui_controller.userSaveInfo(
        _LoginForm(),
        checkState=True,
        loginid="demo_user",
        loginpw="Password123",
        autoLogin=True,
    )

    form = _LoginForm()
    ui_controller.userLoadInfo(form)

    assert form.idEdit.text() == "demo_user"
    assert form.pwEdit.text() == "Password123"
    assert form.rememberCheckbox.isChecked() is True
    assert form.autoLoginCheckbox.isChecked() is True
    assert form.auto_login_enabled is True


def test_user_load_disables_auto_login_without_saved_password(monkeypatch, tmp_path):
    info_path = _patch_storage(monkeypatch, tmp_path)
    info_path.write_text(
        "[User]\nid = demo_user\npw = \nsave = t\nauto_login = t\n\n[Config]\nversion = 1.0.0\n",
        encoding="utf-8",
    )

    form = _LoginForm()
    ui_controller.userLoadInfo(form)

    assert form.idEdit.text() == "demo_user"
    assert form.pwEdit.text() == ""
    assert form.rememberCheckbox.isChecked() is True
    assert form.autoLoginCheckbox.isChecked() is False
    assert form.auto_login_enabled is False
