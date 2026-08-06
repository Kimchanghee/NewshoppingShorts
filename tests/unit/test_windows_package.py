from utils import windows_package


def setup_function():
    windows_package.reset_package_identity_cache()


def teardown_function():
    windows_package.reset_package_identity_cache()


def test_msix_identity_can_be_forced_for_packaged_smoke_tests(monkeypatch):
    monkeypatch.setenv("SSMAKER_MSIX_PACKAGE", "1")

    assert windows_package.is_msix_package() is True
    assert windows_package.get_package_full_name() == "SSMaker.TestPackage"


def test_explicit_unpacked_override_wins(monkeypatch):
    monkeypatch.setenv("SSMAKER_MSIX_PACKAGE", "0")
    monkeypatch.setattr(windows_package.sys, "platform", "win32")
    monkeypatch.setattr(
        windows_package,
        "_query_current_package_full_name",
        lambda: "Should.Not.Be.Used",
    )

    assert windows_package.is_msix_package() is False


def test_frozen_executable_ignores_package_identity_override(monkeypatch):
    monkeypatch.setenv("SSMAKER_MSIX_PACKAGE", "1")
    monkeypatch.setattr(windows_package.sys, "platform", "win32")
    monkeypatch.setattr(windows_package.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        windows_package,
        "_query_current_package_full_name",
        lambda: None,
    )

    assert windows_package.is_msix_package() is False


def test_windows_package_identity_uses_native_query(monkeypatch):
    monkeypatch.delenv("SSMAKER_MSIX_PACKAGE", raising=False)
    monkeypatch.setattr(windows_package.sys, "platform", "win32")
    monkeypatch.setattr(
        windows_package,
        "_query_current_package_full_name",
        lambda: "Kimchanghee.SSMaker_1.5.46.0_x64__publisher",
    )

    assert windows_package.is_msix_package() is True


def test_non_windows_process_has_no_package_identity(monkeypatch):
    monkeypatch.delenv("SSMAKER_MSIX_PACKAGE", raising=False)
    monkeypatch.setattr(windows_package.sys, "platform", "linux")

    assert windows_package.get_package_full_name() is None
