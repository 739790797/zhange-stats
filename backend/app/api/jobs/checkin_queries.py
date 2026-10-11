from __future__ import annotations

from datetime import datetime
from typing import Any, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from app.api.jobs.catalog import JOB_CATALOG, CHECKIN_PLATFORM_ORDER, _CHECKIN_PLATFORMS
from app.api.jobs.helpers import (
    _bind_model,
    _checkin_log_model,
    _fmt_dt,
    _member_label,
)
from app.api.jobs.schemas import (
    CheckinLogItemOut,
    CheckinLogsPageOut,
    JobMemberOptionOut,
    UserCheckinTaskOut,
    UserCheckinTasksPageOut,
)
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.timeutil import BEIJING
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member
from app.models.user import User
from app.schemas.checkin import CheckinAwardItem
from app.services.checkin.common import (
    LOG_SOURCE_ACTION,
    display_checkin_awards_summary,
    loads_awards_json,
    status_label,
)
from app.services.platform_features import CHECKIN_PLATFORM_FEATURES, PLATFORM_SHORT_NAMES, is_feature_enabled

router = APIRouter()

# 各平台「社区」签到 game_code：用户任务树内排最前
_COMMUNITY_GAME_CODES = frozenset({"app", "kujiequ", "exilium_bbs", "mihoyo"})


def _game_code_sort_key(game_code: str | None) -> tuple[int, str]:
    code = str(game_code or "")
    if code in _COMMUNITY_GAME_CODES:
        return (0, code)
    return (1, code)

@router.get("/jobs/checkin-logs", response_model=CheckinLogsPageOut)
def list_checkin_logs(
    platform: str | None = Query(default=None),
    member_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> CheckinLogsPageOut:
    """按平台 / 用户查询签到明细（checkin_logs）。"""
    return query_checkin_logs(
        db,
        platform=platform,
        member_id=member_id,
        page=page,
        page_size=page_size,
    )


@router.get("/jobs/members", response_model=list[JobMemberOptionOut])
def list_job_filter_members(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[JobMemberOptionOut]:
    """供任务调度页「按用户」下拉：仅含任一签到平台已绑定的成员。"""
    bound_ids: set[int] = set()
    for p in sorted(_CHECKIN_PLATFORMS):
        model = _bind_model(p)
        if model is None:
            continue
        bound_ids.update(
            mid for (mid,) in db.query(model.member_id).all() if mid is not None
        )
    if not bound_ids:
        return []

    members = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id.in_(bound_ids))
        .order_by(Member.id.asc())
        .all()
    )
    out: list[JobMemberOptionOut] = []
    for m in members:
        user = m.user
        out.append(
            JobMemberOptionOut(
                member_id=m.id,
                user_id=user.id if user else None,
                label=_member_label(m),
            )
        )
    return out


