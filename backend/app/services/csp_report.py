"""CSP 违规上报：按 (指令, 被拦来源) 聚合计数，每分钟最多打一条 WARNING，公开接口不能刷爆平台日志。"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import Counter
from urllib.parse import urlsplit

logger = logging.getLogger("zhange.csp")

FLUSH_INTERVAL_SEC = 60.0
MAX_DISTINCT_KEYS = 50
TOP_IN_SUMMARY = 10

_URL_SCHEMES = frozenset({"http", "https", "ws", "wss"})
_UNPRINTABLE = re.compile(r"[^\x21-\x7e]")
_DIRECTIVE_CHARS = re.compile(r"[^a-z0-9-]")

_lock = threading.Lock()
_counts: Counter[tuple[str, str]] = Counter()
_overflow = 0
_window_started = 0.0
_next_flush_at = 0.0
_monotonic = time.monotonic


def summarize_blocked_uri(value: str) -> str:
    """只留 scheme://host[:port] 或关键字（inline / eval / data …），路径与 query 可能带令牌。"""
    text = _UNPRINTABLE.sub("", value or "")
    if not text:
        return "-"
    if ":" not in text:
        return text[:32]
    scheme = text.split(":", 1)[0].lower()
    if scheme in _URL_SCHEMES:
        netloc = urlsplit(text).netloc.rsplit("@", 1)[-1]
        return f"{scheme}://{netloc}"[:128]
    return scheme[:32] or "-"


def normalize_directive(value: str) -> str:
    return _DIRECTIVE_CHARS.sub("", (value or "").lower())[:64] or "-"


def parse_csp_report(raw: bytes) -> tuple[str, str] | None:
    """report-uri 格式 {"csp-report": {...}}；解析失败返回 None。"""
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace")) if raw else None
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    csp = payload.get("csp-report")
    if not isinstance(csp, dict):
        return None
    directive = str(csp.get("effective-directive") or csp.get("violated-directive") or "")
    return normalize_directive(directive), summarize_blocked_uri(str(csp.get("blocked-uri") or ""))


def record_csp_report(raw: bytes) -> None:
    global _overflow, _window_started, _next_flush_at
    parsed = parse_csp_report(raw)
    key = parsed or ("-", "unparsable")
    now = _monotonic()
    with _lock:
        if not _counts and not _overflow:
            _window_started = now
        if key in _counts or len(_counts) < MAX_DISTINCT_KEYS:
            _counts[key] += 1
        else:
            _overflow += 1
        if now < _next_flush_at:
            return
        summary = _drain_locked(now)
        _next_flush_at = now + FLUSH_INTERVAL_SEC
    logger.warning(*summary)


def _drain_locked(now: float) -> tuple[object, ...]:
    global _overflow
    total = sum(_counts.values()) + _overflow
    top = "; ".join(
        f"{directive} {blocked} x{count}"
        for (directive, blocked), count in _counts.most_common(TOP_IN_SUMMARY)
    )
    summary = (
        "csp_report reports=%d distinct=%d window=%.0fs other=%d top=%s",
        total,
        len(_counts),
        max(0.0, now - _window_started),
        _overflow,
        top,
    )
    _counts.clear()
    _overflow = 0
    return summary


def reset_csp_reports_for_tests() -> None:
    global _overflow, _window_started, _next_flush_at
    with _lock:
        _counts.clear()
        _overflow = 0
        _window_started = 0.0
        _next_flush_at = 0.0
