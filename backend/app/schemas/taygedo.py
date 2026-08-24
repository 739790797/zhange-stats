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


class ExastrisCharOut(BaseModel):
    char_id: str
    name: str
    quality: str = ""
    element_type: str = ""
    group_type: str = ""
    awaken_lev: int = 0
    portrait_url: str | None = None
    element_icon_url: str | None = None


class ExastrisBoxOut(BaseModel):
    uid: str
    role_id: str = ""
    role_name: str = ""
    game_code: str = "1289"
    game_name: str = "异环"
    char_count: int = 0
    chars: list[ExastrisCharOut] = Field(default_factory=list)
    roles: list[TaygedoRoleOut] = Field(default_factory=list)
    synced_at: str | None = None
    stale: bool = False


class TaygedoExchangeItemOut(BaseModel):
    goods_id: str
    name: str
    cover: str = ""
    price: int = 0
    exchange_num: int = 0
    cycle_limit: int = 0
    cycle_type: int = 0
    stock: int = -1
    stock_limited: bool = False
    tab: str = ""
    state: int = 0
    game_id: str = ""
    can_exchange: bool = False


class TaygedoExchangeTabOut(BaseModel):
    tab: str
    name: str = ""


class TaygedoExchangeRoleOut(BaseModel):
    game_id: str
    game_name: str = ""
    role_id: str
    role_name: str = ""


class TaygedoExchangeShopOut(BaseModel):
    gold: int = 0
    today_get: int = 0
    today_total: int = 0
    tabs: list[TaygedoExchangeTabOut] = Field(default_factory=list)
    items: list[TaygedoExchangeItemOut] = Field(default_factory=list)
    roles: list[TaygedoExchangeRoleOut] = Field(default_factory=list)


class TaygedoExchangeRequest(BaseModel):
    goods_id: str = Field(min_length=1, max_length=64)
    game_id: str = Field(min_length=1, max_length=32)
    role_id: str = Field(min_length=1, max_length=64)


class TaygedoExchangeResultOut(BaseModel):
    ok: bool = True
    message: str = ""
    gold: int | None = None
    item: TaygedoExchangeItemOut | None = None
