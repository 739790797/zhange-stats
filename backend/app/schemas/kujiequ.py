from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.checkin import CheckinLogOut, CheckinResultItem, CheckinResponse


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

