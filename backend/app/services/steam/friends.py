"""Steam 日历可见性：站内已注册成员互看。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.user import User
from app.services.member_sync import ensure_user_member


def visible_member_ids_for_user(db: Session, user: User) -> set[int]:
    """当前用户在 Steam 日历等场景可见的成员 ID（全部站内用户）。"""
    ensure_user_member(db, user)
    db.flush()
    rows = db.query(Member.id).filter(Member.user_id.isnot(None)).all()
    return {r[0] for r in rows}


def can_view_member_steam(db: Session, viewer: User, target_member_id: int) -> bool:
    return target_member_id in visible_member_ids_for_user(db, viewer)


def visibility_meta(
    db: Session,
    user: User,
    visible_ids: set[int] | None = None,
) -> dict:
    member = ensure_user_member(db, user)
    ids = visible_ids if visible_ids is not None else visible_member_ids_for_user(db, user)
    bound = bool((member.steam_id or "").strip())
    return {
        "mode": "site_members",
        "self_member_id": member.id,
        "steam_bound": bound,
        "visible_member_count": len(ids),
        "hint": None,
    }
