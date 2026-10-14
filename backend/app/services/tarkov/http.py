"""塔科夫上游下载：走进程级 httpx，勿再用 urllib.urlopen。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timezone
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from typing import Any

from app.core.http_client import HttpRequestError, http_download, http_request

DEFAULT_UA = "zhange-stats/1.0"


def http_last_modified_iso(headers: Any) -> str | None:
    """把 HTTP Last-Modified 收成 UTC ISO；没有或解析失败则 None。"""
    if headers is None:
        return None
    raw = headers.get("Last-Modified") or headers.get("last-modified")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(str(raw))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _raise_http_error(
    url: str,
    status_code: int,
    content: bytes,
    error_cls: type[Exception],
) -> None:
    detail = ""
    try:
        detail = content.decode("utf-8", errors="replace")[:300]
    except Exception:  # noqa: BLE001
        detail = ""
    msg = f"下载失败 HTTP {status_code}: {url}"
    if detail:
        msg = f"{msg} ({detail})"
    raise error_cls(msg)


def download_response(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | int = 120,
    error_cls: type[Exception] = RuntimeError,
    on_bytes: Callable[[int, int | None], None] | None = None,
    max_bytes: int | None = None,
) -> Any:
    req_headers = {"User-Agent": DEFAULT_UA, **(headers or {})}
    if on_bytes is None:
        try:
            resp = http_request(
                method,
                url,
                headers=req_headers,
                content=body,
                timeout=timeout,
                max_bytes=max_bytes,
            )
        except HttpRequestError as exc:
            raise error_cls(f"无法连接资源站: {exc}") from exc
        if resp.status_code >= 400:
            _raise_http_error(url, resp.status_code, resp.content, error_cls)
        return resp
    try:
        status, content, resp_headers = http_download(
            method,
            url,
            headers=req_headers,
            content=body,
            timeout=timeout,
            on_bytes=on_bytes,
            max_bytes=max_bytes,
        )
    except HttpRequestError as exc:
        raise error_cls(f"无法连接资源站: {exc}") from exc
    if status >= 400:
        _raise_http_error(url, status, content, error_cls)
    return SimpleNamespace(status_code=status, content=content, headers=resp_headers)


def download_bytes(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | int = 120,
    error_cls: type[Exception] = RuntimeError,
    max_bytes: int | None = None,
) -> bytes:
    return download_response(
        url,
        method=method,
        body=body,
        headers=headers,
        timeout=timeout,
        error_cls=error_cls,
        max_bytes=max_bytes,
    ).content


def download_bytes_with_meta(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | int = 120,
    error_cls: type[Exception] = RuntimeError,
    on_bytes: Callable[[int, int | None], None] | None = None,
    max_bytes: int | None = None,
) -> tuple[bytes, str | None]:
    resp = download_response(
        url,
        method=method,
        body=body,
        headers=headers,
        timeout=timeout,
        error_cls=error_cls,
        on_bytes=on_bytes,
        max_bytes=max_bytes,
    )
    return resp.content, http_last_modified_iso(getattr(resp, "headers", None))


# 塔科夫数据下载上限：json.tarkov.dev items ~17MB，maps ~8.6MB；给上游长胖留足余量
TARKOV_DUMP_MAX_BYTES = 64 * 1024 * 1024


def download_dump(
    url: str,
    *,
    timeout: float | int = 120,
    error_cls: type[Exception] = RuntimeError,
    on_bytes: Callable[[int, int | None], None] | None = None,
) -> tuple[bytes, str | None]:
    """塔科夫 dump 下载唯一入口：一律带 TARKOV_DUMP_MAX_BYTES，别再各写一份 _http_request。"""
    return download_bytes_with_meta(
        url,
        timeout=timeout,
        error_cls=error_cls,
        on_bytes=on_bytes,
        max_bytes=TARKOV_DUMP_MAX_BYTES,
    )
