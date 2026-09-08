"""联机大厅房间 WebSocket 广播（进程内；当前单 app 副本）。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class RaidRoomHub:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[WebSocket, int]] = {}
        self._seq: dict[str, int] = {}
        self._log_phases: dict[str, dict[int, dict[str, Any]]] = {}
        self._player_fixes: dict[str, dict[int, dict[str, Any]]] = {}
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

    def player_fixes(self, public_id: str) -> list[dict[str, Any]]:
        room = self._player_fixes.get(public_id) or {}
        return [{"user_id": uid, **dict(payload)} for uid, payload in room.items()]

    def set_player_fix(
        self, public_id: str, user_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """记住最近一次截图坐标，供晚加入的手机端从 snapshot 拿到。"""
        body = dict(payload)
        body["at"] = int(time.time() * 1000)
        self._player_fixes.setdefault(public_id, {})[int(user_id)] = body
        return {"user_id": int(user_id), **body}

    def drop_offline_player_fixes(self, public_id: str, online_ids: set[int]) -> None:
        room = self._player_fixes.get(public_id)
        if not room:
            return
        keep = {int(uid) for uid in online_ids}
        for uid in [key for key in room if key not in keep]:
            room.pop(uid, None)
        if not room:
            self._player_fixes.pop(public_id, None)

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
                self._player_fixes.pop(public_id, None)
                return set()
            remaining = set(room.values())
            self.drop_offline_player_fixes(public_id, remaining)
            return remaining

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
                    self._player_fixes.pop(public_id, None)
                else:
                    self.drop_offline_player_fixes(public_id, set(room.values()))

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
