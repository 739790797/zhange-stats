"""塔吉多社区签到：query / list targets / checkin_target / 每日任务 / 商城。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# 先加载 client，避免 attendance↔client 循环导入
import app.services.taygedo_client  # noqa: F401
from app.services.taygedo_attendance import (
    _parse_shop_goods,
    _tasks_extra_text,
    checkin_target,
    exchange_shop_goods,
    list_checkin_targets,
    list_shop_goods,
    query_app_today,
    query_today_all,
)
from app.services.taygedo_client import (
    GAME_APP,
    GAME_APP_NAME,
    GAME_NTE,
    GAME_NTE_NAME,
    TaygedoCredentials,
    TaygedoRole,
)


def _creds() -> TaygedoCredentials:
    return TaygedoCredentials(
        uid="u100",
        device_id="dev",
        access_token="atok",
        refresh_token="rtok",
    )


def test_query_app_today_pending() -> None:
    with patch(
        "app.services.taygedo_attendance._get_app_sign_state", return_value=False
    ):
        r = query_app_today(_creds())
    assert r.game_code == GAME_APP
    assert r.channel_name == "社区"
    assert r.role_uid == "u100"
    assert r.role_name == "社区账号"
    assert r.status == "pending"
    assert r.awards_text is None


def test_query_app_today_already_with_awards() -> None:
    with (
        patch(
            "app.services.taygedo_attendance._get_app_sign_state", return_value=True
        ),
        patch(
            "app.services.taygedo_attendance._app_signin_awards_from_tasks",
            return_value=("塔塔币+40", [{"name": "塔塔币", "count": 40, "resource_type": "gold"}]),
        ),
        patch(
            "app.services.taygedo_attendance.complete_daily_tasks",
            return_value={
                "text": "每日任务：浏览 5/5(+5) · 点赞 5/5(+5) · 分享 1/1(+20)",
                "all_done": True,
            },
        ) as tasks,
    ):
        r = query_app_today(_creds())
    assert r.status == "already"
    assert r.channel_name == "社区"
    assert r.awards_text == "塔塔币+40"
    assert "获得" in (r.message or "")
    assert r.extra_text and "每日任务" in r.extra_text
    tasks.assert_called_once()


def test_query_app_today_state_unavailable() -> None:
    with patch(
        "app.services.taygedo_attendance._get_app_sign_state", return_value=None
    ):
        r = query_app_today(_creds())
    assert r.status == "error"
    assert "查询社区签到状态失败" in (r.message or "")


def test_list_checkin_targets_includes_app_first() -> None:
    role = TaygedoRole(
        game_code=GAME_NTE,
        game_name=GAME_NTE_NAME,
        role_id="r1",
        role_name="主角",
    )
    with (
        patch(
            "app.services.taygedo_attendance.ensure_session",
            return_value=_creds(),
        ),
        patch(
            "app.services.taygedo_attendance.list_all_game_roles",
            return_value=[role],
        ),
    ):
        working, targets = list_checkin_targets(_creds())
    assert working.uid == "u100"
    assert targets[0] == (GAME_APP, None)
    assert targets[1] == (GAME_NTE, role)


def test_sort_taygedo_results_community_first() -> None:
    from app.services.checkin_common import CheckinResult
    from app.services.taygedo_attendance import sort_taygedo_results

    rows = [
        CheckinResult(
            game_code=GAME_NTE,
            game_name=GAME_NTE_NAME,
            role_uid="r1",
            role_name="主角",
            channel_name="异环",
            status="already",
            message="ok",
        ),
        CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid="u100",
            role_name="社区账号",
            channel_name="社区",
            status="pending",
            message="ok",
        ),
    ]
    ordered = sort_taygedo_results(rows)
    assert [r.game_code for r in ordered] == [GAME_APP, GAME_NTE]


def test_app_signin_awards_from_tasks_defaults() -> None:
    from app.services.taygedo_attendance import _app_signin_awards_from_tasks

    with patch(
        "app.services.taygedo_attendance.get_user_tasks",
        return_value={
            "signin_c": {
                "taskKey": "signin_c",
                "completeTimes": 1,
                "limitTimes": 1,
                "goldCoin": 40,
            }
        },
    ):
        text, items = _app_signin_awards_from_tasks(_creds())
    assert text == "塔塔币+40"
    assert items[0]["name"] == "塔塔币"
    assert items[0]["count"] == 40


def test_query_today_all_community_first() -> None:
    role = TaygedoRole(
        game_code=GAME_NTE,
        game_name=GAME_NTE_NAME,
        role_id="r1",
        role_name="主角",
    )
    community = MagicMock(
        game_code=GAME_APP, role_uid="u100", role_name="社区账号"
    )
    game = MagicMock(game_code=GAME_NTE, role_uid="r1", role_name="主角")
    with (
        patch(
            "app.services.taygedo_attendance.list_checkin_targets",
            return_value=(_creds(), [(GAME_APP, None), (GAME_NTE, role)]),
        ),
        patch(
            "app.services.taygedo_attendance.query_app_today",
            return_value=community,
        ) as q_app,
        patch(
            "app.services.taygedo_attendance.query_game_today",
            return_value=game,
        ) as q_game,
    ):
        _, results = query_today_all(_creds())
    assert [r.game_code for r in results] == [GAME_APP, GAME_NTE]
    assert results[0] is community
    assert results[1] is game
    q_app.assert_called_once()
    q_game.assert_called_once_with(_creds(), role)


def test_checkin_target_app_calls_signin() -> None:
    expected = MagicMock(game_code=GAME_APP, channel_name="社区")
    with patch(
        "app.services.taygedo_attendance.app_signin", return_value=expected
    ) as sign:
        out = checkin_target(_creds(), game_code=GAME_APP, role=None)
    assert out is expected
    sign.assert_called_once()


def test_app_signin_channel_name_is_community() -> None:
    from app.services.taygedo_attendance import app_signin

    with (
        patch(
            "app.services.taygedo_attendance._http",
            return_value=(
                200,
                {"code": 0, "data": {"exp": 10, "goldCoin": 40}},
            ),
        ),
        patch(
            "app.services.taygedo_attendance.complete_daily_tasks",
            return_value={"text": "每日任务：浏览 5/5 · 点赞 5/5 · 分享 1/1"},
        ),
    ):
        r = app_signin(_creds())
    assert r.status == "ok"
    assert r.game_name == GAME_APP_NAME
    assert r.channel_name == "社区"
    assert r.role_uid == "u100"
    assert r.awards_text is not None
    assert "塔塔币+40" in r.awards_text or "经验+10" in r.awards_text
    assert r.extra_text and "每日任务" in r.extra_text


def test_tasks_extra_text_format() -> None:
    text = _tasks_extra_text(
        browse=3,
        browse_need=5,
        like=5,
        like_need=5,
        share=1,
        share_need=1,
        browse_gold=5,
        like_gold=5,
        share_gold=20,
        gold=40,
        today_get=40,
        today_total=80,
    )
    assert "浏览 3/5(+5)" in text
    assert "点赞 5/5(+5)" in text
    assert "分享 1/1(+20)" in text
    assert "塔塔币+40" in text
    assert "今日 40/80" in text


def test_parse_shop_goods_flexible_fields() -> None:
    item = _parse_shop_goods(
        {
            "id": "g1",
            "name": "测试道具",
            "icon": "https://example.com/a.png",
            "price": 100,
            "exchangeNum": 1,
            "cycleLimit": 2,
            "cycleType": 1,
            "stock": 9,
            "limit": 1,
            "tab": "ht",
            "state": 1,
            "gameId": 1256,
        }
    )
    assert item is not None
    assert item.goods_id == "g1"
    assert item.cover.startswith("https://")
    assert item.price == 100
    assert item.game_id == "1256"
    assert item.stock_limited is True
    assert item.can_exchange is True
    d = item.to_dict()
    assert d["goods_id"] == "g1"
    assert d["can_exchange"] is True


def test_parse_shop_goods_unlimited_stock_not_sold_out() -> None:
    """limit=0 且 stock=0：官方不限库存，仍可兑换。"""
    item = _parse_shop_goods(
        {
            "id": 12,
            "name": "游戏名片",
            "price": 40,
            "exchangeNum": 0,
            "cycleLimit": 1,
            "cycleType": 0,
            "stock": 0,
            "limit": 0,
            "state": 1,
            "gameId": 1289,
        }
    )
    assert item is not None
    assert item.stock_limited is False
    assert item.stock == -1
    assert item.can_exchange is True


def test_parse_shop_goods_zero_game_id_uses_tab() -> None:
    """listGoods 常给 gameId=0，需从 tab 推断（yh→异环 / ht→幻塔）。"""
    yh = _parse_shop_goods(
        {
            "id": 12,
            "name": "游戏名片",
            "price": 40,
            "exchangeNum": 0,
            "cycleLimit": 1,
            "stock": 0,
            "limit": 0,
            "state": 1,
            "tab": "yh",
            "gameId": 0,
        }
    )
    assert yh is not None
    assert yh.game_id == "1289"
    ht = _parse_shop_goods(
        {
            "id": 10,
            "name": "金币*1000",
            "price": 300,
            "exchangeNum": 0,
            "cycleLimit": 1,
            "stock": 0,
            "limit": 0,
            "state": 1,
            "tab": "ht",
            "gameId": 0,
        }
    )
    assert ht is not None
    assert ht.game_id == "1256"


def test_parse_shop_goods_tracked_stock_zero_sold_out() -> None:
    item = _parse_shop_goods(
        {
            "id": 9,
            "name": "墨晶*150",
            "price": 4500,
            "exchangeNum": 0,
            "cycleLimit": 1,
            "cycleType": 1,
            "stock": 0,
            "limit": 1,
            "state": 1,
            "gameId": 1289,
        }
    )
    assert item is not None
    assert item.stock_limited is True
    assert item.stock == 0
    assert item.can_exchange is False


def test_list_shop_goods_parses_payload() -> None:
    payload = {
        "code": 0,
        "data": {
            "goods": [
                {
                    "goodsId": "1001",
                    "goodsName": "幻塔礼包",
                    "cover": "https://cdn/x.png",
                    "price": 200,
                    "exchangeNum": 0,
                    "cycleLimit": 1,
                    "cycleType": 1,
                    "remainStock": 3,
                    "tab": "ht",
                    "state": 1,
                    "gameId": "1256",
                }
            ],
            "tabs": [{"tab": "all", "name": "全部"}, {"tab": "ht", "name": "幻塔"}],
            "more": False,
            "version": 1,
        },
    }
    with patch(
        "app.services.taygedo_attendance._http",
        return_value=(200, payload),
    ):
        items, tabs = list_shop_goods(_creds(), tab="all")
    assert len(items) == 1
    assert items[0].goods_id == "1001"
    assert items[0].name == "幻塔礼包"
    assert items[0].stock == 3
    assert [t["tab"] for t in tabs] == ["all", "ht"]


def test_exchange_shop_goods_uses_app_headers_and_count() -> None:
    """官方兑换需 App 头 + count；纯 H5 会 invalid request。"""
    captured: dict = {}

    def _fake_http(method, url, *, headers=None, body=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["body"] = body or ""
        return 200, {"code": 0, "data": {"ok": True}}

    with patch("app.services.taygedo_attendance._http", side_effect=_fake_http):
        out = exchange_shop_goods(
            _creds(), goods_id="12", game_id="1289", role_id="219000995082"
        )
    assert out.get("ok") is True
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/apihub/api/shop/exchange")
    assert captured["headers"].get("authorization") == "atok"
    assert "Origin" not in captured["headers"]
    assert "goodsId=12" in captured["body"]
    assert "gameId=1289" in captured["body"]
    assert "roleId=219000995082" in captured["body"]
    assert "count=1" in captured["body"]
