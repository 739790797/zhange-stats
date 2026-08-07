"""限流 client_ip：默认不信任 XFF。"""

from types import SimpleNamespace

from app.core.config import get_settings
from app.core.rate_limit import client_ip


def test_client_ip_ignores_xff_by_default(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "false")
    get_settings.cache_clear()
    req = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(req) == "127.0.0.1"  # type: ignore[arg-type]
    get_settings.cache_clear()


def test_client_ip_trusts_xff_when_enabled(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    get_settings.cache_clear()
    req = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(req) == "1.2.3.4"  # type: ignore[arg-type]
    get_settings.cache_clear()
