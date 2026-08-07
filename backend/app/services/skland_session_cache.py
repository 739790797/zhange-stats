"""森空岛 Cred 会话短 TTL 缓存（只缓存 cred/sign_token，不落库）。"""

from __future__ import annotations

import hashlib
import json
import logging

from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.services.skland_client import SklandSession

logger = logging.getLogger(__name__)

# 与社区（littleclaw Redis）同级：减少每次 status/checkin 的 grant→cred
SESSION_TTL_SECONDS = 20 * 60
_KEY_PREFIX = "skland:cred:"


def _token_fp(hg_token: str) -> str:
    return hashlib.sha256(hg_token.encode("utf-8")).hexdigest()[:24]


def _cache_key(member_id: int) -> str:
    return f"{_KEY_PREFIX}{int(member_id)}"


def get_cached_skland_session(member_id: int, hg_token: str) -> SklandSession | None:
    raw = ephemeral_get(_cache_key(member_id))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        invalidate_skland_session(member_id)
        return None
    if not isinstance(payload, dict):
        invalidate_skland_session(member_id)
        return None
    if str(payload.get("fp") or "") != _token_fp(hg_token):
        invalidate_skland_session(member_id)
        return None
    cred = str(payload.get("cred") or "").strip()
    sign_token = str(payload.get("sign_token") or "").strip()
    if not cred or not sign_token:
        invalidate_skland_session(member_id)
        return None
    user_id = str(payload.get("user_id") or "").strip() or None
    return SklandSession(cred=cred, sign_token=sign_token, user_id=user_id)


def put_cached_skland_session(
    member_id: int, hg_token: str, session: SklandSession
) -> None:
    payload = {
        "fp": _token_fp(hg_token),
        "cred": session.cred,
        "sign_token": session.sign_token,
        "user_id": session.user_id or "",
    }
    try:
        ephemeral_set(
            _cache_key(member_id),
            json.dumps(payload, separators=(",", ":")),
            ttl_sec=SESSION_TTL_SECONDS,
        )
    except Exception:  # noqa: BLE001
        logger.exception("skland session cache put failed member_id=%s", member_id)


def invalidate_skland_session(member_id: int) -> None:
    ephemeral_delete(_cache_key(member_id))
