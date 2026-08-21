"""Minecraft RCON 性能采样分桶。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import BEIJING, now_naive
from app.models.minecraft import MinecraftPerfSample
from app.services.minecraft_perf import bucket_series, resolve_window
from app.services.minecraft_rcon import parse_chunks_text


def test_bucket_series_even_centers_and_edges() -> None:
    start = datetime(2026, 8, 21, 12, 0, 0)
    end = start + timedelta(minutes=30)
    rows = bucket_series(
        [
            (start, 20.0, 5.0, 100.0, 200.0),
            (end, 10.0, 40.0, 80.0, 150.0),
        ],
        start,
        end,
        buckets=4,
    )
    assert len(rows) == 4
    assert rows[0]["tps"] == 20.0
    assert rows[0]["mspt"] == 5.0
    assert rows[0]["entities"] == 100.0
    assert rows[0]["chunks"] == 200.0
    assert rows[1]["tps"] is None
    assert rows[2]["tps"] is None
    assert rows[3]["tps"] == 10.0
    assert rows[3]["mspt"] == 40.0
    assert rows[3]["entities"] == 80.0
    assert rows[3]["chunks"] == 150.0
    times = [datetime.fromisoformat(row["at"]).astimezone(BEIJING) for row in rows]
    deltas = [(times[i + 1] - times[i]).total_seconds() for i in range(3)]
    assert all(abs(delta - deltas[0]) < 0.01 for delta in deltas)
    assert abs(deltas[0] - 7.5 * 60) < 0.01


def test_bucket_series_averages_inside_bucket() -> None:
    start = datetime(2026, 8, 21, 12, 0, 0)
    end = start + timedelta(minutes=30)
    rows = bucket_series(
        [
            (start + timedelta(seconds=1), 10.0, 4.0, 10.0, 20.0),
            (start + timedelta(seconds=2), 20.0, 6.0, 30.0, 40.0),
        ],
        start,
        end,
        buckets=4,
    )
    assert rows[0]["tps"] == 15.0
    assert rows[0]["mspt"] == 5.0
    assert rows[0]["entities"] == 20.0
    assert rows[0]["chunks"] == 30.0
    assert all(row["tps"] is None for row in rows[1:])


def test_parse_essentials_gc_chunks() -> None:
    raw = (
        "Uptime: 1 hour\n"
        'World "world": 512 chunks, 234 entities, 45 tiles.\n'
        'World "world_nether": 64 chunks, 12 entities, 0 tiles.\n'
    )
    assert parse_chunks_text(raw) == 576


def test_parse_chunks_missing() -> None:
    assert parse_chunks_text("TPS from last 5s: 20.0") is None


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    MinecraftPerfSample.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


def test_resolve_window_all_uses_earliest_sample() -> None:
    db = _session()
    end = now_naive()
    first = end - timedelta(hours=5)
    db.add(MinecraftPerfSample(sampled_at=first, tps=20.0, mspt=4.0))
    db.add(MinecraftPerfSample(sampled_at=end - timedelta(minutes=1), tps=19.0, mspt=5.0))
    db.commit()
    start_n, end_n = resolve_window(db, "all", end=end)
    assert start_n == first
    assert end_n == end
    start_30, end_30 = resolve_window(db, "30m", end=end)
    assert end_30 == end
    assert (end_30 - start_30).total_seconds() == 30 * 60
