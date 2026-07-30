"""Steam 状态轮询：写入 presence_segments + play_sessions，并记 job_runs。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.services.adapters.steam import SteamAdapter, SteamPresence

logger = logging.getLogger(__name__)

JOB_KEY = "steam_presence"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _open_presence(db: Session, member_id: int) -> PresenceSegment | None:
    return (
        db.query(PresenceSegment)
        .filter(
            PresenceSegment.member_id == member_id,
            PresenceSegment.ended_at.is_(None),
            PresenceSegment.source == "steam",
        )
        .order_by(PresenceSegment.started_at.desc())
        .first()
    )


def _open_play(db: Session, member_id: int) -> PlaySession | None:
    return (
        db.query(PlaySession)
        .filter(
            PlaySession.member_id == member_id,
            PlaySession.ended_at.is_(None),
            PlaySession.source == "steam",
        )
        .order_by(PlaySession.started_at.desc())
        .first()
    )


def _same_presence(
    seg: PresenceSegment, status: str, app_id: str | None
) -> bool:
    if seg.status != status:
        return False
    if status == "playing":
        return (seg.steam_app_id or "") == (app_id or "")
    return True


def _apply_presence(
    db: Session,
    member: Member,
    presence: SteamPresence,
    now: datetime,
    stats: dict,
) -> None:
    status = presence.status
    app_id = presence.game_id
    game_name = presence.game_extra_info or (
        f"App {app_id}" if app_id else None
    )

    if status == "playing":
        stats["playing"] += 1
    elif status == "online":
        stats["online"] += 1
    else:
        stats["offline"] += 1

    # ---- presence_segments ----
    open_seg = _open_presence(db, member.id)
    if open_seg is None:
        db.add(
            PresenceSegment(
                member_id=member.id,
                status=status,
                steam_app_id=app_id if status == "playing" else None,
                game_name=game_name if status == "playing" else None,
                started_at=now,
                last_seen_at=now,
                ended_at=None,
                source="steam",
            )
        )
        stats["presence_opened"] += 1
    elif _same_presence(open_seg, status, app_id):
        open_seg.last_seen_at = now
        if status == "playing" and game_name:
            open_seg.game_name = game_name
        stats["presence_continued"] += 1
    else:
        open_seg.ended_at = now
        open_seg.last_seen_at = now
        stats["presence_closed"] += 1
        db.add(
            PresenceSegment(
                member_id=member.id,
                status=status,
                steam_app_id=app_id if status == "playing" else None,
                game_name=game_name if status == "playing" else None,
                started_at=now,
                last_seen_at=now,
                ended_at=None,
                source="steam",
            )
        )
        stats["presence_opened"] += 1

    # ---- play_sessions（仅游戏中，供热力统计兼容）----
    open_play = _open_play(db, member.id)
    if status == "playing" and app_id and game_name:
        if open_play is None:
            db.add(
                PlaySession(
                    member_id=member.id,
                    steam_app_id=app_id,
                    game_name=game_name,
                    started_at=now,
                    last_seen_at=now,
                    ended_at=None,
                    source="steam",
                )
            )
            stats["opened"] += 1
        elif open_play.steam_app_id == app_id:
            open_play.last_seen_at = now
            open_play.game_name = game_name
            stats["continued"] += 1
        else:
            open_play.ended_at = now
            open_play.last_seen_at = now
            stats["closed"] += 1
            db.add(
                PlaySession(
                    member_id=member.id,
                    steam_app_id=app_id,
                    game_name=game_name,
                    started_at=now,
                    last_seen_at=now,
                    ended_at=None,
                    source="steam",
                )
            )
            stats["opened"] += 1
    elif open_play is not None:
        open_play.ended_at = now
        open_play.last_seen_at = now
        stats["closed"] += 1


def run_steam_presence_poll(db: Session) -> dict:
    settings = get_settings()
    job = JobRun(job_key=JOB_KEY, status="running", started_at=_utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)

    stats = {
        "members": 0,
        "playing": 0,
        "online": 0,
        "offline": 0,
        "opened": 0,
        "continued": 0,
        "closed": 0,
        "presence_opened": 0,
        "presence_continued": 0,
        "presence_closed": 0,
        "skipped_private": 0,
    }

    try:
        if not settings.STEAM_API_KEY:
            raise RuntimeError("STEAM_API_KEY 未配置")

        members = (
            db.query(Member)
            .filter(Member.steam_id.isnot(None), Member.steam_id != "")
            .all()
        )
        stats["members"] = len(members)
        if not members:
            job.status = "ok"
            job.message = "无可轮询成员（未绑定 steam_id）"
            job.stats = stats
            job.finished_at = _utcnow()
            db.commit()
            return {"status": job.status, "message": job.message, "stats": stats}

        by_steam = {m.steam_id: m for m in members if m.steam_id}
        adapter = SteamAdapter(settings.STEAM_API_KEY)
        steam_ids = list(by_steam.keys())

        all_presences: list[SteamPresence] = []
        for i in range(0, len(steam_ids), 100):
            chunk = steam_ids[i : i + 100]
            raw = adapter.fetch_summaries(chunk)
            all_presences.extend(adapter.parse_presences(raw))

        presence_map = {p.steam_id: p for p in all_presences}
        now = _utcnow()

        for steam_id, member in by_steam.items():
            presence = presence_map.get(steam_id)
            if presence is None:
                stats["skipped_private"] += 1
                continue
            _apply_presence(db, member, presence, now, stats)

        job.status = "ok"
        job.message = (
            f"轮询 {stats['members']} 人，"
            f"玩 {stats['playing']} / 在线 {stats['online']} / 离线 {stats['offline']}，"
            f"会话开 {stats['opened']} / 续 {stats['continued']} / 关 {stats['closed']}"
        )
        job.stats = stats
        job.finished_at = _utcnow()
        db.commit()
        return {"status": job.status, "message": job.message, "stats": stats}
    except Exception as exc:  # noqa: BLE001
        logger.exception("steam presence poll failed")
        job.status = "error"
        job.message = str(exc)
        job.stats = stats
        job.finished_at = _utcnow()
        db.commit()
        return {"status": job.status, "message": job.message, "stats": stats}


def poll_job_wrapper() -> None:
    """APScheduler 入口：自建 Session。"""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        run_steam_presence_poll(db)
    finally:
        db.close()
