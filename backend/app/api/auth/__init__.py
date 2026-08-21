"""Auth API package（URL 路径不变）。"""
from fastapi import APIRouter

from app.api.auth import (
    change_password,
    email_bind,
    login,
    me,
    qq_login,
    register,
    reset_password,
)
from app.api.auth.helpers import _gen_username

router = APIRouter(prefix="/auth", tags=["auth"])
for _sub in (
    register,
    login,
    qq_login,
    email_bind,
    me,
    change_password,
    reset_password,
):
    router.include_router(_sub.router)

__all__ = ["router", "_gen_username"]
