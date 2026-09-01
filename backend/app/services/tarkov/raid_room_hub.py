"""联机大厅房间 WebSocket 广播（进程内；当前单 app 副本）。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class RaidRoomHub:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[WebSocket, int]] = {}
        self._seq: dict[str, int] = {}
        self._log_phases: dict[str, dict[int, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def next_seq(self, public_id: str) -> int:
        self._seq[public_id] = int(self._seq.get(public_id) or 0) + 1
        return self._seq[public_id]

    def known_public_ids(self) -> set[str]:
        return set(self._rooms.keys())

    def online_user_ids(self, public_id: str) -> set[int]:
        sockets = self._rooms.get(public_id) or {}
        return set(sockets.values())

    def log_phases(self, public_id: str) -> list[dict[str, Any]]:
        room = self._log_phases.get(public_id) or {}
        return [{"user_id": uid, **dict(payload)} for uid, payload in room.items()]

    def set_log_phase(
        self, public_id: str, user_id: int, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        room = self._log_phases.setdefault(public_id, {})
        room[int(user_id)] = dict(payload)
        return self.log_phases(public_id)

    async def join(self, public_id: str, ws: WebSocket, user_id: int) -> set[int]:
        self.bind_loop(asyncio.get_running_loop())
        async with self._lock:
            room = self._rooms.setdefault(public_id, {})
            room[ws] = user_id
            return set(room.values())

    async def leave(self, public_id: str, ws: WebSocket) -> set[int]:
        async with self._lock:
            room = self._rooms.get(public_id)
            if not room:
                return set()
            room.pop(ws, None)
            if not room:
                self._rooms.pop(public_id, None)
                return set()
            return set(room.values())

    async def broadcast(self, public_id: str, payload: dict[str, Any]) -> None:
        message = dict(payload)
        message.setdefault("seq", self.next_seq(public_id))
        async with self._lock:
            targets = list((self._rooms.get(public_id) or {}).keys())
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        if dead:
            async with self._lock:
                room = self._rooms.get(public_id)
                if room is None:
                    return
                for ws in dead:
                    room.pop(ws, None)
                if not room:
                    self._rooms.pop(public_id, None)

    def publish(self, public_id: str, payload: dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop
            if loop is None or not loop.is_running():
                return
            asyncio.run_coroutine_threadsafe(self.broadcast(public_id, payload), loop)
            return
        loop.create_task(self.broadcast(public_id, payload))


hub = RaidRoomHub()
