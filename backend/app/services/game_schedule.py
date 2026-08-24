"""代理 [game-schedule](https://github.com/jacket-sikaha/game-schedule) 活动日历。

上游：`GAME_SCHEDULE_BASE_URL` 的 `/ak`、`/endfield`。
落库 `game_schedule_raws`（按游戏一份）；默认读库，force / 定时任务回源；失败不覆盖已有 raw。
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import BEIJING, ensure, now as beijing_now, now_naive
from app.models.game_schedule import GameScheduleRaw

logger = logging.getLogger(__name__)

GameCode = Literal["arknights", "endfield"]

SCHEDULE_JOB_KEYS: dict[GameCode, str] = {
    "arknights": "game_schedule_arknights_sync",
    "endfield": "game_schedule_endfield_sync",
}

# 方舟公告子项常见「一、」「十一、」编号前缀
_TITLE_ORDINAL_RE = re.compile(
    r"^[一二三四五六七八九十百千零〇两\d]+[、.．]\s*"
)

_PATH_BY_GAME: dict[GameCode, str] = {
    "arknights": "/ak",
    "endfield": "/endfield",
}

_HTTP_TIMEOUT = 25
# 跨度超过此天数视为常驻/占位结束时间，不进日历时间轴
_PERMANENT_SPAN_DAYS = 180

_GAME_FEATURES: dict[GameCode, str] = {
    "arknights": "skland.arknights",
    "endfield": "skland.endfield",
}


class GameScheduleError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _parse_schedule_time(value: Any) -> datetime | None:
    """解析上游 `YYYY-MM-DD HH:mm`（按北京墙钟）。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=BEIJING)
        except ValueError:
            continue
    return None


def _strip_title_ordinal(title: str) -> str:
    """去掉标题开头的「一、」「十一、」等枚举编号。"""
    return _TITLE_ORDINAL_RE.sub("", title).strip() or title


def _normalize_event(raw: dict[str, Any], *, game: GameCode) -> dict[str, Any] | None:
    title = _strip_title_ordinal(str(raw.get("title") or "").strip())
    if not title:
        return None
    start_raw = raw.get("start_time")
    end_raw = raw.get("end_time")
    start_dt = _parse_schedule_time(start_raw)
    end_dt = _parse_schedule_time(end_raw)
    event_type = raw.get("type") or raw.get("category")
    banner = raw.get("banner") or raw.get("img")
    link = raw.get("linkUrl") or raw.get("link_url") or raw.get("url")
    return {
        "id": str(raw.get("id") or f"{game}:{title}:{start_raw}"),
        "game": game,
        "title": title,
        "start_time": (
            start_dt.strftime("%Y-%m-%d %H:%M") if start_dt else str(start_raw or "")
        ),
        "end_time": (
            end_dt.strftime("%Y-%m-%d %H:%M") if end_dt else str(end_raw or "")
        ),
        "banner": str(banner).strip() if banner else None,
        "link_url": str(link).strip() if link else None,
        "event_type": str(event_type).strip() if event_type else None,
    }


def _classify(
    event: dict[str, Any], *, at: datetime
) -> Literal["ongoing", "upcoming", "ended"]:
    start = _parse_schedule_time(event.get("start_time"))
    end = _parse_schedule_time(event.get("end_time"))
    if start is None and end is None:
        return "ongoing"
    if end is not None and end < at:
        return "ended"
    if start is not None and start > at:
        return "upcoming"
    return "ongoing"


def _is_permanent_event(event: dict[str, Any]) -> bool:
    """跨度过长（如结束年到 2031）的常驻/新手活动，不适合日历时间轴。"""
    start = _parse_schedule_time(event.get("start_time"))
    end = _parse_schedule_time(event.get("end_time"))
    if start is None or end is None:
        return False
    return (end - start).days >= _PERMANENT_SPAN_DAYS


def get_game_schedule_raw(db: Session, game: GameCode) -> GameScheduleRaw | None:
    return (
        db.query(GameScheduleRaw)
        .filter(GameScheduleRaw.game == game)
        .one_or_none()
    )


def _download_upstream_payload(game: GameCode) -> tuple[dict[str, Any], str]:
    settings = get_settings()
    base = (settings.GAME_SCHEDULE_BASE_URL or "").rstrip("/")
    if not base:
        raise GameScheduleError("未配置活动日历上游地址")
    path = _PATH_BY_GAME[game]
    url = f"{base}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "zhange-stats/game-schedule-proxy",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise GameScheduleError(f"活动日历上游 HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise GameScheduleError(f"活动日历上游不可达：{exc.reason}") from exc
    except TimeoutError as exc:
        raise GameScheduleError("活动日历上游超时") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise GameScheduleError("活动日历上游返回非 JSON") from exc

    if not isinstance(payload, dict):
        raise GameScheduleError("活动日历上游响应格式异常")
    if payload.get("code") not in (0, 200, None):
        raise GameScheduleError(
            str(payload.get("message") or payload.get("msg") or "活动日历上游失败")
        )
    data = payload.get("data")
    if not isinstance(data, list):
        raise GameScheduleError("活动日历上游无 data 列表")
    return payload, base


