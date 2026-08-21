"""Minecraft 玩家在线/离线片段：轮询写入 + 时间窗查询。"""

from __future__ import annotations

import logging
import re
import threading
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timeutil import day_bounds, ensure, now, now_naive, to_naive
from app.models.job_run import JobRun
from app.models.minecraft import MinecraftPresenceSegment
from app.services import minecraft_profile as profile_svc
from app.services import minecraft_status as status_svc
from app.services.integrations_config import (
    get_minecraft_public_address,
    get_minecraft_rcon_credentials,
)
from app.services.minecraft_rcon import MinecraftRconError, query_list
from app.services.platform_features import is_feature_enabled
from app.services.scheduler_config import load_scheduler_config

logger = logging.getLogger(__name__)

JOB_KEY = "minecraft_presence"
MAX_RANGE_DAYS = 31
_poll_lock = threading.Lock()


def _aware(dt: datetime) -> datetime:
    return ensure(dt)


def _naive(dt: datetime) -> datetime:
    return to_naive(dt)


def _player_uuid(row: dict[str, Any]) -> str:
    uid = re.sub(r"[^0-9a-f]", "", str(row.get("id") or "").lower())
    return uid if len(uid) == 32 else ""


def _normalize_player(row: dict[str, Any], name_map: dict[str, str]) -> dict[str, str] | None:
    name = str(row.get("name") or "").strip()
    uid = _player_uuid(row)
    key = f"id:{uid}" if uid else (f"name:{name.lower()}" if name else "")
    if not key:
        return None
    mapped = name_map.get(name.lower(), "") if name else ""
    if key.startswith("name:") and mapped:
        key = mapped
        if mapped.startswith("id:"):
            uid = mapped[3:]
    return {"key": key, "name": name or uid, "uuid": uid}


