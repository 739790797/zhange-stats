"""Minecraft 性能采样热/冷分层：10 秒原始点 + 1m/1h/1d 聚合档。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timeutil import now_naive, to_naive
from app.models.minecraft import MinecraftPerfRollup, MinecraftPerfSample

GRAIN_1M = "1m"
GRAIN_1H = "1h"
GRAIN_1D = "1d"

RAW_KEEP = timedelta(hours=48)
MINUTE_KEEP = timedelta(days=30)

RANGE_GRAIN: dict[str, str | None] = {
    "30m": None,
    "1h": None,
    "12h": GRAIN_1M,
    "24h": GRAIN_1M,
    "30d": GRAIN_1H,
    "all": GRAIN_1D,
}

_CHILD_GRAIN = {GRAIN_1H: GRAIN_1M, GRAIN_1D: GRAIN_1H}


@dataclass(frozen=True)
class RollupStats:
    sample_count: int
    tps_avg: float | None
    tps_min: float | None
    tps_max: float | None
    mspt_avg: float | None
    mspt_min: float | None
    mspt_max: float | None
    entities_avg: float | None
    entities_max: float | None
    chunks_avg: float | None
    chunks_max: float | None


def grain_step(grain: str) -> timedelta:
    if grain == GRAIN_1M:
        return timedelta(minutes=1)
    if grain == GRAIN_1H:
        return timedelta(hours=1)
    if grain == GRAIN_1D:
        return timedelta(days=1)
    raise ValueError(f"未知 grain: {grain}")


def truncate_to_grain(dt: datetime, grain: str) -> datetime:
    n = to_naive(dt)
    if grain == GRAIN_1M:
        return n.replace(second=0, microsecond=0)
    if grain == GRAIN_1H:
        return n.replace(minute=0, second=0, microsecond=0)
    if grain == GRAIN_1D:
        return n.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"未知 grain: {grain}")


def _avg(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


def stats_from_metric_lists(
    *,
    sample_count: int,
    tps: list[float],
    mspt: list[float],
    entities: list[float],
    chunks: list[float],
) -> RollupStats:
    return RollupStats(
        sample_count=sample_count,
        tps_avg=_avg(tps),
        tps_min=min(tps) if tps else None,
        tps_max=max(tps) if tps else None,
        mspt_avg=_avg(mspt),
        mspt_min=min(mspt) if mspt else None,
        mspt_max=max(mspt) if mspt else None,
        entities_avg=_avg(entities),
        entities_max=max(entities) if entities else None,
        chunks_avg=_avg(chunks),
        chunks_max=max(chunks) if chunks else None,
    )


def stats_from_samples(samples: list[MinecraftPerfSample]) -> RollupStats:
    return stats_from_metric_lists(
        sample_count=len(samples),
        tps=[float(s.tps) for s in samples if s.tps is not None],
        mspt=[float(s.mspt) for s in samples if s.mspt is not None],
        entities=[float(s.entities) for s in samples if s.entities is not None],
        chunks=[float(s.chunks) for s in samples if s.chunks is not None],
    )


def stats_from_rollup_row(row: MinecraftPerfRollup) -> RollupStats:
    return RollupStats(
        sample_count=int(row.sample_count or 0),
        tps_avg=row.tps_avg,
        tps_min=row.tps_min,
        tps_max=row.tps_max,
        mspt_avg=row.mspt_avg,
        mspt_min=row.mspt_min,
        mspt_max=row.mspt_max,
        entities_avg=row.entities_avg,
        entities_max=row.entities_max,
        chunks_avg=row.chunks_avg,
        chunks_max=row.chunks_max,
    )


def _weighted_avg(pairs: list[tuple[float, int]]) -> float | None:
    total_n = sum(n for _avg, n in pairs if n > 0)
    if total_n <= 0:
        return None
    return sum(avg * n for avg, n in pairs if n > 0) / total_n


def merge_stats(parts: list[RollupStats]) -> RollupStats:
    if not parts:
        return stats_from_metric_lists(
            sample_count=0, tps=[], mspt=[], entities=[], chunks=[]
        )
    tps_pairs = [
        (p.tps_avg, p.sample_count)
        for p in parts
        if p.tps_avg is not None and p.sample_count > 0
    ]
    mspt_pairs = [
        (p.mspt_avg, p.sample_count)
        for p in parts
        if p.mspt_avg is not None and p.sample_count > 0
    ]
    ent_pairs = [
        (p.entities_avg, p.sample_count)
        for p in parts
        if p.entities_avg is not None and p.sample_count > 0
    ]
    chunk_pairs = [
        (p.chunks_avg, p.sample_count)
        for p in parts
        if p.chunks_avg is not None and p.sample_count > 0
    ]
    tps_mins = [p.tps_min for p in parts if p.tps_min is not None]
    tps_maxs = [p.tps_max for p in parts if p.tps_max is not None]
    mspt_mins = [p.mspt_min for p in parts if p.mspt_min is not None]
    mspt_maxs = [p.mspt_max for p in parts if p.mspt_max is not None]
    ent_maxs = [p.entities_max for p in parts if p.entities_max is not None]
    chunk_maxs = [p.chunks_max for p in parts if p.chunks_max is not None]
    return RollupStats(
        sample_count=sum(p.sample_count for p in parts),
        tps_avg=_weighted_avg(tps_pairs),
        tps_min=min(tps_mins) if tps_mins else None,
        tps_max=max(tps_maxs) if tps_maxs else None,
        mspt_avg=_weighted_avg(mspt_pairs),
        mspt_min=min(mspt_mins) if mspt_mins else None,
        mspt_max=max(mspt_maxs) if mspt_maxs else None,
        entities_avg=_weighted_avg(ent_pairs),
        entities_max=max(ent_maxs) if ent_maxs else None,
        chunks_avg=_weighted_avg(chunk_pairs),
        chunks_max=max(chunk_maxs) if chunk_maxs else None,
    )


def _apply_stats(row: MinecraftPerfRollup, stats: RollupStats) -> None:
    row.sample_count = stats.sample_count
    row.tps_avg = stats.tps_avg
    row.tps_min = stats.tps_min
    row.tps_max = stats.tps_max
    row.mspt_avg = stats.mspt_avg
    row.mspt_min = stats.mspt_min
    row.mspt_max = stats.mspt_max
    row.entities_avg = stats.entities_avg
    row.entities_max = stats.entities_max
    row.chunks_avg = stats.chunks_avg
    row.chunks_max = stats.chunks_max


def upsert_rollup(
    db: Session, *, grain: str, bucket_at: datetime, stats: RollupStats
) -> None:
    if stats.sample_count <= 0:
        return
    bucket = to_naive(bucket_at)
    row = (
        db.query(MinecraftPerfRollup)
        .filter(
            MinecraftPerfRollup.grain == grain,
            MinecraftPerfRollup.bucket_at == bucket,
        )
        .one_or_none()
    )
    if row is None:
        row = MinecraftPerfRollup(grain=grain, bucket_at=bucket)
        db.add(row)
    _apply_stats(row, stats)


def refresh_minute_bucket(db: Session, minute_start: datetime) -> None:
    start = to_naive(minute_start)
    end = start + timedelta(minutes=1)
    samples = (
        db.query(MinecraftPerfSample)
        .filter(
            MinecraftPerfSample.sampled_at >= start,
            MinecraftPerfSample.sampled_at < end,
        )
        .all()
    )
    if not samples:
        return
    upsert_rollup(db, grain=GRAIN_1M, bucket_at=start, stats=stats_from_samples(samples))


def rollup_parent_bucket(db: Session, *, grain: str, bucket_at: datetime) -> None:
    child = _CHILD_GRAIN.get(grain)
    if child is None:
        return
    start = to_naive(bucket_at)
    end = start + grain_step(grain)
    children = (
        db.query(MinecraftPerfRollup)
        .filter(
            MinecraftPerfRollup.grain == child,
            MinecraftPerfRollup.bucket_at >= start,
            MinecraftPerfRollup.bucket_at < end,
        )
        .all()
    )
    if not children:
        return
    upsert_rollup(
        db,
        grain=grain,
        bucket_at=start,
        stats=merge_stats([stats_from_rollup_row(row) for row in children]),
    )


def _walk_range(
    first: datetime | None, last: datetime | None, grain: str
) -> list[datetime]:
    if first is None or last is None:
        return []
    start = truncate_to_grain(first, grain)
    end = truncate_to_grain(last, grain)
    step = grain_step(grain)
    out: list[datetime] = []
    t = start
    # 含 last 所在桶
    while t <= end:
        out.append(t)
        t = t + step
        if len(out) > 400_000:
            break
    return out


def backfill_minutes_from_raw(db: Session) -> int:
    first = db.query(func.min(MinecraftPerfSample.sampled_at)).scalar()
    last = db.query(func.max(MinecraftPerfSample.sampled_at)).scalar()
    if first is None or last is None:
        return 0
    n = 0
    for hour in _walk_range(first, last, GRAIN_1H):
        hour_end = hour + timedelta(hours=1)
        samples = (
            db.query(MinecraftPerfSample)
            .filter(
                MinecraftPerfSample.sampled_at >= hour,
                MinecraftPerfSample.sampled_at < hour_end,
            )
            .all()
        )
        by_minute: dict[datetime, list[MinecraftPerfSample]] = {}
        for sample in samples:
            minute = truncate_to_grain(sample.sampled_at, GRAIN_1M)
            by_minute.setdefault(minute, []).append(sample)
        for minute, rows in by_minute.items():
            upsert_rollup(
                db, grain=GRAIN_1M, bucket_at=minute, stats=stats_from_samples(rows)
            )
            n += 1
        db.flush()
    return n


def backfill_from_children(db: Session, *, parent_grain: str) -> int:
    child = _CHILD_GRAIN[parent_grain]
    first = (
        db.query(func.min(MinecraftPerfRollup.bucket_at))
        .filter(MinecraftPerfRollup.grain == child)
        .scalar()
    )
    last = (
        db.query(func.max(MinecraftPerfRollup.bucket_at))
        .filter(MinecraftPerfRollup.grain == child)
        .scalar()
    )
    n = 0
    for bucket in _walk_range(first, last, parent_grain):
        rollup_parent_bucket(db, grain=parent_grain, bucket_at=bucket)
        n += 1
        if n % 24 == 0:
            db.flush()
    return n


def prune_raw_and_minutes(db: Session, now: datetime) -> dict[str, int]:
    now_n = to_naive(now)
    raw_cutoff = now_n - RAW_KEEP
    minute_cutoff = now_n - MINUTE_KEEP
    raw_deleted = (
        db.query(MinecraftPerfSample)
        .filter(MinecraftPerfSample.sampled_at < raw_cutoff)
        .delete(synchronize_session=False)
    )
    minute_deleted = (
        db.query(MinecraftPerfRollup)
        .filter(
            MinecraftPerfRollup.grain == GRAIN_1M,
            MinecraftPerfRollup.bucket_at < minute_cutoff,
        )
        .delete(synchronize_session=False)
    )
    return {
        "raw_deleted": int(raw_deleted),
        "minute_deleted": int(minute_deleted),
    }


def maintain_perf_archive(
    db: Session, *, now: datetime | None = None, prune: bool = False
) -> dict[str, Any]:
    """刷新当前/上一分钟与已闭合的小时/日桶。prune=True 时回填缺口并删过期原始/1m。"""
    now_n = to_naive(now) if now is not None else now_naive()
    minute = truncate_to_grain(now_n, GRAIN_1M)
    refresh_minute_bucket(db, minute)
    refresh_minute_bucket(db, minute - timedelta(minutes=1))
    hour = truncate_to_grain(now_n, GRAIN_1H)
    rollup_parent_bucket(db, grain=GRAIN_1H, bucket_at=hour)
    rollup_parent_bucket(db, grain=GRAIN_1H, bucket_at=hour - timedelta(hours=1))
    day = truncate_to_grain(now_n, GRAIN_1D)
    rollup_parent_bucket(db, grain=GRAIN_1D, bucket_at=day)
    rollup_parent_bucket(db, grain=GRAIN_1D, bucket_at=day - timedelta(days=1))
    stats: dict[str, Any] = {"refreshed": True}
    if prune:
        minutes = backfill_minutes_from_raw(db)
        hours = backfill_from_children(db, parent_grain=GRAIN_1H)
        days = backfill_from_children(db, parent_grain=GRAIN_1D)
        deleted = prune_raw_and_minutes(db, now_n)
        stats.update(
            {
                "minutes_backfilled": minutes,
                "hours_backfilled": hours,
                "days_backfilled": days,
                **deleted,
            }
        )
    db.flush()
    return stats


def earliest_archive_at(db: Session) -> datetime | None:
    raw_min = db.query(func.min(MinecraftPerfSample.sampled_at)).scalar()
    roll_min = db.query(func.min(MinecraftPerfRollup.bucket_at)).scalar()
    candidates = [to_naive(v) for v in (raw_min, roll_min) if v is not None]
    return min(candidates) if candidates else None


def fetch_rollup_tuples(
    db: Session, *, grain: str, start: datetime, end: datetime
) -> list[tuple[datetime, float | None, float | None, float | None, float | None]]:
    start_n = to_naive(start)
    end_n = to_naive(end)
    rows = (
        db.query(MinecraftPerfRollup)
        .filter(
            MinecraftPerfRollup.grain == grain,
            MinecraftPerfRollup.bucket_at >= start_n,
            MinecraftPerfRollup.bucket_at <= end_n,
        )
        .order_by(MinecraftPerfRollup.bucket_at.asc())
        .all()
    )
    return [
        (row.bucket_at, row.tps_avg, row.mspt_avg, row.entities_avg, row.chunks_avg)
        for row in rows
    ]
