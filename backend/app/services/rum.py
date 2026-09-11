"""浏览器 RUM：URL 归并、入库、分位数汇总。不上平台日志。"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive, to_naive
from app.models.rum import RumSample

KIND_API = "api"
KIND_IMG = "img"
KINDS = frozenset({KIND_API, KIND_IMG})
HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})

MAX_EVENTS_PER_POST = 80
MAX_DURATION_MS = 120_000
URL_KEY_MAX = 256
HOST_MAX = 128
PAGE_MAX = 256
SUMMARY_ROW_LIMIT = 200
KEEP_DAYS = 14

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX24_RE = re.compile(r"[0-9a-fA-F]{24}")
_HEX40_RE = re.compile(r"[0-9a-fA-F]{40,}")
_NUMERIC_SEG_RE = re.compile(r"/\d+(?=/|$)")
_RAID_ROOM_RE = re.compile(r"(/raid-rooms/)[0-9a-fA-F]{8}(?=/|$)", re.IGNORECASE)
_MAP_TILE_RE = re.compile(
    r"^(/maps/)([^/]+)(/.*\d+/\d+.*)$",
    re.IGNORECASE,
)


def percentile_nearest(values: list[int], p: float) -> int | None:
    """p 为 0–1；空列表返回 None。"""
    if not values:
        return None
    xs = sorted(values)
    n = len(xs)
    if n == 1:
        return xs[0]
    idx = min(n - 1, max(0, int(round((n - 1) * p))))
    return xs[idx]


def _clip(text: str, limit: int) -> str:
    return text[:limit]


def _collapse_ids(path: str) -> str:
    path = _UUID_RE.sub("{id}", path)
    path = _HEX40_RE.sub("{id}", path)
    path = _HEX24_RE.sub("{id}", path)
    path = _RAID_ROOM_RE.sub(r"\1{id}", path)
    path = _NUMERIC_SEG_RE.sub("/{id}", path)
    return path


def _ensure_api_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if path == "/api" or path.startswith("/api/"):
        return path
    return "/api" + path if path.startswith("/") else "/api/" + path


def normalize_api_url(raw: str) -> tuple[str, str]:
    """返回 (host, path_key)。query 丢掉；id 段归并。"""
    text = (raw or "").strip()
    if not text:
        return "", ""
    host = ""
    path = text.split("#", 1)[0].split("?", 1)[0]
    if "://" in text:
        parsed = urlparse(text)
        host = _clip((parsed.netloc or "").lower(), HOST_MAX)
        path = parsed.path or "/"
    path = _ensure_api_path(path)
    path = _collapse_ids(path)
    return host, _clip(path, URL_KEY_MAX)


def _collapse_map_tiles(path: str) -> str:
    match = _MAP_TILE_RE.match(path)
    if not match:
        return path
    rest = match.group(3)
    ext = ""
    leaf = rest.rsplit("/", 1)[-1]
    if "." in leaf:
        ext = "." + leaf.rsplit(".", 1)[-1].split("?", 1)[0]
    return f"{match.group(1)}{{map}}/**{ext}"


def normalize_img_url(raw: str) -> tuple[str, str]:
    """返回 (host, url_key)。data/blob 丢弃。"""
    text = (raw or "").strip()
    if not text:
        return "", ""
    lower = text.lower()
    if lower.startswith("data:") or lower.startswith("blob:"):
        return "", ""
    parsed = urlparse(text)
    host = _clip((parsed.netloc or "").lower(), HOST_MAX)
    path = parsed.path or "/"
    if not host:
        return "", ""
    path = _collapse_map_tiles(path)
    path = _UUID_RE.sub("{id}", path)
    path = _HEX40_RE.sub("{id}", path)
    path = _HEX24_RE.sub("{id}", path)
    path = _NUMERIC_SEG_RE.sub("/{id}", path)
    scheme = "http" if parsed.scheme == "http" else "https"
    key = f"{scheme}://{host}{path}"
    return host, _clip(key, URL_KEY_MAX)


def normalize_method(raw: str | None) -> str:
    method = (raw or "GET").strip().upper()
    if method not in HTTP_METHODS:
        return "GET"
    return method


def _as_duration_ms(value: Any) -> int | None:
    try:
        ms = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if ms < 0 or ms > MAX_DURATION_MS:
        return None
    return ms


def _as_optional_int(value: Any, *, lo: int, hi: int) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n < lo or n > hi:
        return None
    return n


@dataclass
class RumEventIn:
    kind: str
    url: str
    duration_ms: Any
    status: int | None = None
    method: str | None = None
    transfer_size: int | None = None


def ingest_rum_events(
    db: Session,
    *,
    page: str,
    events: list[RumEventIn] | list[Any],
    recorded_at: datetime | None = None,
) -> int:
    """写入合法样本。调用方负责 commit。"""
    now = recorded_at or now_naive()
    page_path = _clip((page or "").strip(), PAGE_MAX)
    accepted = 0
    for raw in events[:MAX_EVENTS_PER_POST]:
        if isinstance(raw, RumEventIn):
            kind = raw.kind
            url = raw.url
            duration = _as_duration_ms(raw.duration_ms)
            status = raw.status
            method_raw = raw.method
            transfer = raw.transfer_size
        else:
            kind = str(getattr(raw, "kind", "") or "")
            url = str(getattr(raw, "url", "") or "")
            duration = _as_duration_ms(getattr(raw, "duration_ms", None))
            status = getattr(raw, "status", None)
            method_raw = getattr(raw, "method", None)
            transfer = getattr(raw, "transfer_size", None)
        if kind not in KINDS or duration is None:
            continue
        raw_url = _clip(url.strip(), 512)
        if kind == KIND_API:
            host, path_key = normalize_api_url(raw_url)
            if not path_key:
                continue
            method = normalize_method(str(method_raw) if method_raw else None)
            url_key = _clip(f"{method} {path_key}", URL_KEY_MAX)
            status_code = _as_optional_int(status, lo=0, hi=599)
            transfer_size = None
        else:
            host, url_key = normalize_img_url(raw_url)
            if not url_key:
                continue
            method = None
            status_code = None
            transfer_size = _as_optional_int(transfer, lo=0, hi=50_000_000)
        db.add(
            RumSample(
                recorded_at=now,
                kind=kind,
                url_key=url_key,
                host=host,
                page_path=page_path,
                duration_ms=duration,
                status_code=status_code,
                transfer_size=transfer_size,
                method=method,
            )
        )
        accepted += 1
    if accepted:
        db.flush()
    return accepted


def prune_rum_samples(db: Session, *, now: datetime | None = None) -> int:
    cutoff = (now or now_naive()) - timedelta(days=KEEP_DAYS)
    deleted = (
        db.query(RumSample)
        .filter(RumSample.recorded_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.flush()
    return int(deleted)


@dataclass
class _Acc:
    durations: list[int] = field(default_factory=list)
    errors: int = 0
    transfer_sum: int = 0
    transfer_n: int = 0
    host: str = ""


def _row_out(
    *,
    url_key: str,
    host: str,
    acc: _Acc,
    kind: str,
) -> dict[str, Any]:
    durs = acc.durations
    count = len(durs)
    avg = int(round(sum(durs) / count)) if count else 0
    out: dict[str, Any] = {
        "url_key": url_key,
        "host": host,
        "count": count,
        "avg_ms": avg,
        "p50_ms": percentile_nearest(durs, 0.50),
        "p95_ms": percentile_nearest(durs, 0.95),
        "max_ms": max(durs) if durs else None,
        "error_count": acc.errors if kind == KIND_API else 0,
        "avg_transfer": (
            int(round(acc.transfer_sum / acc.transfer_n)) if acc.transfer_n else None
        ),
    }
    return out


def rum_series_step(hours: int) -> timedelta:
    if hours <= 1:
        return timedelta(minutes=5)
    if hours <= 6:
        return timedelta(minutes=15)
    if hours <= 24:
        return timedelta(hours=1)
    if hours <= 168:
        return timedelta(hours=6)
    return timedelta(days=1)


def truncate_to_step(dt: datetime, step: timedelta) -> datetime:
    n = to_naive(dt)
    if step >= timedelta(days=1):
        return n.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds = int(step.total_seconds())
    if seconds >= 3600 and seconds % 3600 == 0:
        hour_step = seconds // 3600
        hour = (n.hour // hour_step) * hour_step
        return n.replace(hour=hour, minute=0, second=0, microsecond=0)
    minute_step = max(1, seconds // 60)
    total_min = n.hour * 60 + n.minute
    aligned = (total_min // minute_step) * minute_step
    return n.replace(hour=aligned // 60, minute=aligned % 60, second=0, microsecond=0)


def _series_points(
    *,
    since: datetime,
    moment: datetime,
    step: timedelta,
    buckets: dict[tuple[datetime, str], list[int]],
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    cur = truncate_to_step(since, step)
    last = truncate_to_step(moment, step)
    while cur <= last:
        if len(points) >= 400:
            break
        api_d = buckets.get((cur, KIND_API), [])
        img_d = buckets.get((cur, KIND_IMG), [])
        points.append(
            {
                "at": cur.replace(microsecond=0).isoformat(sep=" "),
                "api_count": len(api_d),
                "img_count": len(img_d),
                "api_p50_ms": percentile_nearest(api_d, 0.50),
                "api_p95_ms": percentile_nearest(api_d, 0.95),
                "img_p50_ms": percentile_nearest(img_d, 0.50),
                "img_p95_ms": percentile_nearest(img_d, 0.95),
            }
        )
        cur += step
    return points


def summarize_rum(
    db: Session,
    *,
    hours: int,
    limit: int = SUMMARY_ROW_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    hours = max(1, min(24 * KEEP_DAYS, int(hours)))
    limit = max(1, min(500, int(limit)))
    moment = now or now_naive()
    since = moment - timedelta(hours=hours)
    step = rum_series_step(hours)
    rows = (
        db.query(
            RumSample.kind,
            RumSample.url_key,
            RumSample.host,
            RumSample.duration_ms,
            RumSample.status_code,
            RumSample.transfer_size,
            RumSample.recorded_at,
        )
        .filter(RumSample.recorded_at >= since)
        .all()
    )
    groups: dict[tuple[str, str, str], _Acc] = defaultdict(_Acc)
    buckets: dict[tuple[datetime, str], list[int]] = defaultdict(list)
    api_durs: list[int] = []
    img_durs: list[int] = []
    for kind, url_key, host, duration_ms, status_code, transfer_size, recorded_at in rows:
        dur = int(duration_ms)
        key = (str(kind), str(url_key), str(host or ""))
        acc = groups[key]
        acc.durations.append(dur)
        acc.host = str(host or "")
        if isinstance(recorded_at, datetime):
            buckets[(truncate_to_step(recorded_at, step), str(kind))].append(dur)
        if kind == KIND_API:
            api_durs.append(dur)
            code = int(status_code) if status_code is not None else 0
            if code == 0 or code >= 400:
                acc.errors += 1
        else:
            img_durs.append(dur)
            if transfer_size:
                acc.transfer_sum += int(transfer_size)
                acc.transfer_n += 1

    def _kind_rows(kind: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for (k, url_key, host), acc in groups.items():
            if k != kind:
                continue
            items.append(_row_out(url_key=url_key, host=host, acc=acc, kind=kind))
        items.sort(key=lambda r: (int(r["p95_ms"] or 0), int(r["count"])), reverse=True)
        return items[:limit]

    return {
        "hours": hours,
        "since": since.replace(microsecond=0).isoformat(sep=" "),
        "api_count": len(api_durs),
        "img_count": len(img_durs),
        "api_p50_ms": percentile_nearest(api_durs, 0.50),
        "api_p95_ms": percentile_nearest(api_durs, 0.95),
        "api_max_ms": max(api_durs) if api_durs else None,
        "img_p50_ms": percentile_nearest(img_durs, 0.50),
        "img_p95_ms": percentile_nearest(img_durs, 0.95),
        "img_max_ms": max(img_durs) if img_durs else None,
        "api": _kind_rows(KIND_API),
        "img": _kind_rows(KIND_IMG),
        "series": _series_points(
            since=since, moment=moment, step=step, buckets=buckets
        ),
    }
