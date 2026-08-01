"""兼容旧导入；实现见 steam_display。"""

from __future__ import annotations

from app.models.member import Member
from app.models.user import User
from app.services.steam_display import apply_steam_profile, force_set_steam_persona_name


def apply_steam_persona_name(
    member: Member,
    persona_name: str | None = None,
    avatar_url: str | None = None,
) -> bool:
    return apply_steam_profile(
        member, persona_name=persona_name, avatar_url=avatar_url
    )


__all__ = [
    "apply_steam_persona_name",
    "force_set_steam_persona_name",
    "User",
]
