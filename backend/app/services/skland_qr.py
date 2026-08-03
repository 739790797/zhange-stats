"""森空岛 App 扫码登录会话（内存态，绑定到当前用户）。"""

from __future__ import annotations

import base64
import io
import threading
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.member import Member
from app.services.skland_checkin import bind_skland
from app.services.skland_client import (
    SklandApiError,
    create_scan_login,
    poll_scan_status,
    token_by_scan_code,
)

QR_TTL_SECONDS = 180


@dataclass
class _PendingQr:
    user_id: int
    member_id: int
    device_id: str
    scan_url: str
    created_at: float
    completed: bool = False


_lock = threading.Lock()
_pending: dict[str, _PendingQr] = {}


def _purge_expired(now: float | None = None) -> None:
    ts = now if now is not None else time.time()
    dead = [
        sid
        for sid, row in _pending.items()
        if row.completed or ts - row.created_at > QR_TTL_SECONDS + 30
    ]
    for sid in dead:
        _pending.pop(sid, None)


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
    with _lock:
        _purge_expired()
        _pending[session.scan_id] = _PendingQr(
            user_id=user_id,
            member_id=member.id,
            device_id=device_id,
            scan_url=session.scan_url,
            created_at=time.time(),
        )
    return {
        "scan_id": session.scan_id,
        "scan_url": session.scan_url,
        "qr_image": qr_image_data_url(session.scan_url),
        "expires_in": QR_TTL_SECONDS,
    }


def poll_qr_bind(db: Session, *, user_id: int, member: Member, scan_id: str) -> dict:
    with _lock:
        _purge_expired()
        pending = _pending.get(scan_id)

    if pending is None:
        return {
            "status": "expired",
            "message": "二维码已失效，请刷新后重试",
        }
    if pending.user_id != user_id or pending.member_id != member.id:
        raise SklandApiError("无权使用该扫码会话")
    if pending.completed:
        return {"status": "ok", "message": "绑定成功"}

    if time.time() - pending.created_at > QR_TTL_SECONDS:
        with _lock:
            _pending.pop(scan_id, None)
        return {"status": "expired", "message": "二维码已过期，请刷新"}

    poll = poll_scan_status(pending.device_id, scan_id)
    if poll.status != "ready" or not poll.scan_code:
        return {
            "status": poll.status,
            "message": poll.message,
        }

    token = token_by_scan_code(pending.device_id, poll.scan_code)
    bind_skland(db, member, token)
    with _lock:
        row = _pending.get(scan_id)
        if row is not None:
            row.completed = True
            _pending.pop(scan_id, None)
    return {
        "status": "ok",
        "message": "扫码绑定成功",
    }
