"""Steam 好友列表同步与日历可见性（仅好友可见对方游玩数据）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.timeutil import ensure, now_naive
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.steam_friend import SteamFriendEdge
from app.models.user import User
from app.services.adapters.steam import SteamAdapter
from app.services.member_sync import ensure_user_member
from app.services.steam_game_names import display_name_for

logger = logging.getLogger(__name__)

FRIENDS_SYNC_TTL = timedelta(hours=6)
# 好友页自动同步冷却；手动刷新不受此限制
FRIENDS_PAGE_SYNC_TTL = timedelta(minutes=15)
FRIENDS_PAGE_SYNC_TTL_SECONDS = int(FRIENDS_PAGE_SYNC_TTL.total_seconds())


@dataclass
class FriendSyncResult:
    ok: bool
    friends_public: bool | None
    friend_count: int
    message: str | None = None


def _utcnow() -> datetime:
    return now_naive()


def _friends_sync_is_fresh(member: Member, ttl: timedelta) -> bool:
    synced = member.steam_friends_synced_at
    if synced is None:
        return False
    synced_aware = ensure(synced).replace(tzinfo=None)
    return _utcnow() - synced_aware < ttl


def clear_member_friends(db: Session, member_id: int) -> None:
    db.query(SteamFriendEdge).filter(SteamFriendEdge.member_id == member_id).delete(
        synchronize_session=False
    )


def sync_member_friends(db: Session, member: Member) -> FriendSyncResult:
    """从 Steam API 同步该成员好友列表到本地。"""
    steam_id = (member.steam_id or "").strip()
    if not steam_id:
        clear_member_friends(db, member.id)
        member.steam_friends_public = None
        member.steam_friends_synced_at = None
        return FriendSyncResult(
            ok=True, friends_public=None, friend_count=0, message="未绑定 Steam"
        )

    from app.services.integrations_config import get_steam_api_key

    steam_key = get_steam_api_key(db)
    if not steam_key:
        return FriendSyncResult(
            ok=False,
            friends_public=member.steam_friends_public,
            friend_count=0,
            message="STEAM_API_KEY 未配置",
        )

    adapter = SteamAdapter(steam_key)
    try:
        friends = adapter.fetch_friend_list(steam_id)
    except PermissionError:
        clear_member_friends(db, member.id)
        member.steam_friends_public = False
        member.steam_friends_synced_at = _utcnow()
        return FriendSyncResult(
            ok=True,
            friends_public=False,
            friend_count=0,
            message="好友列表未公开，日历中只能看到自己",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync steam friends failed member=%s: %s", member.id, exc)
        return FriendSyncResult(
            ok=False,
            friends_public=member.steam_friends_public,
            friend_count=0,
            message=str(exc),
        )

    clear_member_friends(db, member.id)
    now = _utcnow()
    nicknames: dict[str, str] = {}
    try:
        nicknames = adapter.fetch_nickname_list(steam_id)
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "fetch steam nicknames skipped member=%s: %s", member.id, exc
        )

    for item in friends:
        sid = item["steam_id"]
        db.add(
            SteamFriendEdge(
                member_id=member.id,
                friend_steam_id=sid,
                friend_since=item.get("friend_since"),
                nickname=nicknames.get(sid),
                synced_at=now,
            )
        )
    member.steam_friends_public = True
    member.steam_friends_synced_at = now
    return FriendSyncResult(
        ok=True, friends_public=True, friend_count=len(friends), message=None
    )


def ensure_friends_fresh(
    db: Session, member: Member, *, force: bool = False
) -> FriendSyncResult | None:
    if not (member.steam_id or "").strip():
        return None
    synced = member.steam_friends_synced_at
    if not force and synced is not None:
        synced_naive = ensure(synced).replace(tzinfo=None)
        if _utcnow() - synced_naive < FRIENDS_SYNC_TTL:
            return None
    return sync_member_friends(db, member)


def visible_member_ids_for_user(db: Session, user: User) -> set[int]:
    """当前用户在 Steam 日历等场景可见的成员 ID（自己 + Steam 好友）。"""
    member = ensure_user_member(db, user)
    visible = {member.id}
    steam_id = (member.steam_id or "").strip()
    if not steam_id:
        db.flush()
        return visible

    sync_result = ensure_friends_fresh(db, member)
    if sync_result is not None:
        db.commit()
        db.refresh(member)
    else:
        db.flush()

    friend_steam_ids = {
        row.friend_steam_id
        for row in db.query(SteamFriendEdge.friend_steam_id)
        .filter(SteamFriendEdge.member_id == member.id)
        .all()
    }

    if friend_steam_ids:
        rows = (
            db.query(Member.id)
            .filter(
                Member.user_id.isnot(None),
                Member.steam_id.in_(friend_steam_ids),
            )
            .all()
        )
        visible.update(r[0] for r in rows)

    reverse_member_ids = {
        row.member_id
        for row in db.query(SteamFriendEdge.member_id)
        .filter(SteamFriendEdge.friend_steam_id == steam_id)
        .all()
    }
    if reverse_member_ids:
        rows = (
            db.query(Member.id)
            .filter(
                Member.id.in_(reverse_member_ids),
                Member.user_id.isnot(None),
            )
            .all()
        )
        visible.update(r[0] for r in rows)

    return visible


def list_viewer_steam_friends(
    db: Session, user: User, *, force: bool = False
) -> dict:
    """好友列表。冷却期内默认用缓存；force=True 或过期时从 Steam 同步。"""
    member = ensure_user_member(db, user)
    bound = bool((member.steam_id or "").strip())
    did_sync = False
    sync_ok = True
    hint: str | None = None

    if not bound:
        hint = "请先在个人中心绑定 Steam"
        db.flush()
    else:
        should_sync = force or not _friends_sync_is_fresh(member, FRIENDS_PAGE_SYNC_TTL)
        if should_sync:
            sync = sync_member_friends(db, member)
            db.commit()
            db.refresh(member)
            did_sync = True
            sync_ok = sync.ok
            hint = sync.message
            if sync.friends_public is False:
                hint = (
                    "你的 Steam 好友列表未公开，无法拉取好友。"
                    "请在 Steam 隐私设置中将「好友列表」设为公开后点击刷新"
                )
        else:
            db.flush()

    edges = (
        db.query(SteamFriendEdge)
        .filter(SteamFriendEdge.member_id == member.id)
        .all()
        if bound
        else []
    )
    # 未公开时 friends_public=False，edges 应为空；从未同步成功也可能为空
    if bound and member.steam_friends_public is False and not hint:
        hint = (
            "你的 Steam 好友列表未公开，无法拉取好友。"
            "请在 Steam 隐私设置中将「好友列表」设为公开后点击刷新"
        )

    friend_steam_ids = [e.friend_steam_id for e in edges]
    since_map = {e.friend_steam_id: e.friend_since for e in edges}
    alias_map = {
        e.friend_steam_id: e.nickname
        for e in edges
        if e.nickname and str(e.nickname).strip()
    }

    site_by_steam: dict[str, Member] = {}
    if friend_steam_ids:
        for row in (
            db.query(Member)
            .filter(
                Member.user_id.isnot(None),
                Member.steam_id.in_(friend_steam_ids),
            )
            .all()
        ):
            if row.steam_id:
                site_by_steam[row.steam_id] = row

    players: dict[str, dict] = {}
    # 好友边可走缓存，但昵称/头像/在线状态不落库，每次展示都需 GetPlayerSummaries
    # （否则冷却期内 force=false 只会显示 steam_id）
    if friend_steam_ids:
        from app.services.integrations_config import get_steam_api_key

        steam_key = get_steam_api_key(db)
        if steam_key:
            adapter = SteamAdapter(steam_key)
            try:
                for i in range(0, len(friend_steam_ids), 100):
                    chunk = friend_steam_ids[i : i + 100]
                    raw = adapter.fetch_summaries(chunk)
                    for p in (raw or {}).get("response", {}).get("players") or []:
                        sid = str(p.get("steamid") or "")
                        if sid:
                            players[sid] = p
            except Exception as exc:  # noqa: BLE001
                logger.warning("fetch friend summaries failed: %s", exc)
                if not hint:
                    hint = f"好友状态刷新失败：{exc}"

    playing_member_ids: set[int] = set()
    playing_game: dict[int, str] = {}
    playing_app: dict[int, str] = {}
    # summaries 失败时，站内已绑定好友仍可用本地进行中会话兜底「游戏中」
    if site_by_steam and not players:
        site_ids = [m.id for m in site_by_steam.values()]
        if site_ids:
            for s in (
                db.query(PlaySession)
                .filter(
                    PlaySession.source == "steam",
                    PlaySession.ended_at.is_(None),
                    PlaySession.member_id.in_(site_ids),
                )
                .all()
            ):
                playing_member_ids.add(s.member_id)
                if s.steam_app_id:
                    playing_app[s.member_id] = s.steam_app_id
                if s.game_name:
                    playing_game[s.member_id] = s.game_name

    friends: list[dict] = []
    for sid in friend_steam_ids:
        p = players.get(sid) or {}
        site = site_by_steam.get(sid)
        game_id = p.get("gameid")
        persona_state = p.get("personastate")
        if p:
            if game_id:
                status = "playing"
            elif persona_state is None or int(persona_state) == 0:
                status = "offline"
            else:
                status = "online"
            game_name = p.get("gameextrainfo")
            app_id = str(game_id) if game_id else None
        elif site and site.id in playing_member_ids:
            status = "playing"
            game_name = playing_game.get(site.id)
            app_id = playing_app.get(site.id)
        else:
            status = "offline"
            game_name = None
            app_id = None

        if status == "playing" and (app_id or game_name):
            game_name = display_name_for(db, app_id, game_name)

        persona = (
            p.get("personaname")
            or (site.steam_persona_name if site else None)
            or (site.nickname if site else None)
            or sid
        )
        alias = alias_map.get(sid)
        display = f"*{alias.strip()}" if alias and str(alias).strip() else persona

        friends.append(
            {
                "steam_id": sid,
                "persona_name": display,
                "steam_persona_name": persona,
                "friend_nickname": alias,
                "avatar_url": p.get("avatarfull")
                or p.get("avatarmedium")
                or p.get("avatar")
                or (site.avatar_url if site else None),
                "profile_url": p.get("profileurl"),
                "status": status,
                "game_name": game_name,
                "steam_app_id": app_id,
                "friend_since": since_map.get(sid),
                "member_id": site.id if site else None,
                "is_registered": site is not None,
            }
        )

    status_order = {"playing": 0, "online": 1, "offline": 2}
    friends.sort(
        key=lambda f: (
            status_order.get(f["status"], 9),
            (f["persona_name"] or "").lower(),
        )
    )

    return {
        "steam_bound": bound,
        "friends_list_public": member.steam_friends_public,
        "friends_synced_at": member.steam_friends_synced_at,
        "friend_count": len(friends),
        "sync_ok": sync_ok,
        "synced": did_sync,
        "sync_interval_seconds": FRIENDS_PAGE_SYNC_TTL_SECONDS,
        "hint": hint,
        "friends": friends,
    }


def can_view_member_steam(db: Session, viewer: User, target_member_id: int) -> bool:
    return target_member_id in visible_member_ids_for_user(db, viewer)


def visibility_meta(
    db: Session,
    user: User,
    visible_ids: set[int] | None = None,
) -> dict:
    member = ensure_user_member(db, user)
    ids = visible_ids if visible_ids is not None else visible_member_ids_for_user(db, user)
    bound = bool((member.steam_id or "").strip())
    friends_public = member.steam_friends_public
    friend_count = max(0, len(ids) - 1)

    hint: str | None = None
    if not bound:
        hint = "绑定 Steam 后，只能看到自己与 Steam 好友的游玩数据"
    elif friends_public is False:
        hint = (
            "你的 Steam 好友列表未公开：目前只能看到自己。"
            "请在 Steam 隐私设置中将「好友列表」设为公开后，点击换绑或等待自动同步"
        )
    elif friend_count == 0:
        hint = "当前没有站内 Steam 好友，日历仅显示你自己的数据"

    return {
        "mode": "steam_friends",
        "self_member_id": member.id,
        "steam_bound": bound,
        "friends_list_public": friends_public,
        "friends_synced_at": member.steam_friends_synced_at,
        "visible_friend_count": friend_count,
        "hint": hint,
    }
