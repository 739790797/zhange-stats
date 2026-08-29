"""战局准备房间 WebSocket：首包 JWT 鉴权，之后只推送。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, joinedload

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from app.services.platform_features import is_feature_enabled
from app.services.tarkov import raid_rooms as rooms_svc
from app.services.tarkov.raid_room_hub import hub

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404

_pending_idle_leave: dict[tuple[str, int], asyncio.Task] = {}


def _load_user(token: str) -> User:
    principal = decode_access_token(token)
    if not principal or (principal.user_id is None and not principal.username):
        raise PermissionError("unauth")
    db: Session = SessionLocal()
    try:
        if not is_feature_enabled(db, "guides.tarkov"):
            raise PermissionError("feature")
        query = db.query(User).options(joinedload(User.member))
        if principal.user_id is not None:
            user = query.filter(User.id == principal.user_id).first()
        else:
            user = query.filter(User.username == principal.username).first()
        if user is None:
            raise PermissionError("unauth")
        db.expunge(user)
        return user
    finally:
        db.close()


def _publish_reaped(reaped: list[tuple[str, list[int], dict[str, Any]]]) -> None:
    for pid, user_ids, snap in reaped:
        for uid in user_ids:
            hub.publish(
                pid,
                {"event": "member_leave", "snapshot": snap, "user_id": uid},
            )


def _snapshot(public_id: str, user: User) -> dict[str, Any]:
    db: Session = SessionLocal()
    try:
        reaped = rooms_svc.reap_idle_members(db)
        data = rooms_svc.get_room(
            db,
            public_id,
            user,
            online_user_ids=hub.online_user_ids(public_id),
        )
        db.commit()
        _publish_reaped(reaped)
        return data
    except rooms_svc.RaidRoomError:
        db.rollback()
        raise
    finally:
        db.close()


def _touch_presence(public_id: str, user: User) -> None:
    db: Session = SessionLocal()
    try:
        rooms_svc.touch_presence(db, public_id, user)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()


def _cancel_idle_leave(public_id: str, user_id: int) -> None:
    task = _pending_idle_leave.pop((public_id, user_id), None)
    if task is not None:
        task.cancel()


def _db_leave_if_idle(public_id: str, user_id: int) -> None:
    db: Session = SessionLocal()
    try:
        snap = rooms_svc.leave_if_idle(db, public_id, user_id)
        if snap is None:
            db.rollback()
            return
        db.commit()
        hub.publish(
            public_id,
            {"event": "member_leave", "snapshot": snap, "user_id": user_id},
        )
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.debug("raid room idle leave failed", exc_info=True)
    finally:
        db.close()


async def _run_idle_leave(public_id: str, user_id: int) -> None:
    try:
        await asyncio.sleep(rooms_svc.DISCONNECT_GRACE_SECONDS)
    except asyncio.CancelledError:
        return
    finally:
        _pending_idle_leave.pop((public_id, user_id), None)
    if user_id in hub.online_user_ids(public_id):
        return
    _db_leave_if_idle(public_id, user_id)


def _schedule_idle_leave(public_id: str, user_id: int) -> None:
    _cancel_idle_leave(public_id, user_id)
    _pending_idle_leave[(public_id, user_id)] = asyncio.create_task(
        _run_idle_leave(public_id, user_id)
    )


def _can_edit(public_id: str, user: User) -> bool:
    db: Session = SessionLocal()
    try:
        ok = rooms_svc.can_user_edit_room(db, public_id, user)
        db.commit()
        return ok
    except Exception:  # noqa: BLE001
        db.rollback()
        return False
    finally:
        db.close()


async def run_room_session(client: WebSocket, public_id: str) -> None:
    try:
        first = await asyncio.wait_for(client.receive_json(), timeout=10)
    except TimeoutError:
        await client.close(code=CLOSE_UNAUTHORIZED)
        return
    except WebSocketDisconnect:
        return
    except Exception:  # noqa: BLE001
        await client.close(code=CLOSE_UNAUTHORIZED)
        return
    if not isinstance(first, dict) or str(first.get("event") or "") != "auth":
        await client.close(code=CLOSE_UNAUTHORIZED)
        return
    token = str(first.get("token") or "").strip()
    try:
        user = _load_user(token)
    except PermissionError as exc:
        code = CLOSE_FORBIDDEN if str(exc) == "feature" else CLOSE_UNAUTHORIZED
        await client.close(code=code)
        return

    try:
        snapshot = _snapshot(public_id, user)
    except rooms_svc.RaidRoomError as exc:
        code = CLOSE_NOT_FOUND if exc.status_code == 404 else CLOSE_FORBIDDEN
        await client.close(code=code)
        return

    online = await hub.join(public_id, client, user.id)
    _cancel_idle_leave(public_id, user.id)
    await client.send_json(
        {"event": "snapshot", "seq": 0, "snapshot": snapshot, "online_user_ids": list(online)}
    )
    hub.publish(
        public_id,
        {"event": "presence", "online_user_ids": list(online)},
    )
    try:
        while True:
            raw = await client.receive_json()
            if not isinstance(raw, dict):
                continue
            event = str(raw.get("event") or "").strip()
            if event == "ping":
                _touch_presence(public_id, user)
                await client.send_json({"event": "pong"})
                continue
            if event == "draw_draft":
                # 连接时 snapshot.can_edit 可能过期；离开后不再广播草稿
                if not _can_edit(public_id, user):
                    continue
                draft = rooms_svc.parse_draw_draft(raw)
                if draft is None:
                    continue
                hub.publish(
                    public_id,
                    {
                        "event": "draw_draft",
                        "user_id": user.id,
                        "floor": draft["floor"],
                        "points": draft["points"],
                    },
                )
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.debug("raid room ws ended", exc_info=True)
    finally:
        online = await hub.leave(public_id, client)
        hub.publish(
            public_id,
            {"event": "presence", "online_user_ids": list(online)},
        )
        if user.id not in online:
            _schedule_idle_leave(public_id, user.id)
