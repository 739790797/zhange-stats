"""本地/开发假 Steam 演示数据（不访问 Steam presence API）。

仅供 CLI 灌数（见 local_dev/README.md）；管理端假监控与假轮询已移除。
只伪造用户在线/游玩轨迹；游戏 icon / 商店信息等仍走真实请求链路。
"""


from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote

from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.timeutil import now_naive, to_naive
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.models.register_challenge import RegisterChallenge
from app.models.steam_app import SteamApp
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

FAKE_PASSWORD = "demopass123"
FAKE_JOB_MESSAGE_PREFIX = "假监控"

# 演示账号：username, display_name, steam_id（用户A～用户Z）
FAKE_USERS: list[tuple[str, str, str]] = [
    (
        f"user_{letter.lower()}",
        f"用户{letter}",
        f"76561199000000{idx:03d}",
    )
    for idx, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=1)
]

# 纯假头像色板（无 Steam CDN）
_AVATAR_COLORS = [
    "#5470c6",
    "#91cc75",
    "#fac858",
    "#ee6666",
    "#73c0de",
    "#3ba272",
    "#fc8452",
    "#9a60b4",
    "#ea7ccc",
    "#5b8ff9",
]


def letter_avatar_url(letter: str, *, index: int = 0) -> str:
    """生成字母头像 data URL，如 A / B / C（短于 avatar_url 512 上限）。"""
    ch = (letter or "?").strip()[:1].upper() or "?"
    bg = _AVATAR_COLORS[index % len(_AVATAR_COLORS)]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<circle cx="32" cy="32" r="32" fill="{bg}"/>'
        f'<text x="32" y="43" text-anchor="middle" fill="#fff" '
        f'font-size="36" font-family="sans-serif">{ch}</text></svg>'
    )
    return "data:image/svg+xml," + quote(svg)


def _fake_user_letter(index: int) -> str:
    return chr(ord("A") + index)


# ---------------------------------------------------------------------------
# 热销向游戏池（app_id, 中文名）；图床 URL 自动拼接
# ---------------------------------------------------------------------------
FAKE_GAMES: list[tuple[str, str]] = [
    ("730", "反恐精英 2"),
    ("570", "Dota 2"),
    ("578080", "PUBG"),
    ("1172470", "Apex 英雄"),
    ("1422450", "Deadlock"),
    ("1203220", "永劫无间"),
    ("359550", "彩虹六号：围攻"),
    ("252490", "Rust"),
    ("381210", "黎明杀机"),
    ("1364780", "街霸 6"),
    ("440", "团队要塞 2"),
    ("1938090", "使命召唤"),
    ("1091500", "赛博朋克 2077"),
    ("2358720", "黑神话：悟空"),
    ("1245620", "艾尔登法环"),
    ("1086940", "博德之门 3"),
    ("814380", "只狼：影逝二度"),
    ("292030", "巫师 3：狂猎"),
    ("1174180", "荒野大镖客：救赎 2"),
    ("271590", "侠盗猎车手 V"),
    ("2246340", "怪物猎人：荒野"),
    ("582010", "怪物猎人：世界"),
    ("1817070", "漫威蜘蛛侠：重制版"),
    ("1551360", "极限竞速：地平线 5"),
    ("990080", "霍格沃茨之遗"),
    ("2054970", "龙之信条 2"),
    ("1623730", "幻兽帕鲁"),
    ("413150", "星露谷物语"),
    ("105600", "泰拉瑞亚"),
    ("294100", "环世界"),
    ("427520", "异星工厂"),
    ("526870", "幸福工厂"),
    ("892970", "Valheim"),
    ("1966720", "Lethal Company"),
    ("108600", "僵尸毁灭工程"),
    ("1326470", "森林之子"),
    ("1145350", "哈迪斯 II"),
    ("367520", "空洞骑士"),
    ("646570", "杀戮尖塔"),
    ("524220", "尼尔：自动人形"),
    ("550", "求生之路 2"),
    ("227300", "欧洲卡车模拟 2"),
    ("945360", "Among Us"),
    ("2669320", "Schedule I"),
    ("239140", "消逝的光芒"),
]

_FREE_APP_IDS = frozenset(
    {"570", "730", "440", "578080", "1172470", "1422450", "945360"}
)

