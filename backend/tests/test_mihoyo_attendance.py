"""米游社签到：登录失效必须上注，不能当成未签。"""

import pytest

from app.services.checkin.common import CheckinResult
from app.services.mihoyo.attendance import _community_result, query_today_all
from app.services.mihoyo.client import GameRole, MihoyoApiError, MihoyoCredentials


def _creds() -> MihoyoCredentials:
    return MihoyoCredentials(cookie="ltuid=1; stoken=s", stuid="1")


def test_community_query_raises_on_forum_auth(monkeypatch):
    def boom(*_a, **_k):
        raise MihoyoApiError("登录失效", code=-100)

    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_signed_from_missions",
        boom,
    )
    with pytest.raises(MihoyoApiError, match="登录失效"):
        _community_result(_creds(), do_sign=False, attach_tasks=False)


def test_community_query_treats_non_auth_as_pending(monkeypatch):
    def boom(*_a, **_k):
        raise MihoyoApiError("网络超时")

    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_signed_from_missions",
        boom,
    )
    result = _community_result(_creds(), do_sign=False, attach_tasks=False)
    assert result.status == "pending"
    assert "未签" in result.message or "未知" in result.message


def test_community_query_already_from_missions(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_signed_from_missions",
        lambda _c: True,
    )
    result = _community_result(_creds(), do_sign=False, attach_tasks=False)
    assert result.status == "already"


def test_community_signed_from_missions_task_58(monkeypatch):
    from app.services.mihoyo.attendance import _community_signed_from_missions

    monkeypatch.setattr(
        "app.services.mihoyo.attendance._http_json",
        lambda *_a, **_k: {
            "retcode": 0,
            "data": {
                "can_get_points": 30,
                "states": [{"mission_id": 58, "is_get_award": True}],
            },
        },
    )
    monkeypatch.setattr("app.services.mihoyo.attendance._mission_headers", lambda _c: {})
    monkeypatch.setattr(
        "app.services.mihoyo.attendance.call_with_cookie_refresh",
        lambda _c, fn: fn(_c),
    )
    assert _community_signed_from_missions(_creds()) is True


def test_query_today_keeps_games_when_one_game_auth_fails(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo.attendance.ensure_session",
        lambda c: c,
    )
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_result",
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
        "app.services.mihoyo.attendance.list_game_roles",
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
        "app.services.mihoyo.attendance._query_game_signed",
        boom,
    )
    _working, results = query_today_all(_creds())
    genshin = next(r for r in results if r.game_code == "genshin")
    assert genshin.status == "error"
    assert "登录已失效" in genshin.message


def test_query_today_community_auth_does_not_kill_status(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo.attendance.ensure_session",
        lambda c: c,
    )

    def boom_community(*_a, **_k):
        raise MihoyoApiError("登录失效", code=-100)

    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_result",
        boom_community,
    )
    monkeypatch.setattr(
        "app.services.mihoyo.attendance.list_game_roles",
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
        "app.services.mihoyo.attendance._query_game_signed",
        lambda *_a, **_k: (False, None, []),
    )
    _working, results = query_today_all(_creds())
    assert results[0].game_code == "mihoyo"
    assert results[0].status == "error"
    genshin = next(r for r in results if r.game_code == "genshin")
    assert genshin.status == "pending"


def test_query_game_signed_fills_awards_from_home(monkeypatch):
    from app.services.mihoyo.attendance import _query_game_signed
    from app.services.mihoyo.client import GAME_BIZ_META
    from app.services.mihoyo_bbs import setting as bbs_setting

    def fake_http(_method, url, **_k):
        if url == bbs_setting.cn_game_is_signurl:
            return {
                "retcode": 0,
                "data": {"is_sign": True, "total_sign_day": 2, "today": "2"},
            }
        if url == bbs_setting.cn_game_checkin_rewards:
            return {
                "retcode": 0,
                "data": {
                    "awards": [
                        {"name": "A", "cnt": 1, "icon": "https://example.com/a.png"},
                        {
                            "name": "原石",
                            "cnt": 20,
                            "icon": "https://example.com/p.png",
                        },
                        {"name": "C", "cnt": 3},
                    ]
                },
            }
        raise AssertionError(url)

    monkeypatch.setattr("app.services.mihoyo.attendance._http_json", fake_http)
    monkeypatch.setattr(
        "app.services.mihoyo.attendance.call_with_cookie_refresh",
        lambda _c, fn: fn(_c),
    )
    signed, text, items = _query_game_signed(
        _creds(), GAME_BIZ_META["hk4e_cn"], "cn_gf01", "123"
    )
    assert signed is True
    assert text == "原石×20"
    assert items[0]["icon_url"] == "https://example.com/p.png"


