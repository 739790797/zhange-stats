"""今日签到 logs upsert：和并发写入（打开页查询 / 调度签到）撞上唯一键时合并，不报错。"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.models.member import Member
from app.models.skland import SklandBind, SklandCheckinLog
from app.services.checkin.common import (
    LOG_SOURCE_ACTION,
    LOG_SOURCE_STATUS,
    CheckinResult,
    upsert_day_checkin_logs,
)

DAY = date(2026, 10, 10)
NOW = datetime(2026, 10, 10, 8, 0)


@pytest.fixture
def make_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'logs.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        db.add(Member(id=1, nickname="m1"))
        db.add(SklandBind(id=1, member_id=1, token_enc="x"))
        db.commit()
    yield factory
    engine.dispose()


def _result(role_uid: str, status: str, **kw) -> CheckinResult:
    return CheckinResult(
        game_code="arknights",
        game_name="明日方舟",
        role_uid=role_uid,
        role_name="r",
        channel_name="官服",
        status=status,
        message=kw.pop("message", ""),
        **kw,
    )


def _log(role_uid: str, status: str, **kw) -> SklandCheckinLog:
    return SklandCheckinLog(
        member_id=1,
        bind_id=1,
        game_code="arknights",
        game_name="明日方舟",
        role_uid=role_uid,
        status=status,
        checkin_date=DAY,
        checked_at=NOW,
        **kw,
    )


def _upsert(db, results, *, source=LOG_SOURCE_STATUS) -> None:
    upsert_day_checkin_logs(
        db,
        SklandCheckinLog,
        member_id=1,
        bind_id=1,
        checkin_date=DAY,
        results=results,
        now=NOW,
        source=source,
    )


def test_insert_that_loses_the_race_merges_into_the_winning_row(make_session) -> None:
    with make_session() as seed:
        seed.add(_log("existing", "pending", message="今日尚未签到"))
        seed.commit()

    db = make_session()
    engine = db.get_bind()
    state = {"looked_up": False, "fired": False}

    def scheduler_commits_in_between(conn, cursor, statement, parameters, context, executemany):
        # 打开页查到「无记录」之后、它下一条语句之前，调度签到先落了同一角色的执行记录
        # （SQLite 单写者：必须赶在这边第一条写语句拿锁之前）
        if state["fired"]:
            return
        if state["looked_up"]:
            state["fired"] = True
            with make_session() as other:
                other.add(
                    _log(
                        "raced",
                        "ok",
                        message="合成玉x80",
                        awards_text="合成玉x80",
                        source=LOG_SOURCE_ACTION,
                    )
                )
                other.commit()
        elif statement.lstrip().upper().startswith("SELECT") and "raced" in tuple(parameters or ()):
            state["looked_up"] = True

    event.listen(engine, "before_cursor_execute", scheduler_commits_in_between)
    try:
        _upsert(
            db,
            [
                _result("existing", "already", message="今日已签到"),
                _result("raced", "pending", message="今日尚未签到"),
            ],
        )
        db.commit()
    finally:
        event.remove(engine, "before_cursor_execute", scheduler_commits_in_between)
        db.close()
    assert state["fired"]

    with make_session() as check:
        rows = {r.role_uid: r for r in check.query(SklandCheckinLog).all()}
    assert sorted(rows) == ["existing", "raced"]
    # 同一事务里先改的行不能被 savepoint 回滚连带丢掉
    assert (rows["existing"].status, rows["existing"].message) == ("already", "今日已签到")
    # 查询态不把调度刚签成功的行降级，执行记录也不改回「仅查询」
    raced = rows["raced"]
    assert (raced.status, raced.awards_text, raced.source) == ("ok", "合成玉x80", LOG_SOURCE_ACTION)


def test_same_role_twice_in_one_batch_updates_one_row(make_session) -> None:
    with make_session() as db:
        _upsert(
            db,
            [
                _result("1", "pending", message="今日尚未签到"),
                _result("1", "ok", message="签到成功", awards_text="合成玉x80"),
            ],
            source=LOG_SOURCE_ACTION,
        )
        db.commit()
        rows = db.query(SklandCheckinLog).all()

    assert [(r.role_uid, r.status, r.awards_text) for r in rows] == [("1", "ok", "合成玉x80")]
