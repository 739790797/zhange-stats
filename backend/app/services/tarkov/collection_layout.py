"""塔科夫用户 3×4 收集摆放：按 PVP/PVE 分开，改格子即覆盖写入。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import (
    TarkovUserCollectionLayout,
    TarkovUserCollectionPlacement,
)
from app.models.user import User
from app.services.tarkov import collection_owns as owns
from app.services.tarkov.game_mode import current_game_mode, parse_game_mode

GRID_MAX = 14
PLACEMENT_MAX = owns.MERGE_MAX


class TarkovCollectionLayoutError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _mode(game_mode: str | None = None) -> str:
    return parse_game_mode(game_mode) if game_mode is not None else current_game_mode()


def _as_int(value: Any, fallback: int = -1) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number


def _placement_out(row: TarkovUserCollectionPlacement) -> dict[str, Any]:
    return {
        "item_id": str(row.item_id),
        "col": int(row.col),
        "row": int(row.row),
        "rotated": bool(row.rotated),
    }


def sanitize_placements(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            ident = owns.normalize_item_id(
                str(item.get("item_id") or item.get("itemId") or "")
            )
        except owns.TarkovCollectionOwnsError:
            continue
        if ident in seen:
            continue
        col = _as_int(item.get("col"), -1)
        row = _as_int(item.get("row"), -1)
        if col < 0 or row < 0 or col >= GRID_MAX or row >= GRID_MAX:
            continue
        seen.add(ident)
        out.append(
            {
                "item_id": ident,
                "col": col,
                "row": row,
                "rotated": bool(item.get("rotated")),
            }
        )
        if len(out) >= PLACEMENT_MAX:
            break
    return out


def has_saved_layout(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> bool:
    mode = _mode(game_mode)
    if (
        db.query(TarkovUserCollectionLayout)
        .filter(
            TarkovUserCollectionLayout.user_id == user_id,
            TarkovUserCollectionLayout.game_mode == mode,
        )
        .first()
        is not None
    ):
        return True
    return (
        db.query(TarkovUserCollectionPlacement)
        .filter(
            TarkovUserCollectionPlacement.user_id == user_id,
            TarkovUserCollectionPlacement.game_mode == mode,
        )
        .first()
        is not None
    )


def mark_saved_layout(
    db: Session,
    user: User,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> None:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    row = (
        db.query(TarkovUserCollectionLayout)
        .filter(
            TarkovUserCollectionLayout.user_id == user.id,
            TarkovUserCollectionLayout.game_mode == mode,
        )
        .one_or_none()
    )
    if row is None:
        db.add(
            TarkovUserCollectionLayout(
                user_id=user.id,
                game_mode=mode,
                updated_at=stamp,
            )
        )
        return
    row.updated_at = stamp


def get_layout(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    return {
        "placements": list_placements(db, user_id, game_mode=game_mode),
        "saved": has_saved_layout(db, user_id, game_mode=game_mode),
    }


def list_placements(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[dict[str, Any]]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserCollectionPlacement)
        .filter(
            TarkovUserCollectionPlacement.user_id == user_id,
            TarkovUserCollectionPlacement.game_mode == mode,
        )
        .order_by(
            TarkovUserCollectionPlacement.row.asc(),
            TarkovUserCollectionPlacement.col.asc(),
            TarkovUserCollectionPlacement.item_id.asc(),
        )
        .all()
    )
    return [_placement_out(row) for row in rows]


def replace_layout(
    db: Session,
    user: User,
    placements: Any,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    incoming = sanitize_placements(placements)
    rows = (
        db.query(TarkovUserCollectionPlacement)
        .filter(
            TarkovUserCollectionPlacement.user_id == user.id,
            TarkovUserCollectionPlacement.game_mode == mode,
        )
        .all()
    )
    have = {str(row.item_id): row for row in rows}
    want = {row["item_id"] for row in incoming}
    for ident, row in have.items():
        if ident not in want:
            db.delete(row)
    for item in incoming:
        ident = item["item_id"]
        current = have.get(ident)
        if current is None:
            db.add(
                TarkovUserCollectionPlacement(
                    user_id=user.id,
                    game_mode=mode,
                    item_id=ident,
                    col=item["col"],
                    row=item["row"],
                    rotated=item["rotated"],
                    updated_at=stamp,
                )
            )
            continue
        current.col = item["col"]
        current.row = item["row"]
        current.rotated = item["rotated"]
        current.updated_at = stamp
    owns.replace_owns(
        db,
        user,
        [row["item_id"] for row in incoming],
        game_mode=mode,
        now=stamp,
    )
    mark_saved_layout(db, user, game_mode=mode, now=stamp)
    db.flush()
    return get_layout(db, user.id, game_mode=mode)
