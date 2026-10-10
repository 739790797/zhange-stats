"""checkin_role_prefs 单测：纯函数，以及按生产会话配置（不 autoflush）跑的读写。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member
from app.models.skland import SklandBind
from app.services.checkin.role_prefs import (
    enrich_result_dicts,
    load_pref_map,
    matches_role_filter,
    retire_vanished_prefs,
    role_key,
    upsert_role_pref,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    session.add(Member(id=1, nickname="m1"))
    session.add(SklandBind(member_id=1, token_enc="x", auto_checkin=False))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _bind(db) -> SklandBind:
    return db.query(SklandBind).filter_by(member_id=1).one()


def _pref(db, game_code: str, role_uid: str, *, on: bool) -> None:
    db.add(
        CheckinRolePref(
            platform="skland",
            member_id=1,
            game_code=game_code,
            role_uid=role_uid,
            included=on,
            enabled=on,
            checkin_hour=8,
            checkin_minute=0,
        )
    )


def test_role_key_strips() -> None:
    assert role_key(" arknights ", " 123 ") == ("arknights", "123")


def test_matches_role_filter() -> None:
    keys = {("arknights", "1"), ("endfield", "2")}
    assert matches_role_filter("arknights", "1", keys)
    assert not matches_role_filter("arknights", "9", keys)
    assert matches_role_filter("arknights", "9", None)


def test_enrich_result_dicts_defaults_off() -> None:
    results = [
        {
            "game_code": "arknights",
            "role_uid": "u1",
            "status": "pending",
            "message": "x",
        }
    ]
    out = enrich_result_dicts(results, {})
    assert out[0]["included"] is False
    assert out[0]["auto_checkin"] is False
    assert out[0]["checkin_hour"] is None


def test_enrich_result_dicts_from_pref() -> None:
    pref = SimpleNamespace(
        included=True, enabled=True, checkin_hour=8, checkin_minute=30
    )
    results = [{"game_code": "arknights", "role_uid": "u1", "status": "ok", "message": "x"}]
    out = enrich_result_dicts(results, {("arknights", "u1"): pref})  # type: ignore[arg-type]
    assert out[0]["included"] is True
    assert out[0]["auto_checkin"] is True
    assert out[0]["checkin_hour"] == 8
    assert out[0]["checkin_minute"] == 30


def test_filter_included_results() -> None:
    from app.services.checkin.role_prefs import filter_included_results

    rows = [
        {"game_code": "a", "role_uid": "1", "included": True},
        {"game_code": "a", "role_uid": "2", "included": False},
    ]
    assert filter_included_results(rows) == [rows[0]]


def test_build_membership_tree_from_roles() -> None:
    from app.services.checkin.role_prefs import build_membership_tree_from_roles

    pref = SimpleNamespace(included=True)
    nodes = build_membership_tree_from_roles(
        platform="skland",
        roles=[
            {
                "game_code": "arknights",
                "game_name": "明日方舟",
                "uid": "1",
                "role_name": "A",
                "channel_name": "官服",
            }
        ],
        pref_map={("arknights", "1"): pref},  # type: ignore[arg-type]
    )
    assert len(nodes) == 1
    assert nodes[0]["included"] is True
    assert nodes[0]["role_uid"] == "1"


def test_today_done_from_logs_role_keys() -> None:
    from app.services.checkin.common import today_done_from_logs

    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *a, **k):
            return self

        def all(self):
            return self._rows

    class FakeDb:
        def __init__(self, rows):
            self._rows = rows

        def query(self, model):
            return FakeQuery(self._rows)

    rows = [
        SimpleNamespace(
            game_code="arknights",
            game_name="方舟",
            role_uid="1",
            role_name="A",
            channel_name="官服",
            status="ok",
            message="ok",
            awards_text=None,
            awards_json=None,
        ),
        SimpleNamespace(
            game_code="endfield",
            game_name="终末地",
            role_uid="2",
            role_name="B",
            channel_name="国服",
            status="pending",
            message="未签",
            awards_text=None,
            awards_json=None,
        ),
    ]
    db = FakeDb(rows)
    log_model = SimpleNamespace(member_id=None, checkin_date=None)
    done = today_done_from_logs(
        db,
        log_model,
        member_id=1,
        checkin_date="2026-08-26",
        role_keys={("arknights", "1")},
    )
    assert done is not None
    assert len(done) == 1
    assert done[0].role_uid == "1"
    assert (
        today_done_from_logs(
            db,
            log_model,
            member_id=1,
            checkin_date="2026-08-26",
            role_keys={("arknights", "1"), ("endfield", "2")},
        )
        is None
    )


def test_role_pref_toggle_keeps_bind_auto_checkin_in_sync(db) -> None:
    bind = _bind(db)
    upsert_role_pref(
        db,
        platform="skland",
        member_id=1,
        bind=bind,
        game_code="arknights",
        role_uid="1",
        enabled=True,
        checkin_hour=8,
        checkin_minute=0,
    )
    db.refresh(bind)
    assert bind.auto_checkin is True

    upsert_role_pref(
        db,
        platform="skland",
        member_id=1,
        bind=bind,
        game_code="arknights",
        role_uid="1",
        enabled=False,
    )
    db.refresh(bind)
    assert bind.auto_checkin is False


def test_retire_vanished_prefs_only_judges_games_that_were_listed(db) -> None:
    _pref(db, "arknights", "kept", on=True)
    _pref(db, "arknights", "gone", on=True)
    _pref(db, "arknights", "gone-already-off", on=False)
    # 这次终末地一个角色都没列出来：可能是那一路接口挂了，不能据此动偏好
    _pref(db, "endfield", "unlisted-game", on=True)
    bind = _bind(db)
    bind.auto_checkin = True
    db.commit()

    retired = retire_vanished_prefs(
        db,
        platform="skland",
        member_id=1,
        bind=bind,
        roles=[SimpleNamespace(game_code="arknights", uid="kept")],
    )

    assert retired == 1
    db.expire_all()
    prefs = load_pref_map(db, platform="skland", member_id=1)
    state = {key: (p.included, p.enabled) for key, p in prefs.items()}
    assert state == {
        ("arknights", "kept"): (True, True),
        ("arknights", "gone"): (False, False),
        ("arknights", "gone-already-off"): (False, False),
        ("endfield", "unlisted-game"): (True, True),
    }
    assert _bind(db).auto_checkin is True


def test_retire_vanished_prefs_turns_bind_auto_checkin_off_when_nothing_is_left(db) -> None:
    _pref(db, "arknights", "old-account", on=True)
    bind = _bind(db)
    bind.auto_checkin = True
    db.commit()

    retired = retire_vanished_prefs(
        db,
        platform="skland",
        member_id=1,
        bind=bind,
        roles=[{"game_code": "arknights", "uid": "new-account"}],
    )

    assert retired == 1
    db.expire_all()
    assert _bind(db).auto_checkin is False


def test_role_tree_retires_vanished_roles_before_rendering(db) -> None:
    from app.api.platform_checkin import build_role_membership_tree

    _pref(db, "arknights", "kept", on=True)
    _pref(db, "arknights", "gone", on=True)
    db.commit()
    member = db.get(Member, 1)

    tree = build_role_membership_tree(
        db=db,
        platform="skland",
        member_id=1,
        bind=_bind(db),
        preview_roles=lambda _db, _member: [
            {"game_code": "arknights", "game_name": "明日方舟", "uid": "kept"}
        ],
        member=member,
        api_error_cls=RuntimeError,
    )

    assert [(n.role_uid, n.included) for n in tree.roles] == [("kept", True)]
    db.expire_all()
    gone = load_pref_map(db, platform="skland", member_id=1)[("arknights", "gone")]
    assert (gone.included, gone.enabled) == (False, False)


def test_mihoyo_role_tree_community_key_matches_checkin_key(monkeypatch) -> None:
    """角色树的键对不上签到用的键，退役时会把还在的社区账号当成「已不存在」。"""
    from app.services.mihoyo import checkin as mihoyo_checkin
    from app.services.mihoyo.attendance import _bbs_uid
    from app.services.mihoyo.client import MihoyoCredentials

    creds = MihoyoCredentials(cookie="account_id=42", account_id="42")
    monkeypatch.setattr(mihoyo_checkin, "get_bind_for_member", lambda _db, _mid: object())
    monkeypatch.setattr(
        mihoyo_checkin, "_session_for_bind", lambda _db, _bind: SimpleNamespace(creds=creds)
    )
    monkeypatch.setattr(mihoyo_checkin, "list_game_roles", lambda _creds: [])
    monkeypatch.setattr(mihoyo_checkin, "_store_creds", lambda *_a: None)

    roles = mihoyo_checkin.preview_roles(SimpleNamespace(commit=lambda: None), SimpleNamespace(id=1))

    assert role_key(roles[0]["game_code"], roles[0]["uid"]) == ("mihoyo", _bbs_uid(creds))
    assert _bbs_uid(creds) == "42"
