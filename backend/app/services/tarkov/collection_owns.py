"""塔科夫用户 3×4 收集勾选：按 PVP/PVE 分开，供个人中心收集格子。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserCollectionOwn
from app.models.user import User
from app.services.tarkov.game_mode import current_game_mode, parse_game_mode

ITEM_ID_MAX = 64
MERGE_MAX = 200


class TarkovCollectionOwnsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_item_id(raw: str | None) -> str:
    ident = str(raw or "").strip()
    if not ident or len(ident) > ITEM_ID_MAX:
        raise TarkovCollectionOwnsError("收集道具 id 无效")
    return ident


def _mode(game_mode: str | None = None) -> str:
    return parse_game_mode(game_mode) if game_mode is not None else current_game_mode()


def list_item_ids(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserCollectionOwn.item_id)
        .filter(
            TarkovUserCollectionOwn.user_id == user_id,
            TarkovUserCollectionOwn.game_mode == mode,
        )
        .order_by(
            TarkovUserCollectionOwn.created_at.asc(),
            TarkovUserCollectionOwn.item_id.asc(),
        )
        .all()
    )
    return [str(row[0]) for row in rows]


def add_own(
    db: Session,
    user: User,
    item_id: str,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> tuple[list[str], bool]:
    ident = normalize_item_id(item_id)
    mode = _mode(game_mode)
    existing = (
        db.query(TarkovUserCollectionOwn)
        .filter(
            TarkovUserCollectionOwn.user_id == user.id,
            TarkovUserCollectionOwn.game_mode == mode,
            TarkovUserCollectionOwn.item_id == ident,
        )
        .one_or_none()
    )
    added = False
    if existing is None:
        db.add(
            TarkovUserCollectionOwn(
                user_id=user.id,
                game_mode=mode,
                item_id=ident,
                created_at=now or now_naive(),
            )
        )
        db.flush()
        added = True
    return list_item_ids(db, user.id, game_mode=mode), added


def remove_own(
    db: Session,
    user: User,
    item_id: str,
    *,
    game_mode: str | None = None,
) -> tuple[list[str], bool]:
    ident = normalize_item_id(item_id)
    mode = _mode(game_mode)
    row = (
        db.query(TarkovUserCollectionOwn)
        .filter(
            TarkovUserCollectionOwn.user_id == user.id,
            TarkovUserCollectionOwn.game_mode == mode,
            TarkovUserCollectionOwn.item_id == ident,
        )
        .one_or_none()
    )
    removed = False
    if row is not None:
        db.delete(row)
        db.flush()
        removed = True
    return list_item_ids(db, user.id, game_mode=mode), removed


def merge_owns(
    db: Session,
    user: User,
    item_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    seen: set[str] = set()
    incoming: list[str] = []
    for raw in item_ids or []:
        try:
            ident = normalize_item_id(str(raw) if raw is not None else "")
        except TarkovCollectionOwnsError:
            continue
        if ident in seen:
            continue
        seen.add(ident)
        incoming.append(ident)
        if len(incoming) >= MERGE_MAX:
            break
    have = set(list_item_ids(db, user.id, game_mode=mode))
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserCollectionOwn(
                user_id=user.id,
                game_mode=mode,
                item_id=ident,
                created_at=stamp,
            )
        )
        have.add(ident)
    db.flush()
    return list_item_ids(db, user.id, game_mode=mode)


def replace_owns(
    db: Session,
    user: User,
    item_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    seen: set[str] = set()
    incoming: list[str] = []
    for raw in item_ids or []:
        try:
            ident = normalize_item_id(str(raw) if raw is not None else "")
        except TarkovCollectionOwnsError:
            continue
        if ident in seen:
            continue
        seen.add(ident)
        incoming.append(ident)
        if len(incoming) >= MERGE_MAX:
            break
    rows = (
        db.query(TarkovUserCollectionOwn)
        .filter(
            TarkovUserCollectionOwn.user_id == user.id,
            TarkovUserCollectionOwn.game_mode == mode,
        )
        .all()
    )
    have = {str(row.item_id): row for row in rows}
    want = set(incoming)
    for ident, row in have.items():
        if ident not in want:
            db.delete(row)
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserCollectionOwn(
                user_id=user.id,
                game_mode=mode,
                item_id=ident,
                created_at=stamp,
            )
        )
    db.flush()
    return list_item_ids(db, user.id, game_mode=mode)
