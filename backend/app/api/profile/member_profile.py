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

@router.get("/members/{member_id}/profile", response_model=MemberProfileOut)
def get_member_profile(
    member_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
) -> MemberProfileOut:
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
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return _profile_from_member(member, viewer=viewer)


@router.patch("/members/{member_id}/profile", response_model=MemberProfileOut)
def update_member_profile(
    member_id: int,
    body: MemberProfileUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MemberProfileOut:
    """管理员代编辑成员个人中心（测试绑定等）。"""
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    if not member.user:
        raise HTTPException(status_code=400, detail="该成员未关联用户账号")

    data = body.model_dump(exclude_unset=True)
    steam_persona = _apply_profile_fields(db, member.user, member, data)
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member, steam_persona)