# 少量已知 client icon hash；其余留给前端/接口补全
_ICON_HASHES: dict[str, str] = {
    "1091500": "6897c3848f3e0350d512f59d5bae174a1e3739f9",
    "1245620": "b6e290dd5a92ce98f89089a207733c70c41a1871",
    "570": "0bbb630d63262dd66d2fdd0f7d37e8661a410075",
    "730": "8dbc71957312bbd3baea65848b545be9eae2a355",
    "2358720": "764ad8ff458f7020d63a3f7f0abf6ad8882c05df",
    "413150": "35d1377200084a4034238c05b0c8930451e2fb40",
}

_COMPETITIVE = frozenset(
    {
        "730",
        "570",
        "578080",
        "1172470",
        "1422450",
        "1203220",
        "359550",
        "1364780",
        "1938090",
        "381210",
    }
)
_AAA = frozenset(
    {
        "1091500",
        "2358720",
        "1245620",
        "1086940",
        "814380",
        "292030",
        "1174180",
        "271590",
        "2246340",
        "582010",
        "1817070",
        "1551360",
        "990080",
        "2054970",
        "524220",
    }
)
_COZY = frozenset(
    {
        "413150",
        "105600",
        "294100",
        "427520",
        "526870",
        "1623730",
        "1145350",
        "367520",
        "646570",
        "227300",
        "945360",
        "2669320",
    }
)
_SURVIVAL = frozenset(
    {
        "252490",
        "892970",
        "1966720",
        "108600",
        "1326470",
        "239140",
        "550",
        "440",
    }
)



@dataclass(frozen=True)
class _PersonaProfile:
    key: str
    label: str
    # 工作日/周末：可玩窗口 (start_hour, end_hour, play_prob)；hour 可 >24 表示跨午夜
    weekday_windows: tuple[tuple[float, float, float], ...]
    weekend_windows: tuple[tuple[float, float, float], ...]
    weekday_wake: tuple[int, int]
    weekend_wake: tuple[int, int]
    # 下线时刻相对当天 0 点的小时（可 >24，表示熬夜到次日凌晨）
    weekday_sleep: tuple[float, float]
    weekend_sleep: tuple[float, float]
    skip_day_prob: float
    play_minutes: tuple[int, int]
    game_weights: tuple[tuple[frozenset[str], float], ...]


_PERSONAS: dict[str, _PersonaProfile] = {
    "student": _PersonaProfile(
        key="student",
        label="大学生",
        weekday_wake=(9, 11),
        weekend_wake=(10, 13),
        weekday_sleep=(23.2, 27.5),  # 约 23:10～次日 3:30
        weekend_sleep=(24.0, 28.5),  # 约 0:00～4:30
        weekday_windows=(
            (12.0, 13.5, 0.45),
            (15.5, 18.0, 0.55),
            (20.0, 27.0, 0.88),
        ),
        weekend_windows=(
            (11.0, 14.0, 0.55),
            (14.5, 18.5, 0.8),
            (20.0, 28.0, 0.9),
        ),
        skip_day_prob=0.1,
        play_minutes=(35, 150),
        game_weights=(
            (_COMPETITIVE, 0.4),
            (_COZY, 0.25),
            (_AAA, 0.25),
            (_SURVIVAL, 0.1),
        ),
    ),
    "office": _PersonaProfile(
        key="office",
        label="上班族",
        weekday_wake=(7, 8),
        weekend_wake=(8, 10),
        weekday_sleep=(21.8, 24.6),  # 约 21:50～次日 0:35
        weekend_sleep=(22.5, 26.0),  # 约 22:30～2:00
        weekday_windows=(
            (12.2, 13.2, 0.22),
            (19.5, 24.2, 0.82),
        ),
        weekend_windows=(
            (10.0, 12.5, 0.4),
            (14.0, 18.0, 0.55),
            (19.5, 25.5, 0.78),
        ),
        skip_day_prob=0.18,
        play_minutes=(25, 100),
        game_weights=(
            (_AAA, 0.4),
            (_COZY, 0.35),
            (_COMPETITIVE, 0.15),
            (_SURVIVAL, 0.1),
        ),
    ),
    "streamer": _PersonaProfile(
        key="streamer",
        label="游戏主播",
        weekday_wake=(10, 12),
        weekend_wake=(10, 12),
        weekday_sleep=(25.0, 28.8),  # 约 1:00～4:50
        weekend_sleep=(25.5, 29.5),  # 约 1:30～5:30
        weekday_windows=(
            (13.5, 17.5, 0.9),
            (19.0, 28.0, 0.95),
        ),
        weekend_windows=(
            (11.0, 17.5, 0.88),
            (18.5, 29.0, 0.95),
        ),
        skip_day_prob=0.04,
        play_minutes=(50, 180),
        game_weights=(
            (_COMPETITIVE, 0.4),
            (_SURVIVAL, 0.2),
            (_AAA, 0.25),
            (_COZY, 0.15),
        ),
    ),
}


