"""MAA 槽位台账、审计与用户任务编排（控制面）。"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.timeutil import now_naive
from app.models.maa import MaaJob, MaaSlot, MaaSlotAudit
from app.models.member import Member
from app.models.user import User
from app.services.maa_config import get_maa_host_stats, get_maa_max_slots


def _active_slot_filter():
    return MaaSlot.status != "destroyed"


def count_active_slots(db: Session) -> int:
    return (
        db.query(MaaSlot)
        .filter(_active_slot_filter())
        .count()
    )


def append_audit(
    db: Session,
    *,
    slot: MaaSlot,
    action: str,
    admin: User | None,
    from_status: str | None,
    to_status: str | None,
    result: str = "success",
    message: str | None = None,
) -> MaaSlotAudit:
    row = MaaSlotAudit(
        slot_id=slot.id,
        admin_user_id=admin.id if admin else None,
        action=action,
        from_status=from_status,
        to_status=to_status,
        result=result,
        message=message,
    )
    db.add(row)
    return row


def list_slots(db: Session, *, include_destroyed: bool = False) -> list[MaaSlot]:
    q = db.query(MaaSlot).options(joinedload(MaaSlot.bound_member))
    if not include_destroyed:
        q = q.filter(_active_slot_filter())
    return q.order_by(MaaSlot.id.asc()).all()


def get_slot_or_404(db: Session, slot_id: int, *, allow_destroyed: bool = False) -> MaaSlot:
    slot = (
        db.query(MaaSlot)
        .options(joinedload(MaaSlot.bound_member))
        .filter(MaaSlot.id == slot_id)
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="槽位不存在")
    if not allow_destroyed and slot.status == "destroyed":
        raise HTTPException(status_code=404, detail="槽位已销毁")
    return slot


def create_slot(db: Session, admin: User) -> MaaSlot:
    max_slots = get_maa_max_slots(db)
    active = count_active_slots(db)
    if active >= max_slots:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"已达运维安全上限 {max_slots}（环境变量 MAA_MAX_SLOTS），请先移除空闲实例",
        )
    slot = MaaSlot(
        status="provisioning",
        desired_action="provision",
        resolution="720x1280",
        created_by_user_id=admin.id,
        last_error="[1/5 环境检测] 排队中…",
    )
    db.add(slot)
    db.flush()
    slot.container_name = f"zhange-maa-slot-{slot.id}"
    slot.volume_name = f"zhange-maa-slot-{slot.id}-data"
    append_audit(
        db,
        slot=slot,
        action="create",
        admin=admin,
        from_status=None,
        to_status="provisioning",
        message="管理员新增槽位，Worker 将按步骤启动 Android",
    )
    db.commit()
    db.refresh(slot)
    return slot


def request_start(db: Session, admin: User, slot_id: int) -> MaaSlot:
    slot = get_slot_or_404(db, slot_id)
    if slot.status != "offline":
        raise HTTPException(status_code=400, detail="仅离线槽位可上线")
    if slot.desired_action:
        raise HTTPException(status_code=409, detail="槽位有未完成动作，请稍候")
    prev = slot.status
    slot.desired_action = "start"
    slot.last_error = None
    append_audit(
        db,
        slot=slot,
        action="start",
        admin=admin,
        from_status=prev,
        to_status=prev,
        message="请求上线",
    )
    db.commit()
    db.refresh(slot)
    return slot


def request_stop(db: Session, admin: User, slot_id: int) -> MaaSlot:
    slot = get_slot_or_404(db, slot_id)
    if slot.status != "online":
        raise HTTPException(status_code=400, detail="仅在线槽位可下线")
    if slot.desired_action:
        raise HTTPException(status_code=409, detail="槽位有未完成动作，请稍候")
    prev = slot.status
    # 取消该槽排队/运行中的用户任务
    _cancel_open_jobs(db, slot.id)
    slot.desired_action = "stop"
    append_audit(
        db,
        slot=slot,
        action="stop",
        admin=admin,
        from_status=prev,
        to_status=prev,
        message="请求下线（保留数据卷）",
    )
    db.commit()
    db.refresh(slot)
    return slot


def request_destroy(db: Session, admin: User, slot_id: int) -> MaaSlot:
    slot = get_slot_or_404(db, slot_id)
    if slot.status == "online":
        raise HTTPException(status_code=400, detail="请先下线再移除")
    if slot.status not in ("offline", "error", "provisioning"):
        raise HTTPException(status_code=400, detail="当前状态不可移除")
    if slot.desired_action and slot.status != "provisioning":
        raise HTTPException(status_code=409, detail="槽位有未完成动作，请稍候")
    prev = slot.status
    _cancel_open_jobs(db, slot.id)
    slot.status = "destroying"
    slot.desired_action = "destroy"
    slot.bound_member_id = None
    append_audit(
        db,
        slot=slot,
        action="destroy",
        admin=admin,
        from_status=prev,
        to_status="destroying",
        message="请求销毁容器与数据卷",
    )
    db.commit()
    db.refresh(slot)
    return slot


def bind_member(db: Session, admin: User, slot_id: int, member_id: int) -> MaaSlot:
    slot = get_slot_or_404(db, slot_id)
    if slot.status in ("destroying", "destroyed", "provisioning"):
        raise HTTPException(status_code=400, detail="当前状态不可绑定用户")
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    other = (
        db.query(MaaSlot)
        .filter(
            MaaSlot.bound_member_id == member_id,
            MaaSlot.id != slot.id,
            _active_slot_filter(),
        )
        .first()
    )
    if other:
        raise HTTPException(
            status_code=409,
            detail=f"该成员已绑定槽位 #{other.id}",
        )
    prev = slot.bound_member_id
    slot.bound_member_id = member_id
    append_audit(
        db,
        slot=slot,
        action="bind",
        admin=admin,
        from_status=slot.status,
        to_status=slot.status,
        message=f"绑定成员 {member_id}" + (f"（原 {prev}）" if prev else ""),
    )
    db.commit()
    db.refresh(slot)
    return slot


def unbind_member(db: Session, admin: User, slot_id: int) -> MaaSlot:
    slot = get_slot_or_404(db, slot_id)
    if slot.status in ("destroying", "destroyed"):
        raise HTTPException(status_code=400, detail="当前状态不可解绑")
    prev = slot.bound_member_id
    if not prev:
        raise HTTPException(status_code=400, detail="槽位未绑定用户")
    _cancel_open_jobs(db, slot.id)
    slot.bound_member_id = None
    append_audit(
        db,
        slot=slot,
        action="unbind",
        admin=admin,
        from_status=slot.status,
        to_status=slot.status,
        message=f"解绑成员 {prev}",
    )
    db.commit()
    db.refresh(slot)
    return slot


def list_audits(db: Session, slot_id: int, *, limit: int = 50) -> list[MaaSlotAudit]:
    get_slot_or_404(db, slot_id, allow_destroyed=True)
    return (
        db.query(MaaSlotAudit)
        .filter(MaaSlotAudit.slot_id == slot_id)
        .order_by(MaaSlotAudit.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )


def _cancel_open_jobs(db: Session, slot_id: int) -> None:
    now = now_naive()
    jobs = (
        db.query(MaaJob)
        .filter(
            MaaJob.slot_id == slot_id,
            MaaJob.status.in_(("queued", "running")),
        )
        .all()
    )
    for job in jobs:
        job.status = "cancelled"
        job.finished_at = now
        job.error = "槽位状态变更，任务已取消"


def get_slot_for_member(db: Session, member_id: int) -> MaaSlot | None:
    return (
        db.query(MaaSlot)
        .filter(
            MaaSlot.bound_member_id == member_id,
            _active_slot_filter(),
        )
        .first()
    )


def enqueue_daily_job(db: Session, member: Member) -> MaaJob:
    slot = get_slot_for_member(db, member.id)
    if not slot:
        raise HTTPException(status_code=404, detail="未分配 MAA 槽位，请联系管理员")
    if slot.status != "online":
        raise HTTPException(status_code=400, detail="槽位未在线")
    existing = (
        db.query(MaaJob)
        .filter(
            MaaJob.slot_id == slot.id,
            MaaJob.status.in_(("queued", "running")),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="已有进行中的任务")
    job = MaaJob(
        slot_id=slot.id,
        member_id=member.id,
        job_type="daily",
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def enqueue_stop_job(db: Session, member: Member) -> MaaJob:
    slot = get_slot_for_member(db, member.id)
    if not slot:
        raise HTTPException(status_code=404, detail="未分配 MAA 槽位")
    running = (
        db.query(MaaJob)
        .filter(
            MaaJob.slot_id == slot.id,
            MaaJob.status.in_(("queued", "running")),
            MaaJob.job_type == "daily",
        )
        .all()
    )
    now = now_naive()
    for job in running:
        job.status = "cancelled"
        job.finished_at = now
        job.error = "用户请求停止"
    stop = MaaJob(
        slot_id=slot.id,
        member_id=member.id,
        job_type="stop",
        status="queued",
    )
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return stop


def screenshot_abs_path(slot: MaaSlot) -> Path | None:
    if not slot.last_screenshot_relpath:
        return None
    settings = get_settings()
    root = Path(settings.DATA_DIR).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    path = (root / slot.last_screenshot_relpath).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def runtime_log_text(slot_id: int, *, max_chars: int = 80_000) -> str:
    """读取 Worker 写入的槽位运行日志。"""
    settings = get_settings()
    root = Path(settings.DATA_DIR).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    path = (root / "maa" / str(slot_id) / "runtime.log").resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return ""
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


def resource_summary(db: Session) -> dict:
    slots = list_slots(db, include_destroyed=False)
    online = sum(1 for s in slots if s.status == "online")
    offline = sum(1 for s in slots if s.status == "offline")
    error = sum(1 for s in slots if s.status == "error")
    busy = sum(1 for s in slots if s.status in ("provisioning", "destroying"))
    unbound_online = sum(
        1 for s in slots if s.status == "online" and s.bound_member_id is None
    )
    host = get_maa_host_stats(db)
    return {
        "max_slots": get_maa_max_slots(db),
        "active_slots": len(slots),
        "online": online,
        "offline": offline,
        "error": error,
        "busy": busy,
        "unbound_online": unbound_online,
        "host_cpu_percent": host.get("cpu_percent") or None,
        "host_memory_used_mb": host.get("memory_used_mb") or None,
        "host_memory_total_mb": host.get("memory_total_mb") or None,
        "host_cpu_count": host.get("cpu_count") or None,
        "host_reported_at": host.get("reported_at") or None,
    }


def user_availability(db: Session) -> dict:
    """用户未分配时的容量提示（按实际空闲槽位，非管理端配额配置）。"""
    slots = list_slots(db, include_destroyed=False)
    free_online = sum(
        1 for s in slots if s.status == "online" and s.bound_member_id is None
    )
    free_offline = sum(
        1 for s in slots if s.status == "offline" and s.bound_member_id is None
    )
    provisioning = sum(1 for s in slots if s.status == "provisioning")
    if free_online > 0:
        return {
            "availability": "available",
            "free_online_slots": free_online,
            "message": (
                f"当前有 {free_online} 个就绪空闲槽位，可向管理员申请绑定后使用"
            ),
        }
    if free_offline > 0:
        return {
            "availability": "waiting",
            "free_online_slots": 0,
            "message": (
                f"当前有 {free_offline} 个离线空闲槽位，需管理员上线并绑定后才能使用"
            ),
        }
    if provisioning > 0:
        return {
            "availability": "waiting",
            "free_online_slots": 0,
            "message": "有槽位正在启动中，请稍后再申请，或联系管理员",
        }
    if not slots:
        return {
            "availability": "none",
            "free_online_slots": 0,
            "message": "暂无可用 MAA 资源，请联系管理员供给后再申请",
        }
    return {
        "availability": "full",
        "free_online_slots": 0,
        "message": "当前槽位均已分配，请稍后再申请或联系管理员协调",
    }
