"""米游社 App 扫码登录会话（短 TTL；Redis 可用时跨实例）。"""

from __future__ import annotations

import json
import logging
import time

from sqlalchemy.orm import Session

from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.models.member import Member
from app.services.mihoyo.auth import create_qr_login, query_qr_login
from app.services.mihoyo.checkin import bind_member_with_creds
from app.services.mihoyo.client import MihoyoApiError
from app.services.skland.qr import qr_image_data_url

logger = logging.getLogger(__name__)

QR_TTL_SECONDS = 180
_KEY_PREFIX = "mihoyo:qr:"


def _qr_key(scan_id: str) -> str:
    return f"{_KEY_PREFIX}{scan_id}"


def _load_pending(scan_id: str) -> dict | None:
    raw = ephemeral_get(_qr_key(scan_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        ephemeral_delete(_qr_key(scan_id))
        return None
    if not isinstance(data, dict):
        ephemeral_delete(_qr_key(scan_id))
        return None
    return data


def _save_pending(scan_id: str, data: dict, *, remaining_ttl: int | None = None) -> None:
    ttl = remaining_ttl if remaining_ttl is not None else QR_TTL_SECONDS
    ttl = max(1, int(ttl))
    ephemeral_set(
        _qr_key(scan_id),
        json.dumps(data, separators=(",", ":")),
        ttl_sec=ttl,
    )


def start_qr_bind(*, user_id: int, member: Member) -> dict:
    session = create_qr_login()
    ticket = session["ticket"]
    created_at = time.time()
    _save_pending(
        ticket,
        {
            "user_id": int(user_id),
            "member_id": int(member.id),
            "device_id": session["device_id"],
            "scan_url": session["scan_url"],
            "created_at": created_at,
            "completed": False,
        },
        remaining_ttl=QR_TTL_SECONDS + 30,
    )
    return {
        "scan_id": ticket,
        "scan_url": session["scan_url"],
        "qr_image": qr_image_data_url(session["scan_url"]),
        "expires_in": QR_TTL_SECONDS,
    }


def poll_qr_bind(db: Session, *, user_id: int, member: Member, scan_id: str) -> dict:
    pending = _load_pending(scan_id)
    if pending is None:
        return {"status": "expired", "message": "二维码已失效，请刷新后重试"}
    if int(pending.get("user_id") or 0) != user_id or int(
        pending.get("member_id") or 0
    ) != member.id:
        raise MihoyoApiError("无权使用该扫码会话")
    if pending.get("completed"):
        return {"status": "ok", "message": "绑定成功"}

    created_at = float(pending.get("created_at") or 0)
    if time.time() - created_at > QR_TTL_SECONDS:
        ephemeral_delete(_qr_key(scan_id))
        return {"status": "expired", "message": "二维码已过期，请刷新"}

    device_id = str(pending.get("device_id") or "")
    try:
        result = query_qr_login(device_id=device_id, ticket=scan_id)
    except MihoyoApiError as exc:
        return {"status": "error", "message": exc.message or "扫码失败"}
    except Exception:  # noqa: BLE001
        logger.exception("mihoyo qr poll unexpected error scan_id=%s", scan_id[:8])
        return {"status": "error", "message": "扫码状态查询失败，请刷新二维码重试"}

    status = str(result.get("status") or "")
    if status in ("waiting", "scanned", "expired", "cancelled", "error"):
        return {
            "status": "expired" if status in ("expired", "cancelled") else status,
            "message": str(result.get("message") or ""),
        }
    if status != "ok":
        return {"status": "error", "message": str(result.get("message") or "扫码失败")}

    creds = result.get("creds")
    if creds is None:
        return {"status": "error", "message": "扫码成功但未拿到凭证"}
    try:
        bind_member_with_creds(db, member, creds)
    except MihoyoApiError as exc:
        return {"status": "error", "message": exc.message or "绑定失败"}
    except Exception:  # noqa: BLE001
        logger.exception("mihoyo qr bind failed member_id=%s", member.id)
        db.rollback()
        return {"status": "error", "message": "绑定写入失败，请稍后重试"}
    ephemeral_delete(_qr_key(scan_id))
    return {"status": "ok", "message": "扫码绑定成功"}
