"""CS2 对局同步：分享码发现 + 可选 GC 补齐。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.cs2_match import Cs2Match, Cs2MatchPlayer
from app.models.job_run import JobRun
from app.models.member import Member
from app.services.cs2_gc import enrich_pending_matches
from app.services.cs2_sharecode import decode_share_code, normalize_share_code
from app.services.cs2_sharecode_client import Cs2ShareCodeClient

logger = logging.getLogger(__name__)
JOB_KEY = "cs2_match_sync"


def run_cs2_match_sync(db: Session | None = None) -> dict:
    own_session = db is None
    if own_session:
        db = SessionLocal()
    assert db is not None

    job = JobRun(job_key=JOB_KEY, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)

    stats = {
        "members": 0,
        "new_codes": 0,
        "matches_upserted": 0,
        "enrich": {},
        "errors": 0,
    }
    try:
        settings = get_settings()
        if not settings.STEAM_API_KEY:
            raise RuntimeError("STEAM_API_KEY 未配置")

        client = Cs2ShareCodeClient(settings.STEAM_API_KEY)
        members = (
            db.query(Member)
            .filter(
                Member.steam_id.isnot(None),
                Member.cs2_auth_code.isnot(None),
                Member.cs2_known_code.isnot(None),
            )
            .all()
        )
        stats["members"] = len(members)
        max_per = max(1, settings.CS2_MATCH_MAX_PER_MEMBER)

        for member in members:
            try:
                n = _sync_member(db, client, member, max_per)
                stats["new_codes"] += n["codes"]
                stats["matches_upserted"] += n["matches"]
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                logger.warning("CS2 sync member=%s failed: %s", member.id, exc)

        stats["enrich"] = enrich_pending_matches(
            db, limit=max(1, settings.CS2_GC_ENRICH_LIMIT)
        )

        job.status = "ok"
        job.message = (
            f"members={stats['members']} new_codes={stats['new_codes']} "
            f"matches={stats['matches_upserted']} enrich={stats['enrich']}"
        )
        job.stats = stats
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "ok", "message": job.message, "stats": stats}
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.message = str(exc)[:500]
        job.stats = stats
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "error", "message": job.message, "stats": stats}
    finally:
        if own_session:
            db.close()


def cs2_match_sync_wrapper() -> None:
    run_cs2_match_sync()


def sync_member_matches(db: Session, member: Member) -> dict[str, int]:
    """保存验证码后立刻同步该成员（含 known 本场入库 + 尝试 GC 补齐）。"""
    settings = get_settings()
    if not settings.STEAM_API_KEY:
        raise RuntimeError("STEAM_API_KEY 未配置")
    if not (member.steam_id and member.cs2_auth_code and member.cs2_known_code):
        return {"codes": 0, "matches": 0}
    client = Cs2ShareCodeClient(settings.STEAM_API_KEY)
    max_per = max(1, settings.CS2_MATCH_MAX_PER_MEMBER)
    result = _sync_member(db, client, member, max_per)
    try:
        enrich_pending_matches(db, limit=max(1, settings.CS2_GC_ENRICH_LIMIT))
    except Exception as exc:  # noqa: BLE001
        logger.warning("CS2 enrich after member sync failed: %s", exc)
    return result


def _sync_member(
    db: Session, client: Cs2ShareCodeClient, member: Member, max_codes: int
) -> dict[str, int]:
    assert member.steam_id and member.cs2_auth_code and member.cs2_known_code
    known = normalize_share_code(member.cs2_sync_cursor or member.cs2_known_code)
    # 确保 known 本身入库
    _upsert_match_from_code(db, known, member)
    codes = 0
    matches = 1

    for _ in range(max_codes):
        payload = client.get_next_match_sharing_code(
            member.steam_id, member.cs2_auth_code, known
        )
        next_code = client.extract_next_code(payload)
        if not next_code:
            break
        next_code = normalize_share_code(next_code)
        if next_code == known:
            break
        _upsert_match_from_code(db, next_code, member)
        known = next_code
        codes += 1
        matches += 1

    member.cs2_sync_cursor = known
    member.cs2_known_code = known
    db.commit()
    return {"codes": codes, "matches": matches}


def _upsert_match_from_code(db: Session, share_code: str, member: Member) -> Cs2Match:
    decoded = decode_share_code(share_code)
    match = (
        db.query(Cs2Match)
        .filter(Cs2Match.match_id == decoded.match_id_str)
        .first()
    )
    if not match:
        match = Cs2Match(
            match_id=decoded.match_id_str,
            outcome_id=decoded.outcome_id_str,
            token=decoded.token,
            share_code=share_code,
            enriched=False,
        )
        db.add(match)
        db.flush()
    else:
        match.outcome_id = match.outcome_id or decoded.outcome_id_str
        match.token = match.token if match.token is not None else decoded.token
        match.share_code = match.share_code or share_code

    assert member.steam_id
    player = (
        db.query(Cs2MatchPlayer)
        .filter(
            Cs2MatchPlayer.match_id == match.match_id,
            Cs2MatchPlayer.steam_id == member.steam_id,
        )
        .first()
    )
    if not player:
        player = Cs2MatchPlayer(
            match_id=match.match_id,
            steam_id=member.steam_id,
            member_id=member.id,
            persona_name=member.nickname,
        )
        db.add(player)
    else:
        player.member_id = member.id
        if not player.persona_name:
            player.persona_name = member.nickname
    db.flush()
    return match
