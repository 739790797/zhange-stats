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

@router.get("/users", response_model=list[UserBrief])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserBrief]:
    users = (
        db.query(User)
        .options(joinedload(User.member))
        .order_by(User.id.asc())
        .all()
    )
    for u in users:
        ensure_user_member(db, u)
    db.commit()
    users = (
        db.query(User)
        .options(
            joinedload(User.member).joinedload(Member.skland_bind),
            joinedload(User.member).joinedload(Member.taygedo_bind),
            joinedload(User.member).joinedload(Member.exilium_bind),
            joinedload(User.member).joinedload(Member.kujiequ_bind),
        )
        .order_by(User.id.asc())
        .all()
    )
    return [_user_brief(u) for u in users]


@router.post("/users", response_model=UserBrief)
def create_user(
    body: UserAdminCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserBrief:
    from app.api.auth import _gen_username

    email = _normalize_email(body.email)
    if "@" not in email:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    display_name = body.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    user = User(
        username=_gen_username(db),
        email=email,
        display_name=display_name,
        password_hash=hash_password(body.password),
        role=UserRole.user,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    member = ensure_user_member(db, user)
    if body.steam_id is not None:
        _set_steam_id(db, member, body.steam_id)
    db.commit()
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user.id)
        .first()
    )
    return _user_brief(user)


@router.patch("/users/{user_id}", response_model=UserBrief)
def update_user(
    user_id: int,
    body: UserAdminUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> UserBrief:
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    data = body.model_dump(exclude_unset=True)
    member = ensure_user_member(db, user)

    if "email" in data and data["email"] is not None:
        email = _normalize_email(data["email"])
        if "@" not in email:
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        taken = (
            db.query(User)
            .filter(User.email == email, User.id != user.id)
            .first()
        )
        if taken:
            raise HTTPException(status_code=400, detail="该邮箱已被注册")
        user.email = email

    if "display_name" in data and data["display_name"] is not None:
        name = data["display_name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="用户名不能为空")
        user.display_name = name
        member.nickname = name

    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])

    if "steam_id" in data:
        _set_steam_id(db, member, data["steam_id"])

    # 角色：支持 role 或 is_admin（前端以 role 为主）
    target_role: UserRole | None = None
    if "role" in data and data["role"] is not None:
        raw = str(data["role"]).strip().lower()
        if raw not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="角色无效，可选 admin / user")
        target_role = UserRole.admin if raw == "admin" else UserRole.user
    elif "is_admin" in data and data["is_admin"] is not None:
        target_role = UserRole.admin if data["is_admin"] else UserRole.user

    if target_role is not None:
        currently_admin = _is_admin_user(user)
        becoming_user = target_role == UserRole.user and currently_admin
        if becoming_user:
            if user.id == current.id:
                raise HTTPException(
                    status_code=400,
                    detail="不能取消自己的管理员角色",
                )
            admin_count = sum(1 for u in db.query(User).all() if _is_admin_user(u))
            if admin_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="系统至少保留一名管理员",
                )
        user.apply_role(target_role)

    db.commit()
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    return _user_brief(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> None:
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if _is_admin_user(user):
        raise HTTPException(status_code=400, detail="不能删除管理员账号")

    try:
        delete_user_with_member(db, user)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=f"删除失败：{exc}") from exc


