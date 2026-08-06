from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
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
from app.services.checkin_common import is_success_status, status_label
from app.services.platform_features import CHECKIN_PLATFORM_FEATURES, PLATFORM_SHORT_NAMES, is_feature_enabled

router = APIRouter()


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

    platforms = [platform] if platform else list(CHECKIN_PLATFORM_ORDER)
    platforms = [
        p
        for p in platforms
        if p in _CHECKIN_PLATFORMS
        and is_feature_enabled(db, p)
        and is_feature_enabled(db, CHECKIN_PLATFORM_FEATURES.get(p, p))
    ]
    job_by_platform = {
        str(m["platform"]): str(m["id"])
        for m in JOB_CATALOG
        if m.get("kind") == "user_schedule" and m.get("platform")
    }
    platform_rank = {p: i for i, p in enumerate(CHECKIN_PLATFORM_ORDER)}

    items: list[UserCheckinTaskOut] = []
    for p in platforms:
        model = _bind_model(p)
        log_model = _checkin_log_model(p)
        job_id = job_by_platform.get(p)
        if model is None or not job_id:
            continue
        q = db.query(model).options(joinedload(model.member).joinedload(Member.user))
        if member_id is not None:
            q = q.filter(model.member_id == int(member_id))
        for bind in q.order_by(model.member_id.asc()).all():
            member = bind.member
            user_label = (
                _member_label(member) if member else f"member#{bind.member_id}"
            )
            prefs = (
                db.query(CheckinRolePref)
                .filter(
                    CheckinRolePref.platform == p,
                    CheckinRolePref.member_id == int(bind.member_id),
                )
                .all()
            )
            log_meta = _role_log_meta(db, log_model, member_id=int(bind.member_id))

            if prefs:
                for pref in prefs:
                    key = (str(pref.game_code), str(pref.role_uid))
                    meta = log_meta.get(key) or {}
                    game_name = str(meta.get("game_name") or pref.game_code)
                    role_name = str(
                        meta.get("role_name") or pref.role_uid or pref.game_code
                    )
                    items.append(
                        UserCheckinTaskOut(
                            task_key=f"{p}:{bind.member_id}:{pref.game_code}:{pref.role_uid}",
                            job_id=job_id,
                            platform=p,
                            platform_name=PLATFORM_SHORT_NAMES.get(p, p),
                            member_id=bind.member_id,
                            user_label=user_label,
                            auto_checkin=bool(pref.enabled),
                            checkin_hour=int(pref.checkin_hour),
                            checkin_minute=int(pref.checkin_minute),
                            game_code=str(pref.game_code),
                            game_name=game_name,
                            role_uid=str(pref.role_uid),
                            role_name=role_name,
                            last_checkin_at=_fmt_dt(meta.get("checked_at")),
                            last_checkin_date=(
                                meta["checkin_date"].isoformat()
                                if meta.get("checkin_date") is not None
                                else None
                            ),
                            last_checkin_ok=meta.get("ok"),
                            last_checkin_summary=meta.get("summary"),
                            bound_at=_fmt_dt(bind.bound_at),
                        )
                    )
            else:
                # 尚未写出角色偏好：回退展示 bind 级摘要
                items.append(
                    UserCheckinTaskOut(
                        task_key=f"{p}:{bind.member_id}",
                        job_id=job_id,
                        platform=p,
                        platform_name=PLATFORM_SHORT_NAMES.get(p, p),
                        member_id=bind.member_id,
                        user_label=user_label,
                        auto_checkin=bool(bind.auto_checkin),
                        checkin_hour=int(bind.checkin_hour),
                        checkin_minute=int(bind.checkin_minute),
                        last_checkin_at=_fmt_dt(bind.last_checkin_at),
                        last_checkin_date=bind.last_checkin_date.isoformat()
                        if bind.last_checkin_date
                        else None,
                        last_checkin_ok=bind.last_checkin_ok,
                        last_checkin_summary=bind.last_checkin_summary,
                        bound_at=_fmt_dt(bind.bound_at),
                    )
                )

    items.sort(
        key=lambda t: (
            platform_rank.get(t.platform, 99),
            t.member_id,
            t.game_code or "",
            t.role_uid or "",
            t.checkin_hour,
            t.checkin_minute,
        )
    )
    total = len(items)
    start = (page - 1) * page_size
    return UserCheckinTasksPageOut(
        total=total,
        page=page,
        page_size=page_size,
        items=items[start : start + page_size],
    )


def _role_log_meta(
    db: Session,
    log_model: Any | None,
    *,
    member_id: int,
) -> dict[tuple[str, str], dict[str, Any]]:
    """每个角色最近一条签到日志的展示元数据。"""
    if log_model is None:
        return {}
    rows = (
        db.query(log_model)
        .filter(log_model.member_id == int(member_id))
        .order_by(desc(log_model.checked_at), desc(log_model.id))
        .limit(80)
        .all()
    )
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.game_code or ""), str(row.role_uid or ""))
        if not key[0] or not key[1] or key in out:
            continue
        summary = row.awards_text or row.message
        status = str(row.status or "")
        ok: bool | None
        if is_success_status(status):
            ok = True
        elif status == "error":
            ok = False
        else:
            ok = None
        if summary and status:
            label = status_label(status)
            if label and label not in str(summary):
                summary = f"{label} · {summary}"
        out[key] = {
            "game_name": row.game_name,
            "role_name": row.role_name,
            "checked_at": row.checked_at,
            "checkin_date": row.checkin_date,
            "ok": ok,
            "summary": summary,
        }
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
                message=row.message,
                awards_text=row.awards_text,
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
