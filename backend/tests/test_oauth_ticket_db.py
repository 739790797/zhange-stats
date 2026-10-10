"""oauth_exchange_tickets 内存 SQLite 集成测。"""

from datetime import timedelta

import pytest
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
    row = db.get(OAuthExchangeTicket, code)
    assert row is not None
    assert row.access_token.startswith("enc:v1:")
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


def test_two_requests_racing_for_one_ticket_get_one_token(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'tickets.db'}")
    OAuthExchangeTicket.__table__.create(bind=engine)
    make = sessionmaker(bind=engine)
    with make() as setup:
        code = issue_oauth_ticket(setup, "jwt-race")
        setup.commit()

    first, second = make(), make()
    try:
        # 两个请求都已读到这张票，再先后去核销；留住引用，否则 identity map 是弱引用，第二次 get 会重新查库
        loaded = [first.get(OAuthExchangeTicket, code), second.get(OAuthExchangeTicket, code)]
        assert all(row is not None for row in loaded)
        assert consume_oauth_ticket(first, code) == "jwt-race"
        first.commit()
        with pytest.raises(ValueError, match="无效或已使用"):
            consume_oauth_ticket(second, code)
        second.commit()
    finally:
        first.close()
        second.close()
    with make() as check:
        assert check.get(OAuthExchangeTicket, code) is None
    engine.dispose()


def test_consume_leaves_no_stale_row_in_the_session() -> None:
    db = _session()
    code = issue_oauth_ticket(db, "jwt-once")
    db.commit()
    assert consume_oauth_ticket(db, code) == "jwt-once"
    with pytest.raises(ValueError, match="无效或已使用"):
        consume_oauth_ticket(db, code)
    db.commit()
    assert db.get(OAuthExchangeTicket, code) is None


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
