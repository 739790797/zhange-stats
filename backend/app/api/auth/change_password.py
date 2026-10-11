from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth.schemas import PASSWORD_INPUT_MAX
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import (
    auth_limiter,
    clear_login_failures,
    client_ip,
    ensure_login_not_locked,
    record_login_failure,
)
from app.core.security import bump_token_version, hash_password, verify_login_password
from app.core.session_cookies import issue_session
from app.models.user import User
from app.services.auth_config import get_min_password_length
from app.services.password_policy import (
    PasswordPolicyError,
    invalidate_weak_password_cache,
    validate_password,
)

router = APIRouter()

_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,31}$")


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_INPUT_MAX)
    new_password: str = Field(min_length=1, max_length=PASSWORD_INPUT_MAX)


class ChangeUsernameBody(BaseModel):
    new_username: str = Field(min_length=3, max_length=32)
    current_password: str = Field(min_length=1, max_length=PASSWORD_INPUT_MAX)


class ChangeUsernameResponse(BaseModel):
    ok: bool = True
    message: str
    username: str


class PasswordPolicyOut(BaseModel):
    min_password_length: int = 8


def _normalize_username(raw: str) -> str:
    name = (raw or "").strip()
    if not _USERNAME_RE.fullmatch(name):
        raise HTTPException(
            status_code=400,
            detail="用户名须以字母开头，仅含字母/数字/下划线，长度 3～32",
        )
    return name


@router.get("/password-policy", response_model=PasswordPolicyOut)
def get_password_policy(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return {"min_password_length": get_min_password_length(db)}


@router.post("/change-password")
def change_password(
    body: ChangePasswordBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    ip = client_ip(request)
    ensure_login_not_locked(current.username, ip)
    auth_limiter.hit(f"change-password:uid:{current.id}", limit=10, window_sec=600)
    if not verify_login_password(body.current_password, current.password_hash):
        record_login_failure(current.username, ip)
        raise HTTPException(status_code=400, detail="当前密码不正确")
    clear_login_failures(current.username, ip)
    try:
        new_password = validate_password(
            body.new_password,
            username=current.username,
            min_length=get_min_password_length(db),
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.current_password == new_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    invalidate_weak_password_cache(current.password_hash)
    current.password_hash = hash_password(new_password)
    # 其他设备上的旧会话一并作废；本次响应换发新 ver 的令牌，当前设备不掉线
    bump_token_version(current)
    db.commit()
    issue_session(response, request, current)
    return {"ok": True, "message": "密码已更新"}


@router.post("/change-username", response_model=ChangeUsernameResponse)
def change_username(
    body: ChangeUsernameBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ChangeUsernameResponse:
    ip = client_ip(request)
    ensure_login_not_locked(current.username, ip)
    auth_limiter.hit(f"change-username:uid:{current.id}", limit=10, window_sec=600)
    if not verify_login_password(body.current_password, current.password_hash):
        record_login_failure(current.username, ip)
        raise HTTPException(status_code=400, detail="当前密码不正确")
    clear_login_failures(current.username, ip)
    new_username = _normalize_username(body.new_username)
    if new_username.lower() == current.username.lower():
        raise HTTPException(status_code=400, detail="新用户名与当前相同")
    taken = (
        db.query(User)
        .filter(User.username == new_username, User.id != current.id)
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="该用户名已被占用")
    current.username = new_username
    db.commit()
    issue_session(response, request, current)
    return ChangeUsernameResponse(message="用户名已更新", username=current.username)
