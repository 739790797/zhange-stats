from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
import urllib.parse

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.public_url import resolve_backend_base, resolve_frontend_base
from app.core.security import create_access_token, hash_password
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas import (
    MemberProfileOut,
    MemberProfileUpdate,
    QqOAuthStartResponse,
    SteamBindPreviewRequest,
    SteamBindPreviewResponse,
    SteamOpenIdStartResponse,
    UserAdminCreate,
    UserAdminUpdate,
    UserBrief,
)
from app.services.avatar_store import (
    delete_avatar_file,
    is_custom_avatar_url,
    save_avatar_upload,
)
from app.services.member_sync import delete_user_with_member, ensure_user_member
from app.services.steam_bind import (
    PRIVACY_HINT,
    require_public_steam_profile,
    steam_profile_public_dict,
)
from app.services.steam_openid import (
    build_steam_login_url,
    create_openid_state,
    decode_openid_state,
    verify_steam_openid_assertion,
)
from app.services.qq_oauth import (
    PURPOSE_BIND,
    PURPOSE_LOGIN,
    QqOAuthError,
    build_qq_authorize_url,
    create_qq_oauth_state,
    decode_qq_oauth_state,
    exchange_code_for_profile,
)
from app.api.profile.helpers import (
    _apply_profile_fields,
    _frontend_from_state,
    _is_admin_user,
    _normalize_email,
    _profile_from_member,
    _require_steam_feature,
    _set_qq_number,
    _set_qq_profile,
    _set_steam_id,
    _user_brief,
)

router = APIRouter(tags=["profile"])

@router.get("/profile/me", response_model=MemberProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    db.commit()
    member = (
        db.query(Member)
        .options(
            joinedload(Member.user),
            joinedload(Member.skland_bind),
            joinedload(Member.taygedo_bind),
            joinedload(Member.exilium_bind),
                joinedload(Member.kujiequ_bind),
                joinedload(Member.mihoyo_bind),
        )
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.get("/profile/daily-tasks")
def list_my_daily_tasks(
    platform: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户已绑定平台的日常任务（只读，仅本人）。"""
    from app.api.jobs import query_user_checkin_tasks

    member = ensure_user_member(db, user)
    return query_user_checkin_tasks(
        db,
        platform=platform,
        member_id=member.id,
        page=page,
        page_size=page_size,
    )


@router.get("/profile/daily-task-logs")
def list_my_daily_task_logs(
    platform: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户日常任务执行记录（只读，仅本人）。"""
    from app.api.jobs import query_checkin_logs

    member = ensure_user_member(db, user)
    return query_checkin_logs(
        db,
        platform=platform,
        member_id=member.id,
        page=page,
        page_size=page_size,
    )


@router.patch("/profile/me", response_model=MemberProfileOut)
def update_my_profile(
    body: MemberProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    data = body.model_dump(exclude_unset=True)
    # 普通用户绑 Steam 必须走 OpenID，禁止手填他人 SteamID
    if "steam_id" in data and data["steam_id"] is not None and str(data["steam_id"]).strip():
        raise HTTPException(
            status_code=400,
            detail="请通过「Steam 登录绑定」完成绑定，以确保账号归属",
        )
    steam_persona = _apply_profile_fields(db, user, member, data)
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member, steam_persona)


