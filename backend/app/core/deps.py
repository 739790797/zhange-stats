from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.session_cookies import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    SAFE_METHODS,
    csrf_tokens_match,
)
from app.models.member import Member
from app.models.user import User
from app.services.account_anonymize import user_is_anonymized
from app.services.member_sync import ensure_user_member
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    via_bearer = False
    token: str | None = None
    if (
        credentials is not None
        and credentials.scheme.lower() == "bearer"
        and credentials.credentials
    ):
        token = credentials.credentials
        via_bearer = True
    else:
        token = (request.cookies.get(ACCESS_COOKIE) or "").strip() or None

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或令牌无效",
        )
    if not via_bearer and request.method.upper() not in SAFE_METHODS:
        cookie = request.cookies.get(CSRF_COOKIE)
        header = request.headers.get(CSRF_HEADER)
        if not csrf_tokens_match(cookie, header):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF 校验失败",
            )
    principal = decode_access_token(token)
    if not principal or (principal.user_id is None and not principal.username):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或令牌无效",
        )
    q = db.query(User).options(joinedload(User.member))
    if principal.user_id is not None:
        user = q.filter(User.id == principal.user_id).first()
    else:
        user = q.filter(User.username == principal.username).first()
    if not user or user_is_anonymized(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或令牌无效",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


def require_user_member(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Member:
    member = user.member
    if member is None:
        member = ensure_user_member(db, user)
    else:
        name = user.display_name or user.username
        if member.nickname != name:
            member.nickname = name
    if member is None:
        raise HTTPException(status_code=400, detail="用户尚未关联成员档案")
    return member
