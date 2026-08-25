"""米游社签到：登录失效必须上注，不能当成未签。"""

import pytest

from app.services.checkin_common import CheckinResult
from app.services.mihoyo_attendance import _community_result, query_today_all
from app.services.mihoyo_client import GameRole, MihoyoApiError, MihoyoCredentials


def _creds() -> MihoyoCredentials:
    return MihoyoCredentials(cookie="ltuid=1; stoken=s", stuid="1")


def test_community_query_raises_on_forum_auth(monkeypatch):
    def boom(*_a, **_k):
        raise MihoyoApiError("登录失效", code=-100)

    monkeypatch.setattr(
        "app.services.mihoyo_attendance._community_signed_from_missions",
        boom,
    )
    with pytest.raises(MihoyoApiError, match="登录失效"):
        _community_result(_creds(), do_sign=False, attach_tasks=False)


def test_community_query_treats_non_auth_as_pending(monkeypatch):
    def boom(*_a, **_k):
        raise MihoyoApiError("网络超时")

    monkeypatch.setattr(
        "app.services.mihoyo_attendance._community_signed_from_missions",
        boom,
    )
    result = _community_result(_creds(), do_sign=False, attach_tasks=False)
    assert result.status == "pending"
    assert "未签" in result.message or "未知" in result.message


def test_community_query_already_from_missions(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo_attendance._community_signed_from_missions",
        lambda _c: True,
    )
    result = _community_result(_creds(), do_sign=False, attach_tasks=False)
    assert result.status == "already"


def test_community_signed_from_missions_task_58(monkeypatch):
    from app.services.mihoyo_attendance import _community_signed_from_missions

    monkeypatch.setattr(
        "app.services.mihoyo_attendance._http_json",
        lambda *_a, **_k: {
            "retcode": 0,
            "data": {
                "can_get_points": 30,
                "states": [{"mission_id": 58, "is_get_award": True}],
            },
        },
    )
    monkeypatch.setattr("app.services.mihoyo_attendance._mission_headers", lambda _c: {})
    monkeypatch.setattr(
        "app.services.mihoyo_attendance.call_with_cookie_refresh",
        lambda _c, fn: fn(_c),
    )
    assert _community_signed_from_missions(_creds()) is True


def test_query_today_keeps_games_when_one_game_auth_fails(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo_attendance.ensure_session",
        lambda c: c,
    )
    monkeypatch.setattr(
        "app.services.mihoyo_attendance._community_result",
        lambda *_a, **_k: CheckinResult(
            game_code="mihoyo",
            game_name="米游社",
            role_uid="1",
            role_name="x",
            channel_name="社区",
            status="pending",
            message="讨论区未签：原神",
        ),
    )
    monkeypatch.setattr(
        "app.services.mihoyo_attendance.list_game_roles",
        lambda _c: [
            GameRole(
                game_biz="hk4e_cn",
                game_code="genshin",
                game_name="原神",
                role_uid="123",
                role_name="旅人",
                region="cn_gf01",
                channel_name="官服",
            )
        ],
    )

    def boom(*_a, **_k):
        raise MihoyoApiError("登录已失效，请重新绑定", code=-100)

    monkeypatch.setattr(
        "app.services.mihoyo_attendance._query_game_signed",
        boom,
    )
    _working, results = query_today_all(_creds())
    genshin = next(r for r in results if r.game_code == "genshin")
    assert genshin.status == "error"
    assert "登录已失效" in genshin.message


def test_query_today_community_auth_does_not_kill_status(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo_attendance.ensure_session",
        lambda c: c,
    )

    def boom_community(*_a, **_k):
        raise MihoyoApiError("登录失效", code=-100)

    monkeypatch.setattr(
        "app.services.mihoyo_attendance._community_result",
        boom_community,
    )
    monkeypatch.setattr(
        "app.services.mihoyo_attendance.list_game_roles",
        lambda _c: [
            GameRole(
                game_biz="hk4e_cn",
                game_code="genshin",
                game_name="原神",
                role_uid="123",
                role_name="旅人",
                region="cn_gf01",
                channel_name="官服",
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.mihoyo_attendance._query_game_signed",
        lambda *_a, **_k: (False, None, []),
    )
    _working, results = query_today_all(_creds())
    assert results[0].game_code == "mihoyo"
    assert results[0].status == "error"
    genshin = next(r for r in results if r.game_code == "genshin")
    assert genshin.status == "pending"