def _index_name_map(
    known: list[dict[str, Any]],
    opens: list[MinecraftPresenceSegment],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in known:
        player = _normalize_player(row, {})
        if not player:
            continue
        name = player["name"].lower()
        if not name:
            continue
        current = mapping.get(name, "")
        if not current or (player["key"].startswith("id:") and not current.startswith("id:")):
            mapping[name] = player["key"]
    for seg in opens:
        name = (seg.player_name or "").strip().lower()
        if not name:
            continue
        current = mapping.get(name, "")
        if not current or (seg.player_key.startswith("id:") and not current.startswith("id:")):
            mapping[name] = seg.player_key
    return mapping


def _open_segments(db: Session) -> list[MinecraftPresenceSegment]:
    return (
        db.query(MinecraftPresenceSegment)
        .filter(MinecraftPresenceSegment.ended_at.is_(None))
        .order_by(MinecraftPresenceSegment.started_at.desc())
        .all()
    )


def _collapse_duplicate_opens(
    db: Session,
    rows: list[MinecraftPresenceSegment],
    now_dt: datetime,
    stats: dict[str, int],
) -> dict[str, MinecraftPresenceSegment]:
    by_key: dict[str, MinecraftPresenceSegment] = {}
    for seg in rows:
        current = by_key.get(seg.player_key)
        if current is None:
            by_key[seg.player_key] = seg
            continue
        seg.ended_at = now_dt
        seg.last_seen_at = now_dt
        stats["closed"] += 1
        db.flush()
    return by_key


def _new_segment(
    player: dict[str, str],
    status: str,
    now_dt: datetime,
) -> MinecraftPresenceSegment:
    return MinecraftPresenceSegment(
        player_key=player["key"],
        player_name=player["name"][:64],
        player_uuid=player["uuid"][:32],
        status=status,
        started_at=now_dt,
        last_seen_at=now_dt,
        ended_at=None,
    )


def _refresh_identity(seg: MinecraftPresenceSegment, player: dict[str, str]) -> None:
    if player["name"] and player["name"] != seg.player_name:
        seg.player_name = player["name"][:64]
    if player["uuid"] and player["uuid"] != seg.player_uuid:
        seg.player_uuid = player["uuid"][:32]
    if player["key"].startswith("id:") and seg.player_key != player["key"]:
        seg.player_key = player["key"]


def _find_open(
    player: dict[str, str],
    opens: dict[str, MinecraftPresenceSegment],
) -> MinecraftPresenceSegment | None:
    open_seg = opens.get(player["key"])
    if open_seg is None and player["name"]:
        for seg in opens.values():
            if seg.player_name.lower() == player["name"].lower():
                return seg
    return open_seg


def _apply_player(
    db: Session,
    player: dict[str, str],
    status: str,
    now_dt: datetime,
    opens: dict[str, MinecraftPresenceSegment],
    stats: dict[str, int],
) -> None:
    open_seg = _find_open(player, opens)
    if open_seg is None:
        row = _new_segment(player, status, now_dt)
        db.add(row)
        opens[player["key"]] = row
        stats["opened"] += 1
        return
    old_key = open_seg.player_key
    _refresh_identity(open_seg, player)
    if old_key != open_seg.player_key:
        opens.pop(old_key, None)
        opens[open_seg.player_key] = open_seg
    elif player["key"] not in opens:
        opens[player["key"]] = open_seg
    if open_seg.status == status:
        open_seg.last_seen_at = now_dt
        stats["continued"] += 1
        return
    open_seg.ended_at = now_dt
    open_seg.last_seen_at = now_dt
    stats["closed"] += 1
    nxt = _new_segment(player, status, now_dt)
    db.add(nxt)
    opens[player["key"]] = nxt
    stats["opened"] += 1


def _close_open(
    player: dict[str, str],
    now_dt: datetime,
    opens: dict[str, MinecraftPresenceSegment],
    stats: dict[str, int],
) -> None:
    open_seg = _find_open(player, opens)
    if open_seg is None:
        return
    open_seg.ended_at = now_dt
    open_seg.last_seen_at = now_dt
    stats["closed"] += 1
    opens.pop(open_seg.player_key, None)
    if player["key"] != open_seg.player_key:
        opens.pop(player["key"], None)


def _maybe_stale_close(
    seg: MinecraftPresenceSegment,
    player: dict[str, str],
    now_dt: datetime,
    stale_after: timedelta,
    opens: dict[str, MinecraftPresenceSegment],
    stats: dict[str, int],
) -> None:
    if seg.status != "online":
        return
    last = _naive(_aware(seg.last_seen_at))
    if now_dt - last < stale_after:
        return
    _close_open(player, now_dt, opens, stats)
    stats["stale_closed"] += 1


def apply_snapshot(
    db: Session,
    *,
    now_dt: datetime,
    online: list[dict[str, Any]],
    known: list[dict[str, Any]],
    complete: bool,
    stale_after: timedelta,
) -> dict[str, int]:
    """按一次在线快照开/续/关片段。不 commit。"""
    stats = {
        "players": 0,
        "online": 0,
        "offline": 0,
        "opened": 0,
        "continued": 0,
        "closed": 0,
        "stale_closed": 0,
        "complete": 1 if complete else 0,
    }
    open_rows = _open_segments(db)
    opens = _collapse_duplicate_opens(db, open_rows, now_dt, stats)
    name_map = _index_name_map(known, list(opens.values()))

    universe: dict[str, dict[str, str]] = {}
    online_keys: set[str] = set()
    for row in known:
        player = _normalize_player(row, name_map)
        if player:
            universe[player["key"]] = player
            if player["name"]:
                name_map.setdefault(player["name"].lower(), player["key"])
    for row in online:
        player = _normalize_player(row, name_map)
        if not player:
            continue
        universe[player["key"]] = player
        online_keys.add(player["key"])
        if player["name"]:
            name_map[player["name"].lower()] = player["key"]
    for key, seg in list(opens.items()):
        if key in universe:
            continue
        universe[key] = {
            "key": key,
            "name": seg.player_name,
            "uuid": seg.player_uuid or "",
        }

    stats["players"] = len(universe)
    stats["online"] = len(online_keys)
    for key, player in universe.items():
        desired = "online" if key in online_keys else "offline"
        if desired == "online":
            _apply_player(db, player, "online", now_dt, opens, stats)
            continue
        stats["offline"] += 1
        open_seg = opens.get(key)
        if open_seg is None:
            continue
        if complete:
            _close_open(player, now_dt, opens, stats)
            continue
        _maybe_stale_close(open_seg, player, now_dt, stale_after, opens, stats)
    db.flush()
    return stats


def _players_from_facts(facts: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for group_key in ("known", "whitelist"):
        rows = facts.get(group_key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            uid = str(row.get("id") or "").strip()
            if name or uid:
                out.append({"name": name or uid, "id": uid})
    return out


def _players_from_history(db: Session) -> list[dict[str, str]]:
    rows = (
        db.query(MinecraftPresenceSegment)
        .order_by(MinecraftPresenceSegment.started_at.desc())
        .limit(2000)
        .all()
    )
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        if row.player_key in seen:
            continue
        seen.add(row.player_key)
        out.append({"name": row.player_name, "id": row.player_uuid})
        if len(out) >= 200:
            break
    return out


def collect_online_snapshot(db: Session) -> dict[str, Any]:
    """Ping + 可选 RCON list，得到当前在线集合。"""
    host, port = get_minecraft_public_address(db)
    ping_online = False
    players_online = 0
    ping_players: list[dict[str, str]] = []
    ping_message = ""
    if host:
        try:
            parsed = status_svc.ping_server(host, port)
            ping_online = True
            players_online = int(parsed.get("players_online") or 0)
            ping_players = list(parsed.get("players") or [])
        except (status_svc.MinecraftPingError, OSError) as exc:
            ping_message = getattr(exc, "message", None) or str(exc)
    else:
        ping_message = "未设置公开地址"

    rcon_names: list[str] | None = None
    rcon_message = ""
    rcon_host, rcon_port, rcon_password = get_minecraft_rcon_credentials(db)
    if rcon_host and rcon_password:
        try:
            rcon_names = query_list(rcon_host, rcon_port, rcon_password)
        except (MinecraftRconError, OSError) as exc:
            rcon_message = getattr(exc, "message", None) or str(exc)
    elif rcon_host or rcon_password:
        rcon_message = "RCON 未填地址或密码"

    facts = profile_svc.read_cached_live_facts()
    known = _players_from_facts(facts) + _players_from_history(db)

    online: list[dict[str, str]] = []
    complete = False
    if rcon_names is not None:
        by_name = {
            str(item.get("name") or "").strip().lower(): str(item.get("id") or "")
            for item in known
            if str(item.get("name") or "").strip()
        }
        for sample in ping_players:
            name = str(sample.get("name") or "").strip()
            if name:
                by_name[name.lower()] = str(sample.get("id") or "") or by_name.get(
                    name.lower(), ""
                )
        for name in rcon_names:
            online.append({"name": name, "id": by_name.get(name.lower(), "")})
        complete = True
        players_online = max(players_online, len(online))
    else:
        online = [
            {
                "name": str(row.get("name") or "").strip(),
                "id": str(row.get("id") or "").strip(),
            }
            for row in ping_players
            if isinstance(row, dict) and str(row.get("name") or "").strip()
        ]
        complete = ping_online and len(online) >= players_online

    return {
        "online": online,
        "known": known,
        "complete": complete,
        "reachable": ping_online or rcon_names is not None,
        "players_online": players_online,
        "ping_message": ping_message,
        "rcon_message": rcon_message,
        "used_rcon": rcon_names is not None,
    }


def record_snapshot(
    db: Session,
    *,
    online: list[dict[str, Any]],
    known: list[dict[str, Any]],
    players_online: int,
    reachable: bool,
    complete: bool | None = None,
) -> dict[str, Any]:
    """总览 status 附带采样；轮询占用锁时跳过。"""
    if not _poll_lock.acquire(blocking=False):
        return {"status": "skipped", "message": "已有轮询在进行中", "stats": {}}
    try:
        is_complete = (
            complete
            if complete is not None
            else bool(reachable and len(online) >= int(players_online or 0))
        )
        stale_after = _stale_after(db)
        stats = apply_snapshot(
            db,
            now_dt=now_naive(),
            online=online,
            known=known,
            complete=is_complete,
            stale_after=stale_after,
        )
        db.commit()
        return {"status": "ok", "stats": stats}
    except Exception:
        db.rollback()
        logger.exception("minecraft presence sample failed")
        return {"status": "error", "stats": {}}
    finally:
        _poll_lock.release()


def _interval_minutes(db: Session) -> int:
    sched = load_scheduler_config(db).get(JOB_KEY) or {}
    try:
        return max(1, int(sched.get("interval_minutes") or 1))
    except (TypeError, ValueError):
        return 1


def _stale_after(db: Session) -> timedelta:
    return timedelta(minutes=_interval_minutes(db) * 3)


def run_minecraft_presence_poll(db: Session) -> dict[str, Any]:
    if not _poll_lock.acquire(blocking=False):
        return {"status": "skipped", "message": "已有轮询在进行中", "stats": {}}
    try:
        return _run_poll_locked(db)
    finally:
        _poll_lock.release()


def _run_poll_locked(db: Session) -> dict[str, Any]:
    job = JobRun(job_key=JOB_KEY, status="running", started_at=now_naive())
    db.add(job)
    db.commit()
    db.refresh(job)
    stats: dict[str, Any] = {}
    try:
        if not is_feature_enabled(db, "guides.minecraft.presence"):
            job.status = "ok"
            job.message = "功能未启用"
            job.stats = stats
            job.finished_at = now_naive()
            db.commit()
            return {"status": job.status, "message": job.message, "stats": stats}

        snap = collect_online_snapshot(db)
        stats = apply_snapshot(
            db,
            now_dt=now_naive(),
            online=list(snap.get("online") or []),
            known=list(snap.get("known") or []),
            complete=bool(snap.get("complete")),
            stale_after=_stale_after(db),
        )
        source = "RCON list" if snap.get("used_rcon") else "列表 Ping"
        job.status = "ok"
        job.message = (
            f"{source} 在线 {stats.get('online', 0)} / 跟踪 {stats.get('players', 0)}，"
            f"开 {stats.get('opened', 0)} / 续 {stats.get('continued', 0)} / 关 {stats.get('closed', 0)}"
        )
        if not snap.get("reachable"):
            extra = snap.get("rcon_message") or snap.get("ping_message") or "无法探测在线名单"
            job.message = extra
        job.stats = stats
        job.finished_at = now_naive()
        db.commit()
        return {"status": job.status, "message": job.message, "stats": stats}
    except Exception as exc:  # noqa: BLE001
        logger.exception("minecraft presence poll failed")
        job.status = "error"
        job.message = str(exc)
        job.stats = stats
        job.finished_at = now_naive()
        db.commit()
        return {"status": job.status, "message": job.message, "stats": stats}


def poll_job_wrapper() -> None:
    db = SessionLocal()
    try:
        if not is_feature_enabled(db, "guides.minecraft"):
            from app.services.minecraft_rcon import reset_session

            reset_session()
            return
        run_minecraft_presence_poll(db)
    except Exception:
        logger.exception("minecraft presence job failed")
    finally:
        db.close()


def _clip_to_window(
    start: datetime,
    end: datetime,
    window_start: datetime,
    window_end: datetime,
    *,
    span_seconds: int,
) -> tuple[int, int] | None:
    s = max(start, window_start)
    e = min(end, window_end)
    if e <= s:
        return None
    start_sec = int((s - window_start).total_seconds())
    end_sec = int((e - window_start).total_seconds())
    start_sec = max(0, min(span_seconds, start_sec))
    end_sec = max(0, min(span_seconds, end_sec))
    if end_sec <= start_sec:
        return None
    return start_sec, end_sec


def _segment_end(seg: MinecraftPresenceSegment, now_dt: datetime) -> datetime:
    if seg.ended_at is not None:
        return _aware(seg.ended_at)
    return max(_aware(seg.last_seen_at), now_dt)


def build_presence_range(
    db: Session,
    range_start: date,
    range_end: date,
) -> dict[str, Any]:
    if range_end < range_start:
        raise ValueError("end 不能早于 date")
    if (range_end - range_start).days > MAX_RANGE_DAYS:
        raise ValueError(f"时间轴区间最长 {MAX_RANGE_DAYS} 天")

    window_start, _ = day_bounds(range_start)
    _, window_end = day_bounds(range_end)
    span_seconds = int((window_end - window_start).total_seconds())
    now_dt = now()
    rows = (
        db.query(MinecraftPresenceSegment)
        .filter(
            MinecraftPresenceSegment.status == "online",
            MinecraftPresenceSegment.started_at < _naive(window_end),
            (MinecraftPresenceSegment.ended_at.is_(None))
            | (MinecraftPresenceSegment.ended_at >= _naive(window_start))
            | (MinecraftPresenceSegment.last_seen_at >= _naive(window_start)),
        )
        .order_by(MinecraftPresenceSegment.started_at.asc())
        .all()
    )

    grouped: dict[str, dict[str, Any]] = {}
    for seg in rows:
        clipped = _clip_to_window(
            _aware(seg.started_at),
            _segment_end(seg, now_dt),
            window_start,
            window_end,
            span_seconds=span_seconds,
        )
        if not clipped:
            continue
        start_sec, end_sec = clipped
        bucket = grouped.get(seg.player_key)
        if bucket is None:
            bucket = {
                "player_key": seg.player_key,
                "name": seg.player_name,
                "id": seg.player_uuid or "",
                "online": False,
                "online_seconds": 0,
                "offline_seconds": 0,
                "segments": [],
            }
            grouped[seg.player_key] = bucket
        if seg.player_name:
            bucket["name"] = seg.player_name
        if seg.player_uuid:
            bucket["id"] = seg.player_uuid
        dur = max(0, end_sec - start_sec)
        bucket["online_seconds"] += dur
        if seg.ended_at is None:
            bucket["online"] = True
        bucket["segments"].append(
            {
                "status": "online",
                "start_sec": start_sec,
                "end_sec": end_sec,
            }
        )

    out_rows = list(grouped.values())
    out_rows.sort(
        key=lambda row: (
            not row["online"],
            -int(row["online_seconds"]),
            str(row["name"]).lower(),
        )
    )
    return {
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "span_seconds": span_seconds,
        "player_count": len(out_rows),
        "online_count": sum(1 for row in out_rows if row["online"]),
        "rows": out_rows,
    }
