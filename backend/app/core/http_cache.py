"""图鉴 GET 的 ETag / 304。登录接口用 private，不进公共 CDN。"""

from __future__ import annotations

import hashlib

from fastapi import Request, Response

CATALOG_CACHE_CONTROL = "private, max-age=60, stale-while-revalidate=300"


def catalog_etag(*parts: object) -> str:
    blob = "\x1f".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return f'W/"{digest}"'


def etag_matches(if_none_match: str, etag: str) -> bool:
    raw = (if_none_match or "").strip()
    if not raw or raw == "*":
        return False
    needle = etag.strip()
    for token in raw.split(","):
        candidate = token.strip()
        if candidate == needle:
            return True
        if candidate.startswith("W/") and candidate[2:].strip() == needle:
            return True
        if needle.startswith("W/") and needle[2:].strip() == candidate:
            return True
    return False


def if_none_match(request: Request, etag: str) -> bool:
    return etag_matches(request.headers.get("if-none-match") or "", etag)


def not_modified_response(etag: str) -> Response:
    return Response(
        status_code=304,
        headers={
            "ETag": etag,
            "Cache-Control": CATALOG_CACHE_CONTROL,
        },
    )


def set_catalog_cache_headers(response: Response, etag: str) -> None:
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = CATALOG_CACHE_CONTROL


def catalog_freshness(
    request: Request,
    *parts: object,
) -> tuple[str, Response | None]:
    """命中 If-None-Match 则 304；未命中只返回 etag，等业务成功再打头。"""
    etag = catalog_etag(*parts)
    if if_none_match(request, etag):
        return etag, not_modified_response(etag)
    return etag, None
