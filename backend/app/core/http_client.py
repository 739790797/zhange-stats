"""进程级同步 HTTP 客户端：连接复用、分层超时。

平台 client 与塔科夫回源走这里，勿每次新建 httpx.Client / urllib.urlopen。
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx

CONNECT_TIMEOUT_SEC = 3.0
DEFAULT_READ_TIMEOUT_SEC = 12.0

_lock = threading.Lock()
_client: httpx.Client | None = None


class HttpRequestError(Exception):
    """传输层失败（超时 / DNS / 连接），不含 HTTP 4xx/5xx。"""


def _timeout(
    read_sec: float | int | None,
    *,
    connect: float | int | None = None,
) -> httpx.Timeout:
    read = float(DEFAULT_READ_TIMEOUT_SEC if read_sec is None else read_sec)
    connect_sec = (
        float(connect) if connect is not None else min(CONNECT_TIMEOUT_SEC, read)
    )
    return httpx.Timeout(read, connect=connect_sec)


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
    connect: float | int | None = None,
    params: dict[str, Any] | None = None,
    follow_redirects: bool | None = None,
) -> httpx.Response:
    """发请求；4xx/5xx 仍返回 Response，不 raise。"""
    kwargs: dict[str, Any] = {
        "headers": headers,
        "content": content,
        "json": json,
        "params": params,
        "timeout": _timeout(timeout, connect=connect),
    }
    if follow_redirects is not None:
        kwargs["follow_redirects"] = follow_redirects
    try:
        return get_http_client().request(method.upper(), url, **kwargs)
    except httpx.TimeoutException as exc:
        raise HttpRequestError(f"请求超时：{exc}") from exc
    except httpx.RequestError as exc:
        raise HttpRequestError(f"网络错误：{exc}") from exc


def http_download(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
    timeout: float | int | None = None,
    connect: float | int | None = None,
    on_bytes: Callable[[int, int | None], None] | None = None,
) -> tuple[int, bytes, httpx.Headers]:
    """拉进内存；`on_bytes(已下载, Content-Length 或 None)` 边下边报。"""
    if on_bytes is None:
        resp = http_request(
            method,
            url,
            headers=headers,
            content=content,
            timeout=timeout,
            connect=connect,
        )
        return resp.status_code, resp.content, resp.headers
    kwargs: dict[str, Any] = {
        "headers": headers,
        "content": content,
        "timeout": _timeout(timeout, connect=connect),
    }
    try:
        with get_http_client().stream(method.upper(), url, **kwargs) as resp:
            total: int | None = None
            raw_len = resp.headers.get("content-length")
            if raw_len and str(raw_len).isdigit():
                total = int(raw_len)
            on_bytes(0, total)
            if resp.status_code >= 400:
                try:
                    body = resp.read()
                except Exception:
                    body = b""
                return resp.status_code, body, resp.headers
            chunks: list[bytes] = []
            done = 0
            for chunk in resp.iter_bytes():
                if not chunk:
                    continue
                chunks.append(chunk)
                done += len(chunk)
                on_bytes(done, total)
            return resp.status_code, b"".join(chunks), resp.headers
    except httpx.TimeoutException as exc:
        raise HttpRequestError(f"请求超时：{exc}") from exc
    except httpx.RequestError as exc:
        raise HttpRequestError(f"网络错误：{exc}") from exc


@contextmanager
def http_stream(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
    timeout: float | int | None = None,
    connect: float | int | None = None,
    follow_redirects: bool | None = None,
) -> Iterator[httpx.Response]:
    """进程级 client 上流式读；落盘大文件用这个，不要另开 Client。"""
    kwargs: dict[str, Any] = {
        "headers": headers,
        "content": content,
        "timeout": _timeout(timeout, connect=connect),
    }
    if follow_redirects is not None:
        kwargs["follow_redirects"] = follow_redirects
    try:
        with get_http_client().stream(method.upper(), url, **kwargs) as resp:
            yield resp
    except httpx.TimeoutException as exc:
        raise HttpRequestError(f"请求超时：{exc}") from exc
    except httpx.RequestError as exc:
        raise HttpRequestError(f"网络错误：{exc}") from exc


def reset_http_client_for_tests() -> None:
    close_http_client()
