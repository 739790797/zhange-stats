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
    _pref(db, "arknights", "1", on=False)
    db.commit()
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

    assert retired == 2
    db.expire_all()
    prefs = load_pref_map(db, platform="skland", member_id=1)
    state = {key: (p.included, p.enabled) for key, p in prefs.items()}
    assert state == {
        ("arknights", "kept"): (True, True),
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
    assert ("arknights", "gone") not in load_pref_map(db, platform="skland", member_id=1)


def _tree(db, roles: list[dict]):
    from app.api.platform_checkin import build_role_membership_tree

    return build_role_membership_tree(
        db=db,
        platform="skland",
        member_id=1,
        bind=_bind(db),
        preview_roles=lambda _db, _member: roles,
        member=db.get(Member, 1),
        api_error_cls=RuntimeError,
    )


def _replace(db, roles: list[dict]) -> None:
    from app.api.platform_checkin import apply_role_membership_replace
    from app.schemas.checkin import RoleMembershipReplaceBody

    apply_role_membership_replace(
        db=db,
        platform="skland",
        member_id=1,
        bind=_bind(db),
        body=RoleMembershipReplaceBody(roles=roles),
    )


def test_role_tree_seeds_listed_roles_so_memberships_can_be_saved(db) -> None:
    tree = _tree(db, [{"game_code": "arknights", "uid": "1"}, {"game_code": "endfield", "uid": "2"}])

    assert [(n.role_uid, n.included) for n in tree.roles] == [("1", False), ("2", False)]
    _replace(
        db,
        [
            {"game_code": "arknights", "role_uid": "1", "included": True},
            {"game_code": "endfield", "role_uid": "2", "included": False},
        ],
    )
    db.expire_all()
    state = {k: p.included for k, p in load_pref_map(db, platform="skland", member_id=1).items()}
    assert state == {("arknights", "1"): True, ("endfield", "2"): False}


def test_role_memberships_reject_the_whole_batch_when_a_role_was_never_listed(db) -> None:
    from fastapi import HTTPException

    from app.services.checkin.role_prefs import UNKNOWN_ROLE_MESSAGE

    _pref(db, "arknights", "1", on=False)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        _replace(
            db,
            [
                {"game_code": "arknights", "role_uid": "1", "included": True},
                {"game_code": "arknights", "role_uid": "made-up", "included": True},
            ],
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == UNKNOWN_ROLE_MESSAGE
    db.rollback()
    prefs = load_pref_map(db, platform="skland", member_id=1)
    assert {k: p.included for k, p in prefs.items()} == {("arknights", "1"): False}


def test_role_memberships_load_the_pref_map_once(db, monkeypatch) -> None:
    from app.services.checkin import role_prefs
    from app.services.checkin.role_prefs import apply_role_memberships

    for uid in ("1", "2", "3"):
        _pref(db, "arknights", uid, on=False)
    db.commit()
    calls: list[int] = []
    real_load = role_prefs.load_pref_map

    def counting_load(*args, **kwargs):
        calls.append(1)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(role_prefs, "load_pref_map", counting_load)
    apply_role_memberships(
        db,
        platform="skland",
        member_id=1,
        bind=_bind(db),
        roles=[{"game_code": "arknights", "role_uid": uid, "included": True} for uid in "123"],
    )

    assert len(calls) == 1
    db.expire_all()
    assert all(p.included for p in real_load(db, platform="skland", member_id=1).values())


def test_upsert_role_pref_does_not_create_rows_for_unknown_roles(db) -> None:
    from app.services.checkin.role_prefs import UNKNOWN_ROLE_MESSAGE, count_prefs

    with pytest.raises(ValueError, match=UNKNOWN_ROLE_MESSAGE):
        upsert_role_pref(
            db,
            platform="skland",
            member_id=1,
            bind=_bind(db),
            game_code="arknights",
            role_uid="made-up",
            enabled=True,
            checkin_hour=8,
            checkin_minute=0,
        )

    db.rollback()
    assert count_prefs(db, platform="skland", member_id=1) == 0


def test_ensure_prefs_stops_at_the_per_member_cap(db) -> None:
    from app.services.checkin.role_prefs import (
        MAX_PREFS_PER_MEMBER,
        count_prefs,
        ensure_prefs_for_roles,
    )

    ensure_prefs_for_roles(
        db,
        platform="skland",
        member_id=1,
        bind=_bind(db),
        roles=[("arknights", str(i)) for i in range(MAX_PREFS_PER_MEMBER + 20)],
    )
    db.commit()

    assert count_prefs(db, platform="skland", member_id=1) == MAX_PREFS_PER_MEMBER


def test_role_tree_hides_roles_that_did_not_fit_under_the_cap(db, monkeypatch) -> None:
    from app.services.checkin import role_prefs

    monkeypatch.setattr(role_prefs, "MAX_PREFS_PER_MEMBER", 1)

    tree = _tree(db, [{"game_code": "arknights", "uid": "1"}, {"game_code": "arknights", "uid": "2"}])

    assert [n.role_uid for n in tree.roles] == ["1"]


def test_role_membership_body_caps_the_number_of_roles() -> None:
    from pydantic import ValidationError

    from app.schemas.checkin import RoleMembershipReplaceBody

    item = {"game_code": "arknights", "role_uid": "1", "included": True}
    assert len(RoleMembershipReplaceBody(roles=[item] * 50).roles) == 50
    with pytest.raises(ValidationError):
        RoleMembershipReplaceBody(roles=[item] * 51)


def test_role_pref_endpoints_are_rate_limited_per_member(db) -> None:
    from fastapi import HTTPException

    from app.api.platform_checkin import ROLE_PREF_WRITE_LIMIT, ROLE_TREE_LIMIT

    for _ in range(ROLE_TREE_LIMIT):
        _tree(db, [])
    with pytest.raises(HTTPException) as tree_exc:
        _tree(db, [])
    assert tree_exc.value.status_code == 429

    for _ in range(ROLE_PREF_WRITE_LIMIT):
        _replace(db, [])
    with pytest.raises(HTTPException) as write_exc:
        _replace(db, [])
    assert write_exc.value.status_code == 429


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