def test_bbs_sign_all_posts_signin_not_info(monkeypatch):
    from app.services.mihoyo.attendance import _bbs_sign_all
    from app.services.mihoyo_bbs import setting as bbs_setting

    calls: list[tuple[str, str]] = []

    def fake_http(method, url, **_k):
        calls.append((method, url))
        if url == bbs_setting.bbs_sign_url:
            return {"retcode": 0, "message": "OK", "data": {"points": 10}}
        raise AssertionError(url)

    monkeypatch.setattr("app.services.mihoyo.attendance._http_json", fake_http)
    monkeypatch.setattr(
        "app.services.mihoyo.attendance.list_bbs_business_ids",
        lambda _c: ["2", "6"],
    )
    monkeypatch.setattr("app.services.mihoyo.attendance.time.sleep", lambda _s: None)
    points, failures = _bbs_sign_all(_creds())
    assert points == 20
    assert failures == []
    assert calls == [
        ("POST", bbs_setting.bbs_sign_url),
        ("POST", bbs_setting.bbs_sign_url),
    ]
    assert all("signInInfo" not in url for _m, url in calls)


def test_bbs_sign_all_collects_non_auth_failures(monkeypatch):
    from app.services.mihoyo.attendance import _bbs_sign_all

    def fake_sign(_c, forum):
        if forum["name"] == "原神":
            raise MihoyoApiError("上游返回非 JSON（HTTP 404）")
        return "OK", 10

    monkeypatch.setattr("app.services.mihoyo.attendance._bbs_forum_sign", fake_sign)
    monkeypatch.setattr(
        "app.services.mihoyo.attendance.list_bbs_business_ids",
        lambda _c: ["1", "2"],
    )
    monkeypatch.setattr("app.services.mihoyo.attendance.time.sleep", lambda _s: None)
    points, failures = _bbs_sign_all(_creds())
    assert points == 10
    assert failures == ["原神失败：上游返回非 JSON（HTTP 404）"]


def test_community_sign_skips_post_when_missions_done(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_signed_from_missions",
        lambda _c: True,
    )

    def boom(*_a, **_k):
        raise AssertionError("should not POST signIn")

    monkeypatch.setattr("app.services.mihoyo.attendance._bbs_sign_all", boom)
    result = _community_result(_creds(), do_sign=True, attach_tasks=False)
    assert result.status == "already"
    assert result.message == "讨论区今日已签到"


def test_community_sign_ok_when_forums_succeed(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_signed_from_missions",
        lambda _c: False,
    )
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._bbs_sign_all",
        lambda _c: (30, []),
    )
    result = _community_result(_creds(), do_sign=True, attach_tasks=False)
    assert result.status == "ok"
    assert result.message == "讨论区签到完成"
    assert result.awards_text == "米游币+30"


def test_community_sign_reports_forum_failure_as_error(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_signed_from_missions",
        lambda _c: False,
    )
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._bbs_sign_all",
        lambda _c: (
            0,
            [
                "崩坏3失败：上游返回非 JSON（HTTP 404）",
                "原神失败：上游返回非 JSON（HTTP 404）",
                "崩坏2失败：上游返回非 JSON（HTTP 404）",
            ],
        ),
    )
    result = _community_result(_creds(), do_sign=True, attach_tasks=False)
    assert result.status == "error"
    assert "讨论区签到完成" not in result.message
    assert "讨论区签到失败" in result.message
    assert "崩坏3失败" in result.message
    assert "崩坏2失败" in result.message


def test_community_sign_partial_fail_is_error(monkeypatch):
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._community_signed_from_missions",
        lambda _c: False,
    )
    monkeypatch.setattr(
        "app.services.mihoyo.attendance._bbs_sign_all",
        lambda _c: (10, ["崩坏2失败：网络错误"]),
    )
    result = _community_result(_creds(), do_sign=True, attach_tasks=False)
    assert result.status == "error"
    assert "部分失败" in result.message
    assert result.awards_text == "米游币+10"
