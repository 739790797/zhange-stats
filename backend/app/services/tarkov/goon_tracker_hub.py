"""三狗位置 WebSocket 广播（进程内；当前单 app 副本）。"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Coroutine
from typing import Any

from fastapi import WebSocket

from app.services.tarkov.ws_limits import close_quietly, send_json_timeout

logger = logging.getLogger(__name__)

CLOSE_SLOW_CONSUMER = 1013


class GoonTrackerHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        # 轮询线程 publish、事件循环 join/leave 都会碰；临界区里不 await。
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: set[asyncio.Task[Any]] = set()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def join(self, ws: WebSocket) -> None:
        self.bind_loop(asyncio.get_running_loop())
        with self._lock:
            self._clients.add(ws)

    async def leave(self, ws: WebSocket) -> None:
        with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        message = dict(payload)
        with self._lock:
            targets = list(self._clients)
        if not targets:
            return
        results = await asyncio.gather(*(send_json_timeout(ws, message) for ws in targets))
        dead = [ws for ws, ok in zip(targets, results, strict=True) if not ok]
        if not dead:
            return
        with self._lock:
            for ws in dead:
                self._clients.discard(ws)
        await asyncio.gather(*(close_quietly(ws, CLOSE_SLOW_CONSUMER) for ws in dead))

    def publish(self, payload: dict[str, Any]) -> None:
        self._spawn(self.broadcast(payload))

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop
            if loop is None or not loop.is_running():
                coro.close()
                return
            try:
                loop.call_soon_threadsafe(self._track, coro)
            except RuntimeError:
                coro.close()
            return
        self._track(coro)

    def _track(self, coro: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


hub = GoonTrackerHub()
