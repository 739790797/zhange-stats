from datetime import datetime

from pydantic import BaseModel, Field


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
    extra_text: str | None = None


class CheckinResponse(BaseModel):
    skipped: bool = False
    ok: bool | None = None
    summary: str
    results: list[CheckinResultItem] = Field(default_factory=list)


# 兼容旧命名
SklandCheckinLogOut = CheckinLogOut
SklandCheckinResultItem = CheckinResultItem
SklandCheckinResponse = CheckinResponse
