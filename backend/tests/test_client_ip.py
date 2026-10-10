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


def test_client_ip_takes_rightmost_xff_hop_when_enabled(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    get_settings.cache_clear()
    # 左侧各段是客户端自填的，可伪造；受信反代追加的是最右一段
    req = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(req) == "10.0.0.1"  # type: ignore[arg-type]
    get_settings.cache_clear()


def test_client_ip_joins_repeated_xff_headers(monkeypatch) -> None:
    from starlette.datastructures import Headers

    get_settings.cache_clear()
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    get_settings.cache_clear()
    req = SimpleNamespace(
        headers=Headers(
            raw=[
                (b"x-forwarded-for", b"6.6.6.6"),
                (b"x-forwarded-for", b"1.2.3.4, 203.0.113.9"),
            ]
        ),
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(req) == "203.0.113.9"  # type: ignore[arg-type]
    empty = SimpleNamespace(
        headers={"x-forwarded-for": ""},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(empty) == "127.0.0.1"  # type: ignore[arg-type]
    get_settings.cache_clear()
