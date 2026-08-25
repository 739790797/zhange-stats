"""Steam 显示名 / 头像：仅写入 Steam 专用字段，不覆盖站内身份。"""

from __future__ import annotations

from app.models.member import Member
from app.models.user import User


def _clip(name: str, n: int = 64) -> str:
    return name.strip()[:n]


def apply_steam_profile(
    member: Member,
    *,
    persona_name: str | None = None,
    avatar_url: str | None = None,
) -> bool:
    """只更新 steam_persona_name / steam_avatar_url。返回是否有字段变化。"""
    changed = False

    if persona_name and str(persona_name).strip():
        new_name = _clip(str(persona_name))
        if member.steam_persona_name != new_name:
            member.steam_persona_name = new_name
            changed = True

    if avatar_url and str(avatar_url).strip():
        url = str(avatar_url).strip()[:512]
        if member.steam_avatar_url != url:
            member.steam_avatar_url = url
            changed = True

    return changed


def force_set_steam_persona_name(
    member: Member,
    persona_name: str | None,
    *,
    user: User | None = None,
    update_display: bool = True,
    avatar_url: str | None = None,
) -> None:
    """绑定 Steam 时写入 Steam 专用资料（update_display 已废弃，保留参数兼容）。"""
    del update_display  # 不再覆盖站内 display_name / nickname / avatar_url
    target = user if user is not None else member.user
    if target is not None and member.user is None:
        member.user = target

    if avatar_url and str(avatar_url).strip():
        member.steam_avatar_url = str(avatar_url).strip()[:512]
    else:
        member.steam_avatar_url = None

    if not persona_name or not str(persona_name).strip():
        member.steam_persona_name = None
        return

    member.steam_persona_name = _clip(str(persona_name))


def format_steam_display_name(
    member: Member | None,
    *,
    fallback: str | None = None,
) -> str:
    """优先 Steam 昵称；否则用 fallback / #id。"""
    if member is not None:
        name = (member.steam_persona_name or "").strip()
        if name:
            return name
        return fallback or f"#{member.id}"
    return fallback or "未知"


def member_steam_presentation(
    member: Member | None,
    *,
    fallback_id: int | str | None = None,
) -> dict:
    steam_avatar = None
    if member is not None:
        steam_avatar = member.steam_avatar_url or None
    return {
        "member_nickname": format_steam_display_name(
            member,
            fallback=str(fallback_id) if fallback_id is not None else None,
        ),
        "avatar_url": steam_avatar,
        "steam_persona_name": (member.steam_persona_name if member else None),
    }
