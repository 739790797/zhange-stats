"""Steam 图标 / 商店卡片：只回源站内出现过的 AppID，查无落库，GetOwnedGames 次数封顶，同 id 并发只回源一次。"""

from __future__ import annotations

import logging
import threading
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.biz_logging import clear_log_until_change
from app.core.database import Base
from app.core.http_client import HttpRequestError
from app.core.timeutil import now_naive
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.steam_app import SteamApp
from app.services.adapters.steam import SteamAdapter
from app.services.steam import game_names

_ICON = "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/570/abc.jpg"


@pytest.fixture
def factory(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(game_names, "SessionLocal", maker)
    clear_log_until_change()
    yield maker
    engine.dispose()


@pytest.fixture
def no_http(monkeypatch):
    calls: list[str] = []

    def fake(method, url, **_kw):
        calls.append(url)
        raise AssertionError(f"unexpected upstream call: {url}")

    monkeypatch.setattr(game_names, "http_request", fake)
    return calls


def _players(db, app_id: str, count: int) -> None:
    now = now_naive()
    for i in range(count):
        member = Member(nickname=f"m{app_id}-{i}", steam_id=f"76561198{app_id:0>7}{i:02d}")
        db.add(member)
        db.flush()
        db.add(
            PlaySession(
                member_id=member.id,
                steam_app_id=app_id,
                game_name="Dota 2",
                started_at=now,
                last_seen_at=now,
                source="steam",
            )
        )
    db.commit()


def _wire_backfill(monkeypatch, *, owned=None, steamcmd_hash=None, url_ok=True):
    calls = {"owned": [], "steamcmd": []}

    def fake_owned(self, steam_id):
        calls["owned"].append(steam_id)
        if isinstance(owned, Exception):
            raise owned
        return dict(owned or {})

    def fake_steamcmd(app_id):
        calls["steamcmd"].append(app_id)
        return steamcmd_hash

    monkeypatch.setattr("app.services.integrations_config.get_steam_api_key", lambda *_a: "k")
    monkeypatch.setattr(SteamAdapter, "fetch_owned_game_icons", fake_owned)
    monkeypatch.setattr(game_names, "_fetch_icon_hash_from_steamcmd", fake_steamcmd)
    monkeypatch.setattr(game_names, "_http_url_ok", lambda *_a, **_k: url_ok)
    return calls


def _client(monkeypatch, factory) -> TestClient:
    from app.api.steam import router
    from app.core import platform_deps
    from app.core.database import get_db
    from app.core.deps import get_current_user

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(platform_deps, "is_feature_enabled", lambda db, feature_id: True)
    api = FastAPI()
    api.include_router(router, prefix="/api")
    api.dependency_overrides[get_db] = _db
    api.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    return TestClient(api)


@pytest.mark.parametrize("app_id", ["abc", "12345678901", "570x"])
def test_app_endpoints_reject_malformed_ids(monkeypatch, factory, no_http, app_id) -> None:
    client = _client(monkeypatch, factory)
    assert client.get(f"/api/steam/apps/{app_id}/icon").status_code == 422
    assert client.get(f"/api/steam/apps/{app_id}").status_code == 422
    assert no_http == []


def test_unknown_app_ids_are_404_without_upstream(monkeypatch, factory, no_http) -> None:
    client = _client(monkeypatch, factory)
    assert client.get("/api/steam/apps/570/icon").status_code == 404
    assert client.get("/api/steam/apps/570").status_code == 404
    assert no_http == []


def test_app_icon_endpoint_is_rate_limited_per_user(monkeypatch, factory, no_http) -> None:
    client = _client(monkeypatch, factory)
    codes = [client.get(f"/api/steam/apps/{i}/icon").status_code for i in range(121)]
    assert set(codes[:120]) == {404}
    assert codes[120] == 429


def test_icon_backfill_caps_owned_games_and_records_miss(monkeypatch, factory, no_http) -> None:
    db = factory()
    _players(db, "570", 5)
    calls = _wire_backfill(monkeypatch, owned={})

    assert game_names.fetch_app_icon(db, "570") is None
    assert len(calls["owned"]) == game_names._OWNED_GAMES_CALLS_MAX == 2
    assert calls["steamcmd"] == ["570"]
    row = factory().get(SteamApp, "570")
    assert row is not None and row.icon_missed_at is not None and row.icon_url is None

    assert game_names.fetch_app_icon(db, "570") is None
    assert len(calls["owned"]) == 2 and calls["steamcmd"] == ["570"]


def test_icon_miss_is_retried_after_window(monkeypatch, factory, no_http) -> None:
    db = factory()
    _players(db, "570", 1)
    db.add(
        SteamApp(
            app_id="570",
            fetched_at=now_naive(),
            icon_missed_at=now_naive() - game_names._ICON_MISS_RETRY - timedelta(minutes=1),
        )
    )
    db.commit()
    calls = _wire_backfill(monkeypatch, owned={"570": _ICON})

    assert game_names.fetch_app_icon(db, "570") == _ICON
    assert len(calls["owned"]) == 1
    row = factory().get(SteamApp, "570")
    assert row.icon_url == _ICON and row.icon_missed_at is None
    assert game_names.resolve_app_icons(db, ["570", "730"]) == {"570": _ICON}


def test_icon_backfill_skips_owned_games_without_players(monkeypatch, factory, no_http) -> None:
    db = factory()
    db.add(Member(nickname="other", steam_id="76561198000000099"))
    db.add(SteamApp(app_id="570", fetched_at=now_naive()))
    db.commit()
    calls = _wire_backfill(monkeypatch, steamcmd_hash="a" * 40)

    url = game_names.fetch_app_icon(db, "570")
    assert url == game_names._client_icon_cdn_url("570", "a" * 40)
    assert calls["owned"] == []


def test_owned_games_failure_warns_once_without_traceback(
    monkeypatch, factory, no_http, caplog
) -> None:
    db = factory()
    _players(db, "570", 3)
    _players(db, "730", 1)
    calls = _wire_backfill(monkeypatch, owned=RuntimeError("Steam API 暂时不可用（HTTP 429）"))

    with caplog.at_level(logging.DEBUG, logger=game_names.logger.name):
        assert game_names.fetch_app_icon(db, "570") is None
        assert game_names.fetch_app_icon(db, "730") is None

    assert len(calls["owned"]) == 2
    records = [r for r in caplog.records if "GetOwnedGames" in r.getMessage()]
    assert [r.levelno for r in records] == [logging.WARNING, logging.DEBUG]
    assert all(r.exc_info is None for r in records)


def test_store_card_miss_keeps_cached_details_and_is_not_refetched(monkeypatch, factory) -> None:
    db = factory()
    stale = now_naive() - timedelta(hours=7)
    db.add(
        SteamApp(
            app_id="570",
            name="Dota 2",
            header_image="https://cdn.example/header.jpg",
            fetched_at=stale,
            details_fetched_at=stale,
        )
    )
    db.commit()
    calls: list[str] = []

    def failing(method, url, **_kw):
        calls.append(url)
        raise HttpRequestError("timeout")

    monkeypatch.setattr(game_names, "http_request", failing)

    card = game_names.get_store_card(db, "570")
    assert card is not None and card["header_image"] == "https://cdn.example/header.jpg"
    assert len(calls) == 1
    row = factory().get(SteamApp, "570")
    assert row.details_missed_at is not None
    assert row.header_image == "https://cdn.example/header.jpg"

    assert game_names.get_store_card(db, "570") is not None
    assert len(calls) == 1


def test_store_card_without_any_details_is_none(monkeypatch, factory) -> None:
    db = factory()
    db.add(SteamApp(app_id="570", fetched_at=now_naive()))
    db.commit()
    monkeypatch.setattr(
        game_names,
        "fetch_store_details",
        lambda app_id: game_names.StoreDetails(success=False),
    )
    assert game_names.get_store_card(db, "570") is None
    assert factory().get(SteamApp, "570").details_missed_at is not None


def test_resolve_app_names_honours_details_miss(monkeypatch, factory) -> None:
    db = factory()
    now = now_naive()
    db.add_all(
        [
            SteamApp(app_id="10", fetched_at=now, details_missed_at=now),
            SteamApp(app_id="20", fetched_at=now),
        ]
    )
    db.commit()
    fetched: list[str] = []

    def fake_details(app_id):
        fetched.append(app_id)
        return game_names.StoreDetails(success=False)

    monkeypatch.setattr(game_names, "fetch_store_details", fake_details)
    names = game_names.resolve_app_names(db, ["10", "20", "13830775785634496512"])
    assert names == {}
    # 20 是加列前的旧行（无查无时间）：回源一次并记下；非 Steam 快捷方式的超长 id 不回源
    assert fetched == ["20"]
    assert factory().get(SteamApp, "20").details_missed_at is not None
    assert factory().get(SteamApp, "13830775785634496512") is None


def test_single_flight_lets_one_caller_fetch() -> None:
    order: list[tuple[str, bool]] = []
    entered = threading.Event()
    release = threading.Event()

    def leader() -> None:
        with game_names._single_flight("icon:570") as lead:
            order.append(("a", lead))
            entered.set()
            release.wait(5)

    def follower() -> None:
        entered.wait(5)
        with game_names._single_flight("icon:570") as lead:
            order.append(("b", lead))

    a = threading.Thread(target=leader)
    b = threading.Thread(target=follower)
    a.start()
    b.start()
    entered.wait(5)
    time.sleep(0.05)
    assert order == [("a", True)]
    release.set()
    a.join(5)
    b.join(5)
    assert order == [("a", True), ("b", False)]
    assert game_names._flights == {}
    with game_names._single_flight("icon:570") as lead:
        assert lead is True
