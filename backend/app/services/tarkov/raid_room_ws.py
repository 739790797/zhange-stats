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


def _snapshot(public_id: str, user: User) -> dict[str, Any]:
    db: Session = SessionLocal()
    try:
        data = rooms_svc.get_room(
            db,
            public_id,
            user,
            online_user_ids=hub.online_user_ids(public_id),
        )
        db.commit()
        return data
    except rooms_svc.RaidRoomError:
        db.rollback()
        raise
    finally:
        db.close()


def _touch_ws_member(public_id: str, user: User) -> None:
    db: Session = SessionLocal()
    try:
        rooms_svc.touch_member(db, public_id, user)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()


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
    _touch_ws_member(public_id, user)
    await client.send_json(
        {
            "event": "snapshot",
            "seq": 0,
            "snapshot": snapshot,
            "online_user_ids": list(online),
            "log_phases": hub.log_phases(public_id),
        }
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
                _touch_ws_member(public_id, user)
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
                continue
            if event == "player_fix":
                if not _can_edit(public_id, user):
                    continue
                fix = rooms_svc.parse_player_fix(raw)
                if fix is None:
                    continue
                hub.publish(
                    public_id,
                    {
                        "event": "player_fix",
                        "user_id": user.id,
                        **fix,
                    },
                )
                continue
            if event == "log_phase":
                phase = rooms_svc.parse_log_phase(raw)
                if phase is None:
                    continue
                phases = hub.set_log_phase(public_id, user.id, phase)
                hub.publish(
                    public_id,
                    {
                        "event": "log_phase",
                        "user_id": user.id,
                        "log_phases": phases,
                        **phase,
                    },
                )
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.debug("raid room ws ended", exc_info=True)
    finally:
        online = await hub.leave(public_id, client)
        _touch_ws_member(public_id, user)
        hub.publish(
            public_id,
            {"event": "presence", "online_user_ids": list(online)},
        )
