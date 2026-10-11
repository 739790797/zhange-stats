"""森空岛：失效 cred 缓存遇鉴权错误时清缓存并换票重试一次（查今日 / 签到两条路径）。"""

from __future__ import annotations

import pytest

from app.services.checkin.common import CheckinResult
from app.services.skland.checkin import (
    _looks_like_skland_auth_error,
    query_today_for_bind,
    run_checkin_for_bind,
)
from app.services.skland.client import SklandApiError, SklandRole, SklandSession


def test_looks_like_skland_auth_error():
    assert _looks_like_skland_auth_error("用户未登录")
    assert _looks_like_skland_auth_error("凭证可能已失效，请重新绑定森空岛（用户未登录）")
    assert not _looks_like_skland_auth_error("网络超时")
    assert not _looks_like_skland_auth_error("")


class _CredCache:
    """模拟 cred 缓存：作废后下一次取会话才用 hg token 换票。"""

    def __init__(self) -> None:
        self.session: SklandSession | None = SklandSession(cred="stale", sign_token="s0")
        self.logins = 0
        self.invalidated: list[int] = []
        self.login_error: str | None = None

    def session_for_bind(self, _db, _bind) -> SklandSession:
        if self.session is None:
            if self.login_error:
                raise SklandApiError(self.login_error)
            self.logins += 1
            self.session = SklandSession(cred=f"fresh{self.logins}", sign_token="s1")
        return self.session

    def invalidate(self, member_id: int) -> None:
        self.invalidated.append(member_id)
        self.session = None


@pytest.fixture
def cred_cache(monkeypatch):
    cache = _CredCache()
    monkeypatch.setattr(
        "app.services.skland.checkin._session_for_bind", cache.session_for_bind
    )
    monkeypatch.setattr(
        "app.services.skland.session_cache.invalidate_skland_session", cache.invalidate
    )
    return cache


@pytest.fixture
def db_bind():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base
    from app.models.member import Member
    from app.models.skland import SklandBind

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(Member(id=9, nickname="m9"))
    bind = SklandBind(member_id=9, token_enc="enc", auto_checkin=True)
    db.add(bind)
    db.commit()
    yield db, bind
    db.close()


_ROLE = SklandRole(
    game_code="arknights",
    game_name="明日方舟",
    uid="u1",
    role_name="博士",
    channel_name="官服",
    channel_master_id="1",
)


def _result(status: str) -> CheckinResult:
    return CheckinResult(
        game_code=_ROLE.game_code,
        game_name=_ROLE.game_name,
        role_uid=_ROLE.uid,
        role_name=_ROLE.role_name,
        channel_name=_ROLE.channel_name,
        status=status,
        message="",
    )


def _reject_stale_cred(session: SklandSession) -> None:
    if session.cred == "stale":
        raise SklandApiError("用户未登录", code=10001)


@pytest.mark.parametrize("force", [False, True])
def test_query_today_renews_stale_cred_once(monkeypatch, cred_cache, db_bind, force):
    db, bind = db_bind
    queried: list[str] = []

    def query_all(session):
        queried.append(session.cred)
        _reject_stale_cred(session)
        return session, [_result("already")]

    monkeypatch.setattr("app.services.skland.checkin.skland_query_today_all", query_all)

    out = query_today_for_bind(db, bind, force=force)

    assert queried == ["stale", "fresh1"]
    assert cred_cache.invalidated == [9]
    assert [r["status"] for r in out["results"]] == ["already"]


def test_checkin_renews_stale_cred_once(monkeypatch, cred_cache, db_bind):
    """调度签到同样走这里：缓存 cred 被顶掉不能把当天判成凭证失效。"""
    db, bind = db_bind
    listed: list[str] = []

    def list_roles(session):
        listed.append(session.cred)
        _reject_stale_cred(session)
        return [_ROLE]

    monkeypatch.setattr("app.services.skland.checkin.list_roles", list_roles)
    monkeypatch.setattr(
        "app.services.skland.checkin.query_role_today", lambda _s, _r: _result("pending")
    )
    monkeypatch.setattr(
        "app.services.skland.checkin.checkin_role", lambda _s, _r: _result("ok")
    )

    out = run_checkin_for_bind(db, bind, force=False)

    assert listed == ["stale", "fresh1"]
    assert cred_cache.invalidated == [9]
    assert out["ok"] is True
    assert [r["status"] for r in out["results"]] == ["ok"]


def test_query_today_does_not_retry_non_auth(monkeypatch, cred_cache, db_bind):
    db, bind = db_bind

    def query_all(_session):
        raise SklandApiError("网络超时")

    monkeypatch.setattr("app.services.skland.checkin.skland_query_today_all", query_all)

    with pytest.raises(SklandApiError, match="网络超时"):
        query_today_for_bind(db, bind, force=True)
    assert cred_cache.invalidated == []


def test_second_auth_failure_is_surfaced_without_another_retry(
    monkeypatch, cred_cache, db_bind
):
    db, bind = db_bind
    listed: list[str] = []

    def list_roles(session):
        listed.append(session.cred)
        raise SklandApiError("用户未登录", code=10001)

    monkeypatch.setattr("app.services.skland.checkin.list_roles", list_roles)

    with pytest.raises(SklandApiError, match="请重新绑定森空岛") as info:
        run_checkin_for_bind(db, bind, force=True)
    assert info.value.code == 10001
    assert listed == ["stale", "fresh1"]
    assert cred_cache.invalidated == [9]


def test_expired_hg_token_during_renewal_gets_friendly_message(
    monkeypatch, cred_cache, db_bind
):
    db, bind = db_bind
    cred_cache.login_error = "登录已过期"

    def query_all(session):
        _reject_stale_cred(session)
        return session, []

    monkeypatch.setattr("app.services.skland.checkin.skland_query_today_all", query_all)

    with pytest.raises(SklandApiError, match="请重新绑定森空岛（登录已过期）"):
        query_today_for_bind(db, bind, force=True)
    assert cred_cache.invalidated == [9]
