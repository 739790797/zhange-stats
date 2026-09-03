"""塔科夫用户任务进度账：完成 / 进行中按 PVP/PVE 分开，供个人中心任务树。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserTaskDone, TarkovUserTaskStarted
from app.models.user import User
from app.services.tarkov.game_mode import current_game_mode, parse_game_mode

TASK_ID_MAX = 64
MERGE_MAX = 800


class TarkovTaskDonesError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_task_id(raw: str | None) -> str:
    ident = str(raw or "").strip()
    if not ident or len(ident) > TASK_ID_MAX:
        raise TarkovTaskDonesError("任务 id 无效")
    return ident


def _mode(game_mode: str | None = None) -> str:
    return parse_game_mode(game_mode) if game_mode is not None else current_game_mode()


def list_task_ids(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserTaskDone.task_id)
        .filter(
            TarkovUserTaskDone.user_id == user_id,
            TarkovUserTaskDone.game_mode == mode,
        )
        .order_by(TarkovUserTaskDone.created_at.asc(), TarkovUserTaskDone.task_id.asc())
        .all()
    )
    return [str(row[0]) for row in rows]


def list_started_ids(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserTaskStarted.task_id)
        .filter(
            TarkovUserTaskStarted.user_id == user_id,
            TarkovUserTaskStarted.game_mode == mode,
        )
        .order_by(
            TarkovUserTaskStarted.created_at.asc(),
            TarkovUserTaskStarted.task_id.asc(),
        )
        .all()
    )
    return [str(row[0]) for row in rows]


def list_progress(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> tuple[list[str], list[str]]:
    done = list_task_ids(db, user_id, game_mode=game_mode)
    done_set = set(done)
    started = [
        ident
        for ident in list_started_ids(db, user_id, game_mode=game_mode)
        if ident not in done_set
    ]
    return done, started


def filter_visible_progress(
    done: list[str],
    started: list[str],
    catalog: set[str] | None,
) -> tuple[list[str], list[str]]:
    """进度账是冗余 id 表。目录里没有的（overlay disabled 等）只隐藏、不删行。

    catalog 为 None 表示图鉴不可用，原样返回。
    """
    if catalog is None:
        return done, started
    return (
        [ident for ident in done if ident in catalog],
        [ident for ident in started if ident in catalog],
    )


def _started_rows(
    db: Session,
    user_id: int,
    mode: str,
) -> list[TarkovUserTaskStarted]:
    return (
        db.query(TarkovUserTaskStarted)
        .filter(
            TarkovUserTaskStarted.user_id == user_id,
            TarkovUserTaskStarted.game_mode == mode,
        )
        .all()
    )


def _drop_started(
    db: Session,
    user_id: int,
    mode: str,
    task_ids: set[str],
) -> None:
    if not task_ids:
        return
    for row in _started_rows(db, user_id, mode):
        if str(row.task_id) in task_ids:
            db.delete(row)


def add_done(
    db: Session,
    user: User,
    task_id: str,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> tuple[list[str], bool]:
    ident = normalize_task_id(task_id)
    mode = _mode(game_mode)
    existing = (
        db.query(TarkovUserTaskDone)
        .filter(
            TarkovUserTaskDone.user_id == user.id,
            TarkovUserTaskDone.game_mode == mode,
            TarkovUserTaskDone.task_id == ident,
        )
        .one_or_none()
    )
    added = False
    if existing is None:
        db.add(
            TarkovUserTaskDone(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=now or now_naive(),
            )
        )
        db.flush()
        added = True
    _drop_started(db, user.id, mode, {ident})
    db.flush()
    return list_task_ids(db, user.id, game_mode=mode), added


def remove_done(
    db: Session,
    user: User,
    task_id: str,
    *,
    game_mode: str | None = None,
) -> tuple[list[str], bool]:
    ident = normalize_task_id(task_id)
    mode = _mode(game_mode)
    row = (
        db.query(TarkovUserTaskDone)
        .filter(
            TarkovUserTaskDone.user_id == user.id,
            TarkovUserTaskDone.game_mode == mode,
            TarkovUserTaskDone.task_id == ident,
        )
        .one_or_none()
    )
    removed = False
    if row is not None:
        db.delete(row)
        db.flush()
        removed = True
    return list_task_ids(db, user.id, game_mode=mode), removed


def _incoming_ids(task_ids: list[Any] | None) -> list[str]:
    seen: set[str] = set()
    incoming: list[str] = []
    for raw in task_ids or []:
        try:
            ident = normalize_task_id(str(raw) if raw is not None else "")
        except TarkovTaskDonesError:
            continue
        if ident in seen:
            continue
        seen.add(ident)
        incoming.append(ident)
        if len(incoming) >= MERGE_MAX:
            break
    return incoming


def merge_dones(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    incoming = _incoming_ids(task_ids)
    have = set(list_task_ids(db, user.id, game_mode=mode))
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskDone(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
        have.add(ident)
    db.flush()
    _drop_started(db, user.id, mode, have)
    db.flush()
    return list_task_ids(db, user.id, game_mode=mode)


def replace_dones(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    incoming = _incoming_ids(task_ids)
    wanted = set(incoming)
    rows = (
        db.query(TarkovUserTaskDone)
        .filter(
            TarkovUserTaskDone.user_id == user.id,
            TarkovUserTaskDone.game_mode == mode,
        )
        .all()
    )
    have = {str(row.task_id) for row in rows}
    for row in rows:
        if str(row.task_id) not in wanted:
            db.delete(row)
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskDone(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
    db.flush()
    _drop_started(db, user.id, mode, wanted)
    db.flush()
    return list_task_ids(db, user.id, game_mode=mode)


def merge_starteds(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    done = set(list_task_ids(db, user.id, game_mode=mode))
    incoming = [ident for ident in _incoming_ids(task_ids) if ident not in done]
    have = set(list_started_ids(db, user.id, game_mode=mode))
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskStarted(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
        have.add(ident)
    db.flush()
    _done, started = list_progress(db, user.id, game_mode=mode)
    return started


def replace_starteds(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    done = set(list_task_ids(db, user.id, game_mode=mode))
    incoming = [ident for ident in _incoming_ids(task_ids) if ident not in done]
    wanted = set(incoming)
    rows = _started_rows(db, user.id, mode)
    have = {str(row.task_id) for row in rows}
    for row in rows:
        if str(row.task_id) not in wanted:
            db.delete(row)
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskStarted(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
    db.flush()
    _done, started = list_progress(db, user.id, game_mode=mode)
    return started


def write_progress(
    db: Session,
    user: User,
    task_ids: list[Any],
    started_ids: list[Any] | None,
    *,
    replace: bool,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> tuple[list[str], list[str]]:
    if replace:
        replace_dones(db, user, task_ids, game_mode=game_mode, now=now)
        if started_ids is not None:
            replace_starteds(db, user, started_ids, game_mode=game_mode, now=now)
    else:
        merge_dones(db, user, task_ids, game_mode=game_mode, now=now)
        if started_ids is not None:
            merge_starteds(db, user, started_ids, game_mode=game_mode, now=now)
    return list_progress(db, user.id, game_mode=game_mode)
