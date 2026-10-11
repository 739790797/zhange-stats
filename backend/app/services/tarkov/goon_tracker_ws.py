"""三狗位置 WebSocket：首包 JWT 鉴权，之后只推送。"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.deps import load_user_by_access_token
from app.core.session_cookies import access_token_from_websocket
from app.models.user import User
from app.services.platform_features import is_feature_enabled
from app.services.tarkov import goon_tracker as goon_svc
from app.services.tarkov.goon_tracker_hub import CLOSE_SLOW_CONSUMER, hub
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
CLOSE_INTERNAL = 1011
# 客户端只发 auth / ping。
MAX_FRAME_CHARS = 16 * 1024


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


async def run_goon_session(client: WebSocket) -> None:
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
        await asyncio.to_thread(_load_user, token)
    except PermissionError as exc:
        code = CLOSE_FORBIDDEN if str(exc) == "feature" else CLOSE_UNAUTHORIZED
        await client.close(code=code)
        return

    await hub.join(client)
    pings = TokenBucket(0.5, 4)
    try:
        if not await send_json_timeout(client, goon_svc.snapshot_payload()):
            await close_quietly(client, CLOSE_SLOW_CONSUMER)
            return
        while True:
            raw = await receive_json_bounded(client, max_chars=MAX_FRAME_CHARS)
            if not isinstance(raw, dict):
                continue
            if str(raw.get("event") or "") == "ping" and pings.take():
                await send_json_timeout(client, {"event": "pong"})
    except WebSocketDisconnect:
        pass
    except FrameTooLarge:
        await close_quietly(client, CLOSE_TOO_LARGE)
    except Exception:  # noqa: BLE001
        logger.debug("goon tracker ws ended", exc_info=True)
        await close_quietly(client, CLOSE_INTERNAL)
    finally:
        await hub.leave(client)
