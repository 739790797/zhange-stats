"""CS2 生涯数据：基于 Steam GetUserStatsForGame（appid=730）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.member import Member
from app.services.adapters.steam import SteamAdapter

CS2_APP_ID = 730


def _safe_ratio(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round(num / den, 2)


def _parse_member_stats(stats: dict[str, int]) -> dict:
    kills = stats.get("total_kills", 0)
    deaths = stats.get("total_deaths", 0)
    shots_fired = stats.get("total_shots_fired", 0)
    shots_hit = stats.get("total_shots_hit", 0)
    hs = stats.get("total_kills_headshot", 0)
    wins = stats.get("total_wins", 0)
    mvps = stats.get("total_mvps", 0)
    time_played = stats.get("total_time_played", 0)
    planted = stats.get("total_planted_bombs", 0)
    defused = stats.get("total_defused_bombs", 0)
    return {
        "kills": kills,
        "deaths": deaths,
        "kd_ratio": _safe_ratio(kills, deaths),
        "wins": wins,
        "mvps": mvps,
        "headshot_kills": hs,
        "headshot_pct": _safe_ratio(hs * 100, kills) if kills else None,
        "accuracy_pct": _safe_ratio(shots_hit * 100, shots_fired) if shots_fired else None,
        "time_played_seconds": time_played,
        "planted_bombs": planted,
        "defused_bombs": defused,
        "shots_fired": shots_fired,
        "shots_hit": shots_hit,
    }


def build_cs2_overview(db: Session) -> dict:
    settings = get_settings()
    members = (
        db.query(Member)
        .order_by(Member.id.asc())
        .all()
    )
    steam_bound = [m for m in members if m.steam_id]

    players: list[dict] = []
    if not settings.STEAM_API_KEY:
        for m in members:
            players.append(
                {
                    "member_id": m.id,
                    "nickname": m.nickname,
                    "avatar_url": m.avatar_url,
                    "steam_id": m.steam_id,
                    "status": "no_api_key" if m.steam_id else "unbound",
                    "message": "未配置 STEAM_API_KEY" if m.steam_id else "未绑定 Steam",
                    "stats": None,
                }
            )
        return {
            "app_id": CS2_APP_ID,
            "member_count": len(members),
            "steam_bound_count": len(steam_bound),
            "ok_count": 0,
            "players": players,
        }

    adapter = SteamAdapter(settings.STEAM_API_KEY)
    ok_count = 0

    for m in members:
        if not m.steam_id:
            players.append(
                {
                    "member_id": m.id,
                    "nickname": m.nickname,
                    "avatar_url": m.avatar_url,
                    "steam_id": None,
                    "status": "unbound",
                    "message": "未绑定 Steam",
                    "stats": None,
                }
            )
            continue
        try:
            raw = adapter.fetch_user_stats(m.steam_id, CS2_APP_ID)
            stats_map = adapter.stats_to_map(raw)
            if not stats_map:
                players.append(
                    {
                        "member_id": m.id,
                        "nickname": m.nickname,
                        "avatar_url": m.avatar_url,
                        "steam_id": m.steam_id,
                        "status": "empty",
                        "message": "无 CS2 统计（未玩过或资料未公开）",
                        "stats": None,
                    }
                )
                continue
            players.append(
                {
                    "member_id": m.id,
                    "nickname": m.nickname,
                    "avatar_url": m.avatar_url,
                    "steam_id": m.steam_id,
                    "status": "ok",
                    "message": None,
                    "stats": _parse_member_stats(stats_map),
                }
            )
            ok_count += 1
        except Exception as exc:  # noqa: BLE001
            players.append(
                {
                    "member_id": m.id,
                    "nickname": m.nickname,
                    "avatar_url": m.avatar_url,
                    "steam_id": m.steam_id,
                    "status": "error",
                    "message": str(exc)[:200],
                    "stats": None,
                }
            )

    return {
        "app_id": CS2_APP_ID,
        "member_count": len(members),
        "steam_bound_count": len(steam_bound),
        "ok_count": ok_count,
        "players": players,
    }
