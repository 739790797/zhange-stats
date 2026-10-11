"""从 SECRET_KEY 按用途派生独立子密钥（HKDF-SHA256），签名、OAuth state 与凭证加密互不共用一把钥匙。"""

from __future__ import annotations

from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PURPOSE_JWT = "jwt-v1"
PURPOSE_OAUTH_STATE = "oauth-state-v1"
PURPOSE_FERNET = "fernet-v1"

_SALT = b"zhange-stats/hkdf"


@lru_cache(maxsize=32)
def derive_key(secret: str, purpose: str, length: int = 32) -> bytes:
    if not purpose:
        raise ValueError("purpose is required")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=_SALT,
        info=purpose.encode("utf-8"),
    ).derive((secret or "").encode("utf-8"))
