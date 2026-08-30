from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.http_client import HttpRequestError
from app.services.tarkov.ammo import TarkovAmmoError
from app.services.tarkov.http import download_bytes, http_last_modified_iso


@dataclass
class _Resp:
    status_code: int
    content: bytes = b""
    headers: dict | None = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {}


def test_http_last_modified_iso() -> None:
    assert (
        http_last_modified_iso(
            {"Last-Modified": "Wed, 26 Aug 2026 09:01:54 GMT"}
        )
        == "2026-08-26T09:01:54+00:00"
    )
    assert http_last_modified_iso({}) is None
    assert http_last_modified_iso({"Last-Modified": "not-a-date"}) is None


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
