from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import (
    DISPLAY_NAME_MARKUP_ERROR,
    bump_token_version,
    has_markup_chars,
    hash_password,
)
from app.core.session_cookies import issue_session
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas import (
    UserAdminCreate,
    UserAdminUpdate,
    UserBrief,
)
from app.services.auth_config import (
    admins_remaining,
    enforce_single_admin_if_needed,
    get_min_password_length,
    load_auth_config,
    lock_admin_ids,
)
from app.services.password_policy import PasswordPolicyError, validate_password
from app.services.member_sync import ensure_user_member
from app.services.account_anonymize import (
    AccountAnonymizeError,
    anonymize_user_account,
    user_is_anonymized,
)
from app.api.profile.helpers import (
    _is_admin_user,
    _normalize_email,
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
        .filter(User.anonymized_at.is_(None))
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
            joinedload(User.member).joinedload(Member.mihoyo_bind),
        )
        .filter(User.anonymized_at.is_(None))
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
    if has_markup_chars(display_name):
        raise HTTPException(status_code=400, detail=DISPLAY_NAME_MARKUP_ERROR)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    try:
        password = validate_password(
            body.password,
            min_length=get_min_password_length(db),
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = User(
        username=_gen_username(db),
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> UserBrief:
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    if not user or user_is_anonymized(user):
        raise HTTPException(status_code=404, detail="用户不存在")

    data = body.model_dump(exclude_unset=True)
    target_role: UserRole | None = None
    if "role" in data and data["role"] is not None:
        raw = str(data["role"]).strip().lower()
        if raw not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="角色无效，可选 admin / user")
        target_role = UserRole.admin if raw == "admin" else UserRole.user
    elif "is_admin" in data and data["is_admin"] is not None:
        target_role = UserRole.admin if data["is_admin"] else UserRole.user
    currently_admin = _is_admin_user(user)
    role_changing = False
    if target_role is not None:
        role_changing = (target_role == UserRole.admin) != currently_admin
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
        if has_markup_chars(name):
            raise HTTPException(status_code=400, detail=DISPLAY_NAME_MARKUP_ERROR)
        user.display_name = name
        member.nickname = name

    password_set = False
    if "password" in data and data["password"]:
        try:
            password = validate_password(
                data["password"],
                username=user.username,
                min_length=get_min_password_length(db),
            )
        except PasswordPolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        user.password_hash = hash_password(password)
        bump_token_version(user)
        password_set = True

    if "steam_id" in data:
        _set_steam_id(db, member, data["steam_id"])

    if target_role is not None:
        becoming_user = role_changing and currently_admin
        becoming_admin = role_changing and not currently_admin
        if becoming_user:
            if user.id == current.id:
                raise HTTPException(
                    status_code=400,
                    detail="不能取消自己的管理员角色",
                )
            others = [i for i in lock_admin_ids(db) if i != user.id]
            if not others:
                raise HTTPException(
                    status_code=400,
                    detail="系统至少保留一名管理员",
                )
        user.apply_role(target_role)
        if becoming_user:
            bump_token_version(user)
            if admins_remaining(db) < 1:
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="系统至少保留一名管理员",
                )
        if becoming_admin and load_auth_config(db).get("enforce_single_admin"):
            enforce_single_admin_if_needed(db, keep_user_id=user.id)

    db.commit()
    if password_set and user.id == current.id:
        issue_session(response, request, user)
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
    if not user or user_is_anonymized(user):
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if _is_admin_user(user):
        raise HTTPException(status_code=400, detail="不能删除管理员账号")

    try:
        anonymize_user_account(db, user, actor_id=current.id)
        db.commit()
    except AccountAnonymizeError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=f"删除失败：{exc}") from exc


