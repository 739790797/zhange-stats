"""用户与成员 1:1 同步。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.user import User


def ensure_user_member(db: Session, user: User) -> Member:
    """确保用户有且仅有一个成员档案，昵称与 display_name 对齐。"""
    member = db.query(Member).filter(Member.user_id == user.id).first()
    if not member:
        member = Member(
            nickname=user.display_name or user.username,
            user_id=user.id,
        )
        db.add(member)
        db.flush()
    else:
        name = user.display_name or user.username
        if member.nickname != name:
            member.nickname = name
    return member


def delete_member_cascade(db: Session, member: Member) -> None:
    """删除成员及其关联的会话、状态、好友边。"""
    from app.models.presence_segment import PresenceSegment
    from app.models.steam_friend import SteamFriendEdge

    mid = member.id
    db.query(PlaySession).filter(PlaySession.member_id == mid).delete(
        synchronize_session=False
    )
    db.query(PresenceSegment).filter(PresenceSegment.member_id == mid).delete(
        synchronize_session=False
    )
    db.query(SteamFriendEdge).filter(SteamFriendEdge.member_id == mid).delete(
        synchronize_session=False
    )
    db.delete(member)
    db.flush()


def delete_user_with_member(db: Session, user: User) -> None:
    """删除用户并同步删除其成员。"""
    member = db.query(Member).filter(Member.user_id == user.id).first()
    if member:
        delete_member_cascade(db, member)
    db.delete(user)
    db.flush()


def sync_users_and_members(db: Session) -> dict[str, int]:
    """
    修复存量：
    - 每个用户补齐成员
    - 同步成员昵称 = 用户显示名
    - 删除无关联用户的孤儿成员
    """
    created = 0
    synced = 0
    removed = 0

    users = db.query(User).all()
    for user in users:
        before = db.query(Member).filter(Member.user_id == user.id).first()
        member = ensure_user_member(db, user)
        if before is None:
            created += 1
        elif before.nickname != member.nickname:
            synced += 1

    orphans = db.query(Member).filter(Member.user_id.is_(None)).all()
    for member in orphans:
        delete_member_cascade(db, member)
        removed += 1

    # 同一用户若误绑多个成员（理论上 unique），保留最早的
    for user in users:
        members = (
            db.query(Member)
            .filter(Member.user_id == user.id)
            .order_by(Member.id.asc())
            .all()
        )
        for extra in members[1:]:
            extra.user_id = None
            delete_member_cascade(db, extra)
            removed += 1

    db.commit()
    return {"created": created, "synced": synced, "removed": removed}
