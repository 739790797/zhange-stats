"""Steam 游玩会话日历与总览聚合。"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment

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


def _presence_end(seg: PresenceSegment, now: datetime) -> datetime:
    if seg.ended_at is not None:
        return _to_aware(seg.ended_at)
    # 进行中：取 last_seen 与当前时刻较大者，避免色条过短
    return max(_to_aware(seg.last_seen_at), now)


def _clip_to_day(
    start: datetime, end: datetime, day_start: datetime, day_end: datetime
) -> tuple[int, int] | None:
    """返回当日 [start_sec, end_sec)，单位秒；无重叠则 None。"""
    s = max(start, day_start)
    e = min(end, day_end)
    if e <= s:
        return None
    start_sec = int((s - day_start).total_seconds())
    end_sec = int((e - day_start).total_seconds())
    start_sec = max(0, min(86400, start_sec))
    end_sec = max(0, min(86400, end_sec))
    if end_sec <= start_sec:
        return None
    return start_sec, end_sec


def build_day_detail(db: Session, d: date) -> dict:
    day_start, day_end = _day_bounds(d)
    now = datetime.now(timezone.utc)
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

    # ---- 日时间轴：按用户的状态片段 ----
    steam_members = (
        db.query(Member)
        .filter(Member.user_id.isnot(None), Member.steam_id.isnot(None), Member.steam_id != "")
        .order_by(Member.nickname.asc())
        .all()
    )

    presence_rows = (
        db.query(PresenceSegment)
        .options(joinedload(PresenceSegment.member))
        .filter(
            PresenceSegment.source == "steam",
            PresenceSegment.started_at < day_end,
            (PresenceSegment.ended_at.is_(None))
            | (PresenceSegment.ended_at >= day_start)
            | (PresenceSegment.last_seen_at >= day_start),
        )
        .order_by(PresenceSegment.started_at.asc())
        .all()
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
        clipped = _clip_to_day(start, end, day_start, day_end)
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
        # 兼容旧数据：仅有 play_sessions 时当作 playing 片段
        for s in sessions:
            _append_seg(
                s.member_id,
                "playing",
                s.steam_app_id,
                s.game_name,
                _to_aware(s.started_at),
                _session_end(s) if s.ended_at is not None else max(_session_end(s), now),
            )

    # 确保有会话但未绑显示名的成员也出现在轴上
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

    # 有时间轴数据但未在 steam_members 列表的（兜底已处理）
    # 按有片段优先、再按昵称
    timeline.sort(
        key=lambda row: (0 if row["segments"] else 1, row["member_nickname"])
    )

    return {
        "date": d.isoformat(),
        "sessions": items,
        "by_member": member_list,
        "total_seconds": total_seconds,
        "timeline": timeline,
        "games_legend": [
            {"steam_app_id": k, "game_name": v} for k, v in sorted(games_legend.items())
        ],
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
