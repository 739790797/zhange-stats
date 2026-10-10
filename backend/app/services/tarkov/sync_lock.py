"""塔科夫回源单飞：整站同步（定时 / 任务管理 / 管理端）、单栏目回源与冷启动 ensure_* 共用一把进程锁。

整站同步要跑几分钟；冷启动读者只短等，等不到就 503，别让线程池堆满等锁的请求。
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy.orm import Session

BUSY_MESSAGE = "数据同步中，请稍后再试"
COLD_START_WAIT_SEC = 3.0

# 普通 Lock 而非 RLock：管理端在请求线程抢锁、交给后台线程释放。
_lock = threading.Lock()
_owner = threading.local()


class TarkovSyncBusy(Exception):
    def __init__(self, message: str = BUSY_MESSAGE):
        super().__init__(message)
        self.message = message


def _owned() -> bool:
    return bool(getattr(_owner, "held", False))


@contextmanager
def held() -> Iterator[None]:
    """当前线程接管已抢到的锁（可跨线程交接），退出时释放。"""
    _owner.held = True
    try:
        yield
    finally:
        _owner.held = False
        _lock.release()


def claim() -> None:
    """非阻塞抢锁；抢到后必须由某个线程 `held()` 接管或 `unclaim()`。"""
    if not _lock.acquire(blocking=False):
        raise TarkovSyncBusy()


def unclaim() -> None:
    _lock.release()


@contextmanager
def exclusive(*, wait: float = 0.0) -> Iterator[None]:
    """拿锁跑回源；本线程已持锁时直接进。等 `wait` 秒仍拿不到抛 TarkovSyncBusy。"""
    if _owned():
        yield
        return
    acquired = _lock.acquire(timeout=wait) if wait > 0 else _lock.acquire(blocking=False)
    if not acquired:
        raise TarkovSyncBusy()
    with held():
        yield


def cold_start() -> AbstractContextManager[None]:
    return exclusive(wait=COLD_START_WAIT_SEC)


def fill_once(db: Session, missing: Callable[[], bool], fill: Callable[[], object]) -> None:
    """冷启动回源：缺数据才短等锁；拿到锁先结束旧事务再看一眼，别人已补齐就不重复回源。"""
    if not missing():
        return
    with cold_start():
        # MariaDB 可重复读：不提交就看不到等锁期间别人提交的 raw。
        db.commit()
        if missing():
            fill()
