"""塔科夫上游下载：走进程级 httpx，勿再用 urllib.urlopen。"""

from __future__ import annotations

from app.core.http_client import HttpRequestError, http_request

DEFAULT_UA = "zhange-stats/1.0"


def download_bytes(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | int = 120,
    error_cls: type[Exception] = RuntimeError,
) -> bytes:
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
    return resp.content
