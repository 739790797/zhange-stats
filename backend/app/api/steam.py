from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.local_dev_hooks import import_steam_fake
from app.models.user import User
from app.schemas import (
    MemberPlayStatsResponse,
    SteamAppIcon,
    SteamAppStoreCard,
    SteamCalendarResponse,
    SteamDayResponse,
    SteamFriendsResponse,
    SteamNowItem,
    SteamOverviewResponse,
    SteamPollResult,
)
from app.services.steam_friends import list_viewer_steam_friends
from app.services.steam_game_names import get_store_card, resolve_app_icons
from app.services.steam_poller import run_steam_presence_poll
from app.services.steam_stats import (
    build_calendar,
    build_range_detail,
    build_member_play_stats,
    build_overview,
    list_now_playing,
)

router = APIRouter(prefix="/steam", tags=["steam"])


@router.get("/friends", response_model=SteamFriendsResponse)
def steam_friends(
    force: bool = Query(False, description="强制从 Steam 同步；默认受冷却间隔限制"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """当前用户的 Steam 好友列表。冷却期内打开页面用缓存，force=true 手动刷新。"""
    return list_viewer_steam_friends(db, user, force=force)


@router.get("/overview", response_model=SteamOverviewResponse)
def steam_overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return build_overview(db, user)


@router.get("/members/{member_id}", response_model=MemberPlayStatsResponse)
def steam_member_stats(
    member_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    data = build_member_play_stats(db, member_id, user)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="成员不存在，或对方不是你的 Steam 好友",
        )
    return data


@router.get("/calendar", response_model=SteamCalendarResponse)
def steam_calendar(
    granularity: str = Query("month", pattern="^(day|week|month|year)$"),
    date_str: str = Query(..., alias="date", description="锚点日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        anchor = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD") from exc
    return build_calendar(db, granularity, anchor, user)


@router.get("/day", response_model=SteamDayResponse)
def steam_day(
    date_str: str = Query(..., alias="date", description="起始日期 YYYY-MM-DD"),
    end_str: str | None = Query(
        None, alias="end", description="结束日期 YYYY-MM-DD；缺省则仅查询当日"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        start = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD") from exc
    end = start
    if end_str:
        try:
            end = date.fromisoformat(end_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="end 格式应为 YYYY-MM-DD"
            ) from exc
    try:
        return build_range_detail(db, start, end, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/now", response_model=list[SteamNowItem])
def steam_now(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return list_now_playing(db, user)


@router.get("/apps/{app_id}/icon", response_model=SteamAppIcon)
def steam_app_icon(
    app_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """单独补全库列表小图标（可慢）；时间轴热路径不阻塞此逻辑。"""
    app_id = (app_id or "").strip()
    if not app_id:
        raise HTTPException(status_code=400, detail="app_id 无效")
    icons = resolve_app_icons(db, [app_id], fetch_missing=True)
    return {"steam_app_id": app_id, "icon_url": icons.get(app_id)}


@router.get("/apps/{app_id}", response_model=SteamAppStoreCard)
def steam_app_store_card(
    app_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """商店悬停卡片：头图、简介、国区价格（含折扣）。"""
    data = get_store_card(db, app_id)
    if not data:
        raise HTTPException(status_code=404, detail="未找到该游戏的商店信息")
    return data


@router.post("/poll", response_model=SteamPollResult)
def steam_poll(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    if get_settings().STEAM_FAKE_POLL:
        steam_fake = import_steam_fake()
        if steam_fake is None:
            raise HTTPException(
                status_code=503,
                detail="STEAM_FAKE_POLL 已开启但 local_dev.steam_fake 不可用",
            )
        return steam_fake.run_fake_steam_presence_poll(db)
    return run_steam_presence_poll(db)
