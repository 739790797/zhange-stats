"""塔科夫用户藏身处等级：按 PVP/PVE 分开，供个人中心规划器。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserHideoutLevel
from app.models.user import User
from app.services.tarkov.game_mode import current_game_mode, parse_game_mode
from app.services.tarkov.hideout_progress import (
    STATION_ID_MAX,
    apply_level,
    default_level,
    filled_levels,
)


class TarkovHideoutLevelsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _mode(game_mode: str | None = None) -> str:
    return parse_game_mode(game_mode) if game_mode is not None else current_game_mode()


def normalize_station_id(raw: str | None) -> str:
    ident = str(raw or "").strip()
    if not ident or len(ident) > STATION_ID_MAX:
        raise TarkovHideoutLevelsError("藏身处模块 id 无效")
    return ident


def _stored_map(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> dict[str, int]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserHideoutLevel)
        .filter(
            TarkovUserHideoutLevel.user_id == user_id,
            TarkovUserHideoutLevel.game_mode == mode,
        )
        .all()
    )
    out: dict[str, int] = {}
    for row in rows:
        ident = str(row.station_id or "").strip()
        if ident:
            out[ident] = int(row.level or 0)
    return out


def list_levels(
    db: Session,
    user_id: int,
    stations: list[dict[str, Any]] | None,
    *,
    game_mode: str | None = None,
) -> list[dict[str, Any]]:
    filled = filled_levels(stations, _stored_map(db, user_id, game_mode=game_mode))
    return [
        {"station_id": ident, "level": level}
        for ident, level in sorted(filled.items(), key=lambda item: item[0])
    ]


def _persist(
    db: Session,
    user: User,
    stations: list[dict[str, Any]] | None,
    filled: dict[str, int],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    existing = {
        str(row.station_id): row
        for row in db.query(TarkovUserHideoutLevel)
        .filter(
            TarkovUserHideoutLevel.user_id == user.id,
            TarkovUserHideoutLevel.game_mode == mode,
        )
        .all()
    }
    by_id = {str(row.get("id") or ""): row for row in (stations or []) if row.get("id")}
    keep: set[str] = set()
    for ident, level in filled.items():
        station = by_id.get(ident)
        if station is None:
            continue
        if int(level) == default_level(station):
            continue
        keep.add(ident)
        row = existing.get(ident)
        if row is None:
            db.add(
                TarkovUserHideoutLevel(
                    user_id=user.id,
                    game_mode=mode,
                    station_id=ident,
                    level=int(level),
                    updated_at=stamp,
                )
            )
        elif int(row.level) != int(level):
            row.level = int(level)
            row.updated_at = stamp
    for ident, row in existing.items():
        if ident not in keep:
            db.delete(row)
    return [
        {"station_id": ident, "level": level}
        for ident, level in sorted(filled.items(), key=lambda item: item[0])
    ]


def set_level(
    db: Session,
    user: User,
    stations: list[dict[str, Any]] | None,
    station_id: str,
    level: int,
    *,
    game_mode: str | None = None,
) -> list[dict[str, Any]]:
    ident = normalize_station_id(station_id)
    stored = _stored_map(db, user.id, game_mode=game_mode)
    try:
        filled = apply_level(stations, stored, ident, level)
    except ValueError as exc:
        raise TarkovHideoutLevelsError(str(exc)) from exc
    return _persist(db, user, stations, filled, game_mode=game_mode)
