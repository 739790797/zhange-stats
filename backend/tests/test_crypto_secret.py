"""凭证加密：HKDF 新钥加密、旧 sha256 密文仍可解、换钥解密失败只告警一次。"""

from __future__ import annotations

import base64
import hashlib
import logging
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core import crypto_secret
from app.core.biz_logging import clear_log_until_change
from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.key_derivation import PURPOSE_FERNET, derive_key

SECRET = "unit-test-secret-key-0123456789abcdef"


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    holder = SimpleNamespace(SECRET_KEY=SECRET)
    monkeypatch.setattr(crypto_secret, "get_settings", lambda: holder)
    clear_log_until_change(crypto_secret._DECRYPT_FAILED_KEY)
    yield holder
    clear_log_until_change(crypto_secret._DECRYPT_FAILED_KEY)


def _legacy_fernet(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest()))


def test_new_ciphertext_round_trips_with_hkdf_key() -> None:
    stored = encrypt_secret("  token-value  ")
    assert stored.startswith("enc:v1:")
    assert decrypt_secret(stored) == "token-value"

    token = stored[len("enc:v1:") :].encode("ascii")
    hkdf = Fernet(base64.urlsafe_b64encode(derive_key(SECRET, PURPOSE_FERNET)))
    assert hkdf.decrypt(token) == b"token-value"
    with pytest.raises(InvalidToken):
        _legacy_fernet(SECRET).decrypt(token)


def test_legacy_sha256_ciphertext_still_decrypts() -> None:
    legacy = _legacy_fernet(SECRET).encrypt(b"old-cred").decode("ascii")
    assert decrypt_secret(f"enc:v1:{legacy}") == "old-cred"


def test_encrypt_is_idempotent_and_plaintext_passthrough() -> None:
    stored = encrypt_secret("abc")
    assert encrypt_secret(stored) == stored
    assert encrypt_secret("   ") == ""
    assert decrypt_secret("") == ""
    assert decrypt_secret("plain-legacy") == "plain-legacy"


def test_wrong_key_returns_empty_and_warns_once(_fixed_secret, caplog) -> None:
    stored = encrypt_secret("super-secret-value")
    _fixed_secret.SECRET_KEY = "another-secret-key-after-reinstall"

    with caplog.at_level(logging.DEBUG, logger="zhange.crypto"):
        assert decrypt_secret(stored) == ""
        assert decrypt_secret(stored) == ""
        assert decrypt_secret("enc:v1:not-a-token") == ""

    warnings = [r for r in caplog.records if r.name == "zhange.crypto" and r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "decrypt failed" in warnings[0].getMessage()
    assert all("super-secret-value" not in r.getMessage() for r in caplog.records)
    assert all(stored not in r.getMessage() for r in caplog.records)
