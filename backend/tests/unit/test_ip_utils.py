from app.utils import ip_utils


def test_trusted_proxies_default_is_loopback_only(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    proxies = ip_utils._get_trusted_proxies()
    assert proxies == ["127.0.0.1", "::1"]


def test_trusted_proxies_from_env(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1, 192.0.2.0/24")
    proxies = ip_utils._get_trusted_proxies()
    assert proxies == ["10.0.0.1", "192.0.2.0/24"]
