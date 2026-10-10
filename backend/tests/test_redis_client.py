"""共享 Redis 客户端：带超时连接、失败后退避重连、告警去重与恢复。"""

from __future__ import annotations

import logging
import sys
import types

import pytest

from app.core import redis_client
from app.core.config import get_settings


class _FakeClient:
    def __init__(self, url: str, kwargs: dict, module: "_FakeRedisModule") -> None:
        self.url = url
        self.kwargs = kwargs
        self._module = module
        self.closed = False

    def ping(self) -> bool:
        if self._module.fail:
            raise ConnectionError(
                f"Error 111 connecting to {self.url}. Connection refused."
            )
        return True

    def close(self) -> None:
        self.closed = True


class _FakeRedisModule(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("redis")
        self.fail = False
        self.created: list[_FakeClient] = []
        module = self

        class Redis:
            @staticmethod
            def from_url(url: str, **kwargs):
                client = _FakeClient(url, kwargs, module)
                module.created.append(client)
                return client

        self.Redis = Redis


@pytest.fixture
def fake_redis(monkeypatch):
    module = _FakeRedisModule()
    monkeypatch.setitem(sys.modules, "redis", module)
    redis_client.reset_redis_for_tests()
    yield module
    redis_client.reset_redis_for_tests()


@pytest.fixture
def clock(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(redis_client, "_monotonic", lambda: now["t"])
    return now


@pytest.fixture
def redis_url(monkeypatch):
    url = "redis://:hunter2@10.0.0.9:6379/0"
    monkeypatch.setenv("REDIS_URL", url)
    get_settings.cache_clear()
    return url


def _warnings(caplog) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.name == "app.core.redis_client" and r.levelno == logging.WARNING
    ]


def test_unconfigured_returns_none_without_import(monkeypatch, fake_redis) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    get_settings.cache_clear()
    assert redis_client.get_redis() is None
    assert fake_redis.created == []


def test_connects_with_timeouts_and_caches(fake_redis, redis_url) -> None:
    client = redis_client.get_redis()
    assert client is fake_redis.created[0]
    assert client.kwargs["socket_connect_timeout"] == 2
    assert client.kwargs["socket_timeout"] == 2
    assert client.kwargs["health_check_interval"] == 30
    assert client.kwargs["retry_on_timeout"] is True
    assert client.kwargs["decode_responses"] is True
    assert redis_client.get_redis() is client
    assert len(fake_redis.created) == 1


def test_failure_backs_off_then_recovers(fake_redis, redis_url, clock, caplog) -> None:
    fake_redis.fail = True
    with caplog.at_level(logging.DEBUG, logger="app.core.redis_client"):
        assert redis_client.get_redis() is None
        assert fake_redis.created[0].closed is True

        clock["t"] += redis_client.RETRY_AFTER_SEC - 1
        assert redis_client.get_redis() is None
        assert len(fake_redis.created) == 1

        clock["t"] += 2
        assert redis_client.get_redis() is None
        assert len(fake_redis.created) == 2

        warnings = _warnings(caplog)
        assert len(warnings) == 1
        assert "hunter2" not in warnings[0].getMessage()
        assert "***@" in warnings[0].getMessage()

        fake_redis.fail = False
        clock["t"] += redis_client.RETRY_AFTER_SEC + 1
        client = redis_client.get_redis()
        assert client is fake_redis.created[-1]
        assert any(
            r.levelno == logging.INFO and "connected" in r.getMessage()
            for r in caplog.records
        )

        caplog.clear()
        client_count = len(fake_redis.created)
        redis_client.reset_redis_for_tests()
        fake_redis.fail = True
        assert redis_client.get_redis() is None
        assert len(fake_redis.created) == client_count + 1
        assert len(_warnings(caplog)) == 1


def test_url_change_reconnects_and_closes_old(monkeypatch, fake_redis, redis_url) -> None:
    first = redis_client.get_redis()
    assert first is not None
    monkeypatch.setenv("REDIS_URL", "redis://10.0.0.10:6379/1")
    get_settings.cache_clear()
    second = redis_client.get_redis()
    assert second is not None and second is not first
    assert second.url == "redis://10.0.0.10:6379/1"
    assert first.closed is True


def test_busy_connect_falls_back_instead_of_blocking(fake_redis, redis_url, monkeypatch) -> None:
    monkeypatch.setattr(redis_client, "_CONNECT_WAIT_SEC", 0.01)
    assert redis_client._lock.acquire()
    try:
        assert redis_client.get_redis() is None
    finally:
        redis_client._lock.release()
    assert fake_redis.created == []
    assert redis_client.get_redis() is fake_redis.created[0]
