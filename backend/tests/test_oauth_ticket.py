"""oauth ticket：空码失败 + Fernet 落库形态（consume 生命周期见 test_oauth_ticket_db）。"""

import pytest

from app.core.crypto_secret import decrypt_secret
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

    db = DummySession()
    jwt = "eyJhbGciOiJIUzI1NiJ9.payload.sig"
    issue_oauth_ticket(db, jwt)  # type: ignore[arg-type]
    row = stored["row"]
    assert row.access_token.startswith("enc:v1:")
    assert decrypt_secret(row.access_token) == jwt
    get_settings.cache_clear()
