"""Minecraft 性能热/冷分层：桶截断、聚合、保留期。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import now_naive
from app.models.minecraft import MinecraftPerfRollup, MinecraftPerfSample
from app.services.minecraft.perf import resolve_window
from app.services.minecraft.perf_rollup import (
    GRAIN_1D,
    GRAIN_1H,
    GRAIN_1M,
    RANGE_GRAIN,
    RollupStats,
    backfill_from_children,
    backfill_minutes_from_raw,
    earliest_archive_at,
    fetch_rollup_tuples,
    maintain_perf_archive,
    merge_stats,
    prune_raw_and_minutes,
    stats_from_metric_lists,
    truncate_to_grain,
)


def test_truncate_to_grain() -> None:
    dt = datetime(2026, 8, 26, 13, 47, 32)
    assert truncate_to_grain(dt, GRAIN_1M) == datetime(2026, 8, 26, 13, 47, 0)
    assert truncate_to_grain(dt, GRAIN_1H) == datetime(2026, 8, 26, 13, 0, 0)
    assert truncate_to_grain(dt, GRAIN_1D) == datetime(2026, 8, 26, 0, 0, 0)


def test_merge_stats_keeps_min_tps_max_mspt() -> None:
    a = stats_from_metric_lists(
        sample_count=2,
        tps=[20.0, 18.0],
        mspt=[5.0, 8.0],
        entities=[10.0],
        chunks=[100.0],
    )
    b = stats_from_metric_lists(
        sample_count=1,
        tps=[10.0],
        mspt=[40.0],
        entities=[30.0],
        chunks=[80.0],
    )
    merged = merge_stats([a, b])
    assert merged.sample_count == 3
    assert merged.tps_min == 10.0
    assert merged.tps_max == 20.0
    assert abs((merged.tps_avg or 0) - (20 + 18 + 10) / 3) < 1e-9
    assert merged.mspt_max == 40.0
    assert merged.entities_max == 30.0


def test_range_grain_mapping() -> None:
    assert RANGE_GRAIN["30m"] is None
    assert RANGE_GRAIN["1h"] is None
    assert RANGE_GRAIN["12h"] == GRAIN_1M
    assert RANGE_GRAIN["24h"] == GRAIN_1M
    assert RANGE_GRAIN["30d"] == GRAIN_1H
    assert RANGE_GRAIN["all"] == GRAIN_1D


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    MinecraftPerfSample.__table__.create(bind=engine)
    MinecraftPerfRollup.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


def test_maintain_writes_minute_and_hour() -> None:
    db = _session()
    now = datetime(2026, 8, 26, 12, 5, 20)
    db.add(
        MinecraftPerfSample(
            sampled_at=datetime(2026, 8, 26, 12, 5, 10),
            tps=20.0,
            mspt=4.0,
            entities=10.0,
            chunks=100.0,
        )
    )
    db.add(
        MinecraftPerfSample(
            sampled_at=datetime(2026, 8, 26, 12, 5, 18),
            tps=10.0,
            mspt=12.0,
            entities=20.0,
            chunks=80.0,
        )
    )
    db.commit()
    maintain_perf_archive(db, now=now, prune=False)
    db.commit()
    minute = (
        db.query(MinecraftPerfRollup)
        .filter(
            MinecraftPerfRollup.grain == GRAIN_1M,
            MinecraftPerfRollup.bucket_at == datetime(2026, 8, 26, 12, 5, 0),
        )
        .one()
    )
    assert minute.sample_count == 2
    assert minute.tps_avg == 15.0
    assert minute.tps_min == 10.0
    assert minute.mspt_max == 12.0
    hour = (
        db.query(MinecraftPerfRollup)
        .filter(
            MinecraftPerfRollup.grain == GRAIN_1H,
            MinecraftPerfRollup.bucket_at == datetime(2026, 8, 26, 12, 0, 0),
        )
        .one()
    )
    assert hour.sample_count == 2
    assert hour.tps_min == 10.0


def test_prune_keeps_recent_raw_and_drops_old() -> None:
    db = _session()
    now = now_naive()
    db.add(
        MinecraftPerfSample(
            sampled_at=now - timedelta(hours=50), tps=19.0, mspt=6.0
        )
    )
    db.add(MinecraftPerfSample(sampled_at=now - timedelta(minutes=5), tps=20.0, mspt=5.0))
    db.commit()
    deleted = prune_raw_and_minutes(db, now)
    db.commit()
    assert deleted["raw_deleted"] == 1
    assert db.query(MinecraftPerfSample).count() == 1


def test_backfill_and_all_window_uses_rollup() -> None:
    db = _session()
    now = datetime(2026, 8, 26, 18, 0, 0)
    first = now - timedelta(days=2)
    db.add(MinecraftPerfSample(sampled_at=first, tps=16.0, mspt=20.0))
    db.add(MinecraftPerfSample(sampled_at=now - timedelta(minutes=2), tps=20.0, mspt=4.0))
    db.commit()
    assert backfill_minutes_from_raw(db) >= 2
    assert backfill_from_children(db, parent_grain=GRAIN_1H) >= 1
    assert backfill_from_children(db, parent_grain=GRAIN_1D) >= 1
    db.commit()
    start, end = resolve_window(db, "all", end=now)
    assert start <= first
    assert end == now
    assert earliest_archive_at(db) is not None
    day_rows = fetch_rollup_tuples(
        db, grain=GRAIN_1D, start=first.replace(hour=0, minute=0, second=0), end=now
    )
    assert day_rows


def test_merge_empty_is_zero() -> None:
    empty = merge_stats([])
    assert empty == RollupStats(
        sample_count=0,
        tps_avg=None,
        tps_min=None,
        tps_max=None,
        mspt_avg=None,
        mspt_min=None,
        mspt_max=None,
        entities_avg=None,
        entities_max=None,
        chunks_avg=None,
        chunks_max=None,
    )
