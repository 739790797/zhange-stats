"""塔科夫用户任务完成：按 PVP/PVE 勾选，供个人中心任务树。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserTaskDone
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


def _incoming_ids(task_ids: list[Any]) -> list[str]:
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
    return list_task_ids(db, user.id, game_mode=mode)
