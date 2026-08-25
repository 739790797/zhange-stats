"""森空岛 App 扫码登录会话（短 TTL；Redis 可用时跨实例，否则进程内）。"""

from __future__ import annotations

import base64
import io
import json
import time
import uuid

from sqlalchemy.orm import Session

from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.models.member import Member
from app.services.skland.checkin import bind_skland
from app.services.skland.client import (
    SklandApiError,
    create_scan_login,
    poll_scan_status,
    token_by_scan_code,
)

QR_TTL_SECONDS = 180
_KEY_PREFIX = "skland:qr:"


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


def qr_image_data_url(content: str) -> str:
    import qrcode

    qr = qrcode.QRCode(version=None, box_size=6, border=2)
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def start_qr_bind(*, user_id: int, member: Member) -> dict:
    device_id = uuid.uuid4().hex
    session = create_scan_login(device_id)
    created_at = time.time()
    _save_pending(
        session.scan_id,
        {
            "user_id": int(user_id),
            "member_id": int(member.id),
            "device_id": device_id,
            "scan_url": session.scan_url,
            "created_at": created_at,
            "completed": False,
        },
        remaining_ttl=QR_TTL_SECONDS + 30,
    )
    return {
        "scan_id": session.scan_id,
        "scan_url": session.scan_url,
        "qr_image": qr_image_data_url(session.scan_url),
        "expires_in": QR_TTL_SECONDS,
    }


def poll_qr_bind(db: Session, *, user_id: int, member: Member, scan_id: str) -> dict:
    pending = _load_pending(scan_id)
    if pending is None:
        return {
            "status": "expired",
            "message": "二维码已失效，请刷新后重试",
        }
    if int(pending.get("user_id") or 0) != user_id or int(
        pending.get("member_id") or 0
    ) != member.id:
        raise SklandApiError("无权使用该扫码会话")
    if pending.get("completed"):
        return {"status": "ok", "message": "绑定成功"}

    created_at = float(pending.get("created_at") or 0)
    age = time.time() - created_at
    if age > QR_TTL_SECONDS:
        ephemeral_delete(_qr_key(scan_id))
        return {"status": "expired", "message": "二维码已过期，请刷新"}

    device_id = str(pending.get("device_id") or "")
    poll = poll_scan_status(device_id, scan_id)
    if poll.status != "ready" or not poll.scan_code:
        return {
            "status": poll.status,
            "message": poll.message,
        }

    token = token_by_scan_code(device_id, poll.scan_code)
    bind_skland(db, member, token)
    ephemeral_delete(_qr_key(scan_id))
    return {
        "status": "ok",
        "message": "扫码绑定成功",
    }
