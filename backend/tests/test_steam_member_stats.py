"""成员游玩聚合，以及日时间轴按 member_id 过滤。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.timeutil import BEIJING
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.models.steam_app import SteamApp
from app.models.user import User, UserRole
from app.services.steam import stats


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _wall(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi)


def _user(db: Session, username: str) -> User:
    row = User(
        username=username,
        display_name=username,
        password_hash="x",
        role=UserRole.user,
    )
    db.add(row)
    db.flush()
    return row


def _member(
    db: Session,
    user: User,
    *,
    steam_id: str,
    persona: str,
) -> Member:
    row = Member(
        nickname=user.display_name,
        user_id=user.id,
        steam_id=steam_id,
        steam_persona_name=persona,
        joined_at=_wall(2026, 1, 1),
    )
    db.add(row)
    db.flush()
    return row


def _play(
    db: Session,
    member: Member,
    app_id: str,
    name: str,
    start: datetime,
    end: datetime,
) -> None:
    db.add(
        PlaySession(
            member_id=member.id,
            steam_app_id=app_id,
            game_name=name,
            started_at=start,
            last_seen_at=end,
            ended_at=end,
            source="steam",
        )
    )


def _icon(app_id: str) -> str:
    return (
        "https://cdn.example/steamcommunity/public/images/apps/"
        f"{app_id}/icon.jpg"
    )


def _cache_app(db: Session, app_id: str, name: str) -> None:
    db.add(
        SteamApp(
            app_id=app_id,
            name=name,
            icon_url=_icon(app_id),
            is_free=False,
            fetched_at=_wall(2026, 9, 1),
        )
    )


def test_member_play_stats_splits_cross_day_sessions(monkeypatch) -> None:
    monkeypatch.setattr(stats, "today", lambda: date(2026, 9, 3))
    monkeypatch.setattr(
        stats,
        "now",
        lambda: datetime(2026, 9, 3, 18, tzinfo=BEIJING),
    )
    db = _session()
    viewer = _user(db, "alice")
    alice = _member(db, viewer, steam_id="76561198000000001", persona="Alice")
    bob_user = _user(db, "bob")
    bob = _member(db, bob_user, steam_id="76561198000000002", persona="Bob")
    _cache_app(db, "730", "CS")
    _cache_app(db, "570", "Dota")
    _cache_app(db, "10", "Other")

    # 周首之前 2 小时 + 周内 2 小时，只应把周一 00:00 之后计入本周。
    _play(db, alice, "730", "CS", _wall(2026, 8, 30, 22), _wall(2026, 8, 31, 2))
    # 跨月：8/31 22:00–9/1 02:00，本月只计 2 小时。
    _play(db, alice, "730", "CS", _wall(2026, 8, 31, 22), _wall(2026, 9, 1, 2))
    _play(db, alice, "570", "Dota", _wall(2026, 9, 3, 10), _wall(2026, 9, 3, 11))
    _play(db, alice, "730", "CS", _wall(2026, 9, 3, 12), _wall(2026, 9, 3, 14))
    _play(db, bob, "10", "Other", _wall(2026, 9, 3, 8), _wall(2026, 9, 3, 18))
    db.commit()

    data = stats.build_member_play_stats(db, alice.id, viewer)
    assert data is not None
    assert data["today_play_seconds"] == 3 * 3600
    assert data["week_play_seconds"] == 9 * 3600
    assert data["month_play_seconds"] == 5 * 3600

    today_games = data["games_today"]
    assert [row["steam_app_id"] for row in today_games] == ["730", "570"]
    assert today_games[0]["total_seconds"] == 2 * 3600
    assert today_games[0]["session_count"] == 1
    assert today_games[0]["icon_url"] == _icon("730")
    assert today_games[1]["total_seconds"] == 3600

    week_games = data["games_week"]
    assert [row["steam_app_id"] for row in week_games] == ["730", "570"]
    assert week_games[0]["total_seconds"] == 8 * 3600
    assert week_games[0]["session_count"] == 3
    assert week_games[1]["total_seconds"] == 3600

    month_games = data["games_month"]
    assert [row["steam_app_id"] for row in month_games] == ["730", "570"]
    assert month_games[0]["total_seconds"] == 4 * 3600
    assert month_games[0]["session_count"] == 2

    by_date = {point["date"]: point["total_seconds"] for point in data["trend"]}
    assert by_date["2026-08-31"] == 4 * 3600
    assert by_date["2026-09-01"] == 2 * 3600
    assert by_date["2026-09-03"] == 3 * 3600
    assert data["recent_sessions"][0]["steam_app_id"] == "730"
    assert data["recent_sessions"][0]["icon_url"] == _icon("730")
    assert all(row["member_id"] == alice.id for row in data["recent_sessions"])


def test_day_timeline_member_filter() -> None:
    db = _session()
    viewer = _user(db, "alice")
    alice = _member(db, viewer, steam_id="76561198000000001", persona="Alice")
    bob_user = _user(db, "bob")
    bob = _member(db, bob_user, steam_id="76561198000000002", persona="Bob")
    day = date(2026, 9, 3)
    _cache_app(db, "730", "CS")
    _cache_app(db, "570", "Dota")
    _play(db, alice, "730", "CS", _wall(2026, 9, 3, 10), _wall(2026, 9, 3, 12))
    _play(db, bob, "570", "Dota", _wall(2026, 9, 3, 10), _wall(2026, 9, 3, 15))
    for member, app_id, name, end_h in (
        (alice, "730", "CS", 12),
        (bob, "570", "Dota", 15),
    ):
        db.add(
            PresenceSegment(
                member_id=member.id,
                status="playing",
                steam_app_id=app_id,
                game_name=name,
                started_at=_wall(2026, 9, 3, 10),
                last_seen_at=_wall(2026, 9, 3, end_h),
                ended_at=_wall(2026, 9, 3, end_h),
                source="steam",
            )
        )
    db.commit()

    everyone = stats.build_range_detail(db, day, day, viewer)
    assert everyone is not None
    assert {row["member_id"] for row in everyone["timeline"]} == {alice.id, bob.id}
    assert everyone["total_seconds"] == 7 * 3600

    only = stats.build_range_detail(db, day, day, viewer, member_id=alice.id)
    assert only is not None
    assert [row["member_id"] for row in only["timeline"]] == [alice.id]
    assert only["timeline"][0]["segments"]
    assert all(item["member_id"] == alice.id for item in only["sessions"])
    assert only["total_seconds"] == 2 * 3600
    assert {item["steam_app_id"] for item in only["games_legend"]} == {"730"}

    quiet = stats.build_range_detail(
        db, date(2026, 9, 2), date(2026, 9, 2), viewer, member_id=alice.id
    )
    assert quiet is not None
    assert quiet["sessions"] == []
    assert quiet["total_seconds"] == 0
    assert [row["member_id"] for row in quiet["timeline"]] == [alice.id]
    assert quiet["timeline"][0]["segments"] == []

    assert stats.build_range_detail(db, day, day, viewer, member_id=99999) is None
