"""Shared helpers for skland routes."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.user import User
from app.services.member_sync import ensure_user_member


def _member_or_404(db: Session, user: User) -> Member:
    member = ensure_user_member(db, user)
    if member is None:
        raise HTTPException(status_code=400, detail="用户尚未关联成员档案")
    return member
