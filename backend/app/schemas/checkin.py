from datetime import datetime

from pydantic import BaseModel, Field


class CheckinAwardItem(BaseModel):
    """结构化签到奖励；有 icon_url 时前端应展示图标。"""

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
    included: bool = False
    auto_checkin: bool = False
    checkin_hour: int | None = None
    checkin_minute: int | None = None
    # 与「我的日常」任务行同源：该角色最近一次签到日志
    last_checkin_at: str | None = None
    last_checkin_date: str | None = None
    last_checkin_ok: bool | None = None
    last_checkin_summary: str | None = None
    last_checkin_awards: list[CheckinAwardItem] = Field(default_factory=list)


class CheckinRolePrefUpdate(BaseModel):
    game_code: str = Field(min_length=1, max_length=32)
    role_uid: str = Field(min_length=1, max_length=64)
    enabled: bool | None = None
    included: bool | None = None
    checkin_hour: int | None = Field(default=None, ge=0, le=23)
    checkin_minute: int | None = Field(default=None, ge=0, le=59)


class RoleMembershipItem(BaseModel):
    game_code: str = Field(min_length=1, max_length=32)
    role_uid: str = Field(min_length=1, max_length=64)
    included: bool = True


class RoleMembershipReplaceBody(BaseModel):
    roles: list[RoleMembershipItem] = Field(default_factory=list)


class RoleMembershipNodeOut(BaseModel):
    game_code: str
    game_name: str
    role_uid: str
    role_name: str
    channel_name: str = ""
    included: bool = False


class RoleMembershipTreeOut(BaseModel):
    platform: str
    roles: list[RoleMembershipNodeOut] = Field(default_factory=list)


class CheckinNowBody(BaseModel):
    """立即签到：可指定单个角色；省略则签该账号下全部角色。"""

    game_code: str | None = Field(default=None, min_length=1, max_length=32)
    role_uid: str | None = Field(default=None, min_length=1, max_length=64)


class CheckinResponse(BaseModel):
    skipped: bool = False
    ok: bool | None = None
    summary: str
    results: list[CheckinResultItem] = Field(default_factory=list)


# 兼容旧命名
SklandCheckinLogOut = CheckinLogOut
SklandCheckinResultItem = CheckinResultItem
SklandCheckinResponse = CheckinResponse
