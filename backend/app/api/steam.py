from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas import (
    MemberPlayStatsResponse,
    SteamCalendarResponse,
    SteamDayResponse,
    SteamNowItem,
    SteamOverviewResponse,
    SteamPollResult,
)
from app.services.steam_poller import run_steam_presence_poll
from app.services.steam_stats import (
    build_calendar,
    build_day_detail,
    build_member_play_stats,
    build_overview,
    list_now_playing,
)

router = APIRouter(prefix="/steam", tags=["steam"])


@router.get("/overview", response_model=SteamOverviewResponse)
def steam_overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return build_overview(db)


@router.get("/members/{member_id}", response_model=MemberPlayStatsResponse)
def steam_member_stats(
    member_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    data = build_member_play_stats(db, member_id)
    if not data:
        raise HTTPException(status_code=404, detail="成员不存在")
    return data


@router.get("/calendar", response_model=SteamCalendarResponse)
def steam_calendar(
    granularity: str = Query("month", pattern="^(day|week|month|year)$"),
    date_str: str = Query(..., alias="date", description="锚点日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        anchor = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD") from exc
    try:
        return build_calendar(db, granularity, anchor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/day", response_model=SteamDayResponse)
def steam_day(
    date_str: str = Query(..., alias="date", description="日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        d = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD") from exc
    return build_day_detail(db, d)


@router.get("/now", response_model=list[SteamNowItem])
def steam_now(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    return list_now_playing(db)


@router.post("/poll", response_model=SteamPollResult)
def steam_poll(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    return run_steam_presence_poll(db)
