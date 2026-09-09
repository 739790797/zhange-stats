"""出站 HTTP 收口：Steam / 图鉴 / 日历走 http_request，不打真站。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.http_client import HttpRequestError
from app.services.minecraft import modrinth as modrinth
from app.services.minecraft import mod_catalog as mod_catalog
from app.services.minecraft.modrinth import ModrinthError
from app.services.skland import arknights_catalog as catalog
from app.services.steam import game_names as game_names
from app.services.steam import openid as steam_openid
from app.services.steam import resolve as steam_resolve
from app.services import game_schedule as gs


class _Resp:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: object = None,
        text: str = "",
        content: bytes = b"",
    ):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def test_fetch_store_details_network_fail(monkeypatch) -> None:
    def boom(*_a, **_k):
        raise HttpRequestError("timeout")

    monkeypatch.setattr(game_names, "http_request", boom)
    out = game_names.fetch_store_details("570")
    assert out.success is False


def test_fetch_store_details_parses_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        game_names,
        "http_request",
        lambda *_a, **_k: _Resp(
            payload={
                "570": {
                    "success": True,
                    "data": {"name": "Dota 2", "is_free": True},
                }
            }
        ),
    )
    out = game_names.fetch_store_details("570")
    assert out.success is True
    assert out.name == "Dota 2"


def test_http_url_ok_rejects_short_body(monkeypatch) -> None:
    monkeypatch.setattr(
        game_names,
        "http_request",
        lambda *_a, **_k: _Resp(status_code=200, content=b"x"),
    )
    assert game_names._http_url_ok("https://example.test/icon.jpg") is False


def test_resolve_vanity_http_error(monkeypatch) -> None:
    monkeypatch.setattr(
        steam_resolve,
        "http_request",
        lambda *_a, **_k: _Resp(status_code=403, text="denied"),
    )
    with pytest.raises(RuntimeError, match="HTTP 403"):
        steam_resolve.resolve_vanity("key", "gaben")


def test_openid_falls_back_to_get_on_403(monkeypatch) -> None:
    calls: list[str] = []

    def fake(method: str, url: str, **_k):
        calls.append(method)
        if method == "POST":
            return _Resp(status_code=403, text="no")
        return _Resp(status_code=200, text="ns:http://specs.openid.net/auth/2.0\nis_valid:true\n")

    monkeypatch.setattr(steam_openid, "http_request", fake)
    sid = steam_openid.verify_steam_openid_assertion(
        {
            "openid.mode": "id_res",
            "openid.claimed_id": "https://steamcommunity.com/openid/id/76561198000000000",
            "openid.op_endpoint": steam_openid.STEAM_OPENID_ENDPOINT,
        }
    )
    assert sid == "76561198000000000"
    assert calls == ["POST", "GET"]


def test_modrinth_get_json_http_error(monkeypatch) -> None:
    monkeypatch.setattr(
        modrinth,
        "http_request",
        lambda *_a, **_k: _Resp(status_code=500, payload={}),
    )
    with pytest.raises(ModrinthError, match="HTTP 500"):
        modrinth._get_json("https://example.test/x")


def test_mod_catalog_http_json_bad_status(monkeypatch) -> None:
    monkeypatch.setattr(
        mod_catalog,
        "http_request",
        lambda *_a, **_k: _Resp(status_code=503, payload={}),
    )
    with pytest.raises(ValueError, match="HTTP 503"):
        mod_catalog._http_json("https://example.test/s")


def test_arknights_catalog_http_error(monkeypatch) -> None:
    monkeypatch.setattr(
        catalog,
        "http_request",
        lambda *_a, **_k: _Resp(status_code=404, content=b""),
    )
    with pytest.raises(catalog.ArknightsCatalogError, match="HTTP 404"):
        catalog._http_get_bytes("https://example.test/table.json")


def test_arknights_catalog_network_error(monkeypatch) -> None:
    def boom(*_a, **_k):
        raise HttpRequestError("dns")

    monkeypatch.setattr(catalog, "http_request", boom)
    with pytest.raises(catalog.ArknightsCatalogError, match="无法连接"):
        catalog._http_get_bytes("https://example.test/table.json")


def test_game_schedule_download_maps_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(
        gs,
        "get_settings",
        lambda: SimpleNamespace(GAME_SCHEDULE_BASE_URL="https://example.test"),
    )

    def boom(*_a, **_k):
        raise HttpRequestError("timeout")

    monkeypatch.setattr(gs, "http_request", boom)
    with pytest.raises(gs.GameScheduleError, match="不可达"):
        gs._download_upstream_payload("arknights")
