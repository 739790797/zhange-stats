"""把 Pelican Wings 控制台 WebSocket 中继到战鸽（管理员）。"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Callable
from typing import Any

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from app.services.minecraft import pelican as pelican
from app.services.integrations_config import get_pelican_credentials
from app.services.platform_features import is_feature_enabled

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_CONFIGURED = 4000
MAX_COMMAND_LEN = 1024
FORWARD_EVENTS = {
    "console output",
    "install output",
    "daemon message",
    "daemon error",
    "status",
    "stats",
}


def parse_wings_message(raw: str | bytes) -> dict[str, Any] | None:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    event = str(data.get("event") or "").strip()
    if not event:
        return None
    args = data.get("args")
    if not isinstance(args, list):
        args = []
    return {"event": event, "args": args}


def client_command_to_wings(payload: dict[str, Any]) -> dict[str, Any] | None:
    if str(payload.get("event") or "") != "command":
        return None
    cmd = str(payload.get("command") or "").strip()
    if not cmd or len(cmd) > MAX_COMMAND_LEN:
        return None
    if any(ch in cmd for ch in ("\n", "\r", "\x00")):
        return None
    return {"event": "send command", "args": [cmd]}


def parse_stats_payload(args: list[Any]) -> dict[str, Any] | None:
    if not args:
        return None
    raw = args[0]
    data: Any = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    net = data.get("network") if isinstance(data.get("network"), dict) else {}
    return {
        "cpu": float(data.get("cpu_absolute") or 0),
        "memory_bytes": int(data.get("memory_bytes") or 0),
        "memory_limit_bytes": int(data.get("memory_limit_bytes") or 0),
        "disk_bytes": int(data.get("disk_bytes") or 0),
        "disk_limit_bytes": int(data.get("disk_limit_bytes") or 0),
        "network_rx_bytes": int(net.get("rx_bytes") or 0),
        "network_tx_bytes": int(net.get("tx_bytes") or 0),
        "uptime_ms": int(data.get("uptime") or 0),
        "state": str(data.get("state") or ""),
    }


def _wings_connect_kwargs(origin: str) -> dict[str, Any]:
    params = inspect.signature(websockets.connect).parameters
    kwargs: dict[str, Any] = {
        "max_size": 4 * 1024 * 1024,
        "open_timeout": 15,
    }
    if "reconnect_delays" in params:
        kwargs["reconnect_delays"] = lambda: iter(())
    if "origin" in params:
        kwargs["origin"] = origin
        if "additional_headers" in params:
            kwargs["additional_headers"] = {"User-Agent": pelican.USER_AGENT}
        elif "extra_headers" in params:
            kwargs["extra_headers"] = [("User-Agent", pelican.USER_AGENT)]
    elif "additional_headers" in params:
        kwargs["additional_headers"] = {
            "Origin": origin,
            "User-Agent": pelican.USER_AGENT,
        }
    elif "extra_headers" in params:
        kwargs["extra_headers"] = [
            ("Origin", origin),
            ("User-Agent", pelican.USER_AGENT),
        ]
    return kwargs


async def _connect_wings(socket_url: str, panel_origin: str) -> Any:
    return await websockets.connect(socket_url, **_wings_connect_kwargs(panel_origin))


def _load_console_session(token: str) -> tuple[str, str, str]:
    """校验管理员后返回 panel_base, client_token, server_uuid。"""
    principal = decode_access_token(token)
    if not principal or (principal.user_id is None and not principal.username):
        raise PermissionError("unauth")
    db: Session = SessionLocal()
    try:
        if not is_feature_enabled(db, "guides.minecraft"):
            raise PermissionError("feature")
        if principal.user_id is not None:
            user = db.query(User).filter(User.id == principal.user_id).first()
        else:
            user = db.query(User).filter(User.username == principal.username).first()
        if user is None:
            raise PermissionError("unauth")
        if not user.is_admin_user:
            raise PermissionError("forbidden")
        base, client_token, uuid = get_pelican_credentials(db)
        if not pelican.pelican_configured(base, client_token, uuid):
            raise RuntimeError("unconfigured")
        return base, client_token, uuid
    finally:
        db.close()


async def run_console_session(client: WebSocket) -> None:
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
    jwt = str(first.get("token") or "").strip()
    try:
        panel_base, client_token, server_uuid = await asyncio.to_thread(
            _load_console_session, jwt
        )
    except PermissionError as exc:
        code = str(exc)
        if code == "forbidden" or code == "feature":
            await client.close(code=CLOSE_FORBIDDEN)
        else:
            await client.close(code=CLOSE_UNAUTHORIZED)
        return
    except RuntimeError:
        await client.send_json({"event": "error", "message": "未配置 Pelican"})
        await client.close(code=CLOSE_NOT_CONFIGURED)
        return

    async def fetch_creds() -> tuple[str, str]:
        return await asyncio.to_thread(
            pelican.get_websocket, panel_base, client_token, server_uuid
        )

    try:
        socket_url, wings_token = await fetch_creds()
    except pelican.PelicanError as exc:
        await client.send_json({"event": "error", "message": exc.message})
        await client.close(code=1011)
        return

    meta = {
        "name": "",
        "address": "",
        "memory_limit_mb": 0,
        "cpu_limit": 0,
        "disk_limit_mb": 0,
    }
    try:
        server = await asyncio.to_thread(
            pelican.get_server, panel_base, client_token, server_uuid
        )
        meta = pelican.parse_server_meta(server)
    except pelican.PelicanError:
        pass

    wings = None
    try:
        wings = await _connect_wings(socket_url, panel_base)
        await wings.send(json.dumps({"event": "auth", "args": [wings_token]}))
        await client.send_json({"event": "ready", **meta})
        await _bridge(client, wings, fetch_creds)
    except WebSocketDisconnect:
        return
    except pelican.PelicanError as exc:
        try:
            await client.send_json({"event": "error", "message": exc.message})
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("minecraft console bridge failed: %s", exc)
        try:
            await client.send_json({"event": "error", "message": "控制台连接失败"})
        except Exception:  # noqa: BLE001
            pass
    finally:
        if wings is not None:
            try:
                await wings.close()
            except Exception:  # noqa: BLE001
                pass


async def _bridge(
    client: WebSocket,
    wings: Any,
    fetch_creds: Callable[[], Any],
) -> None:
    send_lock = asyncio.Lock()

    async def send_client(payload: dict[str, Any]) -> None:
        async with send_lock:
            await client.send_json(payload)

    async def send_wings(payload: dict[str, Any]) -> None:
        await wings.send(json.dumps(payload, ensure_ascii=False))

    async def refresh_auth() -> None:
        socket_url, token = await fetch_creds()
        await send_wings({"event": "auth", "args": [token]})
        logger.debug("minecraft console re-authed socket=%s", socket_url.split("?")[0])

    async def from_wings() -> None:
        async for raw in wings:
            parsed = parse_wings_message(raw)
            if parsed is None:
                continue
            event = parsed["event"]
            args = parsed["args"]
            if event == "auth success":
                await send_wings({"event": "send logs", "args": [None]})
                await send_wings({"event": "send stats", "args": [None]})
                continue
            if event in {"token expiring", "token expired", "jwt error"}:
                try:
                    await refresh_auth()
                except pelican.PelicanError as exc:
                    await send_client({"event": "error", "message": exc.message})
                continue
            if event not in FORWARD_EVENTS:
                continue
            if event == "stats":
                stats = parse_stats_payload(args)
                if stats:
                    await send_client({"event": "stats", **stats})
                continue
            if event == "status":
                state = str(args[0] if args else "")
                await send_client({"event": "status", "state": state})
                continue
            for item in args:
                line = item if isinstance(item, str) else str(item)
                if line:
                    await send_client({"event": event, "line": line})

    async def from_client() -> None:
        while True:
            incoming = await client.receive_json()
            if not isinstance(incoming, dict):
                continue
            wings_msg = client_command_to_wings(incoming)
            if wings_msg is None:
                continue
            await send_wings(wings_msg)

    wings_task = asyncio.create_task(from_wings())
    client_task = asyncio.create_task(from_client())
    done, pending = await asyncio.wait(
        {wings_task, client_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        exc = task.exception() if not task.cancelled() else None
        if isinstance(exc, WebSocketDisconnect):
            return
        if exc:
            raise exc
