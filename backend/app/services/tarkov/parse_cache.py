"""进程内 raw 解析缓存：PVP / PVE 各留一份，键为 raw 表头（synced_at、overlay token 等）。

命中只比键，不再读库解码 raw；换键（重新同步）时整份替换。
"""

from __future__ import annotations

import threading
from typing import Generic, TypeVar

from app.services.tarkov.game_mode import parse_game_mode

T = TypeVar("T")


class ModeCache(Generic[T]):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[str, T]] = {}

    def get(self, key: str) -> T | None:
        with self._lock:
            hit = self._entries.get(parse_game_mode())
        if hit is None or hit[0] != key:
            return None
        return hit[1]

    def put(self, key: str, value: T) -> None:
        with self._lock:
            self._entries[parse_game_mode()] = (key, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class ModeKeyedCache(Generic[T]):
    """同上，但一个表头键下按子键（如地图）各存一份；换键时旧子键一并丢弃，不会越攒越多。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[str, dict[str, T]]] = {}

    def get(self, key: str, sub: str) -> T | None:
        with self._lock:
            hit = self._entries.get(parse_game_mode())
            if hit is None or hit[0] != key:
                return None
            return hit[1].get(sub)

    def put(self, key: str, sub: str, value: T) -> None:
        mode = parse_game_mode()
        with self._lock:
            hit = self._entries.get(mode)
            if hit is None or hit[0] != key:
                hit = (key, {})
                self._entries[mode] = hit
            hit[1][sub] = value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
