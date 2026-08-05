"""Shared helpers for profile / users / oauth routes."""
from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.public_url import resolve_backend_base, resolve_frontend_base
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas import MemberProfileOut, MemberProfileUpdate, UserBrief


def _frontend_from_state(state_data: dict, request: Request) -> str:
    stored = str(state_data.get("frontend") or "").rstrip("/")
    if stored:
        return stored
    backend = str(state_data.get("backend") or "").rstrip("/")
    if backend:
        return backend
    settings = get_settings()
    override = (settings.PUBLIC_FRONTEND_URL or "").rstrip("/")
    if override:
        return override
    return resolve_frontend_base(request) or resolve_backend_base(request)


def _set_qq_profile(
    db: Session,
    member: Member,
    *,
    openid: str | None,
    unionid: str | None = None,
    nickname: str | None = None,
    avatar_url: str | None = None,
) -> str | None:
    """绑定或解绑 QQ；返回昵称（解绑为 None）。"""
    value = (openid or "").strip() or None
    if not value:
        member.qq_openid = None
        member.qq_unionid = None
        member.qq_nickname = None
        member.qq_avatar_url = None
        return None

    conflict = (
        db.query(Member)
        .filter(Member.qq_openid == value, Member.id != member.id)
        .first()
    )
    if conflict:
        raise HTTPException(status_code=400, detail="该 QQ 已绑定其他账号")

    member.qq_openid = value
    member.qq_unionid = (unionid or "").strip() or None
    member.qq_nickname = (nickname or "").strip() or None
    member.qq_avatar_url = (avatar_url or "").strip() or None
    return member.qq_nickname


def _profile_from_member(
    member: Member,
    steam_persona_name: str | None = None,
    *,
    viewer: User | None = None,
    include_email: bool | None = None,
) -> MemberProfileOut:
    user = member.user
    show_email = include_email
    if show_email is None:
        if viewer is None:
            show_email = True
        else:
            show_email = _is_admin_user(viewer) or (
                user is not None and user.id == viewer.id
            )
    persona = (
        steam_persona_name
        if steam_persona_name is not None
        else member.steam_persona_name
    )
    skland = getattr(member, "skland_bind", None)
    taygedo = getattr(member, "taygedo_bind", None)
    exilium = getattr(member, "exilium_bind", None)
    kujiequ = getattr(member, "kujiequ_bind", None)
    return MemberProfileOut(
        member_id=member.id,
        nickname=member.nickname,
        avatar_url=member.avatar_url,
        steam_id=member.steam_id,
        steam_persona_name=persona,
        steam_avatar_url=member.steam_avatar_url,
        steam_friends_public=member.steam_friends_public,
        steam_friends_synced_at=member.steam_friends_synced_at,
        skland_bound=skland is not None,
        skland_auto_checkin=bool(skland.auto_checkin) if skland is not None else None,
        taygedo_bound=taygedo is not None,
        taygedo_auto_checkin=bool(taygedo.auto_checkin) if taygedo is not None else None,
        taygedo_phone_mask=taygedo.phone_mask if taygedo is not None else None,
        exilium_bound=exilium is not None,
        exilium_auto_checkin=bool(exilium.auto_checkin) if exilium is not None else None,
        exilium_phone_mask=exilium.phone_mask if exilium is not None else None,
        kujiequ_bound=kujiequ is not None,
        kujiequ_auto_checkin=bool(kujiequ.auto_checkin) if kujiequ is not None else None,
        kujiequ_phone_mask=kujiequ.phone_mask if kujiequ is not None else None,
        qq_bound=bool(member.qq_openid),
        qq_nickname=member.qq_nickname,
        qq_avatar_url=member.qq_avatar_url,
        qq_number=member.qq_number,
        user_id=member.user_id,
        username=user.username if user else None,
        email=(user.email if user else None) if show_email else None,
        display_name=user.display_name if user else None,
        joined_at=member.joined_at,
    )


