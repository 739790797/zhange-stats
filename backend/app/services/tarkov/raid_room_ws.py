"""联机大厅房间 WebSocket：首包 JWT 鉴权，之后只推送。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.deps import load_user_by_access_token
from app.core.session_cookies import access_token_from_websocket
from app.models.user import User
from app.services.platform_features import is_feature_enabled
from app.services.tarkov import raid_rooms as rooms_svc
from app.services.tarkov.raid_room_hub import CLOSE_SLOW_CONSUMER, hub, presence_client
from app.services.tarkov.ws_limits import (
    CLOSE_TOO_LARGE,
    FrameTooLarge,
    TokenBucket,
    close_quietly,
    receive_json_bounded,
    send_json_timeout,
)

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404
# 笔画草稿最多 160 点，正常帧只有几 KB。
MAX_FRAME_CHARS = 256 * 1024
SEAT_RECHECK_SEC = 10.0
TOUCH_MIN_INTERVAL_SEC = 15.0


def _load_user(token: str) -> User:
    db: Session = SessionLocal()
    try:
        if not is_feature_enabled(db, "guides.tarkov"):
            raise PermissionError("feature")
        user = load_user_by_access_token(db, token, with_member=True)
        if user is None:
            raise PermissionError("unauth")
        db.expunge(user)
        return user
    finally:
        db.close()


def _snapshot(public_id: str, user: User) -> dict[str, Any]:
    db: Session = SessionLocal()
    try:
        return rooms_svc.run_in_room_tx(
            db,
            lambda: rooms_svc.get_room(
                db,
                public_id,
                user,
                online_user_ids=hub.online_user_ids(public_id),
            ),
        )
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


def _is_member(public_id: str, user: User) -> bool:
    db: Session = SessionLocal()
    try:
        ok = rooms_svc.is_room_member(db, public_id, user)
        db.commit()
        return ok
    except Exception:  # noqa: BLE001
        db.rollback()
        return False
    finally:
        db.close()


def _presence(public_id: str) -> dict[str, Any]:
    return {
        "event": "presence",
        "online_user_ids": list(hub.online_user_ids(public_id)),
        "online_clients": hub.online_clients(public_id),
    }


def _event_buckets() -> dict[str, TokenBucket]:
    """前端草稿约 48ms 一帧、心跳 25s 一次；超出的帧直接丢弃。"""
    return {
        "ping": TokenBucket(0.5, 4),
        "view_map": TokenBucket(2, 10),
        "draw_draft": TokenBucket(25, 40),
        "player_fix": TokenBucket(1, 5),
        "log_phase": TokenBucket(2, 10),
    }


class _SeatCheck:
    """单连接的入座复核。离座会直接 evict socket，这里只是隔一段时间再查一次库兜底。"""

    def __init__(self, public_id: str, user: User) -> None:
        self.public_id = public_id
        self.user = user
        self._ok_until = 0.0
        self._touched_at = 0.0

    def mark_ok(self) -> None:
        self._ok_until = time.monotonic() + SEAT_RECHECK_SEC

    async def ok(self) -> bool:
        now = time.monotonic()
        if now < self._ok_until:
            return True
        seated = await asyncio.to_thread(_is_member, self.public_id, self.user)
        self._ok_until = now + SEAT_RECHECK_SEC if seated else 0.0
        return seated

    async def touch(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._touched_at < TOUCH_MIN_INTERVAL_SEC:
            return
        self._touched_at = now
        await asyncio.to_thread(_touch_ws_member, self.public_id, self.user)


async def _drop_session(client: WebSocket, public_id: str, code: int) -> None:
    await hub.leave(public_id, client)
    hub.publish(public_id, _presence(public_id))
    await close_quietly(client, code)


async def run_room_session(client: WebSocket, public_id: str) -> None:
    try:
        first = await asyncio.wait_for(
            receive_json_bounded(client, max_chars=MAX_FRAME_CHARS), timeout=10
        )
    except TimeoutError:
        await client.close(code=CLOSE_UNAUTHORIZED)
        return
    except WebSocketDisconnect:
        return
    except FrameTooLarge:
        await client.close(code=CLOSE_TOO_LARGE)
        return
    except Exception:  # noqa: BLE001
        await client.close(code=CLOSE_UNAUTHORIZED)
        return
    if not isinstance(first, dict) or str(first.get("event") or "") != "auth":
        await client.close(code=CLOSE_UNAUTHORIZED)
        return
    token = access_token_from_websocket(client, first)
    try:
        user = await asyncio.to_thread(_load_user, token)
    except PermissionError as exc:
        code = CLOSE_FORBIDDEN if str(exc) == "feature" else CLOSE_UNAUTHORIZED
        await client.close(code=code)
        return

    try:
        snapshot = await asyncio.to_thread(_snapshot, public_id, user)
    except rooms_svc.RaidRoomError as exc:
        code = CLOSE_NOT_FOUND if exc.status_code == 404 else CLOSE_FORBIDDEN
        await client.close(code=code)
        return
    if not snapshot.get("is_member"):
        await client.close(code=CLOSE_FORBIDDEN)
        return

    online = await hub.join(public_id, client, user.id, presence_client(first.get("client")))
    seat = _SeatCheck(public_id, user)
    await seat.touch(force=True)
    try:
        snapshot = await asyncio.to_thread(_snapshot, public_id, user)
    except rooms_svc.RaidRoomError as exc:
        code = CLOSE_NOT_FOUND if exc.status_code == 404 else CLOSE_FORBIDDEN
        await _drop_session(client, public_id, code)
        return
    if not snapshot.get("is_member") or not hub.is_connected(public_id, client):
        await _drop_session(client, public_id, CLOSE_FORBIDDEN)
        return
    seat.mark_ok()
    sent = await send_json_timeout(
        client,
        {
            "event": "snapshot",
            "seq": 0,
            "snapshot": snapshot,
            "online_user_ids": list(online),
            "online_clients": hub.online_clients(public_id),
            "log_phases": hub.log_phases(public_id),
            "player_fixes": hub.player_fixes(public_id),
            "view_maps": hub.view_maps(public_id),
        },
    )
    if not sent:
        await _drop_session(client, public_id, CLOSE_SLOW_CONSUMER)
        return
    hub.publish(public_id, _presence(public_id))
    buckets = _event_buckets()
    try:
        while True:
            raw = await receive_json_bounded(client, max_chars=MAX_FRAME_CHARS)
            # 被 evict 的连接等 hub 发来关闭帧即可，期间的入站帧一律不处理。
            if not hub.is_connected(public_id, client):
                continue
            if not isinstance(raw, dict):
                continue
            event = str(raw.get("event") or "").strip()
            bucket = buckets.get(event)
            if bucket is None or not bucket.take():
                continue
            if event == "ping":
                await seat.touch()
                await send_json_timeout(client, {"event": "pong"})
                continue
            if event == "view_map":
                slug = rooms_svc.normalize_room_map_slug(
                    str(raw.get("map_id") or raw.get("map") or "")
                )
                if not slug or not await seat.ok():
                    continue
                hub.set_view_map(public_id, user.id, slug)
                hub.publish(
                    public_id,
                    {
                        "event": "view_map",
                        "user_id": user.id,
                        "map_slug": slug,
                        "view_maps": hub.view_maps(public_id),
                    },
                )
                continue
            if event == "draw_draft":
                view_map = hub.view_map_of(public_id, user.id)
                if not view_map or not await seat.ok():
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
                        "map_id": view_map,
                    },
                )
                continue
            if event == "player_fix":
                if not hub.view_map_of(public_id, user.id) or not await seat.ok():
                    continue
                fix = rooms_svc.parse_player_fix(raw)
                if fix is None:
                    continue
                stored = hub.set_player_fix(public_id, user.id, fix)
                hub.publish(
                    public_id,
                    {
                        "event": "player_fix",
                        **stored,
                    },
                )
                continue
            if event == "log_phase":
                if not await seat.ok():
                    continue
                phase = rooms_svc.parse_log_phase(raw)
                if phase is None:
                    continue
                phases = hub.set_log_phase(public_id, user.id, phase)
                changed = rooms_svc.note_view_map_from_phase(public_id, user.id, phase)
                payload: dict[str, Any] = {
                    "event": "log_phase",
                    "user_id": user.id,
                    "log_phases": phases,
                    **phase,
                }
                if changed:
                    payload["view_maps"] = hub.view_maps(public_id)
                hub.publish(public_id, payload)
    except WebSocketDisconnect:
        pass
    except FrameTooLarge:
        await close_quietly(client, CLOSE_TOO_LARGE)
    except Exception:  # noqa: BLE001
        logger.debug("raid room ws ended", exc_info=True)
    finally:
        await hub.leave(public_id, client)
        await seat.touch(force=True)
        hub.publish(public_id, _presence(public_id))
