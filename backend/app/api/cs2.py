from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas import (
    Cs2MatchOut,
    Cs2OverviewResponse,
    Cs2SyncResult,
    Cs2TogetherMatchOut,
)
from app.services.cs2_match_query import list_my_matches, list_together_matches
from app.services.cs2_match_sync import run_cs2_match_sync
from app.services.cs2_stats import build_cs2_overview

router = APIRouter(prefix="/cs2", tags=["cs2"])


@router.get("/overview", response_model=Cs2OverviewResponse)
def cs2_overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """圈子成员 CS2 Steam 生涯统计。"""
    return build_cs2_overview(db)


@router.get("/matches/me", response_model=list[Cs2MatchOut])
def cs2_my_matches(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return list_my_matches(db, user, limit=limit)


@router.get("/matches/together", response_model=list[Cs2TogetherMatchOut])
def cs2_together_matches(
    member_ids: str = Query(..., description="逗号分隔的成员 ID，须含自己或会自动并入"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    try:
        ids = [int(x) for x in member_ids.split(",") if x.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="member_ids 格式无效") from exc
    try:
        return list_together_matches(db, user, ids, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync", response_model=Cs2SyncResult)
def cs2_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    return run_cs2_match_sync(db)