def _user_brief(u: User) -> UserBrief:
    member = u.member
    skland = getattr(member, "skland_bind", None) if member else None
    taygedo = getattr(member, "taygedo_bind", None) if member else None
    exilium = getattr(member, "exilium_bind", None) if member else None
    kujiequ = getattr(member, "kujiequ_bind", None) if member else None
    return UserBrief(
        id=u.id,
        username=u.username,
        email=u.email,
        display_name=u.display_name,
        role=u.role.value if isinstance(u.role, UserRole) else str(u.role),
        is_admin=u.is_admin_user,
        email_verified=bool(u.email_verified),
        member_id=member.id if member else None,
        steam_id=member.steam_id if member else None,
        steam_bound=bool(member and member.steam_id),
        skland_bound=skland is not None,
        taygedo_bound=taygedo is not None,
        exilium_bound=exilium is not None,
        kujiequ_bound=kujiequ is not None,
        qq_bound=bool(member and member.qq_openid),
    )


def _is_admin_user(u: User) -> bool:
    return u.is_admin_user


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _require_steam_feature(db: Session) -> None:
    from app.services.platform_features import is_feature_enabled

    if not is_feature_enabled(db, "steam"):
        raise HTTPException(status_code=403, detail="该功能未启用")


def _set_steam_id(db: Session, member: Member, steam_id: str | None) -> str | None:
    """绑定或解绑 Steam；仅同步 Steam 专用昵称/头像，不改站内身份。"""
    from app.services.steam_friends import clear_member_friends, sync_member_friends
    from app.services.steam_persona import force_set_steam_persona_name

    value = (steam_id or "").strip() or None
    if not value:
        # 解绑在平台关闭时仍允许，便于清理
        member.steam_id = None
        member.steam_friends_public = None
        member.steam_friends_synced_at = None
        member.steam_persona_name = None
        member.steam_avatar_url = None
        clear_member_friends(db, member.id)
        return None

    _require_steam_feature(db)

    try:
        profile = require_public_steam_profile(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    taken = (
        db.query(Member)
        .filter(Member.steam_id == profile.steam_id, Member.id != member.id)
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="该 Steam 账号已被其他成员绑定")

    member.steam_id = profile.steam_id
    user = member.user
    if user is None and member.user_id is not None:
        user = db.query(User).filter(User.id == member.user_id).first()
    force_set_steam_persona_name(
        member,
        profile.persona_name,
        user=user,
        update_display=False,
        avatar_url=profile.avatar_url,
    )
    sync_member_friends(db, member)
    return profile.persona_name


def _set_qq_number(db: Session, member: Member, raw: str | None) -> None:
    if raw is None:
        member.qq_number = None
        return
    value = str(raw).strip()
    if not value:
        member.qq_number = None
        return
    if not value.isdigit() or not (5 <= len(value) <= 12):
        raise HTTPException(status_code=400, detail="QQ 号须为 5–12 位数字")
    conflict = (
        db.query(Member)
        .filter(Member.qq_number == value, Member.id != member.id)
        .first()
    )
    if conflict:
        raise HTTPException(status_code=400, detail="该 QQ 号已被其他账号使用")
    member.qq_number = value


def _apply_profile_fields(
    db: Session,
    user: User,
    member: Member,
    data: dict,
) -> str | None:
    """应用个人中心字段更新。返回绑定时的 Steam 昵称（若有）。"""
    if "display_name" in data and data["display_name"] is not None:
        name = str(data["display_name"]).strip()
        if not name:
            raise HTTPException(status_code=400, detail="显示名称不能为空")
        name = name[:64]
        user.display_name = name
        member.nickname = name

    steam_persona: str | None = None
    if "steam_id" in data:
        steam_persona = _set_steam_id(db, member, data["steam_id"])
    if "qq_number" in data:
        _set_qq_number(db, member, data["qq_number"])
    return steam_persona

