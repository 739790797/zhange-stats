"""NapCat 群列表 / 群成员（管理员）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.member import Member
from app.models.user import User
from app.services.integrations_config import get_napcat_credentials
from app.services.napcat_client import (
    NapCatError,
    get_group_list,
    get_group_member_list,
)

router = APIRouter(prefix="/napcat", tags=["napcat"])


class NapCatGroupOut(BaseModel):
    group_id: str
    group_name: str
    member_count: int | None = None
    max_member_count: int | None = None


class NapCatSiteMemberOut(BaseModel):
    id: int
    nickname: str
    user_id: int | None = None
    qq_number: str | None = None


class NapCatGroupMemberOut(BaseModel):
    user_id: str
    nickname: str = ""
    card: str = ""
    role: str = ""
    title: str = ""
    site_member: NapCatSiteMemberOut | None = None


class NapCatGroupsResponse(BaseModel):
    configured: bool
    groups: list[NapCatGroupOut]


class NapCatGroupMembersResponse(BaseModel):
    group_id: str
    members: list[NapCatGroupMemberOut]
    site_bound_count: int


def _require_napcat(db: Session) -> tuple[str, str]:
    base_url, token = get_napcat_credentials(db)
    if not base_url or not token:
        raise HTTPException(status_code=400, detail="未配置 NapCat（请在集成密钥中填写）")
    return base_url, token


def _role_label(role: str) -> str:
    mapping = {"owner": "群主", "admin": "管理员", "member": "成员"}
    return mapping.get(role, role or "成员")


@router.get("/groups", response_model=NapCatGroupsResponse)
def list_groups(
    force: bool = Query(default=False, description="强制不走 NapCat 缓存"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> NapCatGroupsResponse:
    base_url, token = _require_napcat(db)
    try:
        raw = get_group_list(base_url, token, no_cache=force)
    except NapCatError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    groups: list[NapCatGroupOut] = []
    for item in raw:
        gid = item.get("group_id")
        if gid is None:
            continue
        member_count = item.get("member_count")
        max_member_count = item.get("max_member_count")
        groups.append(
            NapCatGroupOut(
                group_id=str(gid),
                group_name=str(item.get("group_name") or item.get("group_memo") or gid),
                member_count=int(member_count) if member_count is not None else None,
                max_member_count=(
                    int(max_member_count) if max_member_count is not None else None
                ),
            )
        )
    groups.sort(key=lambda g: g.group_name)
    return NapCatGroupsResponse(configured=True, groups=groups)


@router.get(
    "/groups/{group_id}/members",
    response_model=NapCatGroupMembersResponse,
)
def list_group_members(
    group_id: str,
    force: bool = Query(default=False, description="强制不走 NapCat 缓存"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> NapCatGroupMembersResponse:
    base_url, token = _require_napcat(db)
    try:
        raw = get_group_member_list(base_url, token, group_id, no_cache=force)
    except NapCatError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    qq_ids = {
        str(item.get("user_id"))
        for item in raw
        if item.get("user_id") is not None
    }
    site_by_qq: dict[str, Member] = {}
    if qq_ids:
        rows = (
            db.query(Member)
            .options(joinedload(Member.user))
            .filter(Member.qq_number.in_(qq_ids))
            .all()
        )
        for m in rows:
            if m.qq_number:
                site_by_qq[m.qq_number] = m

    members: list[NapCatGroupMemberOut] = []
    for item in raw:
        uid = item.get("user_id")
        if uid is None:
            continue
        qq = str(uid)
        site = site_by_qq.get(qq)
        role = str(item.get("role") or "member")
        members.append(
            NapCatGroupMemberOut(
                user_id=qq,
                nickname=str(item.get("nickname") or ""),
                card=str(item.get("card") or ""),
                role=_role_label(role),
                title=str(item.get("title") or ""),
                site_member=(
                    NapCatSiteMemberOut(
                        id=site.id,
                        nickname=site.nickname,
                        user_id=site.user_id,
                        qq_number=site.qq_number,
                    )
                    if site
                    else None
                ),
            )
        )

    # 群主/管理员靠前，站内用户其次，再按名片/昵称
    def _sort_key(m: NapCatGroupMemberOut) -> tuple:
        role_rank = {"群主": 0, "管理员": 1}.get(m.role, 2)
        site_rank = 0 if m.site_member else 1
        name = m.card or m.nickname or m.user_id
        return (role_rank, site_rank, name)

    members.sort(key=_sort_key)
    site_bound_count = sum(1 for m in members if m.site_member)
    return NapCatGroupMembersResponse(
        group_id=str(group_id),
        members=members,
        site_bound_count=site_bound_count,
    )