def _now() -> datetime:
    return now_naive()


def _rand_duration(lo: timedelta, hi: timedelta) -> timedelta:
    lo_s = int(lo.total_seconds())
    hi_s = int(hi.total_seconds())
    return timedelta(seconds=random.randint(lo_s, hi_s))


def _stable_duration(key: str, lo: timedelta, hi: timedelta) -> timedelta:
    """同一 session/segment 用稳定时长，避免重启后 until 乱跳。"""
    lo_s = int(lo.total_seconds())
    hi_s = int(hi.total_seconds())
    span = max(1, hi_s - lo_s)
    h = 0
    for ch in key:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return timedelta(seconds=lo_s + (h % (span + 1)))


def _cdn_images(app_id: str) -> tuple[str, str, str | None]:
    base = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}"
    header = f"{base}/header.jpg"
    capsule = f"{base}/capsule_231x87.jpg"
    icon_hash = _ICON_HASHES.get(app_id)
    icon = (
        "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/"
        f"apps/{app_id}/{icon_hash}.jpg"
        if icon_hash
        else None
    )
    return header, capsule, icon


def _game_by_id(app_id: str) -> tuple[str, str]:
    for gid, name in FAKE_GAMES:
        if gid == app_id:
            return gid, name
    return app_id, app_id


def _games_in(pool: frozenset[str]) -> list[tuple[str, str]]:
    return [g for g in FAKE_GAMES if g[0] in pool]


def _pick_game_for_persona(persona: _PersonaProfile, rng: random.Random) -> tuple[str, str]:
    weights = []
    pools: list[list[tuple[str, str]]] = []
    for tag_set, w in persona.game_weights:
        games = _games_in(tag_set)
        if games:
            pools.append(games)
            weights.append(w)
    if not pools:
        return rng.choice(FAKE_GAMES)
    chosen_pool = rng.choices(pools, weights=weights, k=1)[0]
    return rng.choice(chosen_pool)


def _persona_for_index(index: int) -> _PersonaProfile:
    # A–I 大学生，J–R 上班族，S–Z 游戏主播
    if index < 9:
        return _PERSONAS["student"]
    if index < 18:
        return _PERSONAS["office"]
    return _PERSONAS["streamer"]


def _persona_for_member(member: Member) -> _PersonaProfile:
    steam_id = (member.steam_id or "").strip()
    for i, (_, _, sid) in enumerate(FAKE_USERS):
        if sid == steam_id:
            return _persona_for_index(i)
    return _PERSONAS["office"]


def _history_start(now: datetime) -> datetime:
    """上个月 1 日 00:00。"""
    first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if first_this.month == 1:
        return first_this.replace(year=first_this.year - 1, month=12)
    return first_this.replace(month=first_this.month - 1)


def ensure_fake_user(
    db: Session, username: str, display_name: str, steam_id: str, avatar_url: str
) -> Member:
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        user = User(
            username=username,
            email=f"{username}@localhost",
            display_name=display_name,
            password_hash=hash_password(FAKE_PASSWORD),
            email_verified=True,
        )
        user.apply_role(UserRole.user)
        db.add(user)
        db.flush()
    else:
        user.display_name = display_name
        user.email_verified = True

    member = db.query(Member).filter(Member.user_id == user.id).first()
    if member is None:
        member = db.query(Member).filter(Member.steam_id == steam_id).first()
        if member is not None:
            member.user_id = user.id
        else:
            member = Member(
                nickname=display_name,
                user_id=user.id,
                steam_id=steam_id,
                steam_persona_name=display_name,
                avatar_url=avatar_url,
            )
            db.add(member)
            db.flush()

    conflict = (
        db.query(Member)
        .filter(Member.steam_id == steam_id, Member.id != member.id)
        .first()
    )
    if conflict is not None:
        conflict.steam_id = None
        db.flush()
    member.nickname = display_name
    member.steam_id = steam_id
    member.steam_persona_name = display_name
    member.avatar_url = avatar_url
    return member


