"""塔科夫用户钥匙拥有：账号级勾选，供分类速查与准备总结。"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserKeyOwn
from app.models.user import User

ITEM_ID_MAX = 64
MERGE_MAX = 400
OWNS_MAX = 1500
UNKNOWN_KEY_MSG = "不在钥匙目录里，不能记为拥有"
CATALOG_UNAVAILABLE_MSG = "钥匙目录暂时不可用，请稍后再试"


class TarkovKeyOwnsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_item_id(raw: str | None) -> str:
    ident = str(raw or "").strip()
    if not ident or len(ident) > ITEM_ID_MAX:
        raise TarkovKeyOwnsError("钥匙 id 无效")
    return ident


def _known_key_ids(db: Session) -> frozenset[str]:
    from app.services.tarkov.key_packs import known_key_ids

    known = known_key_ids(db)
    if not known:
        raise TarkovKeyOwnsError(CATALOG_UNAVAILABLE_MSG, 503)
    return known


def _own_count(db: Session, user_id: int) -> int:
    return int(
        db.query(func.count(TarkovUserKeyOwn.item_id))
        .filter(TarkovUserKeyOwn.user_id == user_id)
        .scalar()
        or 0
    )


def list_item_ids(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(TarkovUserKeyOwn.item_id)
        .filter(TarkovUserKeyOwn.user_id == user_id)
        .order_by(TarkovUserKeyOwn.created_at.asc(), TarkovUserKeyOwn.item_id.asc())
        .all()
    )
    return [str(row[0]) for row in rows]


def list_owns_for_users(
    db: Session,
    user_ids: list[int] | set[int],
    *,
    item_ids: Collection[str] | None = None,
) -> list[TarkovUserKeyOwn]:
    """item_ids 给出时只取这些钥匙；空集合直接返回空。"""
    ids = sorted({int(uid) for uid in user_ids if uid is not None})
    if not ids or (item_ids is not None and not item_ids):
        return []
    query = db.query(TarkovUserKeyOwn).filter(TarkovUserKeyOwn.user_id.in_(ids))
    if item_ids is not None:
        query = query.filter(TarkovUserKeyOwn.item_id.in_(sorted(item_ids)))
    return (
        query.order_by(
            TarkovUserKeyOwn.created_at.asc(),
            TarkovUserKeyOwn.user_id.asc(),
            TarkovUserKeyOwn.item_id.asc(),
        )
        .all()
    )


def add_own(
    db: Session,
    user: User,
    item_id: str,
    *,
    now: datetime | None = None,
) -> tuple[list[str], bool]:
    ident = normalize_item_id(item_id)
    existing = (
        db.query(TarkovUserKeyOwn)
        .filter(
            TarkovUserKeyOwn.user_id == user.id,
            TarkovUserKeyOwn.item_id == ident,
        )
        .one_or_none()
    )
    added = False
    if existing is None:
        if ident not in _known_key_ids(db):
            raise TarkovKeyOwnsError(UNKNOWN_KEY_MSG)
        if _own_count(db, user.id) >= OWNS_MAX:
            raise TarkovKeyOwnsError(f"最多记录 {OWNS_MAX} 把钥匙", 409)
        db.add(
            TarkovUserKeyOwn(
                user_id=user.id,
                item_id=ident,
                created_at=now or now_naive(),
            )
        )
        db.flush()
        added = True
    return list_item_ids(db, user.id), added


def remove_own(db: Session, user: User, item_id: str) -> tuple[list[str], bool]:
    ident = normalize_item_id(item_id)
    row = (
        db.query(TarkovUserKeyOwn)
        .filter(
            TarkovUserKeyOwn.user_id == user.id,
            TarkovUserKeyOwn.item_id == ident,
        )
        .one_or_none()
    )
    removed = False
    if row is not None:
        db.delete(row)
        db.flush()
        removed = True
    return list_item_ids(db, user.id), removed


def merge_owns(
    db: Session,
    user: User,
    item_ids: list[Any],
    *,
    now: datetime | None = None,
) -> list[str]:
    """目录外的 id 直接丢掉；加满 OWNS_MAX 后其余不再写入。"""
    stamp = now or now_naive()
    known = _known_key_ids(db)
    seen: set[str] = set()
    incoming: list[str] = []
    for raw in item_ids or []:
        try:
            ident = normalize_item_id(str(raw) if raw is not None else "")
        except TarkovKeyOwnsError:
            continue
        if ident in seen or ident not in known:
            continue
        seen.add(ident)
        incoming.append(ident)
        if len(incoming) >= MERGE_MAX:
            break
    have = set(list_item_ids(db, user.id))
    room = OWNS_MAX - len(have)
    for ident in incoming:
        if ident in have:
            continue
        if room <= 0:
            break
        room -= 1
        db.add(
            TarkovUserKeyOwn(
                user_id=user.id,
                item_id=ident,
                created_at=stamp,
            )
        )
        have.add(ident)
    db.flush()
    return list_item_ids(db, user.id)
