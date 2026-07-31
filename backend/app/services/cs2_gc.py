"""CS2 对局 GC 详情补齐。

流程：boiler-writter（本机 Steam 登录）→ Node 解析 protobuf → 落库地图/比分/KDA。
配置 CS2_GC_BOILER_PATH；解析脚本默认 tools/cs2_gc/fetch_match.mjs。
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.cs2_match import Cs2Match, Cs2MatchPlayer
from app.models.member import Member

logger = logging.getLogger(__name__)

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools" / "cs2_gc"
_DEFAULT_BOILER = _TOOLS_DIR / "boiler" / "bin" / "boiler-writter.exe"
_DEFAULT_SCRIPT = _TOOLS_DIR / "fetch_match.mjs"


def enrich_pending_matches(db: Session, limit: int = 10) -> dict[str, int]:
    settings = get_settings()
    pending = (
        db.query(Cs2Match)
        .filter(Cs2Match.enriched.is_(False))
        .order_by(Cs2Match.id.asc())
        .limit(limit)
        .all()
    )
    if not pending:
        return {"pending": 0, "enriched": 0, "skipped": 0, "errors": 0}

    boiler = _resolve_boiler_path(settings.CS2_GC_BOILER_PATH)
    script = _resolve_script_path(getattr(settings, "CS2_GC_FETCH_SCRIPT", "") or "")
    if not boiler:
        logger.info("CS2 GC：未配置/找不到 boiler，跳过补齐")
        return {
            "pending": len(pending),
            "enriched": 0,
            "skipped": len(pending),
            "errors": 0,
        }
    if not script or not script.exists():
        logger.warning("CS2 GC：找不到 fetch_match.mjs: %s", script)
        return {
            "pending": len(pending),
            "enriched": 0,
            "skipped": len(pending),
            "errors": 0,
        }

    enriched = 0
    skipped = 0
    errors = 0
    for match in pending:
        try:
            raw = _fetch_match_json(
                match,
                boiler=boiler,
                script=script,
                timeout=max(30, settings.CS2_GC_TIMEOUT_SECONDS),
            )
            if not raw:
                skipped += 1
                continue
            _apply_gc_payload(db, match, raw)
            match.enriched = True
            match.raw_json = json.dumps(raw, ensure_ascii=False)[:65000]
            enriched += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.warning("CS2 GC enrich failed match=%s: %s", match.match_id, exc)
    db.commit()
    return {
        "pending": len(pending),
        "enriched": enriched,
        "skipped": skipped,
        "errors": errors,
    }


def _resolve_boiler_path(configured: str) -> Path | None:
    candidates: list[Path] = []
    if configured.strip():
        candidates.append(Path(configured.strip()))
    candidates.append(_DEFAULT_BOILER)
    for path in candidates:
        if path.exists():
            return path
    return None


def _resolve_script_path(configured: str) -> Path | None:
    if configured.strip():
        path = Path(configured.strip())
        return path if path.exists() else path
    if _DEFAULT_SCRIPT.exists():
        return _DEFAULT_SCRIPT
    return _DEFAULT_SCRIPT


def _fetch_match_json(
    match: Cs2Match,
    *,
    boiler: Path,
    script: Path,
    timeout: int,
) -> dict[str, Any] | None:
    if not match.outcome_id or match.token is None:
        return None
    cmd = [
        "node",
        str(script),
        str(match.match_id),
        str(match.outcome_id),
        str(match.token),
        str(boiler),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        check=False,
        cwd=str(script.parent),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="ignore")
        raise RuntimeError(err.strip() or f"fetch_match exit {proc.returncode}")
    text = proc.stdout.decode("utf-8", errors="ignore").strip()
    if not text:
        raise RuntimeError("fetch_match 无输出")
    return json.loads(text)


def _apply_gc_payload(db: Session, match: Cs2Match, raw: dict[str, Any]) -> None:
    """JSON：{map_name, played_at, score_team0, score_team1, demo_url, players:[...]}"""
    if raw.get("map_name"):
        match.map_name = str(raw["map_name"])[:64]
    if raw.get("demo_url"):
        match.demo_url = str(raw["demo_url"])[:512]
    if raw.get("score_team0") is not None:
        match.score_team0 = int(raw["score_team0"])
    if raw.get("score_team1") is not None:
        match.score_team1 = int(raw["score_team1"])
    played_at = raw.get("played_at")
    if played_at:
        try:
            if isinstance(played_at, (int, float)):
                match.played_at = datetime.utcfromtimestamp(int(played_at))
            else:
                text = str(played_at).replace("Z", "+00:00")
                match.played_at = datetime.fromisoformat(text).replace(tzinfo=None)
        except ValueError:
            pass

    players = raw.get("players") or []
    steam_to_member = {
        m.steam_id: m.id
        for m in db.query(Member).filter(Member.steam_id.isnot(None)).all()
        if m.steam_id
    }
    for p in players:
        steam_id = str(p.get("steam_id") or "").strip()
        if not steam_id:
            continue
        row = (
            db.query(Cs2MatchPlayer)
            .filter(
                Cs2MatchPlayer.match_id == match.match_id,
                Cs2MatchPlayer.steam_id == steam_id,
            )
            .first()
        )
        if not row:
            row = Cs2MatchPlayer(match_id=match.match_id, steam_id=steam_id)
            db.add(row)
        row.member_id = steam_to_member.get(steam_id)
        if p.get("team") is not None:
            row.team = int(p["team"])
        for field in ("kills", "deaths", "assists", "mvps", "score", "damage"):
            if p.get(field) is not None:
                setattr(row, field, int(p[field]))
        if "won" in p and p["won"] is not None:
            row.won = bool(p["won"])
        if p.get("persona_name"):
            row.persona_name = str(p["persona_name"])[:128]
