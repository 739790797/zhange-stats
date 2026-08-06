from datetime import datetime

from pydantic import BaseModel, Field


class CheckinAwardItem(BaseModel):
    """结构化签到奖励（方舟可含 icon_url）。"""

    name: str
    count: int = 1
    resource_id: str | None = None
    resource_type: str | None = None
    icon_url: str | None = None


class CheckinLogOut(BaseModel):
    """签到记录公共结构（森空岛 / 塔吉多等共用）。"""

    id: int
    game_code: str
    game_name: str
    role_uid: str
    role_name: str | None = None
    channel_name: str | None = None
    status: str
    status_label: str = ""
    message: str | None = None
    awards_text: str | None = None
    awards: list[CheckinAwardItem] = Field(default_factory=list)
    checkin_date: str
    checked_at: datetime


class CheckinResultItem(BaseModel):
    game_code: str
    game_name: str
    role_uid: str
    role_name: str
    channel_name: str
    status: str
    status_label: str = ""
    message: str
    awards_text: str | None = None
    awards: list[CheckinAwardItem] = Field(default_factory=list)
    extra_text: str | None = None
    auto_checkin: bool = False
    checkin_hour: int | None = None
    checkin_minute: int | None = None


class CheckinRolePrefUpdate(BaseModel):
    game_code: str = Field(min_length=1, max_length=32)
    role_uid: str = Field(min_length=1, max_length=64)
    enabled: bool
    checkin_hour: int | None = Field(default=None, ge=0, le=23)
    checkin_minute: int | None = Field(default=None, ge=0, le=59)


class CheckinResponse(BaseModel):
    skipped: bool = False
    ok: bool | None = None
    summary: str
    results: list[CheckinResultItem] = Field(default_factory=list)


# 兼容旧命名
SklandCheckinLogOut = CheckinLogOut
SklandCheckinResultItem = CheckinResultItem
SklandCheckinResponse = CheckinResponse
