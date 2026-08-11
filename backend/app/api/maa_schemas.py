"""MAA 全托管 API schemas。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MaaSlotOut(BaseModel):
    id: int
    status: str
    desired_action: str | None = None
    container_name: str | None = None
    volume_name: str | None = None
    adb_endpoint: str | None = None
    bound_member_id: int | None = None
    bound_member_nickname: str | None = None
    resolution: str
    last_error: str | None = None
    last_heartbeat_at: datetime | None = None
    last_screenshot_at: datetime | None = None
    has_screenshot: bool = False
    cpu_percent: str | None = None
    memory_usage_mb: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
    destroyed_at: datetime | None = None

    model_config = {"from_attributes": True}


class MaaResourceSummaryOut(BaseModel):
    max_slots: int
    active_slots: int
    online: int
    offline: int
    error: int
    busy: int
    unbound_online: int = 0
    host_cpu_percent: str | None = None
    host_memory_used_mb: str | None = None
    host_memory_total_mb: str | None = None
    host_cpu_count: str | None = None
    host_reported_at: str | None = None


class MaaAdminListOut(BaseModel):
    summary: MaaResourceSummaryOut
    slots: list[MaaSlotOut]


class MaaBindRequest(BaseModel):
    member_id: int = Field(..., ge=1)


class MaaSlotAuditOut(BaseModel):
    id: int
    slot_id: int
    admin_user_id: int | None = None
    action: str
    from_status: str | None = None
    to_status: str | None = None
    result: str
    message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MaaJobOut(BaseModel):
    id: int
    slot_id: int
    member_id: int
    job_type: str
    status: str
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class MaaUserStatusOut(BaseModel):
    assigned: bool
    slot: MaaSlotOut | None = None
    active_job: MaaJobOut | None = None
    message: str | None = None
    availability: str | None = None
    free_online_slots: int = 0


class MaaSlotLogsOut(BaseModel):
    slot_id: int
    status: str
    last_error: str | None = None
    text: str


class MaaWorkerHeartbeatIn(BaseModel):
    slot_id: int
    status: str | None = None
    desired_action: str | None = None
    clear_desired_action: bool = False
    container_name: str | None = None
    volume_name: str | None = None
    adb_endpoint: str | None = None
    last_error: str | None = None
    cpu_percent: str | None = None
    memory_usage_mb: str | None = None
    screenshot_relpath: str | None = None
    audit_action: str | None = None
    audit_message: str | None = None
    audit_result: str = "success"


class MaaWorkerJobUpdateIn(BaseModel):
    job_id: int
    status: str
    error: str | None = None


class MaaWorkerHostStatsIn(BaseModel):
    cpu_percent: str = ""
    memory_used_mb: str = ""
    memory_total_mb: str = ""
    cpu_count: str = ""


class MaaWorkerPullOut(BaseModel):
    slots: list[MaaSlotOut]
    jobs: list[MaaJobOut]
