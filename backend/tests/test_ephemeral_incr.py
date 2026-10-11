"""ephemeral_incr：原子 +1 并续期（登录失败计数、单次使用的 state / nonce 都靠它）。"""

from __future__ import annotations

import threading

import pytest

import app.core.ephemeral_kv as kv
from app.core.ephemeral_kv import (
    ephemeral_get,
    ephemeral_incr,
    ephemeral_set,
    reset_ephemeral_kv_for_tests,
)


@pytest.fixture(autouse=True)
def _memory_only(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    reset_ephemeral_kv_for_tests()
    yield
    reset_ephemeral_kv_for_tests()


class _FakePipeline:
    def __init__(self, redis: "_FakeRedis") -> None:
        self._redis = redis
        self._ops: list[tuple] = []

    def incr(self, key: str) -> "_FakePipeline":
        self._ops.append(("incr", key))
        return self

    def expire(self, key: str, ttl: int) -> "_FakePipeline":
        self._ops.append(("expire", key, ttl))
        return self

    def execute(self) -> list:
        if self._redis.fail:
            raise ConnectionError("redis down")
        results: list = []
        for op in self._ops:
            if op[0] == "incr":
                self._redis.values[op[1]] = self._redis.values.get(op[1], 0) + 1
                results.append(self._redis.values[op[1]])
            else:
                self._redis.ttls[op[1]] = op[2]
                results.append(True)
        return results


class _FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)


def test_incr_starts_from_zero_and_counts() -> None:
    assert ephemeral_incr("c", ttl_sec=60) == 1
    assert ephemeral_incr("c", ttl_sec=60) == 2
    assert ephemeral_get("c") == "2"


def test_incr_renews_ttl_and_restarts_after_expiry(monkeypatch) -> None:
    clock = {"t": 1_000.0}
    monkeypatch.setattr(kv.time, "time", lambda: clock["t"])
    ephemeral_incr("c", ttl_sec=10)
    clock["t"] += 8
    assert ephemeral_incr("c", ttl_sec=10) == 2
    clock["t"] += 8
    assert ephemeral_get("c") == "2"
    clock["t"] += 3
    assert ephemeral_get("c") is None
    assert ephemeral_incr("c", ttl_sec=10) == 1


def test_incr_treats_non_numeric_value_as_zero() -> None:
    ephemeral_set("c", "not-a-number", ttl_sec=60)
    assert ephemeral_incr("c", ttl_sec=60) == 1


def test_incr_rejects_non_positive_ttl() -> None:
    with pytest.raises(ValueError):
        ephemeral_incr("c", ttl_sec=0)


def test_concurrent_incr_never_loses_updates() -> None:
    threads = 8
    per_thread = 200
    barrier = threading.Barrier(threads)

    def worker() -> None:
        barrier.wait()
        for _ in range(per_thread):
            ephemeral_incr("hot", ttl_sec=60)

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    assert ephemeral_get("hot") == str(threads * per_thread)


def test_incr_uses_redis_incr_and_expire_in_one_pipeline(monkeypatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(kv, "_get_redis", lambda: fake)
    assert ephemeral_incr("r", ttl_sec=30) == 1
    assert ephemeral_incr("r", ttl_sec=45) == 2
    assert fake.values == {"r": 2}
    assert fake.ttls == {"r": 45}
    assert kv._memory == {}


def test_incr_falls_back_to_memory_when_redis_fails(monkeypatch) -> None:
    monkeypatch.setattr(kv, "_get_redis", lambda: _FakeRedis(fail=True))
    assert ephemeral_incr("r", ttl_sec=30) == 1
    assert ephemeral_incr("r", ttl_sec=30) == 2
    assert kv._memory["r"][0] == "2"
