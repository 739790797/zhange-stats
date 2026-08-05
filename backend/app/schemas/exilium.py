from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.checkin import CheckinLogOut, CheckinResultItem, CheckinResponse


class ExiliumBindPasswordRequest(BaseModel):
    account: str = Field(min_length=5, max_length=128)
    password: str = Field(min_length=4, max_length=128)


class ExiliumBindSmsSendRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    graph_code: str | None = Field(default=None, max_length=16)


class ExiliumBindSmsSendResponse(BaseModel):
    ok: bool = True
    message: str = "验证码已发送"
    need_graph_captcha: bool = False
    graph_captcha_image: str | None = None


class ExiliumBindSmsRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    captcha: str = Field(min_length=4, max_length=8)


class ExiliumBindUpdate(BaseModel):
    auto_checkin: bool | None = None
    checkin_hour: int | None = Field(default=None, ge=0, le=23)
    checkin_minute: int | None = Field(default=None, ge=0, le=59)


class ExiliumRoleOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    channel_name: str


ExiliumCheckinLogOut = CheckinLogOut
ExiliumCheckinResultItem = CheckinResultItem
ExiliumCheckinResponse = CheckinResponse


class ExiliumStatusOut(BaseModel):
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
    roles: list[ExiliumRoleOut] = Field(default_factory=list)
    today_results: list[CheckinResultItem] = Field(default_factory=list)
    today_logs: list[CheckinLogOut] = Field(default_factory=list)

class ExiliumExchangeItemOut(BaseModel):
    exchange_id: int
    item_name: str
    item_count: int = 1
    item_pic: str = ""
    item_context: str = ""
    use_score: int = 0
    exchange_count: int = 0
    max_exchange_count: int = 0
    cycle: str = "day"
    remain_seconds: int | None = None


class ExiliumExchangeShopOut(BaseModel):
    score: int = 0
    items: list[ExiliumExchangeItemOut] = Field(default_factory=list)


class ExiliumExchangeRequest(BaseModel):
    exchange_id: int = Field(ge=1)


class ExiliumExchangeResultOut(BaseModel):
    ok: bool = True
    message: str = ""
    score: int | None = None
    item: ExiliumExchangeItemOut | None = None


class ExiliumScoreLogItemOut(BaseModel):
    score: int = 0
    reason: str = ""
    log_time: str = ""


class ExiliumScoreLogOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[ExiliumScoreLogItemOut] = Field(
        default_factory=list,
        alias="list",
        serialization_alias="list",
    )
    total: int = 0
    page: int = 1
    page_size: int = 50
