from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth.helpers import _user_out
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas import UserOut
from app.services.member_sync import ensure_user_member

router = APIRouter()


@router.get("/me", response_model=UserOut)
def me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserOut:
    member = ensure_user_member(db, user)
    db.commit()
    db.refresh(user)
    db.refresh(member)
    user.member = member
    return _user_out(user)
