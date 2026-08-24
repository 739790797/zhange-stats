"""森空岛页：活动日历（代理 game-schedule）。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.platform_features import is_feature_enabled
from app.schemas import GameScheduleCalendarOut, GameScheduleEventOut
from app.services.game_schedule import GameScheduleError, get_game_events

router = APIRouter(tags=["skland"])

GameQuery = Literal["arknights", "endfield"]

_GAME_FEATURE: dict[GameQuery, str] = {
    "arknights": "skland.arknights",
    "endfield": "skland.endfield",
}


@router.get("/game-events", response_model=GameScheduleCalendarOut)
def skland_game_events(
    _user: User = Depends(get_current_user),
    game: GameQuery = Query(..., description="arknights | endfield"),
    force: bool = Query(default=False),
    include_ended: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """明日方舟 / 终末地活动日历（game-schedule 上游）；默认读缓存，force 回源。"""
    feature = _GAME_FEATURE[game]
    if not is_feature_enabled(db, feature):
        raise HTTPException(status_code=403, detail="该功能未启用")

    try:
        data = get_game_events(
            db, game, force=force, include_ended=include_ended
        )
    except GameScheduleError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return GameScheduleCalendarOut(
        game=str(data.get("game") or game),
        source=str(data.get("source") or "game-schedule"),
        synced_at=data.get("synced_at"),
        stale=bool(data.get("stale")),
        ongoing_count=int(data.get("ongoing_count") or 0),
        upcoming_count=int(data.get("upcoming_count") or 0),
        permanent_count=int(data.get("permanent_count") or 0),
        events=[
            GameScheduleEventOut(**e)
            for e in (data.get("events") or [])
            if isinstance(e, dict)
        ],
        permanent_events=[
            GameScheduleEventOut(**e)
            for e in (data.get("permanent_events") or [])
            if isinstance(e, dict)
        ],
    )
