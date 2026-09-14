"""塔科夫个人资料：阵营 / 版本 / 角色等级 / 商人好感，按 PVP/PVE 分开。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserProfile
from app.models.user import User
from app.services.tarkov.game_mode import current_game_mode, parse_game_mode
from app.services.tarkov.hideout_progress import (
    EDITION_EOD,
    EDITION_STANDARD,
    parse_game_edition,
    stash_floor_for_edition,
)
from app.services.tarkov.traders import TRADER_SLUG_ORDER

FACTIONS = frozenset({"bear", "usec"})
PLAYER_LEVEL_MIN = 1
PLAYER_LEVEL_MAX = 79
TRADER_LEVEL_MIN = 1
TRADER_LEVEL_MAX = 4
SKIP_TRADER_SLUGS = frozenset({"btr-driver"})
PROFILE_TRADER_SLUGS = tuple(
    slug for slug in TRADER_SLUG_ORDER if slug not in SKIP_TRADER_SLUGS
)


class TarkovProfileError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _mode(game_mode: str | None = None) -> str:
    return parse_game_mode(game_mode) if game_mode is not None else current_game_mode()


def parse_edition_input(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if text in ("", EDITION_STANDARD, "white", "std"):
        return EDITION_STANDARD
    if text in (EDITION_EOD, "edge", "blue"):
        return EDITION_EOD
    raise TarkovProfileError("游戏版本无效")


def parse_faction(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return ""
    if text not in FACTIONS:
        raise TarkovProfileError("阵营无效")
    return text


def parse_player_level(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise TarkovProfileError("角色等级无效") from exc
    if value < PLAYER_LEVEL_MIN or value > PLAYER_LEVEL_MAX:
        raise TarkovProfileError("角色等级无效")
    return value


def parse_trader_level(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise TarkovProfileError("商人好感无效") from exc
    if value < TRADER_LEVEL_MIN or value > TRADER_LEVEL_MAX:
        raise TarkovProfileError("商人好感无效")
    return value


def _known_trader(slug: str) -> bool:
    return slug in PROFILE_TRADER_SLUGS


def normalize_trader_levels(raw: Any, existing: dict[str, int] | None = None) -> dict[str, int]:
    out = dict(existing or {})
    if raw is None:
        return out
    if not isinstance(raw, dict):
        raise TarkovProfileError("商人好感格式无效")
    for key, value in raw.items():
        slug = str(key or "").strip().lower()
        if not slug or not _known_trader(slug):
            continue
        out[slug] = parse_trader_level(value)
    return out


def empty_profile(game_mode: str) -> dict[str, Any]:
    return {
        "pmc_faction": "",
        "game_edition": EDITION_STANDARD,
        "player_level": PLAYER_LEVEL_MIN,
        "trader_levels": {},
        "game_mode": game_mode,
    }


def serialize_row(row: TarkovUserProfile) -> dict[str, Any]:
    traders = normalize_trader_levels(row.trader_levels, {})
    return {
        "pmc_faction": parse_faction(row.pmc_faction) if row.pmc_faction else "",
        "game_edition": parse_game_edition(row.game_edition),
        "player_level": parse_player_level(row.player_level or PLAYER_LEVEL_MIN),
        "trader_levels": traders,
        "game_mode": str(row.game_mode or "pvp"),
    }


def _row(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> TarkovUserProfile | None:
    mode = _mode(game_mode)
    return (
        db.query(TarkovUserProfile)
        .filter(
            TarkovUserProfile.user_id == user_id,
            TarkovUserProfile.game_mode == mode,
        )
        .one_or_none()
    )


def get_edition(db: Session, user_id: int, *, game_mode: str | None = None) -> str:
    row = _row(db, user_id, game_mode=game_mode)
    if row is None:
        return EDITION_STANDARD
    return parse_game_edition(row.game_edition)


def get_stash_floor(db: Session, user_id: int, *, game_mode: str | None = None) -> int:
    return stash_floor_for_edition(get_edition(db, user_id, game_mode=game_mode))


def get_profile(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    mode = _mode(game_mode)
    row = _row(db, user_id, game_mode=mode)
    if row is None:
        return empty_profile(mode)
    return serialize_row(row)


def _ensure_row(
    db: Session,
    user: User,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> TarkovUserProfile:
    mode = _mode(game_mode)
    row = _row(db, user.id, game_mode=mode)
    if row is not None:
        return row
    stamp = now or now_naive()
    row = TarkovUserProfile(
        user_id=user.id,
        game_mode=mode,
        pmc_faction="",
        game_edition=EDITION_STANDARD,
        player_level=PLAYER_LEVEL_MIN,
        trader_levels={},
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    return row


def update_profile(
    db: Session,
    user: User,
    patch: dict[str, Any],
    stations: list[dict[str, Any]] | None,
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    from app.services.tarkov import hideout_levels as hideout_levels_svc

    mode = _mode(game_mode)
    stamp = now_naive()
    row = _ensure_row(db, user, game_mode=mode, now=stamp)
    if "pmc_faction" in patch and patch["pmc_faction"] is not None:
        row.pmc_faction = parse_faction(patch["pmc_faction"])
    if "game_edition" in patch and patch["game_edition"] is not None:
        row.game_edition = parse_edition_input(patch["game_edition"])
    if "player_level" in patch and patch["player_level"] is not None:
        row.player_level = parse_player_level(patch["player_level"])
    if "trader_levels" in patch and patch["trader_levels"] is not None:
        row.trader_levels = normalize_trader_levels(
            patch["trader_levels"],
            normalize_trader_levels(row.trader_levels, {}),
        )
    row.updated_at = stamp
    if parse_game_edition(row.game_edition) != EDITION_STANDARD:
        hideout_levels_svc.ensure_stash_floor(
            db, user, stations, game_mode=mode
        )
    return serialize_row(row)
