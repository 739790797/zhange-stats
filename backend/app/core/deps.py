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


def load_user_by_access_token(
    db: Session,
    token: str,
    *,
    with_member: bool = False,
) -> User | None:
    principal = decode_access_token(token)
    if principal is None:
        return None
    q = db.query(User)
    if with_member:
        q = q.options(joinedload(User.member))
    user = q.filter(User.id == principal.user_id).first()
    if not user or user_is_anonymized(user):
        return None
    return user


def access_token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> tuple[str | None, bool]:
    """Cookie 或 Bearer。via_bearer 供 CSRF：Cookie 会话的写操作才校验。"""
    if (
        credentials is not None
        and credentials.scheme.lower() == "bearer"
        and credentials.credentials
    ):
        return credentials.credentials, True
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip() or None
        return token, True
    token = (request.cookies.get(ACCESS_COOKIE) or "").strip() or None
    return token, False


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """公开接口：有有效会话则带上用户，否则当访客。不挂 HTTPBearer，避免 OpenAPI 标成需登录。"""
    token, _via_bearer = access_token_from_request(request)
    if not token:
        return None
    return load_user_by_access_token(db, token, with_member=True)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token, via_bearer = access_token_from_request(request, credentials)

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
    user = load_user_by_access_token(db, token, with_member=True)
    if user is None:
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
