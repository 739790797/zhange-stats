"""绑定收尾：解绑 / 更换绑定后读库页面不留旧账号数据，重试账清零，补签只签已开的角色。"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy import Date, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
from app.core.timeutil import now as now_beijing
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.services.checkin import binding
from app.services.checkin.attempts import load_attempts, record_checkin_attempt
from app.services.checkin.registry import get_checkin_adapters

# 挂在成员上、但不是签到平台数据的表（Steam 游玩统计）
_NOT_PLATFORM_DATA = {PlaySession, PresenceSegment}


@pytest.fixture(autouse=True)
def _fresh_kv():
    reset_ephemeral_kv_for_tests()
    yield
    reset_ephemeral_kv_for_tests()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    yield session
    session.close()
    engine.dispose()


def _row(model: type, **values: Any) -> Any:
    """只填必填列，模型加字段时测试不用跟着改。"""
    for col in model.__table__.columns:
        if (
            col.primary_key
            or col.name in values
            or col.nullable
            or col.default is not None
            or col.server_default is not None
        ):
            continue
        values[col.name] = date(2026, 10, 10) if isinstance(col.type, Date) else "x"
    return model(**values)


def _seed(db: Session, member_id: int, *, auto_checkin: bool = False) -> None:
    db.add(Member(id=member_id, nickname=f"m{member_id}"))
    for platform in ("skland", "taygedo"):
        adapter = get_checkin_adapters()[platform]
        bind = _row(adapter.bind_model, member_id=member_id, auto_checkin=auto_checkin)
        db.add(bind)
        db.flush()
        db.add(_row(adapter.log_model, member_id=member_id, bind_id=bind.id))
        db.add_all(_row(model, member_id=member_id) for model in adapter.member_raw_models)
        db.add(
            _row(
                CheckinRolePref,
                platform=platform,
                member_id=member_id,
                game_code="game",
                role_uid=str(member_id),
            )
        )
    db.commit()


def _count(db: Session, model: type, member_id: int, **filters: Any) -> int:
    q = db.query(model).filter(model.member_id == member_id)
    for name, value in filters.items():
        q = q.filter(getattr(model, name) == value)
    return q.count()


def _member_scoped_models() -> set[type]:
    return {
        mapper.class_
        for mapper in Base.registry.mappers
        if any(fk.column.table.name == "members" for fk in mapper.local_table.foreign_keys)
    }


def test_every_member_scoped_platform_table_is_cleaned_by_exactly_one_adapter() -> None:
    adapters = list(get_checkin_adapters().values())
    owners: dict[type, list[str]] = {}
    for adapter in adapters:
        for model in adapter.member_raw_models:
            owners.setdefault(model, []).append(adapter.platform)
    assert {m.__name__: p for m, p in owners.items() if len(p) > 1} == {}

    scoped = _member_scoped_models()
    assert set(owners) <= scoped
    handled = set(owners) | _NOT_PLATFORM_DATA | {CheckinRolePref}
    for adapter in adapters:
        handled |= {adapter.bind_model, adapter.log_model}
    # 新的按成员 raw 表要挂到对应 adapter.member_raw_models，否则解绑 / 换号后还会展示旧账号
    assert sorted(m.__name__ for m in scoped - handled) == []


def test_unbind_removes_that_platforms_data_for_that_member_only(db) -> None:
    skland = get_checkin_adapters()["skland"]
    taygedo = get_checkin_adapters()["taygedo"]
    _seed(db, 1)
    _seed(db, 2)
    record_checkin_attempt("skland", 1, {("game", "1")}, now=now_beijing())
    record_checkin_attempt("taygedo", 1, {("game", "1")}, now=now_beijing())

    assert binding.unbind_member(skland, db, 1) is True

    db.expire_all()
    assert _count(db, skland.bind_model, 1) == 0
    assert _count(db, skland.log_model, 1) == 0
    assert _count(db, CheckinRolePref, 1, platform="skland") == 0
    for model in skland.member_raw_models:
        assert _count(db, model, 1) == 0, model.__name__
        assert _count(db, model, 2) == 1, model.__name__
    assert _count(db, skland.bind_model, 2) == 1
    assert _count(db, CheckinRolePref, 2, platform="skland") == 1
    assert _count(db, taygedo.bind_model, 1) == 1
    assert _count(db, CheckinRolePref, 1, platform="taygedo") == 1
    for model in taygedo.member_raw_models:
        assert _count(db, model, 1) == 1, model.__name__
    assert load_attempts("skland", 1, now=now_beijing()) == {}
    assert load_attempts("taygedo", 1, now=now_beijing()) != {}

    assert binding.unbind_member(skland, db, 1) is False


def test_unbind_skland_drops_cached_session_only_when_a_bind_existed(db, monkeypatch) -> None:
    from app.services.skland import checkin as skland_checkin
    from app.services.skland import session_cache

    invalidated: list[int] = []
    monkeypatch.setattr(session_cache, "invalidate_skland_session", invalidated.append)
    _seed(db, 1)
    member = db.get(Member, 1)

    skland_checkin.unbind_skland(db, member)
    skland_checkin.unbind_skland(db, member)

    assert invalidated == [1]


def _bind(db: Session, platform: str, member_id: int) -> Any:
    adapter = get_checkin_adapters()[platform]
    return db.query(adapter.bind_model).filter_by(member_id=member_id).one()


def _record_runs(monkeypatch) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []

    def fake_run(adapter, db, bind, **kwargs):
        runs.append({"platform": adapter.platform, "member_id": bind.member_id, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(binding, "run_checkin_for_bind", fake_run)
    return runs


def test_after_bind_drops_old_account_raws_and_attempts_but_keeps_prefs(db, monkeypatch) -> None:
    skland = get_checkin_adapters()["skland"]
    _seed(db, 1)
    _seed(db, 2)
    record_checkin_attempt("skland", 1, {("game", "1")}, now=now_beijing())
    runs = _record_runs(monkeypatch)

    binding.after_bind(skland, db, _bind(db, "skland", 1))

    for model in skland.member_raw_models:
        assert _count(db, model, 1) == 0, model.__name__
        assert _count(db, model, 2) == 1, model.__name__
    assert _count(db, skland.log_model, 1) == 1
    assert _count(db, CheckinRolePref, 1, platform="skland") == 1
    assert load_attempts("skland", 1, now=now_beijing()) == {}
    assert runs == []


def test_after_bind_checks_in_only_the_roles_with_auto_checkin_on(db, monkeypatch) -> None:
    skland = get_checkin_adapters()["skland"]
    _seed(db, 1, auto_checkin=True)
    db.add_all(
        [
            _row(
                CheckinRolePref,
                platform="skland",
                member_id=1,
                game_code="arknights",
                role_uid="on",
                included=True,
                enabled=True,
            ),
            _row(
                CheckinRolePref,
                platform="skland",
                member_id=1,
                game_code="arknights",
                role_uid="joined-only",
                included=True,
                enabled=False,
            ),
        ]
    )
    db.commit()
    runs = _record_runs(monkeypatch)

    binding.after_bind(skland, db, _bind(db, "skland", 1))

    assert runs == [
        {
            "platform": "skland",
            "member_id": 1,
            "force": False,
            "role_keys": {("arknights", "on")},
        }
    ]


def test_after_bind_legacy_bind_without_prefs_checks_in_every_role(db, monkeypatch) -> None:
    skland = get_checkin_adapters()["skland"]
    _seed(db, 1, auto_checkin=True)
    db.query(CheckinRolePref).delete()
    db.commit()
    runs = _record_runs(monkeypatch)

    binding.after_bind(skland, db, _bind(db, "skland", 1))

    assert [r["role_keys"] for r in runs] == [None]


def test_after_bind_survives_a_failed_checkin(db, monkeypatch) -> None:
    skland = get_checkin_adapters()["skland"]
    _seed(db, 1, auto_checkin=True)
    db.query(CheckinRolePref).delete()
    db.commit()

    def boom(*_a, **_k):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(binding, "run_checkin_for_bind", boom)
    bind = _bind(db, "skland", 1)

    binding.after_bind(skland, db, bind)

    assert bind.auto_checkin is True
