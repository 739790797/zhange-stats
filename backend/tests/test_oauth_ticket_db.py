"""oauth_exchange_tickets 内存 SQLite 集成测。"""

from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import now_naive
from app.models.oauth_ticket import OAuthExchangeTicket
from app.services.oauth_ticket import (
    consume_oauth_ticket,
    issue_oauth_ticket,
    prune_expired_oauth_tickets,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    OAuthExchangeTicket.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


def test_issue_and_consume_once() -> None:
    db = _session()
    code = issue_oauth_ticket(db, "jwt-token-abc")
    db.commit()
    assert len(code) >= 16
    token = consume_oauth_ticket(db, code)
    db.commit()
    assert token == "jwt-token-abc"
    try:
        consume_oauth_ticket(db, code)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_expired_ticket() -> None:
    db = _session()
    code = issue_oauth_ticket(db, "jwt-old")
    row = db.get(OAuthExchangeTicket, code)
    assert row is not None
    row.expires_at = now_naive() - timedelta(seconds=1)
    db.commit()
    try:
        consume_oauth_ticket(db, code)
        raised = False
    except ValueError as exc:
        raised = True
        assert "过期" in str(exc)
    assert raised


def test_prune_expired() -> None:
    db = _session()
    code = issue_oauth_ticket(db, "jwt-prune")
    row = db.get(OAuthExchangeTicket, code)
    assert row is not None
    row.expires_at = now_naive() - timedelta(minutes=1)
    db.commit()
    n = prune_expired_oauth_tickets(db)
    db.commit()
    assert n == 1
    assert db.get(OAuthExchangeTicket, code) is None
