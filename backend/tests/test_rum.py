"""RUM URL 归并、入库、分位数、保留期。"""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.rum import RumSample
from app.services.rum import (
    RumEventIn,
    ingest_rum_events,
    normalize_api_url,
    normalize_img_url,
    percentile_nearest,
    prune_rum_samples,
    rum_series_step,
    summarize_rum,
    truncate_to_step,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    RumSample.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


def test_percentile_nearest() -> None:
    assert percentile_nearest([], 0.95) is None
    assert percentile_nearest([10], 0.95) == 10
    assert percentile_nearest([1, 2, 3, 4, 5], 0.50) == 3
    assert percentile_nearest([10, 20, 30, 40, 50], 0.95) == 50


def test_normalize_api_collapses_ids() -> None:
    host, key = normalize_api_url(
        "/api/guides/tarkov/items/5447b5f14bdc2d61278b4567?game_mode=pve"
    )
    assert host == ""
    assert key == "/api/guides/tarkov/items/{id}"
    _, raid = normalize_api_url("/api/guides/tarkov/raid-rooms/a1b2c3d4")
    assert raid == "/api/guides/tarkov/raid-rooms/{id}"
    _, members = normalize_api_url("/api/members/42")
    assert members == "/api/members/{id}"
    _, prefixed = normalize_api_url("/guides/tarkov/maps")
    assert prefixed == "/api/guides/tarkov/maps"


def test_normalize_img_collapses_tiles_and_item_icons() -> None:
    host, key = normalize_img_url(
        "https://assets.tarkov.dev/maps/labyrinth/main/0/0/0.png?x=1"
    )
    assert host == "assets.tarkov.dev"
    assert key == "https://assets.tarkov.dev/maps/{map}/**.png"
    _, icon = normalize_img_url(
        "https://assets.tarkov.dev/5448ba0b4bdc2d02308b456c-icon.webp"
    )
    assert icon == "https://assets.tarkov.dev/{id}-icon.webp"
    assert normalize_img_url("data:image/png;base64,aaa") == ("", "")
    assert normalize_img_url("blob:https://example/1") == ("", "")


def test_ingest_and_summarize_percentiles() -> None:
    db = _session()
    now = datetime(2026, 9, 11, 12, 0, 0)
    n = ingest_rum_events(
        db,
        page="/guides/tarkov/maps/factory",
        recorded_at=now,
        events=[
            RumEventIn(
                kind="api",
                url="/api/guides/tarkov/items/5447b5f14bdc2d61278b4567",
                duration_ms=100,
                status=200,
                method="GET",
            ),
            RumEventIn(
                kind="api",
                url="/api/guides/tarkov/items/5447b5f14bdc2d61278b4568",
                duration_ms=400,
                status=200,
                method="GET",
            ),
            RumEventIn(
                kind="api",
                url="/api/guides/tarkov/items/5447b5f14bdc2d61278b4569",
                duration_ms=900,
                status=500,
                method="GET",
            ),
            RumEventIn(
                kind="img",
                url="https://assets.tarkov.dev/maps/factory/1/2/3.png",
                duration_ms=80,
                transfer_size=1200,
            ),
            RumEventIn(
                kind="img",
                url="https://assets.tarkov.dev/maps/factory/4/5/6.png",
                duration_ms=120,
                transfer_size=800,
            ),
            RumEventIn(
                kind="api",
                url="/api/client-rum",
                duration_ms=10,
                status=200,
                method="POST",
            ),
        ],
    )
    db.commit()
    assert n == 6
    summary = summarize_rum(db, hours=24, now=now)
    assert summary["api_count"] == 4
    assert summary["img_count"] == 2
    api_row = next(r for r in summary["api"] if r["url_key"].endswith("/items/{id}"))
    assert api_row["count"] == 3
    assert api_row["error_count"] == 1
    assert api_row["p50_ms"] == 400
    img_row = summary["img"][0]
    assert img_row["url_key"] == "https://assets.tarkov.dev/maps/{map}/**.png"
    assert img_row["count"] == 2
    assert img_row["avg_transfer"] == 1000
    filled = [p for p in summary["series"] if p["api_count"] or p["img_count"]]
    assert len(filled) == 1
    assert filled[0]["api_count"] == 4
    assert filled[0]["img_p95_ms"] == 120


def test_truncate_and_series_step() -> None:
    assert rum_series_step(1) == timedelta(minutes=5)
    assert rum_series_step(24) == timedelta(hours=1)
    assert rum_series_step(336) == timedelta(days=1)
    assert truncate_to_step(
        datetime(2026, 9, 11, 12, 7, 30), timedelta(minutes=5)
    ) == datetime(2026, 9, 11, 12, 5, 0)
    assert truncate_to_step(
        datetime(2026, 9, 11, 13, 47, 0), timedelta(hours=6)
    ) == datetime(2026, 9, 11, 12, 0, 0)


def test_summarize_series_two_buckets() -> None:
    db = _session()
    now = datetime(2026, 9, 11, 12, 0, 0)
    ingest_rum_events(
        db,
        page="/",
        recorded_at=now - timedelta(hours=2),
        events=[RumEventIn(kind="api", url="/api/a", duration_ms=100, method="GET")],
    )
    ingest_rum_events(
        db,
        page="/",
        recorded_at=now,
        events=[RumEventIn(kind="api", url="/api/a", duration_ms=400, method="GET")],
    )
    db.commit()
    summary = summarize_rum(db, hours=6, now=now)
    filled = [p for p in summary["series"] if p["api_count"]]
    assert [p["api_p95_ms"] for p in filled] == [100, 400]


def test_ingest_drops_bad_events() -> None:
    db = _session()
    n = ingest_rum_events(
        db,
        page="/",
        events=[
            RumEventIn(kind="other", url="/api/x", duration_ms=10),
            RumEventIn(kind="api", url="/api/x", duration_ms=-1),
            RumEventIn(kind="api", url="/api/x", duration_ms=999999),
            RumEventIn(kind="img", url="", duration_ms=10),
        ],
    )
    assert n == 0


def test_prune_rum_keeps_two_weeks() -> None:
    db = _session()
    now = datetime(2026, 9, 11, 12, 0, 0)
    ingest_rum_events(
        db,
        page="/",
        recorded_at=now - timedelta(days=15),
        events=[RumEventIn(kind="api", url="/api/old", duration_ms=10, method="GET")],
    )
    ingest_rum_events(
        db,
        page="/",
        recorded_at=now - timedelta(days=2),
        events=[RumEventIn(kind="api", url="/api/new", duration_ms=10, method="GET")],
    )
    db.commit()
    deleted = prune_rum_samples(db, now=now)
    db.commit()
    assert deleted == 1
    left = db.query(RumSample).all()
    assert len(left) == 1
    assert left[0].url_key == "GET /api/new"
