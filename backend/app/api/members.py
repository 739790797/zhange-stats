from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.member import Member
from app.models.user import User
from app.schemas import MemberOut

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberOut])
def list_members(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Member]:
    """只读列表。成员补齐依赖启动 sync_users_and_members / 登录懒加载 ensure_user_member。"""
    return (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.user_id.isnot(None))
        .order_by(Member.joined_at.desc())
        .all()
    )


@router.get("/{member_id}", response_model=MemberOut)
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Member:
    member = (
        db.query(Member)
        .filter(Member.id == member_id, Member.user_id.isnot(None))
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return member
