"""Steam 游玩会话日历与总览聚合。"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.models.user import User
from app.services.steam_friends import (
    can_view_member_steam,
    visibility_meta,
    visible_member_ids_for_user,
)

TZ = ZoneInfo("Asia/Shanghai")


def _to_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _session_end(session: PlaySession, now: datetime | None = None) -> datetime:
    if session.ended_at is not None:
        return _to_aware(session.ended_at)
    end = _to_aware(session.last_seen_at)
    if now is None:
        now = datetime.now(timezone.utc)
    return max(end, now)


def _overlap_seconds(
    start: datetime, end: datetime, window_start: datetime, window_end: datetime
) -> int:
    s = max(start, window_start)
    e = min(end, window_end)
    if e <= s:
        return 0
    return int((e - s).total_seconds())


def _range_for(granularity: str, anchor: date) -> tuple[date, date]:
    if granularity == "day":
        return anchor, anchor
    if granularity == "week":
        start = anchor - timedelta(days=anchor.weekday())  # Monday
        return start, start + timedelta(days=6)
    if granularity == "month":
        start = anchor.replace(day=1)
        last = monthrange(anchor.year, anchor.month)[1]
        return start, anchor.replace(day=last)
    if granularity == "year":
        return date(anchor.year, 1, 1), date(anchor.year, 12, 31)
    raise ValueError(f"不支持的粒度: {granularity}")


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=TZ)
    end = start + timedelta(days=1)
    return start, end


def _sessions_in_window(
    db: Session,
    window_start: datetime,
    window_end: datetime,
    member_id: int | None = None,
    member_ids: set[int] | None = None,
) -> list[PlaySession]:
    q = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.member))
        .filter(
            PlaySession.source == "steam",
            PlaySession.started_at < window_end,
            (PlaySession.ended_at.is_(None))
            | (PlaySession.ended_at >= window_start)
            | (PlaySession.last_seen_at >= window_start),
        )
    )
    if member_id is not None:
        q = q.filter(PlaySession.member_id == member_id)
    elif member_ids is not None:
        if not member_ids:
            return []
        q = q.filter(PlaySession.member_id.in_(member_ids))
    return q.order_by(PlaySession.started_at.desc()).all()


def build_calendar(
    db: Session, granularity: str, anchor: date, viewer: User
) -> dict:
    visible_ids = visible_member_ids_for_user(db, viewer)
    range_start, range_end = _range_for(granularity, anchor)
    window_start, _ = _day_bounds(range_start)
    _, window_end = _day_bounds(range_end)

    sessions = _sessions_in_window(
        db, window_start, window_end, member_ids=visible_ids
    )

    # date -> totals; (member_id, date) -> seconds
    day_seconds: dict[str, int] = {}
    day_counts: dict[str, int] = {}
    member_day_seconds: dict[int, dict[str, int]] = {}
    member_meta: dict[int, dict] = {}

    d = range_start
    while d <= range_end:
        key = d.isoformat()
        day_seconds[key] = 0
        day_counts[key] = 0
        d += timedelta(days=1)

    for s in sessions:
        member = s.member
        mid = s.member_id
        if mid not in member_meta:
            member_meta[mid] = {
                "member_id": mid,
                "member_nickname": member.nickname if member else str(mid),
                "avatar_url": member.avatar_url if member else None,
            }
            member_day_seconds[mid] = {k: 0 for k in day_seconds}

        sess_start = _to_aware(s.started_at).astimezone(TZ).date()
        sess_end = _session_end(s).astimezone(TZ).date()
        d = max(sess_start, range_start)
        last = min(sess_end, range_end)
        while d <= last:
            day_start, day_end = _day_bounds(d)
            sec = _overlap_seconds(
                _to_aware(s.started_at), _session_end(s), day_start, day_end
            )
            if sec > 0:
                key = d.isoformat()
                day_seconds[key] += sec
                day_counts[key] += 1
                member_day_seconds[mid][key] += sec
            d += timedelta(days=1)

    cells: list[dict] = []
    total_seconds = 0
    for key, seconds in day_seconds.items():
        cells.append(
            {
                "date": key,
                "total_seconds": seconds,
                "session_count": day_counts[key],
            }
        )
        total_seconds += seconds

    members = []
    for mid, meta in member_meta.items():
        m_cells = [
            {"date": k, "total_seconds": v, "session_count": 1 if v > 0 else 0}
            for k, v in member_day_seconds[mid].items()
        ]
        m_total = sum(c["total_seconds"] for c in m_cells)
        if m_total <= 0 and granularity != "year":
            continue
        members.append({**meta, "cells": m_cells, "total_seconds": m_total})
    members.sort(key=lambda x: x["total_seconds"], reverse=True)

    # year 视图即使无游玩也列出可见好友，便于对照活跃图
    if granularity == "year" and visible_ids:
        known = {m["member_id"] for m in members}
        steam_members = (
            db.query(Member)
            .filter(
                Member.id.in_(visible_ids),
                Member.user_id.isnot(None),
                Member.steam_id.isnot(None),
                Member.steam_id != "",
            )
            .order_by(Member.nickname.asc())
            .all()
        )
        for m in steam_members:
            if m.id in known:
                continue
            members.append(
                {
                    "member_id": m.id,
                    "member_nickname": m.nickname,
                    "avatar_url": m.avatar_url,
                    "cells": [
                        {"date": k, "total_seconds": 0, "session_count": 0}
                        for k in day_seconds
                    ],
                    "total_seconds": 0,
                }
            )

    meta = visibility_meta(db, viewer, visible_ids)
    self_id = meta.get("self_member_id")
    members.sort(
        key=lambda x: (
            0 if x["member_id"] == self_id else 1,
            -x["total_seconds"],
            x["member_nickname"],
        )
    )

    return {
        "granularity": granularity,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "cells": cells,
        "total_seconds": total_seconds,
        "members": members,
        "visibility": meta,
    }


def _presence_end(seg: PresenceSegment, now: datetime) -> datetime:
    if seg.ended_at is not None:
        return _to_aware(seg.ended_at)
    return max(_to_aware(seg.last_seen_at), now)


def _clip_to_window(
    start: datetime,
    end: datetime,
    window_start: datetime,
    window_end: datetime,
    *,
    span_seconds: int,
) -> tuple[int, int] | None:
    """返回窗口内 [start_sec, end_sec)，相对 window_start；无重叠则 None。"""
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


def build_day_detail(db: Session, d: date, viewer: User) -> dict:
    return build_range_detail(db, d, d, viewer)


def build_range_detail(
    db: Session, range_start: date, range_end: date, viewer: User
) -> dict:
    if range_end < range_start:
        raise ValueError("end 不能早于 date")
    # 防止误请求超长区间拖垮查询
    if (range_end - range_start).days > 31:
        raise ValueError("时间轴区间最长 31 天")

    visible_ids = visible_member_ids_for_user(db, viewer)
    window_start, _ = _day_bounds(range_start)
    _, window_end = _day_bounds(range_end)
    span_seconds = int((window_end - window_start).total_seconds())
    now = datetime.now(timezone.utc)
    sessions = _sessions_in_window(
        db, window_start, window_end, member_ids=visible_ids
    )
    sessions = sorted(sessions, key=lambda s: _to_aware(s.started_at))

    items: list[dict] = []
    by_member: dict[int, dict] = {}
    total_seconds = 0

    for s in sessions:
        duration = _overlap_seconds(
            _to_aware(s.started_at), _session_end(s), window_start, window_end
        )
        if duration <= 0:
            continue
        total_seconds += duration
        member = s.member
        item = {
            "id": s.id,
            "member_id": s.member_id,
            "member_nickname": member.nickname if member else str(s.member_id),
            "avatar_url": member.avatar_url if member else None,
            "steam_app_id": s.steam_app_id,
            "game_name": s.game_name,
            "started_at": s.started_at,
            "last_seen_at": s.last_seen_at,
            "ended_at": s.ended_at,
            "duration_seconds": duration,
            "is_ongoing": s.ended_at is None,
        }
        items.append(item)

        summary = by_member.get(s.member_id)
        if not summary:
            summary = {
                "member_id": s.member_id,
                "member_nickname": item["member_nickname"],
                "avatar_url": item["avatar_url"],
                "total_seconds": 0,
                "games": [],
            }
            by_member[s.member_id] = summary
        summary["total_seconds"] += duration
        if s.game_name not in summary["games"]:
            summary["games"].append(s.game_name)

    member_list = sorted(
        by_member.values(), key=lambda x: x["total_seconds"], reverse=True
    )

    steam_members = (
        db.query(Member)
        .filter(
            Member.id.in_(visible_ids),
            Member.user_id.isnot(None),
            Member.steam_id.isnot(None),
            Member.steam_id != "",
        )
        .order_by(Member.nickname.asc())
        .all()
        if visible_ids
        else []
    )

    presence_rows = (
        db.query(PresenceSegment)
        .options(joinedload(PresenceSegment.member))
        .filter(
            PresenceSegment.source == "steam",
            PresenceSegment.member_id.in_(visible_ids),
            PresenceSegment.started_at < window_end,
            (PresenceSegment.ended_at.is_(None))
            | (PresenceSegment.ended_at >= window_start)
            | (PresenceSegment.last_seen_at >= window_start),
        )
        .order_by(PresenceSegment.started_at.asc())
        .all()
        if visible_ids
        else []
    )

    segments_by_member: dict[int, list[dict]] = {m.id: [] for m in steam_members}
    games_legend: dict[str, str] = {}

    def _append_seg(
        member_id: int,
        status: str,
        app_id: str | None,
        game_name: str | None,
        start: datetime,
        end: datetime,
    ) -> None:
        clipped = _clip_to_window(
            start, end, window_start, window_end, span_seconds=span_seconds
        )
        if not clipped:
            return
        start_sec, end_sec = clipped
        if member_id not in segments_by_member:
            segments_by_member[member_id] = []
        segments_by_member[member_id].append(
            {
                "status": status,
                "steam_app_id": app_id,
                "game_name": game_name,
                "start_sec": start_sec,
                "end_sec": end_sec,
            }
        )
        if status == "playing" and app_id:
            games_legend[app_id] = game_name or f"App {app_id}"

    if presence_rows:
        for seg in presence_rows:
            _append_seg(
                seg.member_id,
                seg.status,
                seg.steam_app_id,
                seg.game_name,
                _to_aware(seg.started_at),
                _presence_end(seg, now),
            )
    else:
        for s in sessions:
            _append_seg(
                s.member_id,
                "playing",
                s.steam_app_id,
                s.game_name,
                _to_aware(s.started_at),
                _session_end(s) if s.ended_at is not None else max(_session_end(s), now),
            )

    known_ids = {m.id for m in steam_members}
    for mid, segs in list(segments_by_member.items()):
        if mid not in known_ids and segs:
            mem = db.query(Member).filter(Member.id == mid).first()
            if mem:
                steam_members.append(mem)

    timeline = []
    for m in steam_members:
        segs = sorted(segments_by_member.get(m.id, []), key=lambda x: x["start_sec"])
        timeline.append(
            {
                "member_id": m.id,
                "member_nickname": m.nickname,
                "avatar_url": m.avatar_url,
                "segments": segs,
            }
        )

    timeline.sort(
        key=lambda row: (0 if row["segments"] else 1, row["member_nickname"])
    )

    return {
        "date": range_start.isoformat(),
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "span_seconds": span_seconds,
        "sessions": items,
        "by_member": member_list,
        "total_seconds": total_seconds,
        "timeline": timeline,
        "games_legend": [
            {"steam_app_id": k, "game_name": v} for k, v in sorted(games_legend.items())
        ],
        "visibility": visibility_meta(db, viewer, visible_ids),
    }


def list_now_playing(db: Session, viewer: User) -> list[dict]:
    visible_ids = visible_member_ids_for_user(db, viewer)
    if not visible_ids:
        return []
    sessions = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.member))
        .filter(
            PlaySession.source == "steam",
            PlaySession.ended_at.is_(None),
            PlaySession.member_id.in_(visible_ids),
        )
        .order_by(PlaySession.started_at.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    result = []
    for s in sessions:
        start = _to_aware(s.started_at)
        result.append(
            {
                "id": s.id,
                "member_id": s.member_id,
                "member_nickname": s.member.nickname if s.member else str(s.member_id),
                "avatar_url": s.member.avatar_url if s.member else None,
                "steam_app_id": s.steam_app_id,
                "game_name": s.game_name,
                "started_at": s.started_at,
                "last_seen_at": s.last_seen_at,
                "duration_seconds": max(0, int((now - start).total_seconds())),
            }
        )
    return result


def build_overview(db: Session, viewer: User) -> dict:
    """圈子 Steam 总览：仅自己与 Steam 好友。"""
    visible_ids = visible_member_ids_for_user(db, viewer)
    today = datetime.now(TZ).date()
    week_start = today - timedelta(days=today.weekday())
    window_start, _ = _day_bounds(week_start)
    _, window_end = _day_bounds(today)

    members = (
        db.query(Member)
        .filter(Member.id.in_(visible_ids), Member.user_id.isnot(None))
        .all()
        if visible_ids
        else []
    )
    member_count = len(members)
    steam_bound_count = sum(1 for m in members if m.steam_id)

    week_sessions = _sessions_in_window(
        db, window_start, window_end, member_ids=visible_ids
    )
    week_seconds = 0
    for s in week_sessions:
        week_seconds += _overlap_seconds(
            _to_aware(s.started_at), _session_end(s), window_start, window_end
        )

    now_playing = list_now_playing(db, viewer)

    recent_q = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.member))
        .filter(PlaySession.source == "steam")
    )
    if visible_ids:
        recent_q = recent_q.filter(PlaySession.member_id.in_(visible_ids))
    else:
        recent_q = recent_q.filter(PlaySession.id < 0)
    recent = recent_q.order_by(PlaySession.started_at.desc()).limit(20).all()
    recent_sessions = []
    now = datetime.now(timezone.utc)
    for s in recent:
        end = _session_end(s)
        start = _to_aware(s.started_at)
        if s.ended_at is None:
            duration = max(0, int((now - start).total_seconds()))
        else:
            duration = max(0, int((end - start).total_seconds()))
        recent_sessions.append(
            {
                "id": s.id,
                "member_id": s.member_id,
                "member_nickname": s.member.nickname if s.member else str(s.member_id),
                "avatar_url": s.member.avatar_url if s.member else None,
                "steam_app_id": s.steam_app_id,
                "game_name": s.game_name,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
                "duration_seconds": duration,
                "is_ongoing": s.ended_at is None,
            }
        )

    return {
        "member_count": member_count,
        "steam_bound_count": steam_bound_count,
        "week_play_seconds": week_seconds,
        "now_playing": now_playing,
        "recent_sessions": recent_sessions,
        "visibility": visibility_meta(db, viewer, visible_ids),
    }


def build_member_play_stats(
    db: Session, member_id: int, viewer: User
) -> dict | None:
    member = (
        db.query(Member)
        .filter(Member.id == member_id, Member.user_id.isnot(None))
        .first()
    )
    if not member:
        return None
    if not can_view_member_steam(db, viewer, member_id):
        return None

    today = datetime.now(TZ).date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    trend_start = today - timedelta(days=13)

    week_ws, _ = _day_bounds(week_start)
    _, week_we = _day_bounds(today)
    month_ws, _ = _day_bounds(month_start)
    trend_ws, _ = _day_bounds(trend_start)
    _, day_we = _day_bounds(today)

    all_for_month = _sessions_in_window(db, month_ws, day_we, member_id=member_id)

    week_seconds = 0
    month_seconds = 0
    for s in all_for_month:
        start = _to_aware(s.started_at)
        end = _session_end(s)
        week_seconds += _overlap_seconds(start, end, week_ws, week_we)
        month_seconds += _overlap_seconds(start, end, month_ws, day_we)

    trend_sessions = _sessions_in_window(db, trend_ws, day_we, member_id=member_id)
    trend: list[dict] = []
    d = trend_start
    while d <= today:
        day_start, day_end = _day_bounds(d)
        seconds = 0
        count = 0
        for s in trend_sessions:
            sec = _overlap_seconds(
                _to_aware(s.started_at), _session_end(s), day_start, day_end
            )
            if sec > 0:
                seconds += sec
                count += 1
        trend.append(
            {
                "date": d.isoformat(),
                "total_seconds": seconds,
                "session_count": count,
            }
        )
        d += timedelta(days=1)

    recent = (
        db.query(PlaySession)
        .filter(PlaySession.source == "steam", PlaySession.member_id == member_id)
        .order_by(PlaySession.started_at.desc())
        .limit(50)
        .all()
    )
    now = datetime.now(timezone.utc)
    recent_sessions = []
    for s in recent:
        start = _to_aware(s.started_at)
        end = _session_end(s)
        if s.ended_at is None:
            duration = max(0, int((now - start).total_seconds()))
        else:
            duration = max(0, int((end - start).total_seconds()))
        recent_sessions.append(
            {
                "id": s.id,
                "member_id": s.member_id,
                "member_nickname": member.nickname,
                "avatar_url": member.avatar_url,
                "steam_app_id": s.steam_app_id,
                "game_name": s.game_name,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
                "duration_seconds": duration,
                "is_ongoing": s.ended_at is None,
            }
        )

    return {
        "member": {
            "id": member.id,
            "nickname": member.nickname,
            "avatar_url": member.avatar_url,
            "user_id": member.user_id,
            "joined_at": member.joined_at,
            "steam_id": member.steam_id,
        },
        "week_play_seconds": week_seconds,
        "month_play_seconds": month_seconds,
        "session_count": len(recent),
        "trend": trend,
        "recent_sessions": recent_sessions,
    }