def _parse_events_from_payload(payload: dict[str, Any], game: GameCode) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise GameScheduleError("活动日历 raw 无 data 列表")
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_event(item, game=game)
        if normalized:
            out.append(normalized)
    return out


def _parse_events_from_raw(row: GameScheduleRaw, game: GameCode) -> list[dict[str, Any]]:
    try:
        payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise GameScheduleError("活动日历 raw_json 无效") from exc
    if not isinstance(payload, dict):
        raise GameScheduleError("活动日历 raw_json 格式无效")
    return _parse_events_from_payload(payload, game)


def _upsert_game_schedule_raw(
    db: Session,
    *,
    game: GameCode,
    payload: dict[str, Any],
    upstream_base: str,
    synced_at: datetime,
) -> None:
    raw_json = json.dumps(payload, ensure_ascii=False)
    row = get_game_schedule_raw(db, game)
    if row is None:
        db.add(
            GameScheduleRaw(
                game=game,
                source="game-schedule",
                upstream_base=upstream_base,
                raw_json=raw_json,
                synced_at=synced_at,
            )
        )
    else:
        row.source = "game-schedule"
        row.upstream_base = upstream_base
        row.raw_json = raw_json
        row.synced_at = synced_at


def sync_game_schedule(db: Session, game: GameCode) -> dict[str, Any]:
    """回源并落库；失败不覆盖已有成功 raw。"""
    payload, upstream_base = _download_upstream_payload(game)
    events = _parse_events_from_payload(payload, game)
    now = now_naive()
    _upsert_game_schedule_raw(
        db,
        game=game,
        payload=payload,
        upstream_base=upstream_base,
        synced_at=now,
    )
    db.commit()
    logger.info("game_schedule synced game=%s count=%s", game, len(events))
    return {
        "game": game,
        "count": len(events),
        "synced_at": now.isoformat(),
    }


def _format_synced_at(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return ensure(dt).strftime("%Y-%m-%d %H:%M:%S")


def _build_calendar(
    events: list[dict[str, Any]],
    *,
    game: GameCode,
    include_ended: bool,
    synced_at: str | None,
    stale: bool,
) -> dict[str, Any]:
    at = beijing_now()
    ongoing: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    ended: list[dict[str, Any]] = []
    permanent: list[dict[str, Any]] = []
    for raw in events:
        item = dict(raw)
        if _is_permanent_event(item):
            status = _classify(item, at=at)
            item["status"] = status
            if status != "ended" or include_ended:
                permanent.append(item)
            continue
        status = _classify(item, at=at)
        item["status"] = status
        if status == "ongoing":
            ongoing.append(item)
        elif status == "upcoming":
            upcoming.append(item)
        else:
            ended.append(item)

    def _sort_key(e: dict[str, Any]) -> tuple[str, str]:
        return (str(e.get("start_time") or ""), str(e.get("id") or ""))

    ongoing.sort(key=_sort_key)
    upcoming.sort(key=_sort_key)
    ended.sort(key=_sort_key, reverse=True)
    permanent.sort(key=_sort_key)

    result_events = ongoing + upcoming
    if include_ended:
        result_events = result_events + ended[:20]

    return {
        "game": game,
        "source": "game-schedule",
        "synced_at": synced_at,
        "stale": stale,
        "events": result_events,
        "permanent_events": permanent,
        "ongoing_count": len(ongoing),
        "upcoming_count": len(upcoming),
        "permanent_count": len(permanent),
    }


def get_game_events(
    db: Session,
    game: GameCode,
    *,
    force: bool = False,
    include_ended: bool = False,
) -> dict[str, Any]:
    """读库优先；force 或库无记录时回源；回源失败则降级旧 raw。"""
    stale = False
    row = get_game_schedule_raw(db, game)

    if force or row is None:
        try:
            sync_game_schedule(db, game)
            row = get_game_schedule_raw(db, game)
        except GameScheduleError as exc:
            if row is None:
                raise
            stale = True
            logger.warning(
                "game_schedule refresh failed game=%s, using stale raw: %s",
                game,
                exc.message,
            )

    if row is None:
        raise GameScheduleError("活动日历无缓存且回源失败")

    events = _parse_events_from_raw(row, game)
    synced_at = _format_synced_at(row.synced_at)
    return _build_calendar(
        events,
        game=game,
        include_ended=include_ended,
        synced_at=synced_at,
        stale=stale,
    )


def _game_schedule_sync_job(game: GameCode) -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    job_key = SCHEDULE_JOB_KEYS[game]
    db = SessionLocal()
    job = JobRun(job_key=job_key, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_game_schedule(db, game)
        job.status = "ok"
        job.message = json.dumps(result, ensure_ascii=False)
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("game_schedule sync job failed game=%s", game)
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()


def game_schedule_arknights_sync_job_wrapper() -> None:
    _game_schedule_sync_job("arknights")


def game_schedule_endfield_sync_job_wrapper() -> None:
    _game_schedule_sync_job("endfield")
