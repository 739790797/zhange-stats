from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.checkin import CheckinAwardItem, CheckinLogOut, CheckinResultItem, CheckinResponse


class TaygedoBindPasswordRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    password: str = Field(min_length=4, max_length=128)


class TaygedoBindSmsSendRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    device_id: str | None = Field(default=None, max_length=64)


class TaygedoBindSmsSendResponse(BaseModel):
    device_id: str
    message: str = "验证码已发送"


class TaygedoBindSmsRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    captcha: str = Field(min_length=4, max_length=8)
    device_id: str = Field(min_length=8, max_length=64)


class TaygedoBindJsonRequest(BaseModel):
    credentials_json: str = Field(min_length=8, max_length=8192)


class TaygedoBindUpdate(BaseModel):
    auto_checkin: bool | None = None
    checkin_hour: int | None = Field(default=None, ge=0, le=23)
    checkin_minute: int | None = Field(default=None, ge=0, le=59)


class TaygedoRoleOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    channel_name: str


TaygedoCheckinLogOut = CheckinLogOut
TaygedoCheckinResultItem = CheckinResultItem
TaygedoCheckinResponse = CheckinResponse


class TaygedoStatusOut(BaseModel):
    bound: bool
    auto_checkin: bool | None = None
    checkin_hour: int | None = None
    checkin_minute: int | None = None
    phone_mask: str | None = None
    bound_at: datetime | None = None
    last_checkin_at: datetime | None = None
    last_checkin_date: str | None = None
    last_checkin_ok: bool | None = None
    last_checkin_summary: str | None = None
    token_ok: bool | None = None
    token_error: str | None = None
    roles: list[TaygedoRoleOut] = Field(default_factory=list)
    today_results: list[CheckinResultItem] = Field(default_factory=list)
    today_logs: list[CheckinLogOut] = Field(default_factory=list)


class TaygedoAttendanceDayOut(BaseModel):
    """签到周期第 N 天（非公历日期）。"""

    day: int
    claimed: bool
    awards: list[CheckinAwardItem] = Field(default_factory=list)


class TaygedoAttendanceCalendarOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    claimed_days: int = 0
    total_days: int = 0
    has_today_claim: bool = False
    progress_reliable: bool = True
    days: list[TaygedoAttendanceDayOut] = Field(default_factory=list)
    roles: list[TaygedoRoleOut] = Field(default_factory=list)
    synced_at: str | None = None
    stale: bool = False
