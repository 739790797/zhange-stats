"""图鉴回源单飞。一把锁只服务一个游戏，不和塔科夫那把混用。"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

BUSY_MESSAGE = "数据同步中，请稍后再试"
COLD_START_WAIT_SEC = 3.0


class SyncBusy(Exception):
    def __init__(self, message: str = BUSY_MESSAGE):
        super().__init__(message)
        self.message = message


class SyncGate:
    def __init__(self, busy_message: str = BUSY_MESSAGE) -> None:
        self.busy_message = busy_message
        self._lock = threading.Lock()
        self._owner = threading.local()

    def _owned(self) -> bool:
        return bool(getattr(self._owner, "held", False))

    @contextmanager
    def exclusive(self, *, wait: float = 0.0) -> Iterator[None]:
        """本线程已持锁时直接进。等 ``wait`` 秒仍拿不到就抛 SyncBusy。"""
        if self._owned():
            yield
            return
        acquired = self._lock.acquire(timeout=wait) if wait > 0 else self._lock.acquire(blocking=False)
        if not acquired:
            raise SyncBusy(self.busy_message)
        self._owner.held = True
        try:
            yield
        finally:
            self._owner.held = False
            self._lock.release()

    def fill_once(self, db: Session, missing: Callable[[], bool], fill: Callable[[], object]) -> None:
        """缺数据才短等锁。拿到锁先结束旧事务再看一眼，别人已补齐就不重复回源。"""
        if not missing():
            return
        with self.exclusive(wait=COLD_START_WAIT_SEC):
            db.commit()
            if missing():
                fill()
