"""MAA Worker 与 app 共用的内部鉴权 token 解析。"""

from __future__ import annotations

import hashlib
import hmac


def resolve_maa_worker_token(explicit: str | None, secret_key: str | None) -> str:
    """显式 MAA_WORKER_TOKEN 优先；否则用 SECRET_KEY 派生，便于生产免手填。"""
    token = (explicit or "").strip()
    if token:
        return token
    sk = (secret_key or "").strip()
    if not sk:
        return ""
    return hmac.new(
        sk.encode("utf-8"),
        b"zhange-maa-worker-v1",
        hashlib.sha256,
    ).hexdigest()
