"""Isolate config/*.json, runtime data and the network so tests never touch the real install root or upstreams."""

from __future__ import annotations

import ipaddress
import os
import socket
import tempfile

import pytest

# 进程级运行时目录：import app.main 时挂的 JSONL 日志、更新锁等落到临时目录，不写安装根 data/
_SESSION_DATA_ROOT = tempfile.mkdtemp(prefix="zhange-test-data-")
os.environ.setdefault("DATA_DIR", os.path.join(_SESSION_DATA_ROOT, "runtime"))
os.environ.setdefault("UPLOAD_DIR", os.path.join(_SESSION_DATA_ROOT, "uploads"))

from app.core.config import get_settings  # noqa: E402
from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests  # noqa: E402
from app.core.file_config import set_config_dir_for_tests  # noqa: E402
from app.core.rate_limit import reset_rate_limits_for_tests  # noqa: E402
from app.core.runtime_cache import pin_library_cache_env  # noqa: E402

_LOCAL_HOSTS = frozenset({"localhost", "localhost.localdomain", "ip6-localhost", ""})


def _is_local_host(host: object) -> bool:
    text = str(host or "").strip().strip("[]").lower()
    if text in _LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(text.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


class NetworkAccessBlocked(RuntimeError):
    """测试里禁止连外网；上游一律用 httpx.MockTransport / monkeypatch。"""


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo


def _guarded_target(sock: socket.socket, address: object) -> None:
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return
    host = address[0] if isinstance(address, tuple) and address else address
    if not _is_local_host(host):
        raise NetworkAccessBlocked(f"tests must not open network connections (target={host!r})")


def _guarded_connect(self: socket.socket, address: object) -> None:
    _guarded_target(self, address)
    return _real_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: object) -> int:
    _guarded_target(self, address)
    return _real_connect_ex(self, address)


def _guarded_getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
    if not _is_local_host(host):
        raise NetworkAccessBlocked(f"tests must not resolve external hosts (host={host!r})")
    return _real_getaddrinfo(host, *args, **kwargs)


@pytest.fixture(autouse=True)
def _block_external_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)


@pytest.fixture(autouse=True)
def _reset_process_limits():
    """限流与短时 KV 是进程级状态：每个用例从空开始，避免前面用例的计数让后面的登录/发码吃 429。"""
    reset_rate_limits_for_tests()
    reset_ephemeral_kv_for_tests()
    yield
    reset_rate_limits_for_tests()
    reset_ephemeral_kv_for_tests()


@pytest.fixture(autouse=True)
def _isolate_config_dir(tmp_path):
    cfg = tmp_path / "zhange-config"
    cfg.mkdir()
    set_config_dir_for_tests(cfg)
    get_settings.cache_clear()
    yield
    set_config_dir_for_tests(None)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _pin_library_caches(tmp_path, monkeypatch):
    """Keep Hugging Face / Torch / tempfile off the developer home directory."""
    install = tmp_path / "lib-cache-root"
    install.mkdir()
    applied = pin_library_cache_env(install=install)
    for key, value in applied.items():
        monkeypatch.setenv(key, value)
