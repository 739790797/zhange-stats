"""MAA 全托管：管理端 / 用户端 / Worker 内部 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.maa_schemas import (
    MaaAdminListOut,
    MaaBindRequest,
    MaaJobOut,
    MaaResourceSummaryOut,
    MaaSlotAuditOut,
    MaaSlotLogsOut,
    MaaSlotOut,
    MaaUserStatusOut,
    MaaWorkerHeartbeatIn,
    MaaWorkerHostStatsIn,
    MaaWorkerJobUpdateIn,
    MaaWorkerPullOut,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.core.timeutil import now_naive
from app.models.maa import MaaJob, MaaSlot
from app.models.member import Member
from app.models.user import User
from app.services import maa_slots as svc
from app.services.maa_config import get_maa_max_slots, set_maa_host_stats
from app.services.member_sync import ensure_user_member

router = APIRouter(tags=["maa"])


def _slot_out(slot: MaaSlot) -> MaaSlotOut:
    nick = None
    if slot.bound_member is not None:
        nick = slot.bound_member.nickname
    return MaaSlotOut(
        id=slot.id,
        status=slot.status,
        desired_action=slot.desired_action,
        container_name=slot.container_name,
        volume_name=slot.volume_name,
        adb_endpoint=slot.adb_endpoint,
        bound_member_id=slot.bound_member_id,
        bound_member_nickname=nick,
        resolution=slot.resolution or "720x1280",
        last_error=slot.last_error,
        last_heartbeat_at=slot.last_heartbeat_at,
        last_screenshot_at=slot.last_screenshot_at,
        has_screenshot=bool(slot.last_screenshot_relpath),
        cpu_percent=slot.cpu_percent,
        memory_usage_mb=slot.memory_usage_mb,
        created_by_user_id=slot.created_by_user_id,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
        destroyed_at=slot.destroyed_at,
    )


def _require_worker_token(
    x_maa_worker_token: str | None = Header(default=None, alias="X-Maa-Worker-Token"),
) -> None:
    settings = get_settings()
    expected = settings.effective_maa_worker_token
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="未配置 MAA_WORKER_TOKEN（或 SECRET_KEY 不可用，无法派生）",
        )
    if not x_maa_worker_token or x_maa_worker_token != expected:
        raise HTTPException(status_code=401, detail="Worker 鉴权失败")


# ----- Admin -----


@router.get("/settings/maa", response_model=MaaAdminListOut)
def admin_list_maa(
    include_destroyed: bool = Query(False),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slots = svc.list_slots(db, include_destroyed=include_destroyed)
    return MaaAdminListOut(
        summary=MaaResourceSummaryOut(**svc.resource_summary(db)),
        slots=[_slot_out(s) for s in slots],
    )


@router.post("/settings/maa/slots", response_model=MaaSlotOut)
def admin_create_slot(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _slot_out(svc.create_slot(db, admin))


@router.post("/settings/maa/slots/{slot_id}/start", response_model=MaaSlotOut)
def admin_start_slot(
    slot_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _slot_out(svc.request_start(db, admin, slot_id))


@router.post("/settings/maa/slots/{slot_id}/stop", response_model=MaaSlotOut)
def admin_stop_slot(
    slot_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _slot_out(svc.request_stop(db, admin, slot_id))


@router.post("/settings/maa/slots/{slot_id}/destroy", response_model=MaaSlotOut)
def admin_destroy_slot(
    slot_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _slot_out(svc.request_destroy(db, admin, slot_id))


@router.post("/settings/maa/slots/{slot_id}/bind", response_model=MaaSlotOut)
def admin_bind_slot(
    slot_id: int,
    body: MaaBindRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _slot_out(svc.bind_member(db, admin, slot_id, body.member_id))


@router.post("/settings/maa/slots/{slot_id}/unbind", response_model=MaaSlotOut)
def admin_unbind_slot(
    slot_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _slot_out(svc.unbind_member(db, admin, slot_id))


@router.get(
    "/settings/maa/slots/{slot_id}/audits",
    response_model=list[MaaSlotAuditOut],
)
def admin_slot_audits(
    slot_id: int,
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return svc.list_audits(db, slot_id, limit=limit)


@router.post("/settings/maa/reconcile")
def admin_reconcile(
    _: User = Depends(require_admin),
):
    """触发对账：Worker 侧轮询会处理；此处仅作显式操作记录入口。"""
    return {"ok": True, "message": "已请求对账，Worker 将在下一轮扫描执行"}


@router.get("/settings/maa/slots/{slot_id}/screenshot")
def admin_slot_screenshot(
    slot_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slot = svc.get_slot_or_404(db, slot_id, allow_destroyed=True)
    path = svc.screenshot_abs_path(slot)
    if not path:
        raise HTTPException(status_code=404, detail="暂无截图")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/settings/maa/slots/{slot_id}/logs", response_model=MaaSlotLogsOut)
def admin_slot_logs(
    slot_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """槽位运行日志（Worker 采集的事件 + docker logs 片段）。"""
    slot = svc.get_slot_or_404(db, slot_id, allow_destroyed=True)
    text = svc.runtime_log_text(slot_id)
    if not text:
        text = (
            f"暂无运行日志。\n"
            f"当前状态: {slot.status}\n"
            f"desired_action: {slot.desired_action or '-'}\n"
            f"adb: {slot.adb_endpoint or '-'}\n"
            f"last_error: {slot.last_error or '-'}\n"
            f"\n提示: 需 maa-worker 运行后才会写入 DATA_DIR/maa/{slot_id}/runtime.log"
        )
    return MaaSlotLogsOut(
        slot_id=slot_id,
        status=slot.status,
        last_error=slot.last_error,
        text=text,
    )


# ----- User -----


@router.get(
    "/maa/me",
    response_model=MaaUserStatusOut,
    dependencies=[Depends(require_feature("skland.arknights.maa"))],
)
def user_maa_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = ensure_user_member(db, user)
    slot = svc.get_slot_for_member(db, member.id)
    if not slot:
        tip = svc.user_availability(db)
        return MaaUserStatusOut(
            assigned=False,
            message=tip["message"],
            availability=tip["availability"],
            free_online_slots=int(tip["free_online_slots"]),
        )
    active = (
        db.query(MaaJob)
        .filter(
            MaaJob.slot_id == slot.id,
            MaaJob.status.in_(("queued", "running")),
        )
        .order_by(MaaJob.id.desc())
        .first()
    )
    return MaaUserStatusOut(
        assigned=True,
        slot=_slot_out(slot),
        active_job=MaaJobOut.model_validate(active) if active else None,
        availability="assigned",
        free_online_slots=0,
    )


@router.post(
    "/maa/me/daily",
    response_model=MaaJobOut,
    dependencies=[Depends(require_feature("skland.arknights.maa"))],
)
def user_start_daily(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = ensure_user_member(db, user)
    return MaaJobOut.model_validate(svc.enqueue_daily_job(db, member))


@router.post(
    "/maa/me/stop",
    response_model=MaaJobOut,
    dependencies=[Depends(require_feature("skland.arknights.maa"))],
)
def user_stop_daily(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = ensure_user_member(db, user)
    return MaaJobOut.model_validate(svc.enqueue_stop_job(db, member))


@router.get(
    "/maa/me/screenshot",
    dependencies=[Depends(require_feature("skland.arknights.maa"))],
)
def user_maa_screenshot(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = ensure_user_member(db, user)
    slot = svc.get_slot_for_member(db, member.id)
    if not slot:
        raise HTTPException(status_code=404, detail="未分配槽位")
    path = svc.screenshot_abs_path(slot)
    if not path:
        raise HTTPException(status_code=404, detail="暂无截图")
    return FileResponse(path, media_type="image/jpeg")


@router.get(
    "/maa/me/logs",
    response_model=MaaSlotLogsOut,
    dependencies=[Depends(require_feature("skland.arknights.maa"))],
)
def user_maa_logs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户绑定槽位的运行日志（与管理端同源 runtime.log）。"""
    member = ensure_user_member(db, user)
    slot = svc.get_slot_for_member(db, member.id)
    if not slot:
        raise HTTPException(status_code=404, detail="未分配槽位")
    text = svc.runtime_log_text(slot.id)
    if not text:
        active = (
            db.query(MaaJob)
            .filter(
                MaaJob.slot_id == slot.id,
                MaaJob.status.in_(("queued", "running")),
            )
            .order_by(MaaJob.id.desc())
            .first()
        )
        job_hint = (
            f"{active.job_type}:{active.status}" if active else "无进行中任务"
        )
        text = (
            f"暂无运行日志。\n"
            f"当前状态: {slot.status}\n"
            f"任务: {job_hint}\n"
            f"last_error: {slot.last_error or '-'}\n"
            f"\n提示: 需 maa-worker 运行后才会写入运行日志"
        )
    return MaaSlotLogsOut(
        slot_id=slot.id,
        status=slot.status,
        last_error=slot.last_error,
        text=text,
    )


