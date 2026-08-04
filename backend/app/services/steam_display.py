"""Steam 显示名 / 头像：仅写入 Steam 专用字段，不覆盖站内身份。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.steam_friend import SteamFriendEdge
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


def load_viewer_friend_aliases(db: Session, viewer: User | Member | int | None) -> dict[str, str]:
    """viewer 对好友 steam_id -> 备注名。"""
    if viewer is None:
        return {}
    if isinstance(viewer, Member):
        member_id = viewer.id
    elif isinstance(viewer, int):
        member_id = viewer
    else:
        ensure = getattr(viewer, "member", None)
        if ensure is None:
            from app.services.member_sync import ensure_user_member

            ensure = ensure_user_member(db, viewer)
        member_id = ensure.id

    rows = (
        db.query(SteamFriendEdge.friend_steam_id, SteamFriendEdge.nickname)
        .filter(
            SteamFriendEdge.member_id == member_id,
            SteamFriendEdge.nickname.isnot(None),
            SteamFriendEdge.nickname != "",
        )
        .all()
    )
    return {sid: nick for sid, nick in rows if sid and nick}


def format_steam_display_name(
    member: Member | None,
    *,
    alias: str | None = None,
    fallback: str | None = None,
) -> str:
    """有备注时显示 ``*备注``（与 Steam 一致）；否则用 Steam 昵称。"""
    if alias and str(alias).strip():
        return f"*{_clip(str(alias))}"
    if member is not None:
        name = (member.steam_persona_name or "").strip()
        if name:
            return name
        return fallback or f"#{member.id}"
    return fallback or "未知"


def member_steam_presentation(
    member: Member | None,
    *,
    aliases: dict[str, str] | None = None,
    fallback_id: int | str | None = None,
) -> dict:
    aliases = aliases or {}
    alias = None
    if member is not None and member.steam_id:
        alias = aliases.get(member.steam_id)
    steam_avatar = None
    if member is not None:
        steam_avatar = member.steam_avatar_url or None
    return {
        "member_nickname": format_steam_display_name(
            member,
            alias=alias,
            fallback=str(fallback_id) if fallback_id is not None else None,
        ),
        "avatar_url": steam_avatar,
        "friend_nickname": alias,
        "steam_persona_name": (member.steam_persona_name if member else None),
    }
