"""Shared helpers for profile / users / oauth routes."""
from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.public_url import (
    allowed_frontend_base,
    resolve_backend_base,
    resolve_frontend_base,
)
from app.core.security import (
    DISPLAY_NAME_MARKUP_ERROR,
    has_markup_chars,
    strip_markup_chars,
)
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas import MemberProfileOut, UserBrief


class BindError(HTTPException):
    """绑定失败：detail 给接口调用方看；reason 是 OAuth 回调跳回前端时用的固定码（不把文案放进 URL）。"""

    def __init__(self, status_code: int, detail: str, *, reason: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.reason = reason


def _frontend_from_state(state_data: dict | None, request: Request) -> str:
    """回调时按本次请求重算白名单：state 里记的地址不在其中就退回默认，绝不跳去发起方自报的站点。"""
    stored = str((state_data or {}).get("frontend") or "")
    return (
        allowed_frontend_base(stored, request)
        or resolve_frontend_base(request)
        or resolve_backend_base(request)
    )


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
        raise BindError(400, "该 QQ 已绑定其他账号", reason="already_bound")

    member.qq_openid = value
    member.qq_unionid = (unionid or "").strip() or None
    member.qq_nickname = strip_markup_chars(nickname).strip() or None
    member.qq_avatar_url = (avatar_url or "").strip() or None
    return member.qq_nickname


def _can_view_private_profile(member: Member, viewer: User | None) -> bool:
    """viewer 为 None 表示路由已按本人 / 管理员鉴权过。"""
    if viewer is None:
        return True
    return _is_admin_user(viewer) or (
        member.user_id is not None and member.user_id == viewer.id
    )


def _profile_from_member(
    member: Member,
    steam_persona_name: str | None = None,
    *,
    viewer: User | None = None,
) -> MemberProfileOut:
    """本人 / 管理员看全量；其他登录用户只看显示名、头像、各平台是否已绑与 Steam 公开昵称头像。

    登录名、邮箱、QQ 资料、SteamID、手机号掩码、自动签到开关都不给旁人。
    """
    user = member.user
    persona = (
        steam_persona_name
        if steam_persona_name is not None
        else member.steam_persona_name
    )
    skland = getattr(member, "skland_bind", None)
    taygedo = getattr(member, "taygedo_bind", None)
    exilium = getattr(member, "exilium_bind", None)
    kujiequ = getattr(member, "kujiequ_bind", None)
    mihoyo = getattr(member, "mihoyo_bind", None)
    public = MemberProfileOut(
        member_id=member.id,
        nickname=member.nickname,
        avatar_url=member.avatar_url,
        steam_id=None,
        steam_persona_name=persona,
        steam_avatar_url=member.steam_avatar_url,
        skland_bound=skland is not None,
        taygedo_bound=taygedo is not None,
        exilium_bound=exilium is not None,
        kujiequ_bound=kujiequ is not None,
        mihoyo_bound=mihoyo is not None,
        qq_bound=bool(member.qq_openid),
        display_name=user.display_name if user else None,
        joined_at=member.joined_at,
    )
    if not _can_view_private_profile(member, viewer):
        return public
    return public.model_copy(
        update={
            "steam_id": member.steam_id,
            "skland_auto_checkin": bool(skland.auto_checkin) if skland is not None else None,
            "taygedo_auto_checkin": bool(taygedo.auto_checkin) if taygedo is not None else None,
            "taygedo_phone_mask": taygedo.phone_mask if taygedo is not None else None,
            "exilium_auto_checkin": bool(exilium.auto_checkin) if exilium is not None else None,
            "exilium_phone_mask": exilium.phone_mask if exilium is not None else None,
            "kujiequ_auto_checkin": bool(kujiequ.auto_checkin) if kujiequ is not None else None,
            "kujiequ_phone_mask": kujiequ.phone_mask if kujiequ is not None else None,
            "mihoyo_auto_checkin": bool(mihoyo.auto_checkin) if mihoyo is not None else None,
            "mihoyo_phone_mask": mihoyo.phone_mask if mihoyo is not None else None,
            "qq_nickname": member.qq_nickname,
            "qq_avatar_url": member.qq_avatar_url,
            "user_id": member.user_id,
            "username": user.username if user else None,
            "email": user.email if user else None,
        }
    )


def _user_brief(u: User) -> UserBrief:
    member = u.member
    skland = getattr(member, "skland_bind", None) if member else None
    taygedo = getattr(member, "taygedo_bind", None) if member else None
    exilium = getattr(member, "exilium_bind", None) if member else None
    kujiequ = getattr(member, "kujiequ_bind", None) if member else None
    mihoyo = getattr(member, "mihoyo_bind", None) if member else None
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
        mihoyo_bound=mihoyo is not None,
        qq_bound=bool(member and member.qq_openid),
    )


def _is_admin_user(u: User) -> bool:
    return u.is_admin_user


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _require_steam_feature(db: Session) -> None:
    from app.services.platform_features import is_feature_enabled

    if not is_feature_enabled(db, "steam"):
        raise BindError(403, "该功能未启用", reason="feature_disabled")


def _set_steam_id(db: Session, member: Member, steam_id: str | None) -> str | None:
    """绑定或解绑 Steam；仅同步 Steam 专用昵称/头像，不改站内身份。"""
    from app.services.steam.bind import PRIVACY_HINT, lookup_steam_profile
    from app.services.steam.persona import force_set_steam_persona_name

    value = (steam_id or "").strip() or None
    if not value:
        # 解绑在平台关闭时仍允许，便于清理
        member.steam_id = None
        member.steam_persona_name = None
        member.steam_avatar_url = None
        return None

    _require_steam_feature(db)

    try:
        profile = lookup_steam_profile(value)
    except ValueError as exc:
        raise BindError(400, str(exc), reason="steam_not_found") from exc
    except RuntimeError as exc:
        raise BindError(400, str(exc), reason="upstream_error") from exc
    if not profile.is_public:
        raise BindError(
            400,
            "该 Steam 个人资料未公开，无法获取游戏与在线信息。" + PRIVACY_HINT,
            reason="steam_private",
        )

    taken = (
        db.query(Member)
        .filter(Member.steam_id == profile.steam_id, Member.id != member.id)
        .first()
    )
    if taken:
        raise BindError(400, "该 Steam 账号已被其他成员绑定", reason="already_bound")

    member.steam_id = profile.steam_id
    user = member.user
    if user is None and member.user_id is not None:
        user = db.query(User).filter(User.id == member.user_id).first()
    force_set_steam_persona_name(
        member,
        profile.persona_name,
        user=user,
        avatar_url=profile.avatar_url,
    )
    return profile.persona_name


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
        if has_markup_chars(name):
            raise HTTPException(status_code=400, detail=DISPLAY_NAME_MARKUP_ERROR)
        name = name[:64]
        user.display_name = name
        member.nickname = name

    steam_persona: str | None = None
    if "steam_id" in data:
        steam_persona = _set_steam_id(db, member, data["steam_id"])
    return steam_persona

