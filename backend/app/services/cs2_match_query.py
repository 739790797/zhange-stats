"""CS2 对局查询：我的对局 / 开黑对照。"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.cs2_match import Cs2Match, Cs2MatchPlayer
from app.models.member import Member
from app.models.user import User
from app.services.member_sync import ensure_user_member


def _player_out(p: Cs2MatchPlayer) -> dict:
    nick = None
    avatar = None
    if p.member:
        nick = p.member.nickname
        avatar = p.member.avatar_url
    return {
        "steam_id": p.steam_id,
        "member_id": p.member_id,
        "nickname": nick or p.persona_name,
        "avatar_url": avatar,
        "team": p.team,
        "kills": p.kills,
        "deaths": p.deaths,
        "assists": p.assists,
        "mvps": p.mvps,
        "score": p.score,
        "damage": p.damage,
        "won": p.won,
        "persona_name": p.persona_name,
    }


def list_my_matches(db: Session, user: User, limit: int = 50) -> list[dict]:
    member = ensure_user_member(db, user)
    db.commit()
    rows = (
        db.query(Cs2MatchPlayer)
        .options(
            joinedload(Cs2MatchPlayer.match),
            joinedload(Cs2MatchPlayer.member),
        )
        .filter(Cs2MatchPlayer.member_id == member.id)
        .all()
    )
    # 按对局时间/id 排序
    rows.sort(
        key=lambda r: (
            r.match.played_at is not None,
            r.match.played_at or r.match.created_at,
            r.match.id,
        ),
        reverse=True,
    )
    result: list[dict] = []
    for row in rows[:limit]:
        m = row.match
        result.append(
            {
                "match_id": m.match_id,
                "share_code": m.share_code,
                "map_name": m.map_name,
                "played_at": m.played_at,
                "score_team0": m.score_team0,
                "score_team1": m.score_team1,
                "demo_url": m.demo_url,
                "enriched": bool(m.enriched),
                "my_stats": _player_out(row),
                "players": [],
            }
        )
    return result


def list_together_matches(
    db: Session,
    user: User,
    member_ids: list[int],
    limit: int = 50,
) -> list[dict]:
    me = ensure_user_member(db, user)
    db.commit()
    ids = {int(x) for x in member_ids}
    ids.add(me.id)
    if len(ids) < 2:
        raise ValueError("请至少再选择一名对照成员")

    # match_id 下圈内选中成员数 >= 2 且包含自己
    q = (
        db.query(Cs2MatchPlayer.match_id)
        .filter(Cs2MatchPlayer.member_id.in_(ids))
        .group_by(Cs2MatchPlayer.match_id)
        .having(func.count(func.distinct(Cs2MatchPlayer.member_id)) >= 2)
    )
    match_ids = [r[0] for r in q.all()]
    if not match_ids:
        return []

    # 必须包含当前用户
    my_matches = {
        r[0]
        for r in db.query(Cs2MatchPlayer.match_id)
        .filter(
            Cs2MatchPlayer.member_id == me.id,
            Cs2MatchPlayer.match_id.in_(match_ids),
        )
        .all()
    }
    match_ids = [mid for mid in match_ids if mid in my_matches]
    if not match_ids:
        return []

    matches = (
        db.query(Cs2Match)
        .options(joinedload(Cs2Match.players).joinedload(Cs2MatchPlayer.member))
        .filter(Cs2Match.match_id.in_(match_ids))
        .all()
    )
    matches.sort(
        key=lambda m: (m.played_at is not None, m.played_at or m.created_at, m.id),
        reverse=True,
    )

    out: list[dict] = []
    for m in matches[:limit]:
        circled = [
            _player_out(p)
            for p in m.players
            if p.member_id is not None and p.member_id in ids
        ]
        if len(circled) < 2:
            continue
        out.append(
            {
                "match_id": m.match_id,
                "share_code": m.share_code,
                "map_name": m.map_name,
                "played_at": m.played_at,
                "score_team0": m.score_team0,
                "score_team1": m.score_team1,
                "enriched": bool(m.enriched),
                "circled_players": circled,
            }
        )
    return out
