from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.match_record import MatchRecord, MatchResult
from app.models.member import Member
from app.schemas import (
    LeaderboardItem,
    LeaderboardResponse,
    MemberOut,
    MemberStatsResponse,
    OverviewResponse,
    RecentRecordItem,
    TrendPoint,
    WeekStarItem,
    WinRateOverview,
)


def _range_start(range_key: str) -> datetime | None:
    now = datetime.now(timezone.utc)
    if range_key == "week":
        return now - timedelta(days=7)
    if range_key == "month":
        return now - timedelta(days=30)
    return None


def _win_rate(wins: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(wins / total * 100, 1)


def get_overview(db: Session) -> OverviewResponse:
    recent_q = (
        db.query(MatchRecord, Member.nickname, Game.name)
        .join(Member, MatchRecord.member_id == Member.id)
        .join(Game, MatchRecord.game_id == Game.id)
        .order_by(MatchRecord.played_at.desc())
        .limit(10)
        .all()
    )
    recent_records = [
        RecentRecordItem(
            id=r.id,
            member_nickname=nickname,
            game_name=game_name,
            result=r.result.value if hasattr(r.result, "value") else str(r.result),
            played_at=r.played_at,
            mode=r.mode,
        )
        for r, nickname, game_name in recent_q
    ]

    week_start = _range_start("week")
    week_agg = (
        db.query(
            Member.id,
            Member.nickname,
            func.sum(case((MatchRecord.result == MatchResult.win, 1), else_=0)).label("wins"),
            func.count(MatchRecord.id).label("total"),
        )
        .join(MatchRecord, MatchRecord.member_id == Member.id)
        .filter(MatchRecord.played_at >= week_start)
        .group_by(Member.id, Member.nickname)
        .order_by(func.sum(case((MatchRecord.result == MatchResult.win, 1), else_=0)).desc())
        .first()
    )
    week_star = None
    if week_agg and week_agg.total:
        week_star = WeekStarItem(
            member_id=week_agg.id,
            member_nickname=week_agg.nickname,
            wins=int(week_agg.wins or 0),
            total=int(week_agg.total or 0),
            win_rate=_win_rate(int(week_agg.wins or 0), int(week_agg.total or 0)),
        )

    totals = db.query(
        func.count(MatchRecord.id).label("total"),
        func.sum(case((MatchRecord.result == MatchResult.win, 1), else_=0)).label("wins"),
        func.sum(case((MatchRecord.result == MatchResult.lose, 1), else_=0)).label("losses"),
        func.sum(case((MatchRecord.result == MatchResult.draw, 1), else_=0)).label("draws"),
    ).one()
    total = int(totals.total or 0)
    wins = int(totals.wins or 0)
    losses = int(totals.losses or 0)
    draws = int(totals.draws or 0)

    return OverviewResponse(
        recent_records=recent_records,
        week_star=week_star,
        win_rate=WinRateOverview(
            total_matches=total,
            wins=wins,
            losses=losses,
            draws=draws,
            win_rate=_win_rate(wins, total),
        ),
    )


def get_leaderboard(
    db: Session,
    game_id: int | None = None,
    range_key: str = "all",
) -> LeaderboardResponse:
    q = db.query(
        Member.id,
        Member.nickname,
        Member.avatar_url,
        func.sum(case((MatchRecord.result == MatchResult.win, 1), else_=0)).label("wins"),
        func.sum(case((MatchRecord.result == MatchResult.lose, 1), else_=0)).label("losses"),
        func.sum(case((MatchRecord.result == MatchResult.draw, 1), else_=0)).label("draws"),
        func.count(MatchRecord.id).label("total"),
    ).join(MatchRecord, MatchRecord.member_id == Member.id)

    if game_id is not None:
        q = q.filter(MatchRecord.game_id == game_id)
    start = _range_start(range_key)
    if start is not None:
        q = q.filter(MatchRecord.played_at >= start)

    rows = (
        q.group_by(Member.id, Member.nickname, Member.avatar_url)
        .order_by(
            func.sum(case((MatchRecord.result == MatchResult.win, 1), else_=0)).desc(),
            func.count(MatchRecord.id).desc(),
        )
        .all()
    )

    items: list[LeaderboardItem] = []
    for idx, row in enumerate(rows, start=1):
        wins = int(row.wins or 0)
        total = int(row.total or 0)
        items.append(
            LeaderboardItem(
                rank=idx,
                member_id=row.id,
                member_nickname=row.nickname,
                avatar_url=row.avatar_url,
                wins=wins,
                losses=int(row.losses or 0),
                draws=int(row.draws or 0),
                total=total,
                win_rate=_win_rate(wins, total),
            )
        )

    return LeaderboardResponse(items=items, game_id=game_id, range=range_key)


def get_member_stats(db: Session, member_id: int) -> MemberStatsResponse | None:
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        return None

    totals = (
        db.query(
            func.count(MatchRecord.id).label("total"),
            func.sum(case((MatchRecord.result == MatchResult.win, 1), else_=0)).label("wins"),
            func.sum(case((MatchRecord.result == MatchResult.lose, 1), else_=0)).label("losses"),
            func.sum(case((MatchRecord.result == MatchResult.draw, 1), else_=0)).label("draws"),
        )
        .filter(MatchRecord.member_id == member_id)
        .one()
    )
    total = int(totals.total or 0)
    wins = int(totals.wins or 0)
    losses = int(totals.losses or 0)
    draws = int(totals.draws or 0)

    recent_q = (
        db.query(MatchRecord, Member.nickname, Game.name)
        .join(Member, MatchRecord.member_id == Member.id)
        .join(Game, MatchRecord.game_id == Game.id)
        .filter(MatchRecord.member_id == member_id)
        .order_by(MatchRecord.played_at.desc())
        .limit(20)
        .all()
    )
    recent_records = [
        RecentRecordItem(
            id=r.id,
            member_nickname=nickname,
            game_name=game_name,
            result=r.result.value if hasattr(r.result, "value") else str(r.result),
            played_at=r.played_at,
            mode=r.mode,
        )
        for r, nickname, game_name in recent_q
    ]

    # 近 14 天按日趋势
    day_start = datetime.now(timezone.utc) - timedelta(days=13)
    day_expr = func.date(MatchRecord.played_at)
    trend_rows = (
        db.query(
            day_expr.label("day"),
            func.sum(case((MatchRecord.result == MatchResult.win, 1), else_=0)).label("wins"),
            func.count(MatchRecord.id).label("total"),
        )
        .filter(MatchRecord.member_id == member_id, MatchRecord.played_at >= day_start)
        .group_by(day_expr)
        .order_by(day_expr.asc())
        .all()
    )
    trend = [
        TrendPoint(
            date=str(row.day),
            wins=int(row.wins or 0),
            total=int(row.total or 0),
            win_rate=_win_rate(int(row.wins or 0), int(row.total or 0)),
        )
        for row in trend_rows
    ]

    return MemberStatsResponse(
        member=MemberOut.model_validate(member),
        total_matches=total,
        wins=wins,
        losses=losses,
        draws=draws,
        win_rate=_win_rate(wins, total),
        recent_records=recent_records,
        trend=trend,
    )
