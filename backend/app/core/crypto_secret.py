"""Fernet helpers for secrets stored in system_config."""

from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.biz_logging import log_until_change
from app.core.config import get_settings
from app.core.key_derivation import PURPOSE_FERNET, derive_key

logger = logging.getLogger("zhange.crypto")

_PREFIX = "enc:v1:"
_DECRYPT_FAILED_KEY = "crypto_secret:decrypt_failed"


@lru_cache(maxsize=4)
def _fernet_for(secret: str) -> MultiFernet:
    # 新密文用 HKDF 子密钥；旧版 sha256(SECRET_KEY) 只用于解历史密文，前缀仍是 enc:v1:。
    primary = Fernet(base64.urlsafe_b64encode(derive_key(secret, PURPOSE_FERNET)))
    legacy = Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest()))
    return MultiFernet([primary, legacy])


def _fernet() -> MultiFernet:
    return _fernet_for(get_settings().SECRET_KEY)


def encrypt_secret(plain: str) -> str:
    value = (plain or "").strip()
    if not value:
        return ""
    if value.startswith(_PREFIX):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt_secret(stored: str) -> str:
    value = stored or ""
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX) :].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        log_until_change(
            logger,
            _DECRYPT_FAILED_KEY,
            "credential decrypt failed (SECRET_KEY changed or ciphertext corrupt); stored secret treated as empty",
        )
        return ""
