from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.http_client import HttpRequestError
from app.services.tarkov.ammo import TarkovAmmoError
from app.services.tarkov.http import download_bytes
from app.services.tarkov.tracker import TarkovTrackerError, _http_json


@dataclass
class _Resp:
    status_code: int
    content: bytes = b""


def test_download_bytes_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tarkov.http.http_request",
        lambda *a, **k: _Resp(200, b"hello"),
    )
    assert download_bytes("https://example.test/x", error_cls=TarkovAmmoError) == b"hello"


def test_download_bytes_http_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tarkov.http.http_request",
        lambda *a, **k: _Resp(502, b"upstream down"),
    )
    with pytest.raises(TarkovAmmoError, match="HTTP 502"):
        download_bytes("https://example.test/x", error_cls=TarkovAmmoError)


def test_download_bytes_transport_error(monkeypatch) -> None:
    def _boom(*a, **k):
        raise HttpRequestError("请求超时：timed out")

    monkeypatch.setattr("app.services.tarkov.http.http_request", _boom)
    with pytest.raises(TarkovAmmoError, match="无法连接资源站"):
        download_bytes("https://example.test/x", error_cls=TarkovAmmoError)


def test_tracker_json_maps_401(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tarkov.tracker.http_request",
        lambda *a, **k: _Resp(401, b"{}"),
    )
    with pytest.raises(TarkovTrackerError, match="Token 无效") as exc:
        _http_json("/token", "PVP_deadbeefcafefeed01")
    assert exc.value.status_code == 401
