from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.checkin import CheckinAwardItem, CheckinLogOut, CheckinResultItem, CheckinResponse


class MihoyoBindSmsSendRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    geetest: str | None = Field(default=None, max_length=4096)
    mmt_key: str | None = Field(default=None, max_length=128)


class MihoyoBindSmsSendResponse(BaseModel):
    ok: bool = True
    message: str = "验证码已发送"
    need_geetest: bool = False
    captcha_id: str | None = None
    mmt_key: str | None = None


class MihoyoBindSmsRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    captcha: str = Field(min_length=4, max_length=16)


class MihoyoBindPasswordRequest(BaseModel):
    account: str = Field(min_length=5, max_length=128)
    password: str = Field(min_length=4, max_length=128)
    geetest: str | None = Field(default=None, max_length=4096)
    mmt_key: str | None = Field(default=None, max_length=128)


class MihoyoQrStartResponse(BaseModel):
    scan_id: str
    scan_url: str
    qr_image: str
    expires_in: int = 180


class MihoyoQrPollRequest(BaseModel):
    scan_id: str = Field(min_length=8, max_length=128)


class MihoyoQrPollResponse(BaseModel):
    status: str
    message: str = ""


class MihoyoBindUpdate(BaseModel):
    auto_checkin: bool | None = None
    checkin_hour: int | None = Field(default=None, ge=0, le=23)
    checkin_minute: int | None = Field(default=None, ge=0, le=59)


class MihoyoRoleOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    channel_name: str


MihoyoCheckinLogOut = CheckinLogOut
MihoyoCheckinResultItem = CheckinResultItem
MihoyoCheckinResponse = CheckinResponse


class MihoyoStatusOut(BaseModel):
    bound: bool
    auto_checkin: bool | None = None
    checkin_hour: int | None = None
    checkin_minute: int | None = None
    phone_mask: str | None = None
    bound_at: datetime | None = None
    token_ok: bool | None = None
    token_error: str | None = None
    roles: list[MihoyoRoleOut] = Field(default_factory=list)
    today_results: list[CheckinResultItem] = Field(default_factory=list)
    today_logs: list[CheckinLogOut] = Field(default_factory=list)


class MihoyoBindPasswordResponse(BaseModel):
    ok: bool = True
    message: str = ""
    need_geetest: bool = False
    captcha_id: str | None = None
    mmt_key: str | None = None
    status: MihoyoStatusOut | None = None


class MihoyoExchangeItemOut(BaseModel):
    goods_id: str
    goods_name: str
    goods_num: int = 1
    goods_img: str = ""
    price: int = 0
    exchange_limit: int = 0
    exchanged_count: int = 0
    next_exchange_time: str | None = None
    game_biz: str = ""
    game_code: str = ""
    game_name: str = ""


class MihoyoExchangeRoleOut(BaseModel):
    game_biz: str
    game_code: str
    game_name: str = ""
    role_uid: str
    role_name: str = ""
    region: str = ""
    channel_name: str = ""


class MihoyoExchangeShopOut(BaseModel):
    points: int = 0
    items: list[MihoyoExchangeItemOut] = Field(default_factory=list)
    roles: list[MihoyoExchangeRoleOut] = Field(default_factory=list)


class MihoyoExchangeRequest(BaseModel):
    goods_id: str = Field(min_length=1, max_length=64)
    game_biz: str = Field(default="", max_length=32)
    region: str = Field(default="", max_length=32)
    role_uid: str = Field(default="", max_length=64)


class MihoyoExchangeResultOut(BaseModel):
    ok: bool = True
    message: str = ""
    points: int | None = None
    item: MihoyoExchangeItemOut | None = None


class MihoyoPointsLogItemOut(BaseModel):
    points: int = 0
    reason: str = ""
    log_time: str = ""


class MihoyoPointsLogOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[MihoyoPointsLogItemOut] = Field(
        default_factory=list,
        alias="list",
        serialization_alias="list",
    )
    total: int = 0
    page: int = 1
    page_size: int = 50


class MihoyoAttendanceDayOut(BaseModel):
    """签到周期第 N 天（非公历日期）。"""

    day: int
    claimed: bool
    awards: list[CheckinAwardItem] = Field(default_factory=list)


class MihoyoAttendanceCalendarOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    claimed_days: int = 0
    total_days: int = 0
    has_today_claim: bool = False
    progress_reliable: bool = True
    days: list[MihoyoAttendanceDayOut] = Field(default_factory=list)
    roles: list[MihoyoRoleOut] = Field(default_factory=list)
    synced_at: str | None = None
    stale: bool = False
