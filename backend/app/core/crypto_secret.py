"""Fernet helpers for secrets stored in system_config."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


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
        return ""