# ----- Worker internal -----


@router.get("/internal/maa/pull", response_model=MaaWorkerPullOut)
def worker_pull(
    _: None = Depends(_require_worker_token),
    db: Session = Depends(get_db),
):
    slots = (
        db.query(MaaSlot)
        .filter(MaaSlot.status != "destroyed")
        .order_by(MaaSlot.id.asc())
        .all()
    )
    jobs = (
        db.query(MaaJob)
        .filter(MaaJob.status.in_(("queued", "running")))
        .order_by(MaaJob.id.asc())
        .all()
    )
    return MaaWorkerPullOut(
        slots=[_slot_out(s) for s in slots],
        jobs=[MaaJobOut.model_validate(j) for j in jobs],
    )


@router.post("/internal/maa/heartbeat", response_model=MaaSlotOut)
def worker_heartbeat(
    body: MaaWorkerHeartbeatIn,
    _: None = Depends(_require_worker_token),
    db: Session = Depends(get_db),
):
    slot = db.query(MaaSlot).filter(MaaSlot.id == body.slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="槽位不存在")
    prev = slot.status
    now = now_naive()
    slot.last_heartbeat_at = now
    # 销毁中禁止被供给心跳改回 provisioning/online
    protect_destroy = prev in ("destroying", "destroyed")
    apply_status = body.status
    if (
        protect_destroy
        and apply_status is not None
        and apply_status not in ("destroyed", "error", "destroying")
    ):
        apply_status = None
        ignore_conflict = True
    else:
        ignore_conflict = False

    if apply_status is not None:
        slot.status = apply_status
    if body.clear_desired_action:
        if not protect_destroy or apply_status in ("destroyed", "error"):
            slot.desired_action = None
    elif body.desired_action is not None:
        if not (protect_destroy and body.desired_action != "destroy"):
            slot.desired_action = body.desired_action
    if body.container_name is not None:
        slot.container_name = body.container_name
    if body.volume_name is not None:
        slot.volume_name = body.volume_name
    if body.adb_endpoint is not None:
        slot.adb_endpoint = body.adb_endpoint
    if body.last_error is not None and not ignore_conflict:
        slot.last_error = body.last_error or None
    if body.cpu_percent is not None:
        slot.cpu_percent = body.cpu_percent
    if body.memory_usage_mb is not None:
        slot.memory_usage_mb = body.memory_usage_mb
    if body.screenshot_relpath is not None:
        slot.last_screenshot_relpath = body.screenshot_relpath
        slot.last_screenshot_at = now
    if apply_status == "destroyed":
        slot.destroyed_at = now
        slot.desired_action = None
        slot.bound_member_id = None
    if body.audit_action and not ignore_conflict:
        svc.append_audit(
            db,
            slot=slot,
            action=body.audit_action,
            admin=None,
            from_status=prev,
            to_status=slot.status,
            result=body.audit_result,
            message=body.audit_message,
        )
    db.commit()
    db.refresh(slot)
    return _slot_out(slot)


