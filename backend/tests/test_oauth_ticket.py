"""oauth ticket：空码失败 + Fernet 落库往返。"""

from datetime import timedelta

import pytest

from app.core.crypto_secret import decrypt_secret
from app.core.timeutil import now_naive
from app.services.oauth_ticket import consume_oauth_ticket, issue_oauth_ticket


def test_consume_empty_raises() -> None:
    class DummySession:
        def get(self, *_a, **_k):
            return None

        def delete(self, *_a, **_k):
            return None

        def flush(self):
            return None

    with pytest.raises(ValueError, match="缺少"):
        consume_oauth_ticket(DummySession(), "")  # type: ignore[arg-type]


def test_issue_stores_encrypted_token(monkeypatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-for-oauth-ticket")
    get_settings.cache_clear()

    stored: dict = {}

    class DummySession:
        def add(self, row):
            stored["row"] = row

        def flush(self):
            return None

        def get(self, _cls, code):
            row = stored.get("row")
            if row is None or row.code != code:
                return None
            return row

        def delete(self, row):
            if stored.get("row") is row:
                stored.pop("row", None)

    db = DummySession()
    jwt = "eyJhbGciOiJIUzI1NiJ9.payload.sig"
    code = issue_oauth_ticket(db, jwt)  # type: ignore[arg-type]
    row = stored["row"]
    assert row.access_token.startswith("enc:v1:")
    assert decrypt_secret(row.access_token) == jwt
    # 未过期
    row.expires_at = now_naive() + timedelta(seconds=60)
    out = consume_oauth_ticket(db, code)  # type: ignore[arg-type]
    assert out == jwt
    assert "row" not in stored
    get_settings.cache_clear()