@router.get("/jobs/user-tasks", response_model=UserCheckinTasksPageOut)
def list_user_checkin_tasks(
    platform: str | None = Query(default=None),
    member_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserCheckinTasksPageOut:
    """列出所有「用户 × 已绑定平台」签到任务（含用户自设时间）。"""
    return query_user_checkin_tasks(
        db,
        platform=platform,
        member_id=member_id,
        page=page,
        page_size=page_size,
    )


def query_user_checkin_tasks(
    db: Session,
    *,
    platform: str | None = None,
    member_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> UserCheckinTasksPageOut:
    """按平台 / 成员列出角色级日常任务（无角色偏好时回退整平台一行）。"""
    if platform and platform not in _CHECKIN_PLATFORMS:
        raise HTTPException(status_code=400, detail="不支持的平台")

    job_by_platform = {
        str(m["platform"]): str(m["id"])
        for m in JOB_CATALOG
        if m.get("kind") == "user_schedule" and m.get("platform")
    }
    platforms = [platform] if platform else list(CHECKIN_PLATFORM_ORDER)
    platforms = [
        p
        for p in platforms
        if p in _CHECKIN_PLATFORMS
        and p in job_by_platform
        and _bind_model(p) is not None
        and is_feature_enabled(db, p)
        and is_feature_enabled(db, CHECKIN_PLATFORM_FEATURES.get(p, p))
    ]
    platform_rank = {p: i for i, p in enumerate(CHECKIN_PLATFORM_ORDER)}

    # 任务页 30 秒轮询、逐页拉全量：成员与日志只给当页查，不要先拼完整列表再切片
    tasks = _task_rows(db, platforms, member_id=member_id)
    tasks.sort(
        key=lambda t: (
            platform_rank.get(t.platform, 99),
            t.member_id,
            _game_code_sort_key(t.game_code),
            t.role_uid or "",
            t.checkin_hour,
            t.checkin_minute,
        )
    )
    start = (page - 1) * page_size
    page_tasks = tasks[start : start + page_size]

    member_ids = {t.member_id for t in page_tasks}
    members = {
        m.id: m
        for m in db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id.in_(member_ids))
        .all()
    } if member_ids else {}
    last_meta: dict[str, dict[int, dict[tuple[str, str], dict[str, Any]]]] = {}
    today_meta: dict[str, dict[int, dict[tuple[str, str], dict[str, Any]]]] = {}
    for p in {t.platform for t in page_tasks}:
        log_model = _checkin_log_model(p)
        page_member_ids = sorted({t.member_id for t in page_tasks if t.platform == p})
        last_meta[p] = _role_log_meta(db, log_model, member_ids=page_member_ids)
        today_meta[p] = _role_today_status_meta(db, log_model, member_ids=page_member_ids)

    items: list[UserCheckinTaskOut] = []
    for t in page_tasks:
        member = members.get(t.member_id)
        user_label = _member_label(member) if member else f"member#{t.member_id}"
        job_id = job_by_platform[t.platform]
        log_meta = last_meta[t.platform].get(t.member_id, {})
        if t.game_code is not None:
            key = (t.game_code, t.role_uid or "")
            meta = log_meta.get(key) or {}
            tmeta = today_meta[t.platform].get(t.member_id, {}).get(key) or {}
            game_name = str(
                tmeta.get("game_name")
                or meta.get("game_name")
                or t.game_code
            )
            role_name = str(
                tmeta.get("role_name")
                or meta.get("role_name")
                or t.role_uid
                or t.game_code
            )
            items.append(
                UserCheckinTaskOut(
                    task_key=f"{t.platform}:{t.member_id}:{t.game_code}:{t.role_uid}",
                    job_id=job_id,
                    platform=t.platform,
                    platform_name=PLATFORM_SHORT_NAMES.get(t.platform, t.platform),
                    member_id=t.member_id,
                    user_label=user_label,
                    included=t.included,
                    auto_checkin=t.auto_checkin,
                    checkin_hour=t.checkin_hour,
                    checkin_minute=t.checkin_minute,
                    game_code=t.game_code,
                    game_name=game_name,
                    role_uid=t.role_uid,
                    role_name=role_name,
                    channel_name=tmeta.get("channel_name")
                    or meta.get("channel_name"),
                    today_status=tmeta.get("status"),
                    today_status_label=tmeta.get("status_label"),
                    today_awards_text=tmeta.get("awards_text"),
                    today_awards=[
                        CheckinAwardItem(**a)
                        for a in (tmeta.get("awards") or [])
                        if isinstance(a, dict) and a.get("name")
                    ],
                    last_checkin_at=_fmt_dt(meta.get("checked_at")),
                    last_checkin_date=(
                        meta["checkin_date"].isoformat()
                        if meta.get("checkin_date") is not None
                        else None
                    ),
                    bound_at=_fmt_dt(t.bound_at),
                )
            )
            continue
        # 尚未写出角色偏好：时间仍用 bind 种子；上次执行只信 logs
        latest_meta: dict[str, Any] = {}
        for meta in log_meta.values():
            checked = meta.get("checked_at")
            if checked is None:
                continue
            prev = latest_meta.get("checked_at")
            if prev is None or checked > prev:
                latest_meta = meta
        items.append(
            UserCheckinTaskOut(
                task_key=f"{t.platform}:{t.member_id}",
                job_id=job_id,
                platform=t.platform,
                platform_name=PLATFORM_SHORT_NAMES.get(t.platform, t.platform),
                member_id=t.member_id,
                user_label=user_label,
                included=True,
                auto_checkin=t.auto_checkin,
                checkin_hour=t.checkin_hour,
                checkin_minute=t.checkin_minute,
                last_checkin_at=_fmt_dt(latest_meta.get("checked_at")),
                last_checkin_date=(
                    latest_meta["checkin_date"].isoformat()
                    if latest_meta.get("checkin_date") is not None
                    else None
                ),
                bound_at=_fmt_dt(t.bound_at),
            )
        )

    return UserCheckinTasksPageOut(
        total=len(tasks),
        page=page,
        page_size=page_size,
        items=items,
    )


class _TaskRow(NamedTuple):
    platform: str
    member_id: int
    game_code: str | None
    role_uid: str | None
    included: bool
    auto_checkin: bool
    checkin_hour: int
    checkin_minute: int
    bound_at: datetime | None


def _task_rows(
    db: Session, platforms: list[str], *, member_id: int | None
) -> list[_TaskRow]:
    """有角色偏好的每个角色一行；尚未写出偏好的整平台一行（时间用 bind 种子）。"""
    if not platforms:
        return []
    pref_q = db.query(
        CheckinRolePref.platform,
        CheckinRolePref.member_id,
        CheckinRolePref.game_code,
        CheckinRolePref.role_uid,
        CheckinRolePref.included,
        CheckinRolePref.enabled,
        CheckinRolePref.checkin_hour,
        CheckinRolePref.checkin_minute,
    ).filter(CheckinRolePref.platform.in_(platforms))
    if member_id is not None:
        pref_q = pref_q.filter(CheckinRolePref.member_id == int(member_id))
    prefs_by_bind: dict[tuple[str, int], list[Any]] = {}
    for pref in pref_q.all():
        prefs_by_bind.setdefault((pref.platform, int(pref.member_id)), []).append(pref)

    rows: list[_TaskRow] = []
    for p in platforms:
        model = _bind_model(p)
        q = db.query(
            model.member_id,
            model.auto_checkin,
            model.checkin_hour,
            model.checkin_minute,
            model.bound_at,
        )
        if member_id is not None:
            q = q.filter(model.member_id == int(member_id))
        for bind in q.all():
            mid = int(bind.member_id)
            prefs = prefs_by_bind.get((p, mid))
            if not prefs:
                rows.append(
                    _TaskRow(
                        platform=p,
                        member_id=mid,
                        game_code=None,
                        role_uid=None,
                        included=True,
                        auto_checkin=bool(bind.auto_checkin),
                        checkin_hour=int(bind.checkin_hour),
                        checkin_minute=int(bind.checkin_minute),
                        bound_at=bind.bound_at,
                    )
                )
                continue
            for pref in prefs:
                rows.append(
                    _TaskRow(
                        platform=p,
                        member_id=mid,
                        game_code=str(pref.game_code),
                        role_uid=str(pref.role_uid),
                        included=bool(pref.included),
                        auto_checkin=bool(pref.enabled) and bool(pref.included),
                        checkin_hour=int(pref.checkin_hour or 0),
                        checkin_minute=int(pref.checkin_minute or 0),
                        bound_at=bind.bound_at,
                    )
                )
    return rows


def _action_only_filter(log_model: Any):
    """执行记录 / 上次执行只认 source=action。"""
    if hasattr(log_model, "source"):
        return log_model.source == LOG_SOURCE_ACTION
    return True


def _role_log_meta(
    db: Session,
    log_model: Any | None,
    *,
    member_ids: list[int],
) -> dict[int, dict[tuple[str, str], dict[str, Any]]]:
    """member_id → 每个角色最近一条「真正执行」签到日志的展示元数据。"""
    if log_model is None or not member_ids:
        return {}
    q = db.query(
        log_model.member_id,
        log_model.game_code,
        log_model.role_uid,
        func.max(log_model.checkin_date).label("day"),
    ).filter(log_model.member_id.in_(member_ids))
    if hasattr(log_model, "source"):
        q = q.filter(_action_only_filter(log_model))
    # logs 按角色+日唯一：最近一天那行就是该角色最近一次执行
    latest = q.group_by(
        log_model.member_id, log_model.game_code, log_model.role_uid
    ).subquery()
    rows = (
        db.query(
            log_model.member_id,
            log_model.game_code,
            log_model.role_uid,
            log_model.game_name,
            log_model.role_name,
            log_model.channel_name,
            log_model.checked_at,
            log_model.checkin_date,
        )
        .join(
            latest,
            and_(
                log_model.member_id == latest.c.member_id,
                log_model.game_code == latest.c.game_code,
                log_model.role_uid == latest.c.role_uid,
                log_model.checkin_date == latest.c.day,
            ),
        )
        .all()
    )
    out: dict[int, dict[tuple[str, str], dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.game_code or ""), str(row.role_uid or ""))
        if not key[0] or not key[1]:
            continue
        out.setdefault(int(row.member_id), {})[key] = {
            "game_name": row.game_name,
            "role_name": row.role_name,
            "checked_at": row.checked_at,
            "checkin_date": row.checkin_date,
            "channel_name": str(row.channel_name or "").strip() or None,
        }
    return out


def _role_today_status_meta(
    db: Session,
    log_model: Any | None,
    *,
    member_ids: list[int],
) -> dict[int, dict[tuple[str, str], dict[str, Any]]]:
    """member_id → 今日签到状态（查询或执行写入的今日 logs，与是否执行无关）。"""
    from app.core.timeutil import today

    if log_model is None or not member_ids:
        return {}
    rows = (
        db.query(log_model)
        .filter(
            log_model.member_id.in_(member_ids),
            log_model.checkin_date == today(),
        )
        .all()
    )
    out: dict[int, dict[tuple[str, str], dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.game_code or ""), str(row.role_uid or ""))
        if not key[0] or not key[1]:
            continue
        out.setdefault(int(row.member_id), {})[key] = {
            "status": str(row.status or ""),
            "status_label": status_label(row.status),
            "awards_text": display_checkin_awards_summary(
                awards_text=row.awards_text,
                message=row.message,
                status=str(row.status or ""),
                channel_name=getattr(row, "channel_name", None),
                game_code=str(row.game_code or ""),
            ),
            "awards": loads_awards_json(getattr(row, "awards_json", None)) or [],
            "game_name": row.game_name,
            "role_name": row.role_name,
            "channel_name": str(getattr(row, "channel_name", None) or "").strip()
            or None,
        }
    return out


def attach_last_checkin_to_result_dicts(
    db: Session,
    *,
    platform: str,
    member_id: int,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """把任务页同源的上次执行字段挂到 status today_results。"""
    if not results:
        return results
    meta = _role_log_meta(
        db, _checkin_log_model(platform), member_ids=[int(member_id)]
    ).get(int(member_id), {})
    out: list[dict[str, Any]] = []
    for r in results:
        item = dict(r)
        key = (str(item.get("game_code") or ""), str(item.get("role_uid") or ""))
        m = meta.get(key) or {}
        item["last_checkin_at"] = _fmt_dt(m.get("checked_at"))
        item["last_checkin_date"] = (
            m["checkin_date"].isoformat()
            if m.get("checkin_date") is not None
            else None
        )
        out.append(item)
    return out


def query_checkin_logs(
    db: Session,
    *,
    platform: str | None = None,
    member_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CheckinLogsPageOut:
    """按平台 / 成员查询签到明细（供管理端与「我的日常」复用）。"""
    if platform and platform not in _CHECKIN_PLATFORMS:
        raise HTTPException(status_code=400, detail="不支持的平台")

    platforms = [platform] if platform else sorted(_CHECKIN_PLATFORMS)

    page_rows: list[tuple[str, Any]]
    total: int

    if len(platforms) == 1:
        p = platforms[0]
        model = _checkin_log_model(p)
        if model is None:
            return CheckinLogsPageOut(total=0, page=page, page_size=page_size, items=[])
        q = db.query(model)
        if member_id is not None:
            q = q.filter(model.member_id == int(member_id))
        if hasattr(model, "source"):
            q = q.filter(model.source == LOG_SOURCE_ACTION)
        total = int(q.count() or 0)
        rows = (
            q.order_by(desc(model.checked_at), desc(model.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        page_rows = [(p, row) for row in rows]
    else:
        total = 0
        merged: list[tuple[str, Any]] = []
        fetch_n = page * page_size
        for p in platforms:
            model = _checkin_log_model(p)
            if model is None:
                continue
            q = db.query(model)
            if member_id is not None:
                q = q.filter(model.member_id == int(member_id))
            if hasattr(model, "source"):
                q = q.filter(model.source == LOG_SOURCE_ACTION)
            total += int(q.count() or 0)
            for row in q.order_by(desc(model.checked_at), desc(model.id)).limit(
                fetch_n
            ).all():
                merged.append((p, row))
        merged.sort(
            key=lambda pair: (
                pair[1].checked_at or datetime.min.replace(tzinfo=BEIJING),
                pair[1].id,
            ),
            reverse=True,
        )
        start = (page - 1) * page_size
        page_rows = merged[start : start + page_size]

    member_ids = {r.member_id for _, r in page_rows}
    members = {
        m.id: m
        for m in db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id.in_(member_ids))
        .all()
    } if member_ids else {}

    items = []
    for p, row in page_rows:
        member = members.get(row.member_id)
        raw_awards = loads_awards_json(getattr(row, "awards_json", None)) or []
        awards = [
            CheckinAwardItem(**a) if isinstance(a, dict) else a for a in raw_awards
        ]
        # 过滤非法条目：CheckinAwardItem 需要 name
        awards = [a for a in awards if getattr(a, "name", None)]
        awards_display = display_checkin_awards_summary(
            awards_text=row.awards_text,
            message=row.message,
            status=str(row.status or ""),
            channel_name=getattr(row, "channel_name", None),
            game_code=str(row.game_code or ""),
        )
        items.append(
            CheckinLogItemOut(
                id=row.id,
                platform=p,
                member_id=row.member_id,
                user_label=_member_label(member) if member else None,
                game_code=row.game_code,
                game_name=row.game_name,
                role_uid=row.role_uid,
                role_name=row.role_name,
                status=row.status,
                status_label=status_label(row.status),
                message=row.message,
                awards_text=awards_display,
                awards=awards,
                checkin_date=row.checkin_date.isoformat()
                if row.checkin_date
                else "",
                checked_at=_fmt_dt(row.checked_at),
            )
        )
    return CheckinLogsPageOut(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )
