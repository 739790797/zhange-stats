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
VersionFilter = Annotated[str | None, Query(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}:[A-Za-z0-9_:.\-]{1,128}$")]
_MAX_DATABASE_ID = 2_147_483_647


def _viewer(user: User) -> int | None:
    return user.member.id if user.member else None


@router.get("/community", response_model=StrongholdCommunityOut)
def stronghold_community(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    season: Annotated[StrongholdScopeId | None, Query()] = None,
    difficulty: Annotated[StrongholdScopeId | None, Query()] = None,
    mode: Annotated[StrongholdMode | None, Query()] = None,
    version: VersionFilter = None,
    selected_date: Annotated[date | None, Query(alias="date", ge=date(2019, 1, 1), le=date(2100, 12, 31))] = None,
    member: int | None = Query(default=None, gt=0, le=_MAX_DATABASE_ID),
    offset: int = Query(default=0, ge=0, le=_MAX_DATABASE_ID),
    limit: int = Query(default=12, ge=1, le=40),
):
    return stronghold.community(
        db,
        _viewer(user),
        selected_date=selected_date,
        season=season,
        difficulty=difficulty,
        mode=mode,
        version=version,
        offset=offset,
        limit=limit,
        contributor=member,
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
