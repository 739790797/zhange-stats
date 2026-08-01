"""开发库造「正在游玩」演示数据：多游戏 × 多人。

会话 source=demo，Steam 轮询不会收尾，可一直显示。

用法（仓库 backend 目录）:
  .venv\\Scripts\\python.exe scripts_dev_seed_now_playing.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.models.steam_friend import SteamFriendEdge
from app.models.user import User, UserRole
from app.services.steam_game_names import display_name_for

DEMO_SOURCE = "demo"

# 仅用演示账号，避免真实 Steam 轮询把会话关掉
GAMES: list[tuple[str, list[tuple[str, int]]]] = [
    (
        "1091500",  # 赛博朋克 2077
        [("演示甲", 45 * 60), ("演示乙", 28 * 60), ("演示丙", 12 * 60)],
    ),
    (
        "2622380",  # 艾尔登法环 黑夜君临
        [("演示丁", 90 * 60), ("演示戊", 33 * 60), ("演示己", 8 * 60)],
    ),
    (
        "3561220",  # 风暴怕死队
        [("演示庚", 55 * 60), ("演示辛", 20 * 60), ("演示壬", 6 * 60)],
    ),
    (
        "2436940",  # 赛菲莉娅
        [("演示癸", 15 * 60), ("演示子", 41 * 60)],
    ),
]

DEMO_USERS = [
    ("demo_viewer", "演示观察者", "76561199000000999"),
    ("demo_jia", "演示甲", "76561199000000001"),
    ("demo_yi", "演示乙", "76561199000000002"),
    ("demo_bing", "演示丙", "76561199000000003"),
    ("demo_ding", "演示丁", "76561199000000004"),
    ("demo_wu", "演示戊", "76561199000000005"),
    ("demo_ji", "演示己", "76561199000000006"),
    ("demo_geng", "演示庚", "76561199000000007"),
    ("demo_xin", "演示辛", "76561199000000008"),
    ("demo_ren", "演示壬", "76561199000000009"),
    ("demo_gui", "演示癸", "76561199000000010"),
    ("demo_zi", "演示子", "76561199000000011"),
]
DEMO_PASSWORD = "demopass123"
AVATAR_POOL = [
    "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg",
    "https://avatars.steamstatic.com/b5bd56c1aa4644a474a2e4972be27ef9e82e517e_full.jpg",
    "https://avatars.steamstatic.com/8c6fb3bf7f817d3940983d61a36c9b45e66f7f56_full.jpg",
    "https://avatars.steamstatic.com/7470330d5f99528905a6e9fc6bc2f5b03386f129_full.jpg",
    "https://avatars.steamstatic.com/37cf1dc1f48ac849fb89a0b11182816609a9e6eb_full.jpg",
    "https://avatars.steamstatic.com/40506bef7351cb1ca374f07fa05aa6be95c7e36a_full.jpg",
    "https://avatars.steamstatic.com/5fea668694c95ff82c2d9cc2b2afdb06a9d2bbb4_full.jpg",
    "https://avatars.steamstatic.com/3fb6cde7db0bafe17c9c2708d04e0ed8d6214f0e_full.jpg",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_demo_user(
    db, username: str, display_name: str, steam_id: str, avatar_url: str
) -> Member:
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        user = User(
            username=username,
            email=f"{username}@localhost",
            display_name=display_name,
            password_hash=hash_password(DEMO_PASSWORD),
            email_verified=True,
        )
        user.apply_role(UserRole.user)
        db.add(user)
        db.flush()
    else:
        user.display_name = display_name
        user.password_hash = hash_password(DEMO_PASSWORD)
        user.email_verified = True

    member = db.query(Member).filter(Member.user_id == user.id).first()
    if member is None:
        # 可能是旧脚本按 steam_id 建过成员
        member = db.query(Member).filter(Member.steam_id == steam_id).first()
        if member is not None:
            member.user_id = user.id
            member.nickname = display_name
            member.avatar_url = avatar_url
            member.steam_friends_public = True
        else:
            # 释放其它成员占用的同 steam_id
            conflict = (
                db.query(Member)
                .filter(Member.steam_id == steam_id, Member.user_id.isnot(None))
                .first()
            )
            if conflict is not None and conflict.user_id != user.id:
                conflict.steam_id = None
                db.flush()
            member = Member(
                nickname=display_name,
                user_id=user.id,
                steam_id=steam_id,
                avatar_url=avatar_url,
                steam_friends_public=True,
            )
            db.add(member)
            db.flush()
    else:
        conflict = (
            db.query(Member)
            .filter(
                Member.steam_id == steam_id,
                Member.id != member.id,
            )
            .first()
        )
        if conflict is not None:
            conflict.steam_id = None
            db.flush()
        member.nickname = display_name
        member.steam_id = steam_id
        member.avatar_url = avatar_url
        member.steam_friends_public = True
    return member


def ensure_friend_edge(db, member_id: int, friend_steam_id: str) -> None:
    exists = (
        db.query(SteamFriendEdge)
        .filter(
            SteamFriendEdge.member_id == member_id,
            SteamFriendEdge.friend_steam_id == friend_steam_id,
        )
        .first()
    )
    if exists is None:
        db.add(
            SteamFriendEdge(
                member_id=member_id,
                friend_steam_id=friend_steam_id,
                friend_since=None,
            )
        )


def close_all_opens(db, member_ids: set[int], now: datetime) -> None:
    """收尾指定成员的所有进行中会话（任意 source）。"""
    if not member_ids:
        return
    for s in (
        db.query(PlaySession)
        .filter(
            PlaySession.member_id.in_(member_ids),
            PlaySession.ended_at.is_(None),
        )
        .all()
    ):
        s.ended_at = now
        s.last_seen_at = now
    for seg in (
        db.query(PresenceSegment)
        .filter(
            PresenceSegment.member_id.in_(member_ids),
            PresenceSegment.ended_at.is_(None),
        )
        .all()
    ):
        seg.ended_at = now
        seg.last_seen_at = now


def close_demo_opens(db, member_ids: set[int], now: datetime) -> None:
    if not member_ids:
        return
    for s in (
        db.query(PlaySession)
        .filter(
            PlaySession.member_id.in_(member_ids),
            PlaySession.source == DEMO_SOURCE,
            PlaySession.ended_at.is_(None),
        )
        .all()
    ):
        s.ended_at = now
        s.last_seen_at = now
    for seg in (
        db.query(PresenceSegment)
        .filter(
            PresenceSegment.member_id.in_(member_ids),
            PresenceSegment.source == DEMO_SOURCE,
            PresenceSegment.ended_at.is_(None),
        )
        .all()
    ):
        seg.ended_at = now
        seg.last_seen_at = now


def main() -> int:
    db = SessionLocal()
    try:
        now = _utcnow()
        demos: dict[str, Member] = {}
        for i, (username, display_name, steam_id) in enumerate(DEMO_USERS):
            demos[display_name] = ensure_demo_user(
                db,
                username,
                display_name,
                steam_id,
                AVATAR_POOL[i % len(AVATAR_POOL)],
            )
        db.flush()

        viewer = demos["演示观察者"]
        players = [m for name, m in demos.items() if name != "演示观察者"]

        for m in players:
            ensure_friend_edge(db, viewer.id, m.steam_id)  # type: ignore[arg-type]
            ensure_friend_edge(db, m.id, viewer.steam_id)  # type: ignore[arg-type]

        # 兼容旧演示账号（demo_alpha 等）也挂到观察者好友下
        for old in ("演示甲", "演示乙", "演示丙"):
            if old in demos:
                continue

        close_all_opens(db, {m.id for m in players}, now)

        # 旧脚本可能写在真实成员上（source=steam），一并收尾避免干扰
        legacy_nicks = (
            "Boom",
            "Hydra",
            "IsolandLUli",
            "熬成修女",
            "AsahiIA",
            "BaiYi",
            "Arakumi",
            "demo_alpha",
            "demo_bravo",
            "demo_charlie",
        )
        legacy_ids = {
            m.id
            for m in db.query(Member)
            .filter(Member.nickname.in_(legacy_nicks))
            .all()
        }
        # 仅收尾他们身上遗留的 demo 源；真实 steam 会话留给轮询
        close_demo_opens(db, legacy_ids, now)
        # 旧假 steam_id 账号上的任意 open 会话都清掉
        demo_steam_ids = {u[2] for u in DEMO_USERS}
        old_demo_members = (
            db.query(Member).filter(Member.steam_id.in_(demo_steam_ids)).all()
        )
        close_all_opens(db, {m.id for m in old_demo_members}, now)

        created = 0
        for app_id, roster in GAMES:
            game_name = display_name_for(db, app_id, f"App {app_id}") or f"App {app_id}"
            print(f"游戏 {game_name} ({app_id}):")
            for nick, ago_sec in roster:
                member = demos[nick]
                started = now - timedelta(seconds=ago_sec)
                db.add(
                    PlaySession(
                        member_id=member.id,
                        steam_app_id=app_id,
                        game_name=game_name,
                        started_at=started,
                        last_seen_at=now,
                        ended_at=None,
                        source=DEMO_SOURCE,
                    )
                )
                db.add(
                    PresenceSegment(
                        member_id=member.id,
                        status="playing",
                        steam_app_id=app_id,
                        game_name=game_name,
                        started_at=started,
                        last_seen_at=now,
                        ended_at=None,
                        source=DEMO_SOURCE,
                    )
                )
                created += 1
                print(f"  - {member.nickname}: 已玩 {ago_sec // 60} 分钟 (source=demo)")

        db.commit()
        print()
        print(f"已写入 {created} 条演示进行中会话（source=demo，轮询不会收尾）。")
        print("登录查看:")
        print("  用户名: demo_viewer")
        print(f"  密码:   {DEMO_PASSWORD}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
