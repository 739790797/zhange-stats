"""进程级同步 HTTP 客户端：连接复用、分层超时。

平台 client 与塔科夫回源走这里，勿每次新建 httpx.Client / urllib.urlopen。
"""

from __future__ import annotations

import threading
from typing import Any

import httpx

CONNECT_TIMEOUT_SEC = 3.0
DEFAULT_READ_TIMEOUT_SEC = 12.0

_lock = threading.Lock()
_client: httpx.Client | None = None


class HttpRequestError(Exception):
    """传输层失败（超时 / DNS / 连接），不含 HTTP 4xx/5xx。"""


def _timeout(read_sec: float | int | None) -> httpx.Timeout:
    read = float(DEFAULT_READ_TIMEOUT_SEC if read_sec is None else read_sec)
    connect = min(CONNECT_TIMEOUT_SEC, read)
    return httpx.Timeout(read, connect=connect)


def get_http_client() -> httpx.Client:
    global _client
    with _lock:
        if _client is None:
            _client = httpx.Client(
                timeout=_timeout(DEFAULT_READ_TIMEOUT_SEC),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=40,
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0,
                ),
            )
        return _client


def close_http_client() -> None:
    global _client
    with _lock:
        if _client is not None:
            _client.close()
            _client = None


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
    json: Any | None = None,
    timeout: float | int | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    """发请求；4xx/5xx 仍返回 Response，不 raise。"""
    try:
        return get_http_client().request(
            method.upper(),
            url,
            headers=headers,
            content=content,
            json=json,
            params=params,
            timeout=_timeout(timeout),
        )
    except httpx.TimeoutException as exc:
        raise HttpRequestError(f"请求超时：{exc}") from exc
    except httpx.RequestError as exc:
        raise HttpRequestError(f"网络错误：{exc}") from exc


def reset_http_client_for_tests() -> None:
    close_http_client()
