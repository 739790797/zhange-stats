"""B服 query_role_today：records 空不得误判未签；签到只信 POST awards。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app.services.skland_client  # noqa: F401 — 解开 attendance↔client 环依赖
from app.services.checkin_common import STATUS_UNKNOWN, CheckinResult
from app.services.skland_attendance import checkin_arknights, query_role_today
from app.services.skland_awards import arknights_result_needs_award_icons
from app.services.skland_client import GAME_ARKNIGHTS


def _bili_role(**kwargs: object) -> SimpleNamespace:
    base = dict(
        game_code=GAME_ARKNIGHTS,
        game_name="明日方舟",
        uid="52430798",
        role_name="白衣#0719",
        channel_name="B服",
        channel_master_id="2",
        role_id=None,
        server_id=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_bilibili_empty_records_is_unknown_not_pending() -> None:
    role = _bili_role()
    empty = {"code": 0, "data": {"records": [], "calendar": [{"done": False}]}}

    with patch(
        "app.services.skland_attendance._attendance_get",
        return_value=empty,
    ):
        result = query_role_today(SimpleNamespace(), role)  # type: ignore[arg-type]

    assert result.status == STATUS_UNKNOWN
    assert "领取记录" in (result.message or "")


def test_bilibili_checkin_ok_trusts_post_awards_only() -> None:
    """B 服签到成功：gameId=channelMasterId，奖励来自 POST data.awards。"""
    role = _bili_role()
    post_resp = {
        "code": 0,
        "message": "OK",
        "data": {
            "awards": [
                {
                    "resource": {
                        "id": "4003",
                        "type": "DIAMOND_SHD",
                        "name": "合成玉",
                    },
                    "count": 80,
                }
            ]
        },
    }
    fetch_mock = MagicMock(return_value=("不应调用", []))

    with (
        patch(
            "app.services.skland_attendance._signed_headers",
            return_value={},
        ),
        patch(
            "app.services.skland_attendance._http_json",
            return_value=post_resp,
        ) as http,
        patch(
            "app.services.skland_attendance.fetch_today_awards",
            fetch_mock,
        ),
    ):
        result = checkin_arknights(SimpleNamespace(), role)  # type: ignore[arg-type]

    assert result.status == "ok"
    assert result.awards_text == "合成玉x80"
    assert result.awards and result.awards[0]["name"] == "合成玉"
    assert http.call_args.kwargs["body"]["gameId"] == "2"
    fetch_mock.assert_not_called()


def test_bilibili_already_does_not_fetch_get_awards() -> None:
    """B 服「请勿重复签到」：不 GET 补奖。"""
    role = _bili_role()
    already_resp = {"code": 10001, "message": "请勿重复签到", "data": {}}
    fetch_mock = MagicMock(return_value=("合成玉x80", [{"name": "合成玉"}]))

    with (
        patch(
            "app.services.skland_attendance._signed_headers",
            return_value={},
        ),
        patch(
            "app.services.skland_attendance._http_json",
            return_value=already_resp,
        ),
        patch(
            "app.services.skland_attendance.fetch_today_awards",
            fetch_mock,
        ),
    ):
        result = checkin_arknights(SimpleNamespace(), role)  # type: ignore[arg-type]

    assert result.status == "already"
    assert not result.awards_text
    fetch_mock.assert_not_called()


def test_official_already_still_fetches_get_awards() -> None:
    """官服「已签」无 POST awards 时仍可 GET records 补奖。"""
    role = _bili_role(channel_name="官服", channel_master_id="1")
    already_resp = {"code": 10001, "message": "请勿重复签到", "data": {}}
    fetch_mock = MagicMock(
        return_value=(
            "合成玉x80",
            [{"name": "合成玉", "count": 80, "resource_type": "DIAMOND_SHD"}],
        )
    )

    with (
        patch(
            "app.services.skland_attendance._signed_headers",
            return_value={},
        ),
        patch(
            "app.services.skland_attendance._http_json",
            return_value=already_resp,
        ),
        patch(
            "app.services.skland_attendance.fetch_today_awards",
            fetch_mock,
        ),
    ):
        result = checkin_arknights(SimpleNamespace(), role)  # type: ignore[arg-type]

    assert result.status == "already"
    assert result.awards_text == "合成玉x80"
    fetch_mock.assert_called_once()


def test_bilibili_cached_awards_do_not_force_icon_refresh() -> None:
    bare = CheckinResult(
        game_code="arknights",
        game_name="明日方舟",
        role_uid="1",
        role_name="a",
        channel_name="B服",
        status="already",
        message="合成玉x80",
        awards_text="合成玉x80",
        awards=None,
    )
    assert arknights_result_needs_award_icons(bare) is False