def ensure_fake_steam_apps(db: Session) -> int:
    now = _now()
    created = 0
    for app_id, name in FAKE_GAMES:
        header, capsule, icon = _cdn_images(app_id)
        row = db.query(SteamApp).filter(SteamApp.app_id == app_id).first()
        if row is None:
            db.add(
                SteamApp(
                    app_id=app_id,
                    name=name,
                    header_image=header,
                    capsule_image=capsule,
                    icon_url=icon,
                    short_description=f"「{name}」本地演示游戏。",
                    is_free=app_id in _FREE_APP_IDS,
                    currency="CNY",
                    fetched_at=now,
                    details_fetched_at=now,
                )
            )
            created += 1
        else:
            row.name = name
            row.header_image = row.header_image or header
            row.capsule_image = row.capsule_image or capsule
            if icon:
                row.icon_url = icon
            if row.details_fetched_at is None:
                row.details_fetched_at = now
    return created


def _add_presence(
    db: Session,
    *,
    member_id: int,
    status: str,
    started: datetime,
    ended: datetime | None,
    last_seen: datetime,
    app_id: str | None = None,
    game_name: str | None = None,
) -> None:
    db.add(
        PresenceSegment(
            member_id=member_id,
            status=status,
            steam_app_id=app_id if status == "playing" else None,
            game_name=game_name if status == "playing" else None,
            started_at=started,
            last_seen_at=last_seen,
            ended_at=ended,
            source="steam",
        )
    )


def _add_span(
    db: Session,
    *,
    member_id: int,
    status: str,
    started: datetime,
    ended: datetime,
    now: datetime,
    leave_open: bool,
    app_id: str | None = None,
    game_name: str | None = None,
) -> int:
    if ended <= started:
        return 0
    is_open = leave_open and ended >= now and started < now
    last_seen = now if is_open else ended
    ended_at = None if is_open else ended
    if status == "playing" and app_id:
        db.add(
            PlaySession(
                member_id=member_id,
                steam_app_id=app_id,
                game_name=game_name,
                started_at=started,
                last_seen_at=last_seen,
                ended_at=ended_at,
                source="steam",
            )
        )
    _add_presence(
        db,
        member_id=member_id,
        status=status,
        started=started,
        ended=ended_at,
        last_seen=last_seen,
        app_id=app_id,
        game_name=game_name,
    )
    return 1


def _jittered_time(day: datetime, hour_lo: float, hour_hi: float, rng: random.Random) -> datetime:
    """在 [hour_lo, hour_hi]（相对 day 0 点，可跨午夜）内随机一个到分钟的时刻。"""
    lo = int(hour_lo * 60)
    hi = int(hour_hi * 60)
    if hi < lo:
        hi = lo
    mins = rng.randint(lo, hi)
    return day + timedelta(minutes=mins)


