"""联机大厅房间 WebSocket 广播（进程内；当前单 app 副本）。"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Coroutine
from typing import Any

from fastapi import WebSocket

from app.services.tarkov.ws_limits import close_quietly, send_json_timeout

logger = logging.getLogger(__name__)

CLOSE_EVICTED = 4403
CLOSE_ROOM_GONE = 4404
CLOSE_SLOW_CONSUMER = 1013
# 超量连接：一个账号在一间房里最多 3 条 socket（网页 / 助手 / 多标签），整房最多 40 条。
# 每条连接各有一套令牌桶，不限量的话 N 条连接就是 N 倍画笔速率。
CLOSE_TOO_MANY_SOCKETS = 4429
MAX_SOCKETS_PER_USER = 3
MAX_SOCKETS_PER_ROOM = 40

_PRESENCE_CLIENTS = frozenset({"web", "desktop"})
_Seat = tuple[int, str]


class RoomSocketLimit(Exception):
    """同一账号 / 同一房间的连接数超上限；握手阶段以 4429 关闭。"""

    def __init__(self, scope: str) -> None:
        super().__init__(scope)
        self.scope = scope


def presence_client(raw: object) -> str:
    text = str(raw or "").strip().lower()
    return text if text in _PRESENCE_CLIENTS else ""


def _user_ids(room: dict[WebSocket, _Seat]) -> set[int]:
    return {int(user_id) for user_id, _client in room.values()}


class RaidRoomHub:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[WebSocket, _Seat]] = {}
        self._seq: dict[str, int] = {}
        self._log_phases: dict[str, dict[int, dict[str, Any]]] = {}
        self._player_fixes: dict[str, dict[int, dict[str, Any]]] = {}
        self._view_maps: dict[str, dict[int, str]] = {}
        # 按 seq 升序发送：HTTP 线程提交的顺序与物化 payload 的时刻可能错开，
        # 这里先把 payload 按 seq 排队，再一条条按序广播，客户端不会先收到旧状态。
        self._pending: dict[str, dict[int, dict[str, Any]]] = {}
        self._sent_seq: dict[str, int] = {}
        self._flushing: dict[str, bool] = {}
        # HTTP 工作线程和事件循环都会读写；临界区里不 await。
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: set[asyncio.Task[Any]] = set()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def next_seq(self, public_id: str) -> int:
        """占一个广播序号。房间写事务在锁内调用，序号顺序即提交顺序。

        序号**只增不减**，房间的 socket 走光也不清：清了以后新连接从 0 重新数，
        而前端只按 seq 判新旧（`isNewerRoomSnapshot`），重连后的快照会被自己手上的大 seq 挡掉。
        """
        with self._lock:
            self._seq[public_id] = int(self._seq.get(public_id) or 0) + 1
            return self._seq[public_id]

    def reserve_seq(self, public_id: str) -> int:
        """有听众才占号：没人听的房间不建 `_seq` 条目，否则写完就走人的房间会一直攒着。"""
        with self._lock:
            if not self._rooms.get(public_id):
                return 0
            self._seq[public_id] = int(self._seq.get(public_id) or 0) + 1
            return self._seq[public_id]

    def current_seq(self, public_id: str) -> int:
        """最近一次已占用的序号；读快照带上它，客户端据此丢弃更旧的帧。"""
        with self._lock:
            return int(self._seq.get(public_id) or 0)

    def known_public_ids(self) -> set[str]:
        with self._lock:
            return set(self._rooms.keys())

    def online_user_ids(self, public_id: str) -> set[int]:
        with self._lock:
            return _user_ids(self._rooms.get(public_id) or {})

    def is_connected(self, public_id: str, ws: WebSocket) -> bool:
        with self._lock:
            return ws in (self._rooms.get(public_id) or {})

    def online_clients(self, public_id: str) -> list[dict[str, Any]]:
        with self._lock:
            seats = list((self._rooms.get(public_id) or {}).values())
        grouped: dict[int, list[str]] = {}
        for user_id, client in seats:
            if not client:
                continue
            grouped.setdefault(int(user_id), []).append(client)
        return [
            {"user_id": user_id, "clients": sorted(clients)}
            for user_id, clients in sorted(grouped.items())
        ]

    def log_phases(self, public_id: str) -> list[dict[str, Any]]:
        with self._lock:
            room = dict(self._log_phases.get(public_id) or {})
        return [{"user_id": uid, **dict(payload)} for uid, payload in room.items()]

    def set_log_phase(
        self, public_id: str, user_id: int, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        with self._lock:
            room = self._log_phases.setdefault(public_id, {})
            room[int(user_id)] = dict(payload)
        return self.log_phases(public_id)

    def player_fixes(self, public_id: str) -> list[dict[str, Any]]:
        with self._lock:
            room = dict(self._player_fixes.get(public_id) or {})
        return [{"user_id": uid, **dict(payload)} for uid, payload in room.items()]

    def set_player_fix(
        self, public_id: str, user_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """记住最近一次截图坐标，供晚加入的手机端从 snapshot 拿到。"""
        body = dict(payload)
        body["at"] = int(time.time() * 1000)
        with self._lock:
            self._player_fixes.setdefault(public_id, {})[int(user_id)] = body
        return {"user_id": int(user_id), **body}

    def view_maps(self, public_id: str) -> list[dict[str, Any]]:
        with self._lock:
            room = dict(self._view_maps.get(public_id) or {})
        return [
            {"user_id": uid, "map_slug": slug}
            for uid, slug in sorted(room.items(), key=lambda item: item[0])
        ]

    def view_map_of(self, public_id: str, user_id: int) -> str:
        with self._lock:
            return str((self._view_maps.get(public_id) or {}).get(int(user_id)) or "")

    def set_view_map(self, public_id: str, user_id: int, map_slug: str) -> list[dict[str, Any]]:
        slug = str(map_slug or "").strip()
        with self._lock:
            room = self._view_maps.setdefault(public_id, {})
            if slug:
                room[int(user_id)] = slug
            else:
                room.pop(int(user_id), None)
            if not room:
                self._view_maps.pop(public_id, None)
        return self.view_maps(public_id)

    def _drop_member_live_locked(self, public_id: str, uid: int) -> None:
        for bucket in (self._view_maps, self._log_phases, self._player_fixes):
            room = bucket.get(public_id)
            if room is None:
                continue
            room.pop(uid, None)
            if not room:
                bucket.pop(public_id, None)

    def drop_offline_player_fixes(self, public_id: str, online_ids: set[int]) -> None:
        with self._lock:
            self._drop_offline_player_fixes_locked(public_id, online_ids)

    def _drop_offline_player_fixes_locked(self, public_id: str, online_ids: set[int]) -> None:
        room = self._player_fixes.get(public_id)
        if not room:
            return
        keep = {int(uid) for uid in online_ids}
        for uid in [key for key in room if key not in keep]:
            room.pop(uid, None)
        if not room:
            self._player_fixes.pop(public_id, None)

    def _forget_room_locked(self, public_id: str) -> None:
        """房间行没了（解散 / 清空）：进程内状态整份丢掉，seq 也归零。"""
        for bucket in (
            self._rooms,
            self._seq,
            self._log_phases,
            self._player_fixes,
            self._view_maps,
            self._pending,
            self._sent_seq,
            self._flushing,
        ):
            bucket.pop(public_id, None)

    def _forget_listeners_locked(self, public_id: str) -> None:
        """最后一条 socket 走了，但房间还在：只丢「连着的人才算数」的状态。

        `_seq` 与 `_view_maps` 留着：seq 清零会让重连的客户端把新快照当旧帧丢掉；
        查看图是座位的属性，只走 HTTP 的成员没有 socket，丢了就会收到「请先选择地图」。
        两者都在 `close_room`（房间真的没了）时一并清掉。
        """
        for bucket in (
            self._rooms,
            self._log_phases,
            self._player_fixes,
            self._pending,
            self._sent_seq,
            self._flushing,
        ):
            bucket.pop(public_id, None)

    async def join(self, public_id: str, ws: WebSocket, user_id: int, client: str = "") -> set[int]:
        """登记一条房间 socket。超量连接抛 `RoomSocketLimit`（握手侧以 4429 关闭）。

        先查再建：被拒时不留下空房间条目（否则没人听的房会在 `_rooms` 里攒着）。
        """
        self.bind_loop(asyncio.get_running_loop())
        uid = int(user_id)
        with self._lock:
            room = self._rooms.get(public_id)
            if room is None:
                room = {}
                self._rooms[public_id] = room
            elif len(room) >= MAX_SOCKETS_PER_ROOM:
                raise RoomSocketLimit("room")
            elif (
                sum(1 for seat_uid, _client in room.values() if seat_uid == uid)
                >= MAX_SOCKETS_PER_USER
            ):
                raise RoomSocketLimit("user")
            room[ws] = (uid, presence_client(client))
            return _user_ids(room)

    async def leave(self, public_id: str, ws: WebSocket) -> set[int]:
        with self._lock:
            room = self._rooms.get(public_id)
            if not room:
                return set()
            if ws not in room:
                return _user_ids(room)
            room.pop(ws, None)
            if not room:
                self._forget_listeners_locked(public_id)
                return set()
            remaining = _user_ids(room)
            self._drop_offline_player_fixes_locked(public_id, remaining)
            return remaining

    def evict(self, public_id: str, user_id: int, *, code: int = CLOSE_EVICTED) -> int:
        """离座后摘掉这个人的 socket 与实时状态。

        摘除在调用线程里同步完成，之后的 publish 不会再发给他；告别帧和关闭交给事件循环。
        """
        uid = int(user_id)
        with self._lock:
            room = self._rooms.get(public_id) or {}
            sockets = [ws for ws, (seat_uid, _client) in room.items() if seat_uid == uid]
            for ws in sockets:
                room.pop(ws, None)
            self._drop_member_live_locked(public_id, uid)
            if public_id in self._rooms and not room:
                # 房间可能还在（只是没人连了）：只丢听众状态，seq / 查看图留给 HTTP 成员与重连。
                self._forget_listeners_locked(public_id)
        if sockets:
            farewell = {"event": "member_leave", "user_id": uid}
            self._spawn(self._close_sockets(sockets, farewell, code))
        return len(sockets)

    def close_room(
        self,
        public_id: str,
        *,
        payload: dict[str, Any] | None = None,
        code: int = CLOSE_ROOM_GONE,
    ) -> int:
        """房间解散：清掉进程内全部状态，给还连着的 socket 发最后一帧后关闭。"""
        with self._lock:
            sockets = list((self._rooms.get(public_id) or {}).keys())
            self._forget_room_locked(public_id)
        if sockets:
            self._spawn(self._close_sockets(sockets, payload, code))
        return len(sockets)

    async def _close_sockets(
        self,
        sockets: list[WebSocket],
        payload: dict[str, Any] | None,
        code: int,
    ) -> None:
        async def one(ws: WebSocket) -> None:
            if payload is not None:
                await send_json_timeout(ws, payload)
            await close_quietly(ws, code)

        await asyncio.gather(*(one(ws) for ws in sockets))

    async def broadcast(self, public_id: str, payload: dict[str, Any]) -> None:
        message = dict(payload)
        with self._lock:
            targets = list((self._rooms.get(public_id) or {}).keys())
            if not targets:
                return
            if "seq" not in message:
                message["seq"] = self.next_seq(public_id)
        results = await asyncio.gather(*(send_json_timeout(ws, message) for ws in targets))
        dead = [ws for ws, ok in zip(targets, results, strict=True) if not ok]
        if not dead:
            return
        with self._lock:
            room = self._rooms.get(public_id)
            if room is not None:
                for ws in dead:
                    room.pop(ws, None)
                if not room:
                    self._forget_listeners_locked(public_id)
                else:
                    self._drop_offline_player_fixes_locked(public_id, _user_ids(room))
        await asyncio.gather(*(close_quietly(ws, CLOSE_SLOW_CONSUMER) for ws in dead))

    def publish(self, public_id: str, payload: dict[str, Any]) -> None:
        """按 seq 排队后广播：早提交的帧先落盘，晚到的高 seq 帧不会插到前面。"""
        message = dict(payload)
        with self._lock:
            if not self._rooms.get(public_id):
                # 空房没人听：不占序号、不建状态，否则一份临时 dict 会一直留在 _seq / _pending。
                return
            if "seq" not in message:
                message["seq"] = self.next_seq(public_id)
            seq = int(message["seq"] or 0)
            sent = int(self._sent_seq.get(public_id) or 0)
            if seq and seq <= sent:
                return
            self._pending.setdefault(public_id, {})[seq] = message
            if self._flushing.get(public_id):
                return
            self._flushing[public_id] = True
        self._spawn(self._flush(public_id))

    async def _flush(self, public_id: str) -> None:
        """一条条等前一条发完再发下一条；某条失败只关掉慢消费者，不阻塞后续帧。"""
        try:
            while True:
                with self._lock:
                    pending = self._pending.get(public_id)
                    if not pending:
                        self._flushing.pop(public_id, None)
                        return
                    seq = min(pending)
                    message = pending.pop(seq)
                    if not pending:
                        self._pending.pop(public_id, None)
                    self._sent_seq[public_id] = seq
                try:
                    await self.broadcast(public_id, message)
                except Exception:  # noqa: BLE001
                    logger.debug("raid room broadcast failed", exc_info=True)
        finally:
            with self._lock:
                if not self._pending.get(public_id):
                    self._flushing.pop(public_id, None)

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


hub = RaidRoomHub()
