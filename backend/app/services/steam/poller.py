"""Steam 状态轮询：写入 presence_segments + play_sessions，并记 job_runs。"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.core.biz_logging import clear_log_until_change, log_until_change
from app.core.timeutil import ensure, now_naive
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.services.adapters.steam import SteamAdapter, SteamPresence
from app.services.job_runs_prune import fail_job_run
from app.services.steam.game_names import prefer_display_name, resolve_app_names
from app.services.steam.persona import apply_steam_persona_name

logger = logging.getLogger(__name__)

JOB_KEY = "steam_presence"
_poll_lock = threading.Lock()
_POLL_FAILURE_LOG_KEY = "steam-presence-poll"
# 这些计数非零才算这轮有变化，调度日志据此决定 done 打 INFO 还是 DEBUG
_CHANGE_STATS = (
    "opened",
    "closed",
    "presence_opened",
    "presence_closed",
    "stale_closed",
    "persona_updated",
)


def _now() -> datetime:
    return now_naive()


def _aware(dt: datetime) -> datetime:
    """读库时间规范为北京墙钟 naive，便于与 _now() 比较。"""
    return ensure(dt).replace(tzinfo=None)


def _open_rows_by_member(db: Session, model, member_ids: list[int]) -> dict[int, list]:
    """一次查出这些成员仍未结束的 steam 行，按成员分组、每组 started_at 倒序。"""
    if not member_ids:
        return {}
    rows = (
        db.query(model)
        .filter(
            model.member_id.in_(member_ids),
            model.ended_at.is_(None),
            model.source == "steam",
        )
        .order_by(model.member_id, model.started_at.desc())
        .all()
    )
    out: dict[int, list] = {}
    for row in rows:
        out.setdefault(int(row.member_id), []).append(row)
    return out


def _collapse_duplicate_opens(
    open_segs: list[PresenceSegment],
    open_plays: list[PlaySession],
    now: datetime,
    stats: dict,
) -> tuple[PresenceSegment | None, PlaySession | None]:
    """Keep at most one open presence / play session per member."""
    for seg in open_segs[1:]:
        seg.ended_at = now
        seg.last_seen_at = now
        stats["presence_closed"] += 1
    for play in open_plays[1:]:
        play.ended_at = now
        play.last_seen_at = now
        stats["closed"] += 1
    return (
        open_segs[0] if open_segs else None,
        open_plays[0] if open_plays else None,
    )


def _close_open_sessions(
    open_segs: list[PresenceSegment],
    open_plays: list[PlaySession],
    now: datetime,
    stats: dict,
) -> None:
    for seg in open_segs:
        seg.ended_at = now
        seg.last_seen_at = now
        stats["presence_closed"] += 1
    for play in open_plays:
        play.ended_at = now
        play.last_seen_at = now
        stats["closed"] += 1


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
    *,
    open_segs: list[PresenceSegment],
    open_plays: list[PlaySession],
    names: dict[str, str],
) -> None:
    open_seg, open_play = _collapse_duplicate_opens(open_segs, open_plays, now, stats)

    status = presence.status
    app_id = presence.game_id
    game_name = (
        prefer_display_name(
            names.get(str(app_id).strip()) if app_id else None,
            presence.game_extra_info,
            app_id,
        )
        if status == "playing"
        else None
    )

    if status == "playing":
        stats["playing"] += 1
    elif status == "online":
        stats["online"] += 1
    else:
        stats["offline"] += 1

    # ---- presence_segments ----
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


def _maybe_close_stale(
    open_segs: list[PresenceSegment],
    open_plays: list[PlaySession],
    now: datetime,
    stale_after: timedelta,
    stats: dict,
) -> None:
    """Steam 未返回该玩家时：仅在超时后收尾，避免短暂隐私/抖动误关。"""
    open_seg = open_segs[0] if open_segs else None
    open_play = open_plays[0] if open_plays else None
    if open_seg is None and open_play is None:
        return
    last_candidates = []
    if open_seg is not None:
        last_candidates.append(_aware(open_seg.last_seen_at))
    if open_play is not None:
        last_candidates.append(_aware(open_play.last_seen_at))
    last = max(last_candidates)
    if now - last < stale_after:
        return
    _close_open_sessions(open_segs, open_plays, now, stats)
    stats["stale_closed"] = stats.get("stale_closed", 0) + 1


def run_steam_presence_poll(db: Session) -> dict:
    if not _poll_lock.acquire(blocking=False):
        return {
            "status": "skipped",
            "message": "已有轮询在进行中",
            "stats": {},
        }

    try:
        return _run_steam_presence_poll_locked(db)
    finally:
        _poll_lock.release()


def _run_steam_presence_poll_locked(db: Session) -> dict:
    from app.services.integrations_config import get_steam_api_key
    from app.services.scheduler_config import load_scheduler_config

    steam_key = get_steam_api_key(db)
    sched = load_scheduler_config(db).get("steam_presence") or {}
    interval = max(1, int(sched.get("interval_minutes") or 3))

    job = JobRun(job_key=JOB_KEY, status="running", started_at=_now())
    db.add(job)
    db.commit()
    db.refresh(job)
    run_id = job.id

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
        "stale_closed": 0,
        "persona_updated": 0,
        "failed": 0,
    }

    try:
        if not steam_key:
            raise RuntimeError("STEAM_API_KEY 未配置")

        members = (
            db.query(Member)
            .options(joinedload(Member.user))
            .filter(Member.steam_id.isnot(None), Member.steam_id != "")
            .all()
        )
        stats["members"] = len(members)
        if not members:
            job.status = "ok"
            job.message = "无可轮询成员（未绑定 steam_id）"
            job.stats = stats
            job.finished_at = _now()
            db.commit()
            return {"status": job.status, "message": job.message, "stats": stats}

        by_steam = {m.steam_id: m for m in members if m.steam_id}
        adapter = SteamAdapter(steam_key)
        steam_ids = list(by_steam.keys())

        all_presences: list[SteamPresence] = []
        for i in range(0, len(steam_ids), 100):
            chunk = steam_ids[i : i + 100]
            raw = adapter.fetch_summaries(chunk)
            all_presences.extend(adapter.parse_presences(raw))

        presence_map = {p.steam_id: p for p in all_presences}
        # 商店名可能要回源，放在逐成员写库之前，循环里不再打 HTTP
        names = resolve_app_names(
            db,
            [
                p.game_id
                for p in presence_map.values()
                if p.status == "playing" and p.game_id
            ],
        )
        member_ids = [m.id for m in by_steam.values()]
        open_segs = _open_rows_by_member(db, PresenceSegment, member_ids)
        open_plays = _open_rows_by_member(db, PlaySession, member_ids)
        now = _now()
        # interval 已从调度配置读取
        stale_after = timedelta(minutes=interval * 3)

        for steam_id, member in by_steam.items():
            mid = member.id
            presence = presence_map.get(steam_id)
            segs = open_segs.get(mid, [])
            plays = open_plays.get(mid, [])
            try:
                with db.begin_nested():
                    if presence is None:
                        stats["skipped_private"] += 1
                        _maybe_close_stale(segs, plays, now, stale_after, stats)
                    else:
                        if apply_steam_persona_name(
                            member,
                            presence.persona_name,
                            avatar_url=presence.avatar_url,
                        ):
                            stats["persona_updated"] += 1
                        _apply_presence(
                            db,
                            member,
                            presence,
                            now,
                            stats,
                            open_segs=segs,
                            open_plays=plays,
                            names=names,
                        )
                clear_log_until_change(f"steam-poll-member:{mid}")
            except Exception:  # noqa: BLE001
                stats["failed"] += 1
                log_until_change(
                    logger,
                    f"steam-poll-member:{mid}",
                    "steam presence apply failed member_id=%s",
                    mid,
                    exc_info=True,
                )

        failed = int(stats["failed"])
        job.status = "error" if failed else "ok"
        job.message = (
            f"轮询 {stats['members']} 人，"
            f"玩 {stats['playing']} / 在线 {stats['online']} / 离线 {stats['offline']}，"
            f"会话开 {stats['opened']} / 续 {stats['continued']} / 关 {stats['closed']}；"
            f"昵称跟随 {stats['persona_updated']}"
            + (f"；失败 {failed} 人" if failed else "")
        )
        job.stats = stats
        job.finished_at = _now()
        db.commit()
        clear_log_until_change(_POLL_FAILURE_LOG_KEY)
        return {"status": job.status, "message": job.message, "stats": stats}
    except RuntimeError as exc:
        # Steam 接口不通 / key 失效（SteamAdapter 统一抛 RuntimeError）：每轮都会失败，原因变了才再打
        log_until_change(logger, _POLL_FAILURE_LOG_KEY, "steam presence poll failed: %s", exc)
        fail_job_run(db, run_id, str(exc), stats=stats)
        return {"status": "error", "message": str(exc), "stats": stats}
    except Exception as exc:  # noqa: BLE001
        logger.exception("steam presence poll failed")
        fail_job_run(db, run_id, str(exc), stats=stats)
        return {"status": "error", "message": str(exc), "stats": stats}


def poll_job_wrapper() -> bool:
    """APScheduler 入口：自建 Session；返回这轮是否有会话 / 在线状态 / 昵称变化。"""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        out = run_steam_presence_poll(db)
    finally:
        db.close()
    stats = out.get("stats") or {}
    return any(stats.get(key) for key in _CHANGE_STATS)
