from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.public_url import resolve_backend_base, resolve_frontend_base
from app.core.rate_limit import auth_limiter, client_ip
from app.schemas import QqOAuthStartResponse, TokenResponse
from app.services.integrations_config import get_qq_credentials
from app.services.oauth_ticket import consume_oauth_ticket, prune_expired_oauth_tickets
from app.services.qq_oauth import (
    PURPOSE_LOGIN,
    QqOAuthError,
    build_qq_authorize_url,
    create_qq_oauth_state,
)

router = APIRouter()


class QqExchangeRequest(BaseModel):
    ticket: str = Field(min_length=16, max_length=128)


@router.get("/qq/oauth/start", response_model=QqOAuthStartResponse)
def qq_oauth_login_start(
    request: Request,
    db: Session = Depends(get_db),
) -> QqOAuthStartResponse:
    """未登录用户发起 QQ 登录 / 一键注册。"""
    ip = client_ip(request)
    auth_limiter.hit(f"qq-login:ip:{ip}", limit=20, window_sec=600)

    qq_app_id, qq_app_key = get_qq_credentials(db)
    if not qq_app_id or not qq_app_key:
        raise HTTPException(status_code=400, detail="未配置 QQ_APP_ID / QQ_APP_KEY")
    backend = resolve_backend_base(request)
    if not backend:
        raise HTTPException(
            status_code=400,
            detail="无法确定回调地址，请检查访问 Host 或配置 PUBLIC_BACKEND_URL",
        )
    frontend = resolve_frontend_base(request, backend=backend)
    try:
        state = create_qq_oauth_state(
            purpose=PURPOSE_LOGIN,
            frontend=frontend,
            backend=backend,
        )
        url = build_qq_authorize_url(state=state, backend=backend)
    except QqOAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return QqOAuthStartResponse(url=url)


@router.post("/qq/exchange", response_model=TokenResponse)
def qq_oauth_exchange(
    body: QqExchangeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """用回调 URL 中的一次性 ticket 换取 JWT（不把 access_token 放进 query）。"""
    ip = client_ip(request)
    auth_limiter.hit(f"qq-exchange:ip:{ip}", limit=30, window_sec=600)
    prune_expired_oauth_tickets(db)
    try:
        token = consume_oauth_ticket(db, body.ticket)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TokenResponse(access_token=token)
