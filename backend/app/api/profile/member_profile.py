from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.member import Member
from app.models.user import User
from app.schemas import (
    MemberProfileOut,
    MemberProfileUpdate,
)
from app.api.profile.helpers import (
    _apply_profile_fields,
    _profile_from_member,
)

router = APIRouter(tags=["profile"])

@router.get("/members/{member_id}/profile", response_model=MemberProfileOut)
def get_member_profile(
    member_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = (
        db.query(Member)
        .options(
            joinedload(Member.user),
            joinedload(Member.skland_bind),
            joinedload(Member.taygedo_bind),
            joinedload(Member.exilium_bind),
            joinedload(Member.kujiequ_bind),
            joinedload(Member.mihoyo_bind),
        )
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return _profile_from_member(member, viewer=viewer)


@router.patch("/members/{member_id}/profile", response_model=MemberProfileOut)
def update_member_profile(
    member_id: int,
    body: MemberProfileUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MemberProfileOut:
    """管理员代编辑成员个人中心（测试绑定等）。"""
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    if not member.user:
        raise HTTPException(status_code=400, detail="该成员未关联用户账号")

    data = body.model_dump(exclude_unset=True)
    steam_persona = _apply_profile_fields(db, member.user, member, data)
    db.commit()
    db.refresh(member)
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member, steam_persona)

