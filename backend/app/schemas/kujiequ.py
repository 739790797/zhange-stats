from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.checkin import (
    CheckinAwardItem,
    CheckinLogOut,
    CheckinResponse,
    CheckinResultItem,
)


class KujiequBindTokenRequest(BaseModel):
    token: str = Field(min_length=8, max_length=8192)


class KujiequBindSmsSendRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    # 极验 getValidate() 结果的 JSON 字符串；首次可为空，官方返回需极验后再带上重试
    gee_test_data: str | None = Field(default=None, max_length=8192)


class KujiequBindSmsSendResponse(BaseModel):
    ok: bool = True
    message: str = "验证码已发送"
    need_geetest: bool = False
    captcha_id: str | None = None


class KujiequBindSmsRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    captcha: str = Field(min_length=4, max_length=8)


class KujiequBindUpdate(BaseModel):
    auto_checkin: bool | None = None
    checkin_hour: int | None = Field(default=None, ge=0, le=23)
    checkin_minute: int | None = Field(default=None, ge=0, le=59)


class KujiequRoleOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    channel_name: str


KujiequCheckinLogOut = CheckinLogOut
KujiequCheckinResultItem = CheckinResultItem
KujiequCheckinResponse = CheckinResponse


class KujiequStatusOut(BaseModel):
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
    roles: list[KujiequRoleOut] = Field(default_factory=list)
    today_results: list[CheckinResultItem] = Field(default_factory=list)
    today_logs: list[CheckinLogOut] = Field(default_factory=list)


class KujiequExchangeItemOut(BaseModel):
    commodity_code: str
    commodity_name: str
    commodity_price: int = 0
    commodity_type: int = 0
    commodity_status: int = 0
    game_id: int = 0
    game_name: str = ""
    picture_url: str = ""
    commodity_desc: str = ""
    commodity_limit: int = 0
    current_user_limit_buy: int = 0
    total_stock: int = 0
    total_surplus_stock: int = 0
    is_sellout: bool = False
    can_exchange: bool = False
    sale_time_ms: int | None = None
    off_shelve_time_ms: int | None = None


class KujiequExchangeRoleOut(BaseModel):
    game_id: int
    game_name: str = ""
    role_id: str
    role_name: str = ""


class KujiequExchangeShopOut(BaseModel):
    gold: int = 0
    items: list[KujiequExchangeItemOut] = Field(default_factory=list)
    roles: list[KujiequExchangeRoleOut] = Field(default_factory=list)


class KujiequExchangeRequest(BaseModel):
    commodity_code: str = Field(min_length=1, max_length=64)
    game_id: int = Field(ge=0)
    role_id: str | None = Field(default=None, max_length=64)


class KujiequExchangeResultOut(BaseModel):
    ok: bool = True
    message: str = ""
    gold: int | None = None
    item: KujiequExchangeItemOut | None = None


class KujiequAttendanceDayOut(BaseModel):
    """签到周期第 N 天（非公历日期）。"""

    day: int
    claimed: bool
    awards: list[CheckinAwardItem] = Field(default_factory=list)


class KujiequAttendanceCalendarOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    claimed_days: int = 0
    total_days: int = 0
    has_today_claim: bool = False
    progress_reliable: bool = True
    days: list[KujiequAttendanceDayOut] = Field(default_factory=list)
    roles: list[KujiequRoleOut] = Field(default_factory=list)
    synced_at: str | None = None
    stale: bool = False


class WwBoxItemOut(BaseModel):
    name: str
    num: int = 0
    icon_url: str | None = None


class WwBoxOut(BaseModel):
    uid: str
    role_id: str = ""
    role_name: str = ""
    server_id: str = ""
    server_name: str = ""
    game_code: str = "3"
    game_name: str = "鸣潮"
    level: int = 0
    world_level: int = 0
    active_days: int = 0
    role_num: int = 0
    achievement_count: int = 0
    achievement_star: int = 0
    energy: int = 0
    max_energy: int = 0
    store_energy: int = 0
    store_energy_limit: int = 0
    store_energy_title: str = ""
    store_energy_icon_url: str | None = None
    liveness: int = 0
    liveness_max: int = 0
    small_count: int = 0
    big_count: int = 0
    sound_box: int = 0
    weekly_inst_count: int = 0
    weekly_inst_limit: int = 0
    weekly_inst_title: str = ""
    weekly_inst_icon_url: str | None = None
    rouge_score: int = 0
    rouge_score_limit: int = 0
    rouge_title: str = ""
    rouge_icon_url: str | None = None
    treasure_boxes: list[WwBoxItemOut] = Field(default_factory=list)
    phantom_boxes: list[WwBoxItemOut] = Field(default_factory=list)
    calabash_level: int = 0
    calabash_unlock: int = 0
    calabash_max: int = 0
    calabash_cost: int = 0
    roles: list[KujiequRoleOut] = Field(default_factory=list)
    synced_at: str | None = None
    stale: bool = False

