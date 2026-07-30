from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas import (
    MemberProfileOut,
    MemberProfileUpdate,
    UserBrief,
    UserRoleUpdate,
)
from app.services.member_sync import delete_user_with_member, ensure_user_member

router = APIRouter(tags=["profile"])


def _profile_from_member(member: Member) -> MemberProfileOut:
    user = member.user
    return MemberProfileOut(
        member_id=member.id,
        nickname=member.nickname,
        avatar_url=member.avatar_url,
        steam_id=member.steam_id,
        user_id=member.user_id,
        username=user.username if user else None,
        email=user.email if user else None,
        display_name=user.display_name if user else None,
        joined_at=member.joined_at,
    )


def _user_brief(u: User) -> UserBrief:
    return UserBrief(
        id=u.id,
        username=u.username,
        email=u.email,
        display_name=u.display_name,
        role=u.role.value if isinstance(u.role, UserRole) else str(u.role),
        is_admin=bool(u.is_admin) or u.role == UserRole.admin,
        email_verified=bool(u.email_verified),
        member_id=u.member.id if u.member else None,
    )


@router.get("/users", response_model=list[UserBrief])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserBrief]:
    users = (
        db.query(User)
        .options(joinedload(User.member))
        .order_by(User.id.asc())
        .all()
    )
    for u in users:
        ensure_user_member(db, u)
    db.commit()
    # 重新加载 member 关系
    users = (
        db.query(User)
        .options(joinedload(User.member))
        .order_by(User.id.asc())
        .all()
    )
    return [_user_brief(u) for u in users]


@router.patch("/users/{user_id}/role", response_model=UserBrief)
def update_user_role(
    user_id: int,
    body: UserRoleUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> UserBrief:
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="不能取消自己的管理员角色")

    user.apply_role(UserRole.admin if body.role == "admin" else UserRole.user)
    db.commit()
    db.refresh(user)
    return _user_brief(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> None:
    user = (
        db.query(User)
        .options(joinedload(User.member))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")

    if user.is_admin or user.role == UserRole.admin:
        admin_count = (
            db.query(User)
            .filter((User.role == UserRole.admin) | (User.is_admin.is_(True)))
            .count()
        )
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="不能删除最后一个管理员")

    delete_user_with_member(db, user)
    db.commit()


@router.get("/profile/me", response_model=MemberProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)
    db.commit()
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.patch("/profile/me", response_model=MemberProfileOut)
def update_my_profile(
    body: MemberProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = ensure_user_member(db, user)

    data = body.model_dump(exclude_unset=True)
    if "display_name" in data:
        name = (data["display_name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="用户名不能为空")
        user.display_name = name
        member.nickname = name

    if "steam_id" in data:
        steam_id = (data["steam_id"] or "").strip() or None
        if steam_id:
            taken = (
                db.query(Member)
                .filter(Member.steam_id == steam_id, Member.id != member.id)
                .first()
            )
            if taken:
                raise HTTPException(
                    status_code=400, detail="该 Steam ID 已被其他成员绑定"
                )
        member.steam_id = steam_id

    db.commit()
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member.id)
        .first()
    )
    return _profile_from_member(member)


@router.get("/members/{member_id}/profile", response_model=MemberProfileOut)
def get_member_profile(
    member_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MemberProfileOut:
    member = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return _profile_from_member(member)
