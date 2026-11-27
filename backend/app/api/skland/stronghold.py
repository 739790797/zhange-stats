"""Logged-in Stronghold community and authenticated role sync."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_user_member
from app.core.platform_deps import require_feature
from app.core.rate_limit import platform_limiter
from app.models.member import Member
from app.models.user import User
from app.schemas.stronghold import (
    StrongholdCommunityOut,
    StrongholdCommunityResult,
    StrongholdHistoryOut,
    StrongholdMatchOut,
    StrongholdMode,
    StrongholdOwnOut,
    StrongholdRecordDetailOut,
    StrongholdResult,
    StrongholdScopeId,
    StrongholdSyncIn,
    StrongholdSyncStatus,
)
from app.services.skland import stronghold, stronghold_sync as sync_service
from app.services.skland.stronghold import StrongholdError
from app.services.skland.stronghold_resources import archive_path, archived_content_type


_PRIVATE = {"Cache-Control": "private, no-store"}


def _private_response(response: Response) -> None:
    response.headers.update(_PRIVATE)


def _error(exc: StrongholdError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc), headers=_PRIVATE)


router = APIRouter(
    prefix="/arknights/stronghold",
    dependencies=[Depends(require_feature("skland.arknights.stronghold")), Depends(_private_response)],
)

ReportId = Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")]
_VERSION_KEY = r"[a-z0-9][a-z0-9_.-]{0,63}:[A-Za-z0-9_:.\-]{1,128}"
VersionFilter = Annotated[str | None, Query(pattern=rf"^{_VERSION_KEY}$")]
CommunityVersionFilter = Annotated[str | None, Query(pattern=rf"^(?:latest|{_VERSION_KEY})$")]
CommunityDateFilter = Annotated[date | None, Query(ge=date(2019, 1, 1), le=date(2100, 12, 31))]
_MAX_DATABASE_ID = 2_147_483_647


def _viewer(user: User) -> int | None:
    return user.member.id if user.member else None


def _date_range(single_day: date | None, start_date: date | None, end_date: date | None) -> tuple[date, date] | None:
    if start_date is None and end_date is None:
        return (single_day, single_day) if single_day is not None else None
    if single_day is not None or start_date is None or end_date is None:
        raise HTTPException(422, "请同时指定起止日期，不要混用单日日期", headers=_PRIVATE)
    if start_date > end_date:
        raise HTTPException(422, "开始日期不能晚于结束日期", headers=_PRIVATE)
    return start_date, end_date


@router.get("/community", response_model=StrongholdCommunityOut)
def stronghold_community(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    season: Annotated[StrongholdScopeId | None, Query()] = None,
    difficulty: Annotated[StrongholdScopeId | None, Query()] = None,
    mode: Annotated[StrongholdMode | None, Query()] = None,
    version: CommunityVersionFilter = None,
    result: Annotated[StrongholdCommunityResult | None, Query()] = None,
    date: CommunityDateFilter = None,
    start_date: CommunityDateFilter = None,
    end_date: CommunityDateFilter = None,
    member: int | None = Query(default=None, gt=0, le=_MAX_DATABASE_ID),
    offset: int = Query(default=0, ge=0, le=_MAX_DATABASE_ID),
    limit: int = Query(default=12, ge=1, le=40),
):
    return stronghold.community(
        db,
        _viewer(user),
        date_range=_date_range(date, start_date, end_date),
        season=season,
        difficulty=difficulty,
        mode=mode,
        version=version,
        result=result,
        offset=offset,
        limit=limit,
        contributor=member,
    )


@router.get("/history", response_model=StrongholdHistoryOut)
def stronghold_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    season: Annotated[StrongholdScopeId | None, Query()] = None,
    difficulty: Annotated[StrongholdScopeId | None, Query()] = None,
    mode: Annotated[StrongholdMode | None, Query()] = None,
    version: CommunityVersionFilter = None,
    result: Annotated[StrongholdResult | None, Query()] = None,
    date: CommunityDateFilter = None,
    start_date: CommunityDateFilter = None,
    end_date: CommunityDateFilter = None,
    related: bool = False,
    role_id: int | None = Query(default=None, gt=0, le=_MAX_DATABASE_ID),
    offset: int = Query(default=0, ge=0, le=_MAX_DATABASE_ID),
    limit: int = Query(default=12, ge=1, le=40),
):
    if role_id is not None and not related:
        raise HTTPException(422, "角色筛选需要开启与我相关", headers=_PRIVATE)
    return stronghold.history(
        db,
        _viewer(user),
        date_range=_date_range(date, start_date, end_date),
        season=season,
        difficulty=difficulty,
        mode=mode,
        version=version,
        result=result,
        related=related,
        role_id=role_id,
        offset=offset,
        limit=limit,
    )


@router.get("/assets/{digest}")
def stronghold_asset(digest: Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")]):
    path = archive_path(digest)
    media_type = archived_content_type(path)
    if media_type is None:
        raise HTTPException(404, "卫戍资源不存在")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/me", response_model=StrongholdOwnOut)
def stronghold_own_matches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    season: Annotated[StrongholdScopeId | None, Query()] = None,
    difficulty: Annotated[StrongholdScopeId | None, Query()] = None,
    mode: Annotated[StrongholdMode | None, Query()] = None,
    version: VersionFilter = None,
    result: Annotated[StrongholdResult | None, Query()] = None,
    start_date: CommunityDateFilter = None,
    end_date: CommunityDateFilter = None,
    role_id: int | None = Query(default=None, gt=0, le=_MAX_DATABASE_ID),
    offset: int = Query(default=0, ge=0, le=_MAX_DATABASE_ID),
    limit: int = Query(default=12, ge=1, le=40),
):
    return stronghold.own_matches(
        db,
        _viewer(user),
        season=season,
        difficulty=difficulty,
        mode=mode,
        version=version,
        role_id=role_id,
        result=result,
        offset=offset,
        limit=limit,
        date_range=_date_range(None, start_date, end_date),
    )


@router.post("/sync", response_model=StrongholdSyncStatus, status_code=202)
def stronghold_sync(
    body: StrongholdSyncIn,
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    platform_limiter.hit(f"stronghold-sync:member:{member.id}", limit=6, window_sec=60)
    try:
        return sync_service.enqueue(db, member.id, body)
    except StrongholdError as exc:
        raise _error(exc) from exc


@router.get("/reports/{match_id}", response_model=StrongholdMatchOut)
def stronghold_report(
    match_id: ReportId,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return stronghold.get_report(db, match_id, _viewer(user))
    except StrongholdError as exc:
        raise _error(exc) from exc


@router.get("/views/{view_id}", response_model=StrongholdRecordDetailOut)
def stronghold_view(
    view_id: ReportId,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return stronghold.get_own_record(db, view_id, _viewer(user))
    except StrongholdError as exc:
        raise _error(exc) from exc
