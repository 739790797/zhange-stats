"""Cross-process locks shared by scheduled and CLI-triggered sync jobs."""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import get_settings
from app.core.paths import runtime_root
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

_LOCK_TTL_SEC = 300
_LOCK_REFRESH_SEC = 60


class JobExecutionBusy(RuntimeError):
    """The same job already has an active execution."""


class JobExecutionLockUnavailable(RuntimeError):
    """The configured cross-instance lock service is unavailable."""


def _lock_file_path(job_id: str) -> Path:
    safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in job_id)
    return runtime_root() / "job-locks" / f"{safe_id}.lock"


@contextmanager
def _file_lock(job_id: str) -> Iterator[None]:
    path = _lock_file_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise JobExecutionBusy(f"任务 {job_id} 正在执行") from exc
            unlock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise JobExecutionBusy(f"任务 {job_id} 正在执行") from exc
            unlock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        try:
            yield
        finally:
            try:
                unlock()
            except OSError:
                logger.warning("job file lock release failed job_id=%s", job_id)
    finally:
        handle.close()


@contextmanager
def job_execution_lock(job_id: str) -> Iterator[None]:
    """Use Redis for configured multi-instance deployments, else a local OS lock.

    A configured but unavailable Redis is a hard failure: silently falling back to
    per-host file locks would allow duplicate work across app replicas.
    """
    redis_url = (get_settings().REDIS_URL or "").strip()
    if not redis_url:
        with _file_lock(job_id):
            yield
        return

    redis = get_redis()
    if redis is None:
        raise JobExecutionLockUnavailable("Redis 锁服务不可用，拒绝启动同步任务")

    lock = redis.lock(
        f"zhange:job-execution:{job_id}",
        timeout=_LOCK_TTL_SEC,
        blocking_timeout=0,
        thread_local=False,
    )
    try:
        acquired = lock.acquire(blocking=False)
    except Exception as exc:  # noqa: BLE001
        raise JobExecutionLockUnavailable("Redis 锁服务不可用，拒绝启动同步任务") from exc
    if not acquired:
        raise JobExecutionBusy(f"任务 {job_id} 正在执行")

    stop = threading.Event()
    lost = threading.Event()

    def refresh() -> None:
        while not stop.wait(_LOCK_REFRESH_SEC):
            try:
                lock.extend(_LOCK_TTL_SEC, replace_ttl=True)
            except Exception:  # noqa: BLE001
                lost.set()
                logger.exception("job redis lock refresh failed job_id=%s", job_id)
                return

    heartbeat = threading.Thread(
        target=refresh,
        name=f"job-lock-heartbeat-{job_id}",
        daemon=True,
    )
    heartbeat.start()
    try:
        yield
        if lost.is_set():
            raise JobExecutionLockUnavailable("Redis 锁续租失败，同步结果需人工确认")
    finally:
        stop.set()
        heartbeat.join(timeout=1)
        try:
            if lock.owned():
                lock.release()
        except Exception:  # noqa: BLE001
            logger.exception("job redis lock release failed job_id=%s", job_id)
