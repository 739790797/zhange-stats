"""Minecraft presence poller / timeline helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import BEIJING, now_naive
from app.models.minecraft import MinecraftPresenceSegment
from app.services.minecraft.presence import (
    apply_snapshot,
    build_presence_range,
    _clip_to_window,
)
from app.services.minecraft.rcon import parse_list_names


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    MinecraftPresenceSegment.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


def test_parse_list_names_vanilla() -> None:
    assert parse_list_names(
        "There are 2 of a max of 20 players online: BaiYi, zhanjun"
    ) == ["BaiYi", "zhanjun"]
    assert parse_list_names("There are 0 of a max of 20 players online:") == []
    assert parse_list_names("当前有 1 名玩家在线：Steve") == ["Steve"]
    assert parse_list_names("There are 2 players online: Alice and Bob") == [
        "Alice",
        "Bob",
    ]


def test_clip_to_window() -> None:
    start = datetime(2026, 8, 21, tzinfo=BEIJING)
    end = datetime(2026, 8, 22, tzinfo=BEIJING)
    window_start = datetime(2026, 8, 21, 12, tzinfo=BEIJING)
    window_end = datetime(2026, 8, 21, 18, tzinfo=BEIJING)
    clipped = _clip_to_window(
        start, end, window_start, window_end, span_seconds=6 * 3600
    )
    assert clipped == (0, 6 * 3600)


def test_apply_snapshot_only_tracks_online():
    db = _session()
    t0 = now_naive()
    stats = apply_snapshot(
        db,
        now_dt=t0,
        online=[{"name": "BaiYi", "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],
        known=[{"name": "Steve", "id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}],
        complete=True,
        stale_after=timedelta(minutes=3),
    )
    db.commit()
    assert stats["opened"] == 1
    rows = db.query(MinecraftPresenceSegment).all()
    assert len(rows) == 1
    assert rows[0].player_name == "BaiYi"
    assert rows[0].status == "online"

    t1 = t0 + timedelta(minutes=5)
    apply_snapshot(
        db,
        now_dt=t1,
        online=[],
        known=[{"name": "BaiYi", "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],
        complete=True,
        stale_after=timedelta(minutes=3),
    )
    db.commit()
    online_closed = (
        db.query(MinecraftPresenceSegment)
        .filter(MinecraftPresenceSegment.player_name == "BaiYi")
        .one()
    )
    assert online_closed.status == "online"
    assert online_closed.ended_at is not None
    assert db.query(MinecraftPresenceSegment).count() == 1


def test_incomplete_sample_does_not_close_online() -> None:
    db = _session()
    t0 = now_naive()
    apply_snapshot(
        db,
        now_dt=t0,
        online=[{"name": "BaiYi", "id": ""}],
        known=[{"name": "BaiYi", "id": ""}],
        complete=True,
        stale_after=timedelta(minutes=3),
    )
    db.commit()
    t1 = t0 + timedelta(minutes=1)
    apply_snapshot(
        db,
        now_dt=t1,
        online=[],
        known=[{"name": "BaiYi", "id": ""}],
        complete=False,
        stale_after=timedelta(minutes=3),
    )
    db.commit()
    row = db.query(MinecraftPresenceSegment).one()
    assert row.status == "online"
    assert row.ended_at is None


def test_build_presence_range_counts_online_seconds() -> None:
    db = _session()
    start = datetime(2026, 8, 21, 10, 0, 0)
    db.add(
        MinecraftPresenceSegment(
            player_key="name:baiyi",
            player_name="BaiYi",
            player_uuid="",
            status="online",
            started_at=start,
            last_seen_at=start + timedelta(hours=2),
            ended_at=start + timedelta(hours=2),
        )
    )
    db.commit()
    data = build_presence_range(db, date(2026, 8, 21), date(2026, 8, 21))
    assert data["span_seconds"] == 86400
    assert data["rows"][0]["online_seconds"] == 2 * 3600
    assert data["rows"][0]["segments"][0]["start_sec"] == 10 * 3600
    assert data["rows"][0]["segments"][0]["end_sec"] == 12 * 3600


def test_build_presence_range_skips_offline_segments() -> None:
    db = _session()
    start = datetime(2026, 8, 21, 8, 0, 0)
    db.add(
        MinecraftPresenceSegment(
            player_key="name:steve",
            player_name="Steve",
            player_uuid="",
            status="offline",
            started_at=start,
            last_seen_at=start + timedelta(hours=4),
            ended_at=start + timedelta(hours=4),
        )
    )
    db.commit()
    data = build_presence_range(db, date(2026, 8, 21), date(2026, 8, 21))
    assert data["rows"] == []
