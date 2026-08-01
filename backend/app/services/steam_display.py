"""Steam 显示名：始终以 Steam 昵称/头像为准，好友备注加 *。"""

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
    """始终用 Steam 资料覆盖本站显示名与头像。返回是否有字段变化。"""
    changed = False

    if persona_name and str(persona_name).strip():
        new_name = _clip(str(persona_name))
        if member.steam_persona_name != new_name:
            member.steam_persona_name = new_name
            changed = True
        if member.nickname != new_name:
            member.nickname = new_name
            changed = True
        user = member.user
        if user is not None and user.display_name != new_name:
            user.display_name = new_name
            changed = True

    if avatar_url and str(avatar_url).strip():
        url = str(avatar_url).strip()[:512]
        if member.avatar_url != url:
            member.avatar_url = url
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
    """绑定 Steam 时强制写入资料。"""
    target = user if user is not None else member.user
    if target is not None and member.user is None:
        member.user = target

    if avatar_url and str(avatar_url).strip():
        member.avatar_url = str(avatar_url).strip()[:512]

    if not persona_name or not str(persona_name).strip():
        member.steam_persona_name = None
        return

    new_name = _clip(str(persona_name))
    member.steam_persona_name = new_name
    if not update_display:
        return
    member.nickname = new_name
    if target is not None:
        target.display_name = new_name


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
        name = (member.steam_persona_name or member.nickname or "").strip()
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
    return {
        "member_nickname": format_steam_display_name(
            member,
            alias=alias,
            fallback=str(fallback_id) if fallback_id is not None else None,
        ),
        "avatar_url": member.avatar_url if member else None,
        "friend_nickname": alias,
        "steam_persona_name": (
            (member.steam_persona_name or member.nickname) if member else None
        ),
    }
