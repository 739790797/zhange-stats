"""一次性 OAuth 换票（避免 JWT 出现在回调 URL）。落库 access_token 经 Fernet 加密。"""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive, to_naive
from app.models.oauth_ticket import OAuthExchangeTicket

TICKET_TTL_SECONDS = 120


def issue_oauth_ticket(db: Session, access_token: str) -> str:
    """写入一次性 ticket，返回可放进 redirect query 的不透明码。"""
    code = secrets.token_urlsafe(32)
    db.add(
        OAuthExchangeTicket(
            code=code,
            access_token=encrypt_secret(access_token),
            expires_at=now_naive() + timedelta(seconds=TICKET_TTL_SECONDS),
        )
    )
    db.flush()
    return code


def consume_oauth_ticket(db: Session, code: str) -> str:
    """核销 ticket，返回 JWT；失败抛 ValueError。"""
    raw = (code or "").strip()
    if not raw:
        raise ValueError("缺少换票码")
    row = db.get(OAuthExchangeTicket, raw)
    if row is None:
        raise ValueError("换票码无效或已使用")
    if to_naive(row.expires_at) < now_naive():
        db.delete(row)
        db.flush()
        raise ValueError("换票码已过期，请重新登录")
    token = decrypt_secret(row.access_token)
    db.delete(row)
    db.flush()
    if not token:
        raise ValueError("换票码无效或已使用")
    return token


def prune_expired_oauth_tickets(db: Session) -> int:
    cutoff = now_naive()
    deleted = (
        db.query(OAuthExchangeTicket)
        .filter(OAuthExchangeTicket.expires_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.flush()
    return int(deleted)
