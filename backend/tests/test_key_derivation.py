"""HKDF 子密钥：同一用途稳定、不同用途互异、与原始 SECRET_KEY 不同。"""

from __future__ import annotations

import pytest

from app.core.key_derivation import (
    PURPOSE_FERNET,
    PURPOSE_JWT,
    PURPOSE_OAUTH_STATE,
    derive_key,
)


def test_stable_per_purpose() -> None:
    assert derive_key("s3cret", PURPOSE_JWT) == derive_key("s3cret", PURPOSE_JWT)


def test_purposes_are_independent() -> None:
    keys = {derive_key("s3cret", p) for p in (PURPOSE_JWT, PURPOSE_OAUTH_STATE, PURPOSE_FERNET)}
    assert len(keys) == 3
    assert all(len(k) == 32 for k in keys)
    assert b"s3cret" not in keys


def test_secret_changes_key() -> None:
    assert derive_key("a", PURPOSE_JWT) != derive_key("b", PURPOSE_JWT)


def test_empty_purpose_rejected() -> None:
    with pytest.raises(ValueError):
        derive_key("s3cret", "")
