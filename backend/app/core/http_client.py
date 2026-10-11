"""进程级同步 HTTP 客户端：连接复用、分层超时、跳转检查、响应体上限与总时限。

平台 client 与塔科夫回源走这里，勿每次新建 httpx.Client / urllib.urlopen。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.cookiejar import CookieJar, DefaultCookiePolicy
from typing import Any

import httpx

CONNECT_TIMEOUT_SEC = 3.0
DEFAULT_READ_TIMEOUT_SEC = 12.0
# 读超时只限两次收包的间隔，慢速滴灌能一直拖着；总时限不传时取 max(此值, 5 × 读超时)
MIN_DEADLINE_SEC = 60.0
DEFAULT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 10

# 跳到别的主机时只有这些头可以照带；其余自定义头（token / cred / sign / DS …）都当凭证
_PORTABLE_HEADERS = frozenset(
    {
        "accept",
        "accept-encoding",
        "accept-language",
        "cache-control",
        "connection",
        "content-length",
        "content-type",
        "host",
        "if-modified-since",
        "if-none-match",
        "origin",
        "pragma",
        "range",
        "referer",
        "user-agent",
    }
)

_lock = threading.Lock()
_client: httpx.Client | None = None


class HttpRequestError(Exception):
    """传输层失败（超时 / DNS / 连接 / 拒绝跟随的跳转 / 响应过大），不含 HTTP 4xx/5xx。"""


class HttpResponseTooLarge(HttpRequestError):
    """响应体超过 max_bytes。"""


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


def _deadline_sec(deadline: float | int | None, read_sec: float | int | None) -> float:
    if deadline is not None:
        return float(deadline)
    read = float(DEFAULT_READ_TIMEOUT_SEC if read_sec is None else read_sec)
    return max(MIN_DEADLINE_SEC, 5 * read)


def _check_deadline(started: float, deadline: float | None) -> None:
    if deadline is not None and time.monotonic() - started > deadline:
        raise HttpRequestError(f"请求超时：超过 {deadline:g} 秒仍未完成")


class _NoStoreCookiePolicy(DefaultCookiePolicy):
    """进程级 client 被所有用户共用：上游 Set-Cookie 只能从 resp.cookies / 响应头读，不得落 jar 串号。"""

    def set_ok(self, cookie, request) -> bool:  # noqa: ANN001
        return False

    def return_ok(self, cookie, request) -> bool:  # noqa: ANN001
        return False


def _new_client(**kwargs: Any) -> httpx.Client:
    return httpx.Client(
        timeout=_timeout(DEFAULT_READ_TIMEOUT_SEC),
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=40,
            max_keepalive_connections=20,
            keepalive_expiry=30.0,
        ),
        cookies=CookieJar(policy=_NoStoreCookiePolicy()),
        **kwargs,
    )


def get_http_client() -> httpx.Client:
    global _client
    with _lock:
        if _client is None:
            _client = _new_client()
        return _client


def close_http_client() -> None:
    global _client
    with _lock:
        if _client is not None:
            _client.close()
            _client = None


def _redirect_refusal(request: httpx.Request, target: httpx.Request) -> str | None:
    """跟随跳转前的检查；返回拒绝原因，None 表示可以跟。

    target 是 httpx 拼好的下一跳（跨源时已去掉 Authorization，Cookie 一律不带），
    这里再拦它会带到别处去的自定义凭证头与 307/308 重发的请求体。
    """
    src, dst = request.url, target.url
    if src.scheme == "https" and dst.scheme != "https":
        return "不跟随从 HTTPS 降到 HTTP 的跳转"
    if dst.host == src.host:
        return None
    if target.method not in ("GET", "HEAD"):
        return "跳到别的主机会重发请求体"
    if any(name.lower() not in _PORTABLE_HEADERS for name in target.headers.keys()):
        return "跳到别的主机会带上凭证请求头"
    return None


def _send(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None,
    content: bytes | None,
    json: Any | None,
    params: dict[str, Any] | None,
    timeout: httpx.Timeout,
    follow_redirects: bool | None,
    started: float,
    deadline: float | None,
) -> httpx.Response:
    """发请求并逐跳检查后跟随跳转；返回还没读 body 的流式响应，调用方负责 close。"""
    client = get_http_client()
    follow = client.follow_redirects if follow_redirects is None else follow_redirects
    request = client.build_request(
        method.upper(),
        url,
        headers=headers,
        content=content,
        json=json,
        params=params,
        timeout=timeout,
    )
    for _ in range(MAX_REDIRECTS + 1):
        _check_deadline(started, deadline)
        response = client.send(request, stream=True, follow_redirects=False)
        target = response.next_request
        if target is None or not follow:
            return response
        response.close()
        refusal = _redirect_refusal(request, target)
        if refusal:
            raise HttpRequestError(f"拒绝跟随跳转到 {target.url.host}：{refusal}")
        request = target
    raise HttpRequestError("网络错误：跳转次数过多")


def _read_body(
    response: httpx.Response,
    *,
    max_bytes: int | None,
    started: float,
    deadline: float | None,
    on_bytes: Callable[[int, int | None], None] | None = None,
) -> bytes:
    """边读边数解压后的字节：超 max_bytes 或总时限立刻断开（由调用方 close）。"""
    total: int | None = None
    raw_len = response.headers.get("content-length")
    if raw_len and str(raw_len).isdigit():
        total = int(raw_len)
    # 压缩时 Content-Length 是压缩后的长度、HEAD 没有 body，只有未压缩的 body 才能据此提前拒绝
    if (
        max_bytes is not None
        and total is not None
        and total > max_bytes
        and not response.headers.get("content-encoding")
        and response.request.method != "HEAD"
    ):
        raise HttpResponseTooLarge(f"响应过大：超过 {max_bytes} 字节上限")
    if on_bytes is not None:
        on_bytes(0, total)
    chunks: list[bytes] = []
    done = 0
    for chunk in response.iter_bytes():
        if not chunk:
            continue
        done += len(chunk)
        if max_bytes is not None and done > max_bytes:
            raise HttpResponseTooLarge(f"响应过大：超过 {max_bytes} 字节上限")
        chunks.append(chunk)
        if on_bytes is not None:
            on_bytes(done, total)
        _check_deadline(started, deadline)
    body = b"".join(chunks)
    # 等同 Response.read() 的结果，之后 .content / .text / .json() 照常可用
    response._content = body
    return body


def _fetch(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None,
    content: bytes | None,
    json: Any | None,
    params: dict[str, Any] | None,
    timeout: float | int | None,
    connect: float | int | None,
    follow_redirects: bool | None,
    max_bytes: int | None,
    deadline: float | int | None,
    on_bytes: Callable[[int, int | None], None] | None,
) -> httpx.Response:
    started = time.monotonic()
    limit = _deadline_sec(deadline, timeout)
    try:
        response = _send(
            method,
            url,
            headers=headers,
            content=content,
            json=json,
            params=params,
            timeout=_timeout(timeout, connect=connect),
            follow_redirects=follow_redirects,
            started=started,
            deadline=limit,
        )
        try:
            _read_body(
                response,
                max_bytes=max_bytes,
                started=started,
                deadline=limit,
                on_bytes=on_bytes,
            )
        finally:
            response.close()
        return response
    except httpx.TimeoutException as exc:
        raise HttpRequestError(f"请求超时：{exc}") from exc
    except httpx.RequestError as exc:
        raise HttpRequestError(f"网络错误：{exc}") from exc


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
    max_bytes: int | None = DEFAULT_MAX_RESPONSE_BYTES,
    deadline: float | int | None = None,
) -> httpx.Response:
    """发请求；4xx/5xx 仍返回 Response，不 raise。

    body 超过 ``max_bytes``（None 不限）或含跳转在内超过 ``deadline`` 秒（不传按读超时推算）
    就断开并抛 HttpRequestError；跳到别的主机 / 降到 HTTP 前按 ``_redirect_refusal`` 检查。
    """
    return _fetch(
        method,
        url,
        headers=headers,
        content=content,
        json=json,
        params=params,
        timeout=timeout,
        connect=connect,
        follow_redirects=follow_redirects,
        max_bytes=max_bytes,
        deadline=deadline,
        on_bytes=None,
    )


def http_download(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
    timeout: float | int | None = None,
    connect: float | int | None = None,
    on_bytes: Callable[[int, int | None], None] | None = None,
    max_bytes: int | None = DEFAULT_MAX_RESPONSE_BYTES,
    deadline: float | int | None = None,
) -> tuple[int, bytes, httpx.Headers]:
    """拉进内存；`on_bytes(已下载, Content-Length 或 None)` 边下边报。上限与总时限同 http_request。"""
    resp = _fetch(
        method,
        url,
        headers=headers,
        content=content,
        json=None,
        params=None,
        timeout=timeout,
        connect=connect,
        follow_redirects=None,
        max_bytes=max_bytes,
        deadline=deadline,
        on_bytes=on_bytes,
    )
    return resp.status_code, resp.content, resp.headers


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
    """进程级 client 上流式读；落盘大文件用这个，不要另开 Client。

    跳转检查同 http_request；不设体积上限与总时限，调用方边读边数。
    """
    try:
        resp = _send(
            method,
            url,
            headers=headers,
            content=content,
            json=None,
            params=None,
            timeout=_timeout(timeout, connect=connect),
            follow_redirects=follow_redirects,
            started=time.monotonic(),
            deadline=None,
        )
        try:
            yield resp
        finally:
            resp.close()
    except httpx.TimeoutException as exc:
        raise HttpRequestError(f"请求超时：{exc}") from exc
    except httpx.RequestError as exc:
        raise HttpRequestError(f"网络错误：{exc}") from exc


def reset_http_client_for_tests() -> None:
    close_http_client()
