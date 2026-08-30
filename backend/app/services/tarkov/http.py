"""塔科夫上游下载：走进程级 httpx，勿再用 urllib.urlopen。"""

from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any

from app.core.http_client import HttpRequestError, http_request

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


def download_response(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | int = 120,
    error_cls: type[Exception] = RuntimeError,
) -> Any:
    req_headers = {"User-Agent": DEFAULT_UA, **(headers or {})}
    try:
        resp = http_request(
            method,
            url,
            headers=req_headers,
            content=body,
            timeout=timeout,
        )
    except HttpRequestError as exc:
        raise error_cls(f"无法连接资源站: {exc}") from exc
    if resp.status_code >= 400:
        detail = ""
        try:
            detail = resp.content.decode("utf-8", errors="replace")[:300]
        except Exception:  # noqa: BLE001
            detail = ""
        msg = f"下载失败 HTTP {resp.status_code}: {url}"
        if detail:
            msg = f"{msg} ({detail})"
        raise error_cls(msg)
    return resp


def download_bytes(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | int = 120,
    error_cls: type[Exception] = RuntimeError,
) -> bytes:
    return download_response(
        url,
        method=method,
        body=body,
        headers=headers,
        timeout=timeout,
        error_cls=error_cls,
    ).content


def download_bytes_with_meta(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | int = 120,
    error_cls: type[Exception] = RuntimeError,
) -> tuple[bytes, str | None]:
    resp = download_response(
        url,
        method=method,
        body=body,
        headers=headers,
        timeout=timeout,
        error_cls=error_cls,
    )
    return resp.content, http_last_modified_iso(getattr(resp, "headers", None))
