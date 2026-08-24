"""统一日志行结构与筛选（内存环缓冲 / 持久化文件共用）。"""

from __future__ import annotations

from dataclasses import dataclass

_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


@dataclass(frozen=True)
class LogLine:
    id: int
    ts: str
    level: str
    logger: str
    biz: str
    context: str
    message: str

    @property
    def dedupe_key(self) -> str:
        return f"{self.ts}|{self.level}|{self.logger}|{self.biz}|{self.context}|{self.message}"


def filter_log_lines(
    rows: list[LogLine],
    *,
    limit: int = 200,
    min_level: str | None = None,
    logger_prefix: str | None = None,
    biz_prefix: str | None = None,
    q: str | None = None,
    after_id: int = 0,
) -> list[LogLine]:
    limit = max(1, min(int(limit), 2000))
    min_num = _LEVEL_ORDER.get((min_level or "").upper()) if min_level else None
    prefix = (logger_prefix or "").strip()
    biz = (biz_prefix or "").strip()
    needle = (q or "").strip().lower()
    after = max(0, int(after_id or 0))

    out: list[LogLine] = []
    for line in rows:
        if line.id > 0 and line.id <= after:
            continue
        if min_num is not None and _LEVEL_ORDER.get(line.level, 0) < min_num:
            continue
        if prefix and not (
            line.logger == prefix or line.logger.startswith(f"{prefix}.")
        ):
            continue
        if biz and not (line.biz == biz or line.biz.startswith(f"{biz}.")):
            continue
        if needle:
            haystacks = (
                line.message.lower(),
                line.logger.lower(),
                line.biz.lower(),
                line.context.lower(),
            )
            if not any(needle in h for h in haystacks):
                continue
        out.append(line)

    if after <= 0:
        return out[-limit:]
    return out[:limit]


def merge_log_lines(
    *groups: list[LogLine],
    limit: int = 400,
) -> list[LogLine]:
    """按时间合并多来源日志，去重后重排 id。"""
    seen: set[str] = set()
    merged: list[LogLine] = []
    for group in groups:
        for line in group:
            key = line.dedupe_key
            if key in seen:
                continue
            seen.add(key)
            merged.append(line)
    merged.sort(key=lambda x: (x.ts, x.id))
    trimmed = merged[-max(1, limit) :]
    return [
        LogLine(
            id=idx + 1,
            ts=line.ts,
            level=line.level,
            logger=line.logger,
            biz=line.biz,
            context=line.context,
            message=line.message,
        )
        for idx, line in enumerate(trimmed)
    ]