def _seed_day_for_member(
    db: Session,
    member: Member,
    day: datetime,
    now: datetime,
    persona: _PersonaProfile,
    rng: random.Random,
    *,
    coverage_from: datetime,
    is_last_day: bool,
) -> tuple[int, datetime]:
    """生成「清醒日」轨迹；可跨过自然日午夜。返回 (条数, 已覆盖到的时刻)。"""
    day = day.replace(hour=0, minute=0, second=0, microsecond=0)
    is_weekend = day.weekday() >= 5
    wake_lo, wake_hi = persona.weekend_wake if is_weekend else persona.weekday_wake
    sleep_lo, sleep_hi = (
        persona.weekend_sleep if is_weekend else persona.weekday_sleep
    )
    windows = persona.weekend_windows if is_weekend else persona.weekday_windows

    sleep_at = _jittered_time(day, sleep_lo, sleep_hi, rng)
    day_cap = min(sleep_at, now)
    start_at = coverage_from
    if day_cap <= start_at:
        return 0, coverage_from

    created = 0

    # 摸鱼日：整段离线到各自下线点（不是卡在 24:00）
    if (not is_last_day) and rng.random() < persona.skip_day_prob:
        created += _add_span(
            db,
            member_id=member.id,
            status="offline",
            started=start_at,
            ended=day_cap,
            now=now,
            leave_open=is_last_day and day_cap >= now,
        )
        return created, day_cap

    wake = _jittered_time(day, float(wake_lo), float(wake_hi) + 0.75, rng)
    cursor = start_at
    if wake > start_at:
        if wake >= day_cap:
            created += _add_span(
                db,
                member_id=member.id,
                status="offline",
                started=start_at,
                ended=day_cap,
                now=now,
                leave_open=is_last_day and day_cap >= now,
            )
            return created, day_cap
        created += _add_span(
            db,
            member_id=member.id,
            status="offline",
            started=start_at,
            ended=wake,
            now=now,
            leave_open=False,
        )
        cursor = wake

    for start_h, end_h, play_prob in windows:
        w_start = day + timedelta(hours=start_h)
        w_end = day + timedelta(hours=end_h)
        w_start = max(w_start, cursor)
        w_end = min(w_end, day_cap)
        if w_start >= w_end:
            continue

        if cursor < w_start:
            gap_status = "online" if rng.random() < 0.35 else "offline"
            created += _add_span(
                db,
                member_id=member.id,
                status=gap_status,
                started=cursor,
                ended=w_start,
                now=now,
                leave_open=False,
            )
            cursor = w_start

        sticky_game: tuple[str, str] | None = None
        while cursor < w_end:
            remain_min = int((w_end - cursor).total_seconds() // 60)
            if remain_min < 8:
                break
            near_end = (w_end - cursor) <= timedelta(minutes=25)
            leave_open = is_last_day and near_end and w_end >= now
            if rng.random() < play_prob:
                lo, hi = persona.play_minutes
                dur = timedelta(minutes=rng.randint(lo, min(hi, max(lo, remain_min))))
                ended = min(cursor + dur, w_end)
                if sticky_game and rng.random() < 0.55:
                    app_id, name = sticky_game
                else:
                    app_id, name = _pick_game_for_persona(persona, rng)
                    sticky_game = (app_id, name)
                created += _add_span(
                    db,
                    member_id=member.id,
                    status="playing",
                    started=cursor,
                    ended=ended,
                    now=now,
                    leave_open=leave_open and ended >= now,
                    app_id=app_id,
                    game_name=name,
                )
                cursor = ended
            else:
                sticky_game = None
                dur = timedelta(minutes=rng.randint(8, min(40, remain_min)))
                ended = min(cursor + dur, w_end)
                created += _add_span(
                    db,
                    member_id=member.id,
                    status="online",
                    started=cursor,
                    ended=ended,
                    now=now,
                    leave_open=leave_open and ended >= now,
                )
                cursor = ended

            if cursor < w_end and rng.random() < 0.45:
                gap = timedelta(minutes=rng.randint(5, 28))
                gap_end = min(cursor + gap, w_end)
                if gap_end > cursor:
                    created += _add_span(
                        db,
                        member_id=member.id,
                        status="offline" if rng.random() < 0.55 else "online",
                        started=cursor,
                        ended=gap_end,
                        now=now,
                        leave_open=False,
                    )
                    cursor = gap_end

    if cursor < day_cap:
        # 收尾：先可能短暂在线，再在各自 sleep 点下线（每人时刻不同）
        remain = day_cap - cursor
        if remain > timedelta(minutes=15) and rng.random() < (
            0.4 if persona.key == "streamer" else 0.22
        ):
            wind = min(
                timedelta(minutes=rng.randint(8, 35)),
                remain - timedelta(minutes=3),
            )
            if wind.total_seconds() >= 180:
                created += _add_span(
                    db,
                    member_id=member.id,
                    status="online",
                    started=cursor,
                    ended=cursor + wind,
                    now=now,
                    leave_open=False,
                )
                cursor = cursor + wind
        created += _add_span(
            db,
            member_id=member.id,
            status="offline",
            started=cursor,
            ended=day_cap,
            now=now,
            leave_open=is_last_day and day_cap >= now,
        )
        cursor = day_cap

    return created, max(coverage_from, cursor)


def _seed_history_for_member(
    db: Session,
    member: Member,
    now: datetime,
    *,
    force: bool = False,
) -> int:
    """写入从上月 1 日到今天的作息化历史（可跨午夜，下线时刻分散）。"""
    if not force:
        has_any = (
            db.query(PresenceSegment.id)
            .filter(
                PresenceSegment.member_id == member.id,
                PresenceSegment.source == "steam",
            )
            .limit(1)
            .first()
        )
        if has_any is not None:
            return 0

    persona = _persona_for_member(member)
    rng = random.Random(f"{member.id}:{persona.key}:{now.date().isoformat()}:v2")
    start = _history_start(now)
    created = 0
    day = start
    last_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    coverage = start
    while day <= last_day:
        n, coverage = _seed_day_for_member(
            db,
            member,
            day,
            now,
            persona,
            rng,
            coverage_from=coverage,
            is_last_day=(day.date() == last_day.date()),
        )
        created += n
        day += timedelta(days=1)

    return created


def wipe_steam_records(
    db: Session, *, member_ids: list[int] | None = None
) -> dict[str, int]:
    """清空游玩 / 在线离线记录（默认全部；可限定成员）。"""
    pq = db.query(PlaySession)
    sq = db.query(PresenceSegment)
    if member_ids is not None:
        if not member_ids:
            return {"play_sessions": 0, "presence_segments": 0}
        pq = pq.filter(PlaySession.member_id.in_(member_ids))
        sq = sq.filter(PresenceSegment.member_id.in_(member_ids))
    deleted = {
        "play_sessions": pq.delete(synchronize_session=False),
        "presence_segments": sq.delete(synchronize_session=False),
    }
    db.commit()
    return deleted


def wipe_non_admin_users(db: Session) -> dict[str, int]:
    """删除除 admin 外的全部用户及其成员 / 会话 / 好友边；保留 steam_apps 等。"""
    settings = get_settings()
    keep_users = (
        db.query(User)
        .filter(
            (User.username == settings.ADMIN_USERNAME)
            | (User.role == UserRole.admin)
        )
        .all()
    )
    keep_ids = {u.id for u in keep_users}
    keep_member_ids: set[int] = set()
    if keep_ids:
        keep_member_ids = {
            m.id
            for m in db.query(Member).filter(Member.user_id.in_(keep_ids)).all()
        }

    if keep_member_ids:
        drop_members = (
            db.query(Member).filter(~Member.id.in_(keep_member_ids)).all()
        )
    else:
        drop_members = db.query(Member).all()
    drop_member_ids = [m.id for m in drop_members]

    deleted = {
        "play_sessions": 0,
        "presence_segments": 0,
        "members": 0,
        "users": 0,
        "register_challenges": 0,
    }

    if drop_member_ids:
        deleted["play_sessions"] = (
            db.query(PlaySession)
            .filter(PlaySession.member_id.in_(drop_member_ids))
            .delete(synchronize_session=False)
        )
        deleted["presence_segments"] = (
            db.query(PresenceSegment)
            .filter(PresenceSegment.member_id.in_(drop_member_ids))
            .delete(synchronize_session=False)
        )
        deleted["members"] = (
            db.query(Member)
            .filter(Member.id.in_(drop_member_ids))
            .delete(synchronize_session=False)
        )

    if keep_ids:
        deleted["users"] = (
            db.query(User)
            .filter(~User.id.in_(keep_ids))
            .delete(synchronize_session=False)
        )
    else:
        deleted["users"] = db.query(User).delete(synchronize_session=False)
    deleted["register_challenges"] = db.query(RegisterChallenge).delete(
        synchronize_session=False
    )

    db.commit()
    return deleted


def wipe_fake_users(db: Session) -> dict[str, int]:
    """仅删除 FAKE_USERS（user_a～user_z）及其 Steam 历史；不影响真实用户。"""
    usernames = [u[0] for u in FAKE_USERS]
    steam_ids = {u[2] for u in FAKE_USERS}

    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_ids = [u.id for u in users]

    member_q = db.query(Member)
    if user_ids:
        members = member_q.filter(
            (Member.user_id.in_(user_ids)) | (Member.steam_id.in_(steam_ids))
        ).all()
    else:
        members = member_q.filter(Member.steam_id.in_(steam_ids)).all()
    member_ids = [m.id for m in members]

    deleted = {
        "users": 0,
        "members": 0,
        "play_sessions": 0,
        "presence_segments": 0,
        "job_runs": 0,
    }

    if member_ids:
        deleted["play_sessions"] = (
            db.query(PlaySession)
            .filter(PlaySession.member_id.in_(member_ids))
            .delete(synchronize_session=False)
        )
        deleted["presence_segments"] = (
            db.query(PresenceSegment)
            .filter(PresenceSegment.member_id.in_(member_ids))
            .delete(synchronize_session=False)
        )
        deleted["members"] = (
            db.query(Member)
            .filter(Member.id.in_(member_ids))
            .delete(synchronize_session=False)
        )

    if user_ids:
        deleted["users"] = (
            db.query(User)
            .filter(User.id.in_(user_ids))
            .delete(synchronize_session=False)
        )

    deleted["job_runs"] = (
        db.query(JobRun)
        .filter(JobRun.message.like(f"{FAKE_JOB_MESSAGE_PREFIX}%"))
        .delete(synchronize_session=False)
    )

    db.commit()
    return deleted


def _sync_fake_user_avatars(db: Session) -> int:
    """把演示账号头像刷成字母假图（覆盖旧 Steam CDN）。"""
    n = 0
    for i, (username, display_name, steam_id) in enumerate(FAKE_USERS):
        avatar = letter_avatar_url(_fake_user_letter(i), index=i)
        ensure_fake_user(db, username, display_name, steam_id, avatar)
        n += 1
    return n


def _demo_members(db: Session) -> list[Member]:
    demo_ids = {u[2] for u in FAKE_USERS}
    return (
        db.query(Member)
        .filter(Member.steam_id.in_(demo_ids))
        .order_by(Member.id.asc())
        .all()
    )


def regenerate_fake_history(db: Session) -> dict[str, int]:
    """清空演示账号的游戏/在线记录，并按作息重生成（上月1日～今天）。"""
    apps = ensure_fake_steam_apps(db)
    _sync_fake_user_avatars(db)
    db.flush()
    members = _demo_members(db)
    if not members:
        # 尚无演示账号则完整补齐
        stats = ensure_local_fake_data(db, force_history=True)
        return {
            "steam_apps": apps,
            "members": int(stats.get("users", 0)),
            "wiped_play": 0,
            "wiped_presence": 0,
            "history_sessions": int(stats.get("history_sessions", 0)),
        }

    wiped = wipe_steam_records(db, member_ids=[m.id for m in members])
    now = _now()
    history = 0
    for m in members:
        history += _seed_history_for_member(db, m, now, force=True)
    db.commit()
    return {
        "steam_apps": apps,
        "members": len(members),
        "wiped_play": wiped["play_sessions"],
        "wiped_presence": wiped["presence_segments"],
        "history_sessions": history,
        "from": _history_start(now).date().isoformat(),
        "to": now.date().isoformat(),
        "personas": {
            "student": "用户A–I",
            "office": "用户J–R",
            "streamer": "用户S–Z",
        },
    }


def ensure_local_fake_data(
    db: Session, *, force_history: bool = False
) -> dict[str, int]:
    """幂等补齐本地演示数据。可被启动 lifespan / 脚本调用。"""
    now = _now()
    apps = ensure_fake_steam_apps(db)
    existing = (
        db.query(User.username)
        .filter(User.username.in_([u[0] for u in FAKE_USERS]))
        .count()
    )
    if existing >= len(FAKE_USERS) and not force_history:
        _sync_fake_user_avatars(db)
        db.commit()
        return {
            "users": existing,
            "steam_apps": apps,
            "history_sessions": 0,
            "skipped": 1,
        }

    members: list[Member] = []
    for i, (username, display_name, steam_id) in enumerate(FAKE_USERS):
        members.append(
            ensure_fake_user(
                db,
                username,
                display_name,
                steam_id,
                letter_avatar_url(_fake_user_letter(i), index=i),
            )
        )
    db.flush()

    apps = ensure_fake_steam_apps(db)
    if force_history:
        wipe_steam_records(db, member_ids=[m.id for m in members])

    history = 0
    for m in members:
        history += _seed_history_for_member(
            db, m, now, force=force_history
        )

    db.commit()
    return {
        "users": len(members),
        "steam_apps": apps,
        "history_sessions": history,
    }
