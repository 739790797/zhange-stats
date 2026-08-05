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

@router.post("/profile/me/avatar", response_model=MemberProfileOut)
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    url = await save_avatar_upload(member.id, file)
    member.avatar_url = url
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.delete("/profile/me/avatar", response_model=MemberProfileOut)
def delete_my_avatar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    if is_custom_avatar_url(member.avatar_url):
        delete_avatar_file(member.id)
    member.avatar_url = None
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.post("/members/{member_id}/avatar", response_model=MemberProfileOut)
async def upload_member_avatar(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MemberProfileOut:
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    url = await save_avatar_upload(member.id, file)
    member.avatar_url = url
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


