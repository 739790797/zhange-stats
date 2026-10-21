from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

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


def test_download_bytes_with_meta_reports_on_bytes(monkeypatch) -> None:
    from app.services.tarkov.http import download_bytes_with_meta

    seen: list[tuple[int, int | None]] = []

    def fake_download(*_a, on_bytes=None, **_k):
        if on_bytes:
            on_bytes(1, 4)
            on_bytes(4, 4)
        return 200, b"abcd", {"Last-Modified": "Wed, 26 Aug 2026 09:01:54 GMT"}

    monkeypatch.setattr("app.services.tarkov.http.http_download", fake_download)
    raw, stamp = download_bytes_with_meta(
        "https://example.test/x",
        on_bytes=lambda n, total: seen.append((n, total)),
    )
    assert raw == b"abcd"
    assert stamp == "2026-08-26T09:01:54+00:00"
    assert seen == [(1, 4), (4, 4)]


def test_download_dump_passes_the_64mib_cap_to_http_request(monkeypatch) -> None:
    """生产 8MiB 默认上限曾把 items ~17MB / maps ~8.6MB 全卡死；上限必须一路带下去。"""
    from app.services.tarkov.http import TARKOV_DUMP_MAX_BYTES, download_dump

    seen: dict[str, object] = {}

    def fake_request(method, url, **kwargs):  # noqa: ANN001
        seen.update(method=method, url=url, **kwargs)
        return _Resp(200, b'{"a":1}')

    monkeypatch.setattr("app.services.tarkov.http.http_request", fake_request)
    raw, _stamp = download_dump("https://json.tarkov.dev/regular/items")
    assert raw == b'{"a":1}'
    assert seen["max_bytes"] == TARKOV_DUMP_MAX_BYTES
    assert TARKOV_DUMP_MAX_BYTES > 8 * 1024 * 1024


def test_download_dump_passes_the_64mib_cap_to_http_download(monkeypatch) -> None:
    from app.services.tarkov.http import TARKOV_DUMP_MAX_BYTES, download_dump

    seen: dict[str, object] = {}

    def fake_download(method, url, **kwargs):  # noqa: ANN001
        seen.update(method=method, url=url, **kwargs)
        return 200, b'{"a":1}', {}

    monkeypatch.setattr("app.services.tarkov.http.http_download", fake_download)
    raw, _stamp = download_dump(
        "https://json.tarkov.dev/regular/maps", on_bytes=lambda _n, _t: None
    )
    assert raw == b'{"a":1}'
    assert seen["max_bytes"] == TARKOV_DUMP_MAX_BYTES


def test_tarkov_dump_wrapper_sends_the_64mib_cap(monkeypatch) -> None:
    """json.tarkov.dev dump 仍使用 64 MiB 上限；overlay 已改为本地克隆读取。"""
    from app.services.tarkov import http as tarkov_http
    from app.services.tarkov import upstream as upstream_svc

    caps: list[int | None] = []

    def fake_response(url, *, method="GET", on_bytes=None, max_bytes=None, **_k):  # noqa: ANN001
        caps.append(max_bytes)
        if on_bytes:
            on_bytes(4, 4)
        return SimpleNamespace(status_code=200, content=b'{"data": {}}', headers={})

    monkeypatch.setattr(tarkov_http, "download_response", fake_response)
    assert tarkov_http.TARKOV_DUMP_MAX_BYTES == 64 * 1024 * 1024

    upstream_svc.download_json_resource("items")
    assert caps == [tarkov_http.TARKOV_DUMP_MAX_BYTES]
