"""Steam 游玩会话日历与总览聚合。"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from app.models.member import Member
from app.models.play_session import PlaySession

TZ = ZoneInfo("Asia/Shanghai")


def _to_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _session_end(session: PlaySession) -> datetime:
    if session.ended_at is not None:
        return _to_aware(session.ended_at)
    return _to_aware(session.last_seen_at)


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
    db: Session, window_start: datetime, window_end: datetime, member_id: int | None = None
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
    return q.order_by(PlaySession.started_at.desc()).all()


def build_calendar(db: Session, granularity: str, anchor: date) -> dict:
    range_start, range_end = _range_for(granularity, anchor)
    window_start, _ = _day_bounds(range_start)
    _, window_end = _day_bounds(range_end)

    sessions = _sessions_in_window(db, window_start, window_end)

    cells: list[dict] = []
    total_seconds = 0
    d = range_start
    while d <= range_end:
        day_start, day_end = _day_bounds(d)
        seconds = 0
        count = 0
        for s in sessions:
            sec = _overlap_seconds(
                _to_aware(s.started_at), _session_end(s), day_start, day_end
            )
            if sec > 0:
                seconds += sec
                count += 1
        cells.append(
            {
                "date": d.isoformat(),
                "total_seconds": seconds,
                "session_count": count,
            }
        )
        total_seconds += seconds
        d += timedelta(days=1)

    return {
        "granularity": granularity,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "cells": cells,
        "total_seconds": total_seconds,
    }


def build_day_detail(db: Session, d: date) -> dict:
    day_start, day_end = _day_bounds(d)
    sessions = _sessions_in_window(db, day_start, day_end)
    sessions = sorted(sessions, key=lambda s: _to_aware(s.started_at))

    items: list[dict] = []
    by_member: dict[int, dict] = {}
    total_seconds = 0

    for s in sessions:
        duration = _overlap_seconds(
            _to_aware(s.started_at), _session_end(s), day_start, day_end
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
    return {
        "date": d.isoformat(),
        "sessions": items,
        "by_member": member_list,
        "total_seconds": total_seconds,
    }


def list_now_playing(db: Session) -> list[dict]:
    sessions = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.member))
        .filter(PlaySession.source == "steam", PlaySession.ended_at.is_(None))
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


def build_overview(db: Session) -> dict:
    """圈子 Steam 总览：成员、绑定、本周时长、正在游玩、近期会话。"""
    today = datetime.now(TZ).date()
    week_start = today - timedelta(days=today.weekday())
    window_start, _ = _day_bounds(week_start)
    _, window_end = _day_bounds(today)

    members = (
        db.query(Member).filter(Member.user_id.isnot(None)).all()
    )
    member_count = len(members)
    steam_bound_count = sum(1 for m in members if m.steam_id)

    week_sessions = _sessions_in_window(db, window_start, window_end)
    week_seconds = 0
    for s in week_sessions:
        week_seconds += _overlap_seconds(
            _to_aware(s.started_at), _session_end(s), window_start, window_end
        )

    now_playing = list_now_playing(db)

    recent = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.member))
        .filter(PlaySession.source == "steam")
        .order_by(PlaySession.started_at.desc())
        .limit(20)
        .all()
    )
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
    }


def build_member_play_stats(db: Session, member_id: int) -> dict | None:
    member = (
        db.query(Member)
        .filter(Member.id == member_id, Member.user_id.isnot(None))
        .first()
    )
    if not member:
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
