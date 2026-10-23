"""图鉴 raw 模板：压缩、落库、失败不覆盖。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.guide_raw import GuideRaw
from app.services.guide_raw.codec import pack_raw_text, unpack_raw_text
from app.services.guide_raw.pipeline import GuideRawPipeline, RawSpec, raw_fingerprint, upsert_raw


def _db() -> Session:
    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    return sessionmaker(bind=engine)()


def test_pack_roundtrip_and_small_text_stays_plain() -> None:
    plain = '{"ok": true}'
    assert pack_raw_text(plain) == plain
    packed = pack_raw_text("x" * 80, min_bytes=16)
    assert packed.startswith("gz1:")
    assert unpack_raw_text(packed) == "x" * 80


def test_unchanged_body_keeps_synced_at_and_reject_keeps_old_row() -> None:
    db = _db()
    first = upsert_raw(db, "demo", "items", "https://example/items", "alpha")
    row = db.query(GuideRaw).filter_by(game="demo", resource="items").one()
    assert row.content_fingerprint == raw_fingerprint("alpha")
    row.synced_at = datetime(2020, 1, 1, 0, 0, 0)
    row.content_fingerprint = None  # legacy row: first unchanged sync backfills the hash
    db.commit()
    second = upsert_raw(db, "demo", "items", "https://example/items", "alpha")
    db.expire_all()
    kept = db.query(GuideRaw).filter_by(game="demo", resource="items").one()
    assert second["changed"] is False
    assert kept.content_fingerprint == raw_fingerprint("alpha")
    assert kept.synced_at == datetime(2020, 1, 1, 0, 0, 0)
    assert first["resource"] == "items"

    def reject(body: str) -> None:
        if body == "beta":
            raise ValueError("nope")

    pipeline = GuideRawPipeline(
        "demo",
        (RawSpec("items", "https://example/items", lambda: "beta", reject),),
    )
    results = pipeline.sync(db)
    assert results[0]["ok"] is False
    db.expire_all()
    still = db.query(GuideRaw).filter_by(game="demo", resource="items").one()
    assert unpack_raw_text(still.raw_body) == "alpha"
    assert pipeline.load_texts(db) == {"items": "alpha"}
