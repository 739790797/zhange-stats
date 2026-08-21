"""经 RCON 采集 Minecraft TPS/MSPT，落库后按时间窗分桶给总览折线。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.core.timeutil import ensure, now, now_naive, to_naive
from app.models.minecraft import MinecraftPerfSample
from app.services.integrations_config import get_minecraft_rcon_credentials
from app.services.minecraft_entities import query_entities
from app.services.minecraft_rcon import (
    MinecraftRconError,
    query_chunks,
    query_perf,
    reset_session,
    session_connected,
)
from app.services.platform_features import is_feature_enabled

logger = logging.getLogger(__name__)

LEGACY_KV_KEY = "minecraft:rcon_perf:v1"
STATUS_KEY = "minecraft:rcon_perf:status:v1"
ENTITY_KEY = "minecraft:rcon_entities:v1"
STATUS_TTL_SEC = 2 * 3600
SAMPLE_INTERVAL_SEC = 10
ENTITY_INTERVAL_SEC = 30
CHART_BUCKETS = 180
RAW_CAP = 4000

PerfRange = Literal["30m", "1h", "12h", "24h", "30d", "all"]
PERF_RANGES: tuple[PerfRange, ...] = ("30m", "1h", "12h", "24h", "30d", "all")
RANGE_SECONDS: dict[str, int] = {
    "30m": 30 * 60,
    "1h": 3600,
    "12h": 12 * 3600,
    "24h": 24 * 3600,
    "30d": 30 * 86400,
}


def _empty_status() -> dict[str, Any]:
    return {
        "ok": False,
        "message": "",
        "tps": None,
        "mspt": None,
        "entity_total": None,
        "chunks": None,
        "at": "",
    }


def _to_iso(dt: datetime) -> str:
    return ensure(dt).isoformat(timespec="seconds")


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def bucket_series(
    samples: list[
        tuple[
            datetime,
            float | None,
            float | None,
            float | None,
            float | None,
        ]
    ],
    start: datetime,
    end: datetime,
    buckets: int = CHART_BUCKETS,
) -> list[dict[str, Any]]:
    """把样本填进 [start, end] 上等宽时间桶；空桶指标为 None。"""
    start_n = to_naive(start)
    end_n = to_naive(end)
    span = (end_n - start_n).total_seconds()
    if span <= 0 or buckets < 1:
        return []
    width = span / buckets
    keys = ("tps", "mspt", "entities", "chunks")
    sums = {key: [0.0] * buckets for key in keys}
    counts = {key: [0] * buckets for key in keys}
    for at, tps, mspt, entities, chunks in samples:
        offset = (to_naive(at) - start_n).total_seconds()
        if offset < 0 or offset > span:
            continue
        idx = int(offset / width)
        if idx >= buckets:
            idx = buckets - 1
        for key, value in (
            ("tps", tps),
            ("mspt", mspt),
            ("entities", entities),
            ("chunks", chunks),
        ):
            if value is not None:
                sums[key][idx] += value
                counts[key][idx] += 1
    out: list[dict[str, Any]] = []
    for i in range(buckets):
        center = start_n + timedelta(seconds=(i + 0.5) * width)
        row: dict[str, Any] = {"at": _to_iso(center)}
        for key in keys:
            n = counts[key][i]
            row[key] = (sums[key][i] / n) if n else None
        out.append(row)
    return out


def resolve_window(
    db: Session, range_key: str, end: datetime | None = None
) -> tuple[datetime, datetime]:
    if range_key not in PERF_RANGES:
        raise ValueError("不支持的时间段")
    end_n = to_naive(end) if end is not None else now_naive()
    if range_key == "all":
        first = db.query(func.min(MinecraftPerfSample.sampled_at)).scalar()
        if first is None:
            start_n = end_n - timedelta(seconds=RANGE_SECONDS["30m"])
        else:
            start_n = to_naive(first)
            if start_n >= end_n:
                start_n = end_n - timedelta(seconds=1)
        return start_n, end_n
    return end_n - timedelta(seconds=RANGE_SECONDS[range_key]), end_n


def _fetch_samples(
    db: Session, start_n: datetime, end_n: datetime
) -> list[MinecraftPerfSample]:
    filters = (
        MinecraftPerfSample.sampled_at >= start_n,
        MinecraftPerfSample.sampled_at <= end_n,
    )
    count = (
        db.query(func.count(MinecraftPerfSample.id)).filter(*filters).scalar() or 0
    )
    query = (
        db.query(MinecraftPerfSample)
        .filter(*filters)
        .order_by(MinecraftPerfSample.sampled_at.asc())
    )
    if count <= RAW_CAP:
        return query.all()
    stride = max(1, count // RAW_CAP)
    return query.filter(MinecraftPerfSample.id % stride == 0).all()


def _parse_legacy_at(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return to_naive(datetime.fromisoformat(text))
    except ValueError:
        return None


def _maybe_import_legacy(db: Session) -> None:
    raw = ephemeral_get(LEGACY_KV_KEY)
    if not raw:
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        ephemeral_delete(LEGACY_KV_KEY)
        return
    samples = data.get("samples") if isinstance(data, dict) else None
    if isinstance(samples, list) and db.query(MinecraftPerfSample.id).first() is None:
        for row in samples:
            if not isinstance(row, dict):
                continue
            at = _parse_legacy_at(str(row.get("at") or ""))
            if at is None:
                continue
            db.add(
                MinecraftPerfSample(
                    sampled_at=at,
                    tps=_as_float(row.get("tps")),
                    mspt=_as_float(row.get("mspt")),
                    entities=_as_float(row.get("entities")),
                    chunks=_as_float(row.get("chunks")),
                )
            )
    ephemeral_delete(LEGACY_KV_KEY)


def _empty_entities() -> dict[str, Any]:
    return {
        "ok": False,
        "message": "",
        "total": 0,
        "command": "",
        "categories": [],
        "types": [],
        "type_count": 0,
        "worlds": [],
        "at": "",
    }


def _save_entities(state: dict[str, Any]) -> None:
    ephemeral_set(ENTITY_KEY, json.dumps(state, ensure_ascii=False), ttl_sec=STATUS_TTL_SEC)


def load_entities() -> dict[str, Any]:
    raw = ephemeral_get(ENTITY_KEY)
    if not raw:
        return _empty_entities()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _empty_entities()
    if not isinstance(data, dict):
        return _empty_entities()
    categories = data.get("categories") if isinstance(data.get("categories"), list) else []
    types = data.get("types") if isinstance(data.get("types"), list) else []
    worlds = data.get("worlds") if isinstance(data.get("worlds"), list) else []
    return {
        "ok": bool(data.get("ok")),
        "message": str(data.get("message") or ""),
        "total": int(data.get("total") or 0),
        "command": str(data.get("command") or ""),
        "categories": categories,
        "types": types,
        "type_count": int(data.get("type_count") or len(types)),
        "worlds": worlds,
        "at": str(data.get("at") or ""),
    }


def _entities_due(cached: dict[str, Any]) -> bool:
    if not cached.get("ok"):
        return True
    stamp = str(cached.get("at") or "")
    if not stamp:
        return True
    try:
        at = datetime.fromisoformat(stamp)
    except ValueError:
        return True
    return (now() - ensure(at)).total_seconds() >= ENTITY_INTERVAL_SEC


def collect_entities(host: str, port: int, password: str) -> None:
    cached = load_entities()
    if not _entities_due(cached):
        return
    stamp = now().isoformat(timespec="seconds")
    try:
        parsed = query_entities(host, port, password)
        _save_entities(
            {
                "ok": True,
                "message": "",
                "at": stamp,
                **parsed,
            }
        )
    except MinecraftRconError as exc:
        logger.info("minecraft rcon entities: %s", exc.message)
        _save_entities(
            {
                **_empty_entities(),
                "ok": False,
                "message": exc.message,
                "at": stamp,
            }
        )
    except OSError as exc:
        logger.info("minecraft rcon entities os: %s", exc)
        _save_entities(
            {
                **_empty_entities(),
                "ok": False,
                "message": str(exc) or "无法连接 RCON",
                "at": stamp,
            }
        )


def _save_status(state: dict[str, Any]) -> None:
    ephemeral_set(STATUS_KEY, json.dumps(state, ensure_ascii=False), ttl_sec=STATUS_TTL_SEC)


def load_status(db: Session | None = None) -> dict[str, Any]:
    raw = ephemeral_get(STATUS_KEY)
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            return {
                "ok": bool(data.get("ok")),
                "message": str(data.get("message") or ""),
                "tps": _as_float(data.get("tps")),
                "mspt": _as_float(data.get("mspt")),
                "entity_total": _as_float(
                    data.get("entity_total", data.get("entities"))
                ),
                "chunks": _as_float(data.get("chunks")),
                "at": str(data.get("at") or ""),
            }
    if db is None:
        return _empty_status()
    last = (
        db.query(MinecraftPerfSample)
        .order_by(MinecraftPerfSample.sampled_at.desc())
        .first()
    )
    if last is None:
        return _empty_status()
    return {
        "ok": True,
        "message": "",
        "tps": last.tps,
        "mspt": last.mspt,
        "entity_total": last.entities,
        "chunks": last.chunks,
        "at": _to_iso(last.sampled_at),
    }


def _rcon_ready(db: Session) -> tuple[bool, str, int, str]:
    host, port, password = get_minecraft_rcon_credentials(db)
    if host and password:
        return True, host, port, password
    return False, host, port, password


def collect_perf(db: Session) -> None:
    _maybe_import_legacy(db)
    enabled, host, port, password = _rcon_ready(db)
    if not enabled:
        reset_session()
        _save_status(
            {
                "ok": False,
                "message": "未配置 RCON",
                "tps": None,
                "mspt": None,
                "entity_total": None,
                "chunks": None,
                "at": "",
            }
        )
        _save_entities(_empty_entities())
        db.commit()
        return
    db.commit()
    stamp = now().isoformat(timespec="seconds")
    sampled_at = now_naive()
    collect_entities(host, port, password)
    entities_state = load_entities()
    entities_total = (
        float(int(entities_state.get("total") or 0))
        if entities_state.get("ok")
        else None
    )

    chunks_total: float | None = None
    try:
        chunk_hit = query_chunks(host, port, password)
        if chunk_hit and chunk_hit.get("chunks") is not None:
            chunks_total = float(int(chunk_hit["chunks"]))
    except MinecraftRconError as exc:
        logger.info("minecraft rcon chunks: %s", exc.message)
    except OSError as exc:
        logger.info("minecraft rcon chunks os: %s", exc)

    try:
        parsed = query_perf(host, port, password)
        tps = _as_float(parsed.get("tps"))
        mspt = _as_float(parsed.get("mspt"))
        db.add(
            MinecraftPerfSample(
                sampled_at=sampled_at,
                tps=tps,
                mspt=mspt,
                entities=entities_total,
                chunks=chunks_total,
            )
        )
        db.commit()
        _save_status(
            {
                "ok": True,
                "message": "",
                "tps": tps,
                "mspt": mspt,
                "entity_total": entities_total,
                "chunks": chunks_total,
                "at": stamp,
            }
        )
    except MinecraftRconError as exc:
        db.rollback()
        _save_status(
            {
                "ok": False,
                "message": exc.message,
                "tps": None,
                "mspt": None,
                "entity_total": entities_total,
                "chunks": chunks_total,
                "at": stamp,
            }
        )
        logger.info("minecraft rcon perf: %s", exc.message)
    except OSError as exc:
        db.rollback()
        _save_status(
            {
                "ok": False,
                "message": str(exc) or "无法连接 RCON",
                "tps": None,
                "mspt": None,
                "entity_total": entities_total,
                "chunks": chunks_total,
                "at": stamp,
            }
        )
        logger.info("minecraft rcon perf os: %s", exc)


def read_public_perf(db: Session, range_key: str = "30m") -> dict[str, Any]:
    _maybe_import_legacy(db)
    db.commit()
    enabled, _host, _port, _password = _rcon_ready(db)
    start_n, end_n = resolve_window(db, range_key)
    rows = _fetch_samples(db, start_n, end_n)
    tuples = [
        (row.sampled_at, row.tps, row.mspt, row.entities, row.chunks)
        for row in rows
    ]
    samples = bucket_series(tuples, start_n, end_n) if tuples else []
    status = load_status(db)
    message = str(status.get("message") or "")
    if not enabled:
        message = "" if samples else "未配置 RCON"
    return {
        "enabled": enabled,
        "ok": bool(status.get("ok")) if enabled else False,
        "connected": bool(enabled and session_connected()),
        "message": message,
        "tps": status.get("tps") if enabled else None,
        "mspt": status.get("mspt") if enabled else None,
        "chunks": status.get("chunks") if enabled else None,
        "range": range_key,
        "range_start": _to_iso(start_n),
        "range_end": _to_iso(end_n),
        "samples": samples,
        "entities": load_entities() if enabled else _empty_entities(),
    }


def poll_job_wrapper() -> None:
    db = SessionLocal()
    try:
        if not is_feature_enabled(db, "guides.minecraft"):
            reset_session()
            _save_entities(_empty_entities())
            return
        collect_perf(db)
    except Exception:
        logger.exception("minecraft rcon perf job failed")
    finally:
        db.close()
