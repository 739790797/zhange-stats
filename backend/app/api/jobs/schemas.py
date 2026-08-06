from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.scheduler_runtime import APP_EXECUTOR_ID


class ExecutorOut(BaseModel):
    id: str
    name: str


class ScheduledJobLastRunOut(BaseModel):
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    message: str | None = None


class ScheduledJobOut(BaseModel):
    id: str
    name: str
    description: str = ""
    kind: str = "cron"
    platform: str | None = None
    executor_id: str = APP_EXECUTOR_ID
    registered: bool = False
    scheduler_running: bool = False
    trigger_type: str | None = None
    schedule: str | None = None
    next_run_at: str | None = None
    config_enabled: bool | None = None
    interval_minutes: int | None = None
    hour: int | None = None
    minute: int | None = None
    last_run: ScheduledJobLastRunOut | None = None


class ScheduledJobsOut(BaseModel):
    scheduler_running: bool = False
    timezone: str = "Asia/Shanghai"
    platforms: list[ExecutorOut] = Field(default_factory=list)
    executors: list[ExecutorOut] = Field(default_factory=list)
    jobs: list[ScheduledJobOut] = Field(default_factory=list)


class JobTriggerRequest(BaseModel):
    member_id: int | None = None


class JobTriggerOut(BaseModel):
    accepted: bool = True
    job_id: str
    message: str = "已提交执行"


class JobRunOut(BaseModel):
    id: int
    job_key: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    message: str | None = None
    stats: dict[str, Any] | None = None


class JobRunsPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[JobRunOut] = Field(default_factory=list)


class CheckinLogItemOut(BaseModel):
    id: int
    platform: str
    member_id: int
    user_label: str | None = None
    game_code: str
    game_name: str
    role_uid: str
    role_name: str | None = None
    status: str
    message: str | None = None
    awards_text: str | None = None
    checkin_date: str
    checked_at: str | None = None


class CheckinLogsPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CheckinLogItemOut] = Field(default_factory=list)


class JobMemberOptionOut(BaseModel):
    member_id: int
    user_id: int | None = None
    label: str


class UserCheckinTaskOut(BaseModel):
    """用户 × 平台 × 角色（或整平台回退）= 一条签到任务。"""

    task_key: str
    job_id: str
    platform: str
    platform_name: str
    member_id: int
    user_label: str
    auto_checkin: bool
    checkin_hour: int
    checkin_minute: int
    # 角色级任务；旧「整平台」回退行时为空
    game_code: str | None = None
    game_name: str | None = None
    role_uid: str | None = None
    role_name: str | None = None
    last_checkin_at: str | None = None
    last_checkin_date: str | None = None
    last_checkin_ok: bool | None = None
    last_checkin_summary: str | None = None
    bound_at: str | None = None


class UserCheckinTasksPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[UserCheckinTaskOut] = Field(default_factory=list)


class JobConfigUpdateItem(BaseModel):
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)


class ScheduledJobsUpdate(BaseModel):
    jobs: dict[str, JobConfigUpdateItem] = Field(default_factory=dict)