@router.post("/internal/maa/jobs/update", response_model=MaaJobOut)
def worker_job_update(
    body: MaaWorkerJobUpdateIn,
    _: None = Depends(_require_worker_token),
    db: Session = Depends(get_db),
):
    job = db.query(MaaJob).filter(MaaJob.id == body.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    now = now_naive()
    job.status = body.status
    if body.error is not None:
        job.error = body.error
    if body.status == "running" and job.started_at is None:
        job.started_at = now
    if body.status in ("success", "failed", "cancelled"):
        job.finished_at = now
    db.commit()
    db.refresh(job)
    return MaaJobOut.model_validate(job)


@router.post("/internal/maa/host-stats")
def worker_host_stats(
    body: MaaWorkerHostStatsIn,
    _: None = Depends(_require_worker_token),
    db: Session = Depends(get_db),
):
    """Worker 上报 Docker 宿主机（容器所在环境）CPU/内存。"""
    saved = set_maa_host_stats(
        db,
        cpu_percent=body.cpu_percent,
        memory_used_mb=body.memory_used_mb,
        memory_total_mb=body.memory_total_mb,
        cpu_count=body.cpu_count,
    )
    return {"ok": True, **saved}


@router.get("/internal/maa/config")
def worker_config(
    _: None = Depends(_require_worker_token),
    db: Session = Depends(get_db),
):
    return {
        "max_slots": get_maa_max_slots(db),
        "data_dir_hint": "maa/{slot_id}/latest.jpg",
    }
