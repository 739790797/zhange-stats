"""Profile / users / oauth API package (URL paths unchanged)."""
from fastapi import APIRouter

from app.api.profile import avatar, me, member_profile, qq, steam, users_admin

router = APIRouter(tags=["profile"])
for _sub in (users_admin, me, steam, qq, avatar, member_profile):
    router.include_router(_sub.router)

__all__ = ["router"]
