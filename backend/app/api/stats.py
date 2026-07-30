from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas import LeaderboardResponse, MemberStatsResponse, OverviewResponse
from app.services import stats as stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewResponse)
def overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OverviewResponse:
    return stats_service.get_overview(db)


@router.get("/leaderboard", response_model=LeaderboardResponse)
def leaderboard(
    game_id: int | None = None,
    range: str = Query(default="all", pattern="^(week|month|all)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LeaderboardResponse:
    return stats_service.get_leaderboard(db, game_id=game_id, range_key=range)


@router.get("/member/{member_id}", response_model=MemberStatsResponse)
def member_stats(
    member_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MemberStatsResponse:
    result = stats_service.get_member_stats(db, member_id)
    if not result:
        raise HTTPException(status_code=404, detail="成员不存在")
    return result
