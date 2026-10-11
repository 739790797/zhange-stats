"""追放社区凭证只存口令 MD5：登录 / 重登 / 旧明文凭证在下次使用时改写。"""

from __future__ import annotations

import hashlib
import json
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core import crypto_secret
from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.database import Base
from app.models.exilium import ExiliumBind
from app.models.member import Member
from app.services.exilium import attendance, checkin, client
from app.services.exilium.client import ExiliumApiError, ExiliumCredentials

ACCOUNT = "player@example.com"
PASSWORD = "plain-Secret-42"
DIGEST = hashlib.md5(PASSWORD.encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    holder = SimpleNamespace(SECRET_KEY="unit-test-secret-key-0123456789abcdef")
    monkeypatch.setattr(crypto_secret, "get_settings", lambda: holder)


@pytest.fixture
def login_calls(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    def fake_http(method, path, *, token=None, body=None, timeout=None):
        calls.append({"method": method, "path": path, "body": body})
        return {"account": {"token": f"tok-{len(calls)}"}}

    monkeypatch.setattr(client, "_http", fake_http)
    monkeypatch.setattr(client, "enrich_user_info", lambda creds: creds)
    return calls


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    session.add(Member(id=1, nickname="m1"))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _stored_payload(db, bind_id: int) -> dict:
    db.expire_all()
    return json.loads(decrypt_secret(db.get(ExiliumBind, bind_id).credentials_enc))


def test_password_login_keeps_only_the_digest(login_calls, caplog) -> None:
    caplog.set_level(logging.DEBUG)

    creds = client.login_with_password(ACCOUNT, PASSWORD)

    assert creds.password_md5 == DIGEST
    stored = json.dumps(creds.to_dict())
    assert PASSWORD not in stored
    assert "password" not in creds.to_dict()
    assert login_calls[0]["body"]["passwd"] == client._aes_encrypt(DIGEST)
    assert PASSWORD not in caplog.text and DIGEST not in caplog.text


def test_login_with_saved_digest_sends_the_same_passwd(login_calls) -> None:
    client.login_with_password(ACCOUNT, PASSWORD)
    creds = client.login_with_password(ACCOUNT, password_md5=DIGEST)

    assert login_calls[0]["body"]["passwd"] == login_calls[1]["body"]["passwd"]
    assert creds.password_md5 == DIGEST


def test_login_requires_a_password_or_digest(login_calls) -> None:
    with pytest.raises(ExiliumApiError):
        client.login_with_password(ACCOUNT)
    assert login_calls == []


def test_expired_token_relogs_with_the_saved_digest(monkeypatch) -> None:
    seen: list[tuple[tuple, dict]] = []

    def expired(_creds):
        raise ExiliumApiError("token 已失效")

    def relogin(*args, **kwargs):
        seen.append((args, kwargs))
        return ExiliumCredentials(token="fresh", account_name=ACCOUNT, password_md5=DIGEST)

    monkeypatch.setattr(attendance, "enrich_user_info", expired)
    monkeypatch.setattr(attendance, "login_with_password", relogin)

    out = attendance.ensure_session(
        ExiliumCredentials(token="stale", account_name=ACCOUNT, password_md5=DIGEST)
    )

    assert out.token == "fresh"
    assert seen == [((ACCOUNT,), {"password_md5": DIGEST})]


def test_bind_with_password_stores_no_plaintext(db, login_calls, monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(checkin, "after_bind", lambda *_a: None)

    bind = checkin.bind_with_password(db, db.get(Member, 1), ACCOUNT, PASSWORD)

    payload = _stored_payload(db, bind.id)
    assert payload["password_md5"] == DIGEST
    assert "password" not in payload
    assert PASSWORD not in caplog.text and DIGEST not in caplog.text


def test_legacy_plaintext_blob_is_rewritten_on_next_use(db, monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    legacy = {"token": "t0", "account_name": ACCOUNT, "password": PASSWORD, "user_id": "u1"}
    bind = ExiliumBind(
        member_id=1,
        credentials_enc=encrypt_secret(json.dumps(legacy)),
        auto_checkin=False,
    )
    db.add(bind)
    db.commit()
    monkeypatch.setattr(checkin, "ensure_session", lambda creds: creds)

    working = checkin._session_for_bind(db, bind).creds

    assert working.password_md5 == DIGEST
    payload = _stored_payload(db, bind.id)
    assert payload == {
        "token": "t0",
        "account_name": ACCOUNT,
        "password_md5": DIGEST,
        "user_id": "u1",
    }
    assert db.get(ExiliumBind, bind.id).phone_mask == client.mask_account(ACCOUNT)
    assert PASSWORD not in caplog.text and DIGEST not in caplog.text


def test_legacy_rewrite_yields_to_a_concurrent_rebind(db) -> None:
    legacy = {"token": "t0", "account_name": ACCOUNT, "password": PASSWORD}
    bind = ExiliumBind(
        member_id=1, credentials_enc=encrypt_secret(json.dumps(legacy)), auto_checkin=False
    )
    db.add(bind)
    db.commit()
    db.refresh(bind)
    rebound = encrypt_secret(json.dumps({"token": "t9", "password_md5": "f" * 32}))
    # 库里已被重新绑定，内存里的 bind 还是旧密文：CAS 落空，不能覆盖新凭证
    db.query(ExiliumBind).filter(ExiliumBind.id == bind.id).update(
        {"credentials_enc": rebound}, synchronize_session=False
    )

    checkin._drop_plaintext_password(db, bind)

    assert _stored_payload(db, bind.id) == {"token": "t9", "password_md5": "f" * 32}
