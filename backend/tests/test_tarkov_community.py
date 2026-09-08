"""社区方案：投影公开列表、过滤非法槽、短时缓存。不打真站。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
from app.core.http_client import HttpRequestError
from app.services.tarkov import community as svc
from app.services.tarkov import workbench as wb
from tests.test_tarkov_workbench import _payload


@pytest.fixture
def index() -> wb.WorkbenchIndex:
    return wb.build_index("json.tarkov.dev", _payload())


@pytest.fixture(autouse=True)
def _reset_kv() -> None:
    reset_ephemeral_kv_for_tests()
    yield
    reset_ephemeral_kv_for_tests()


def _settings(*, enabled: bool = True, base: str = "https://eftforge.com") -> object:
    return type(
        "S",
        (),
        {
            "TARKOV_WORKBENCH_COMMUNITY": enabled,
            "EFTFORGE_BASE_URL": base,
        },
    )()


@dataclass
class _Resp:
    status_code: int
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)


def test_project_public_build_strips_foreign_assets_and_bad_pairs(
    index: wb.WorkbenchIndex,
):
    gun = index.items["gun1"]
    row = {
        "id": 99,
        "gun_id": "gun1",
        "build_name": "夜战 M4",
        "user_display_name": "LianDouDou",
        "user_avatar_url": "https://gitee.com/morph1ne/x.png",
        "card_image_url": "https://gitee.com/morph1ne/card.png",
        "is_admin_build": False,
        "is_featured": True,
        "published_at": "2026-09-05T08:10:15.610844",
        "load_count": 18,
        "ammo_id": "ammo1",
        "tags": ["ergo", "meta", "javascript", "ergo"],
        "pairs": [
            ["slot-grip", "grip1"],
            ["slot-missing", "grip1"],
            ["slot-stock", "stock1"],
        ],
        "stats": {
            "ergo": 62.9,
            "recoil_v": 61,
            "recoil_h": 176,
            "weight": 4.365,
            "eed": 48.92,
            "overswing": False,
        },
        "total_price_rub": 48000,
        "is_mine": True,
    }
    out = svc.project_public_build(index, gun, row)
    assert out is not None
    assert out["id"] == "99"
    assert out["name"] == "夜战 M4"
    assert out["author"] == "LianDouDou"
    assert out["featured"] is True
    assert out["tags"] == ["ergo", "meta"]
    assert out["ammo_id"] == "ammo1"
    assert out["loadable"] is True
    assert out["dropped_pair_count"] == 1
    assert out["pairs"] == [
        {"slot_id": "slot-grip", "item_id": "grip1"},
        {"slot_id": "slot-stock", "item_id": "stock1"},
    ]
    assert "card_image_url" not in out
    assert "user_avatar_url" not in out
    assert "is_mine" not in out
    assert out["preview"]["ergonomics"] == 62.9
    assert out["preview"]["evo_ergo_delta"] == 48.92
    assert out["preview"]["recoil_vertical"] == 61
    assert out["preview"]["price_rub"] == 48000
    assert out["preview"]["overswing"] is False


def test_project_skips_other_gun_and_admin_zh_name(index: wb.WorkbenchIndex):
    gun = index.items["gun1"]
    assert svc.project_public_build(index, gun, {"id": 1, "gun_id": "other"}) is None
    admin = svc.project_public_build(
        index,
        gun,
        {
            "id": "a1",
            "gun_id": "gun1",
            "build_name": "官改",
            "is_admin_build": True,
            "author_display_name_zh": "作者中文",
            "author_display_name": "Morph1ne",
            "pairs": [["slot-grip", "grip1"]],
        },
    )
    assert admin is not None
    assert admin["author"] == "作者中文"
    empty = svc.project_public_build(
        index,
        gun,
        {"id": "z", "gun_id": "gun1", "pairs": [["slot-missing", "grip1"]]},
    )
    assert empty is not None
    assert empty["loadable"] is False
    assert empty["author"] == "匿名"
    orphan = svc.project_public_build(
        index,
        gun,
        {"id": "rail-only", "gun_id": "gun1", "pairs": [["slot-rail", "rail1"]]},
    )
    assert orphan is not None
    assert orphan["loadable"] is False
    assert orphan["pairs"] == []
    assert orphan["dropped_pair_count"] == 1


def test_list_public_builds_featured_first(monkeypatch, index: wb.WorkbenchIndex):
    monkeypatch.setattr(svc, "get_settings", lambda: _settings())
    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    monkeypatch.setattr(
        svc,
        "fetch_public_raw",
        lambda gun_id: [
            {
                "id": 1,
                "gun_id": "gun1",
                "build_name": "旧",
                "is_featured": False,
                "published_at": "2026-01-01T00:00:00",
                "pairs": [["slot-grip", "grip1"]],
            },
            {
                "id": 2,
                "gun_id": "gun1",
                "build_name": "精选",
                "is_featured": True,
                "published_at": "2026-01-02T00:00:00",
                "pairs": [["slot-grip", "grip1"]],
            },
            {
                "id": 3,
                "gun_id": "gun1",
                "build_name": "新",
                "is_featured": False,
                "published_at": "2026-08-01T00:00:00",
                "pairs": [["slot-grip", "grip1"]],
            },
        ],
    )
    out = svc.list_public_builds(object(), "gun1")
    assert out["source"] == "EFTForge"
    assert out["source_url"] == "https://eftforge.com/"
    assert [row["name"] for row in out["builds"]] == ["精选", "新", "旧"]


def test_list_public_builds_disabled(monkeypatch, index: wb.WorkbenchIndex):
    monkeypatch.setattr(svc, "get_settings", lambda: _settings(enabled=False))
    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    with pytest.raises(svc.TarkovCommunityError, match="未开启") as exc:
        svc.list_public_builds(object(), "gun1")
    assert exc.value.status_code == 503


def test_fetch_public_raw_caches(monkeypatch):
    monkeypatch.setattr(svc, "get_settings", lambda: _settings())
    calls = {"n": 0}

    def _http(*_a, **_k):
        assert _k.get("follow_redirects") is False
        calls["n"] += 1
        return _Resp(200, b'[{"id":1}]')

    monkeypatch.setattr(svc, "http_request", _http)
    first = svc.fetch_public_raw("gun1")
    second = svc.fetch_public_raw("gun1")
    assert first == [{"id": 1}]
    assert second == [{"id": 1}]
    assert calls["n"] == 1


def test_fetch_follows_one_www_redirect(monkeypatch):
    monkeypatch.setattr(svc, "get_settings", lambda: _settings())
    urls: list[str] = []

    def _http(_method: str, url: str, **_k):
        urls.append(url)
        if "www.eftforge.com" in url:
            return _Resp(200, b'[{"id":1}]')
        return _Resp(
            301,
            b"redirect",
            headers={
                "location": "https://www.eftforge.com/builds/public?gun_id=gun1"
            },
        )

    monkeypatch.setattr(svc, "http_request", _http)
    assert svc.fetch_public_raw("gun1") == [{"id": 1}]
    assert urls == [
        "https://eftforge.com/builds/public?gun_id=gun1",
        "https://www.eftforge.com/builds/public?gun_id=gun1",
    ]


def test_fetch_rejects_offsite_and_chained_redirect(monkeypatch):
    monkeypatch.setattr(svc, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        svc,
        "http_request",
        lambda _m, url, **_k: _Resp(
            301,
            b"",
            headers={"Location": "https://evil.example/builds/public?gun_id=gun1"},
        ),
    )
    with pytest.raises(svc.TarkovCommunityError, match="异常跳转") as offsite:
        svc.fetch_public_raw("gun1")
    assert offsite.value.status_code == 502

    def _chain(_m: str, url: str, **_k):
        if "www.eftforge.com" in url:
            return _Resp(
                302,
                b"",
                headers={"location": "https://eftforge.com/builds/public?gun_id=gun1"},
            )
        return _Resp(
            301,
            b"",
            headers={
                "location": "https://www.eftforge.com/builds/public?gun_id=gun1"
            },
        )

    monkeypatch.setattr(svc, "http_request", _chain)
    with pytest.raises(svc.TarkovCommunityError, match="异常跳转"):
        svc.fetch_public_raw("gun2")


def test_fetch_public_raw_kill_switch_and_transport(monkeypatch):
    monkeypatch.setattr(svc, "get_settings", lambda: _settings())

    monkeypatch.setattr(
        svc,
        "http_request",
        lambda *_a, **_k: _Resp(
            403, b'{"detail":"community_builds_disabled"}'
        ),
    )
    with pytest.raises(svc.TarkovCommunityError, match="已关闭") as disabled:
        svc.fetch_public_raw("gun1")
    assert disabled.value.status_code == 503

    def _boom(*_a, **_k):
        raise HttpRequestError("请求超时：timed out")

    monkeypatch.setattr(svc, "http_request", _boom)
    with pytest.raises(svc.TarkovCommunityError, match="无法连接"):
        svc.fetch_public_raw("gun2")


def test_fetch_rejects_non_eftforge_host(monkeypatch):
    monkeypatch.setattr(
        svc, "get_settings", lambda: _settings(base="http://127.0.0.1:9")
    )
    with pytest.raises(svc.TarkovCommunityError, match="未配置") as exc:
        svc.fetch_public_raw("gun1")
    assert exc.value.status_code == 503


def test_fetch_rejects_oversized_payload(monkeypatch):
    monkeypatch.setattr(svc, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        svc,
        "http_request",
        lambda *_a, **_k: _Resp(200, b"x" * (svc.MAX_RAW_BYTES + 1)),
    )
    with pytest.raises(svc.TarkovCommunityError, match="过大") as exc:
        svc.fetch_public_raw("gun1")
    assert exc.value.status_code == 502


def test_accept_eftforge_public_url():
    assert svc.accept_eftforge_public_url(
        "https://eftforge.com/builds/public?gun_id=x"
    )
    assert svc.accept_eftforge_public_url(
        "https://www.eftforge.com/builds/public?gun_id=x"
    )
    assert not svc.accept_eftforge_public_url(
        "https://evil.example/builds/public?gun_id=x"
    )
    assert not svc.accept_eftforge_public_url(
        "http://eftforge.com/builds/public?gun_id=x"
    )
