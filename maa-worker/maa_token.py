"""与 app 侧 app.core.maa_token 保持同一算法。"""

from __future__ import annotations

import hashlib
import hmac


def resolve_maa_worker_token(explicit: str | None, secret_key: str | None) -> str:
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
