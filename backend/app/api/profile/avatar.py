from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.member import Member
from app.models.user import User
from app.schemas import MemberProfileOut
from app.services.avatar_store import (
    delete_avatar_file,
    is_custom_avatar_url,
    save_avatar_upload,
)
from app.services.member_sync import ensure_user_member
from app.api.profile.helpers import _profile_from_member

router = APIRouter(tags=["profile"])

@router.post("/profile/me/avatar", response_model=MemberProfileOut)
def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    url = save_avatar_upload(
        member.id, file, db=db, owner_user_id=user.id
    )
    member.avatar_url = url
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.delete("/profile/me/avatar", response_model=MemberProfileOut)
def delete_my_avatar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    if is_custom_avatar_url(member.avatar_url):
        delete_avatar_file(member.id, db=db)
    member.avatar_url = None
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.post("/members/{member_id}/avatar", response_model=MemberProfileOut)
def upload_member_avatar(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MemberProfileOut:
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    url = save_avatar_upload(
        member.id, file, db=db, owner_user_id=member.user_id
    )
    member.avatar_url = url
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


