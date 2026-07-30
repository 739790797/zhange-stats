"""Steam 正在游玩轮询：开/续/关 play_sessions，并写 job_runs。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.play_session import PlaySession
from app.services.adapters.steam import SteamAdapter, SteamPresence

logger = logging.getLogger(__name__)

JOB_KEY = "steam_presence"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_steam_presence_poll(db: Session) -> dict:
    settings = get_settings()
    job = JobRun(job_key=JOB_KEY, status="running", started_at=_utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)

    stats = {
        "members": 0,
        "playing": 0,
        "opened": 0,
        "continued": 0,
        "closed": 0,
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

        # Steam 单次最多 100 个
        all_presences: list[SteamPresence] = []
        for i in range(0, len(steam_ids), 100):
            chunk = steam_ids[i : i + 100]
            raw = adapter.fetch_summaries(chunk)
            all_presences.extend(adapter.parse_presences(raw))

        presence_map = {p.steam_id: p for p in all_presences}
        now = _utcnow()

        for steam_id, member in by_steam.items():
            presence = presence_map.get(steam_id)
            open_session = (
                db.query(PlaySession)
                .filter(
                    PlaySession.member_id == member.id,
                    PlaySession.ended_at.is_(None),
                    PlaySession.source == "steam",
                )
                .order_by(PlaySession.started_at.desc())
                .first()
            )

            if presence is None:
                # API 未返回该玩家：保持现状，记为 skipped
                stats["skipped_private"] += 1
                continue

            playing_app = presence.game_id
            game_name = presence.game_extra_info or (
                f"App {playing_app}" if playing_app else None
            )

            if playing_app:
                stats["playing"] += 1

            if open_session is None:
                if playing_app and game_name:
                    db.add(
                        PlaySession(
                            member_id=member.id,
                            steam_app_id=playing_app,
                            game_name=game_name,
                            started_at=now,
                            last_seen_at=now,
                            ended_at=None,
                            source="steam",
                        )
                    )
                    stats["opened"] += 1
                continue

            # 已有进行中会话
            if playing_app and playing_app == open_session.steam_app_id:
                open_session.last_seen_at = now
                if game_name:
                    open_session.game_name = game_name
                stats["continued"] += 1
            else:
                open_session.ended_at = now
                open_session.last_seen_at = now
                stats["closed"] += 1
                if playing_app and game_name:
                    db.add(
                        PlaySession(
                            member_id=member.id,
                            steam_app_id=playing_app,
                            game_name=game_name,
                            started_at=now,
                            last_seen_at=now,
                            ended_at=None,
                            source="steam",
                        )
                    )
                    stats["opened"] += 1

        job.status = "ok"
        job.message = (
            f"轮询 {stats['members']} 人，在玩 {stats['playing']}，"
            f"开 {stats['opened']} / 续 {stats['continued']} / 关 {stats['closed']}"
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
