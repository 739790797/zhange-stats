from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.checkin import CheckinAwardItem, CheckinLogOut, CheckinResultItem


class SklandBindRequest(BaseModel):
    token: str = Field(min_length=8, max_length=4096)


class SklandBindPasswordRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class SklandBindSmsSendRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=32)


class SklandBindSmsSendResponse(BaseModel):
    message: str = "验证码已发送"


class SklandBindSmsRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    code: str = Field(min_length=4, max_length=16)


class SklandBindUpdate(BaseModel):
    auto_checkin: bool | None = None
    checkin_hour: int | None = Field(default=None, ge=0, le=23)
    checkin_minute: int | None = Field(default=None, ge=0, le=59)


class SklandRoleOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    channel_name: str


class ArknightsCharSkillOut(BaseModel):
    skill_id: str = ""
    specialize_level: int = 0
    label: str = ""


class ArknightsCharEquipOut(BaseModel):
    equip_id: str = ""
    name: str = ""
    level: int = 1
    type_icon: str = ""
    locked: bool = False


class ArknightsCharOut(BaseModel):
    char_id: str
    name: str
    rarity: int
    profession: str
    profession_label: str
    level: int
    evolve_phase: int
    potential_rank: int
    favor_percent: int | None = None
    skin_id: str | None = None
    avatar_url: str | None = None
    obtain_ts: int | None = None
    main_skill_lvl: int = 1
    skills: list[ArknightsCharSkillOut] = Field(default_factory=list)
    equips: list[ArknightsCharEquipOut] = Field(default_factory=list)


class ArknightsBoxOut(BaseModel):
    uid: str
    name: str
    level: int
    register_ts: int | None = None
    ap_current: int | None = None
    ap_max: int | None = None
    char_count: int
    channel_name: str | None = None
    role_name: str | None = None
    chars: list[ArknightsCharOut] = Field(default_factory=list)
    roles: list[SklandRoleOut] = Field(default_factory=list)


class EndfieldEquipOut(BaseModel):
    slot: str
    item_id: str = ""
    name: str = ""
    icon_url: str | None = None
    rarity: int = 1
    level: int | None = None
    refine_level: int | None = None


class EndfieldSkillOut(BaseModel):
    skill_id: str = ""
    name: str = ""
    skill_type: str = ""
    type_label: str = ""
    icon_url: str | None = None
    level: int = 1
    max_level: int = 0


class EndfieldWeaponOut(BaseModel):
    weapon_id: str = ""
    name: str = ""
    icon_url: str | None = None
    rarity: int = 1
    level: int = 1
    refine_level: int = 0
    breakthrough_level: int = 0
    weapon_type: str = ""
    gem_id: str = ""
    gem_name: str = ""
    gem_icon_url: str | None = None


class EndfieldCharOut(BaseModel):
    char_id: str
    name: str
    rarity: int
    level: int
    evolve_phase: int = 0
    potential_level: int = 0
    profession: str = ""
    property_name: str = ""
    weapon_type: str = ""
    label_type: str = ""
    own_ts: int | None = None
    gender: str = ""
    avatar_url: str | None = None
    illustration_url: str | None = None
    property_icon_url: str | None = None
    weapon: EndfieldWeaponOut | None = None
    skills: list[EndfieldSkillOut] = Field(default_factory=list)
    equips: list[EndfieldEquipOut] = Field(default_factory=list)


class EndfieldBoxOut(BaseModel):
    uid: str
    role_id: str = ""
    server_id: str = ""
    name: str
    level: int
    server_name: str | None = None
    avatar_url: str | None = None
    char_count: int
    chars: list[EndfieldCharOut] = Field(default_factory=list)
    roles: list[SklandRoleOut] = Field(default_factory=list)
    synced_at: str | None = None
    stale: bool = False


class ArknightsOperatorOut(BaseModel):
    char_id: str
    name: str
    rarity: int
    profession: str
    profession_label: str
    avatar_url: str | None = None


class ArknightsCatalogOut(BaseModel):
    operators: list[ArknightsOperatorOut] = Field(default_factory=list)
    operator_count: int = 0
    source_version: str | None = None
    synced_at: str | None = None


class ArknightsCatalogSyncOut(BaseModel):
    operator_count: int
    source_version: str | None = None
    synced_at: str | None = None


class ArknightsOwnedCharOut(BaseModel):
    level: int = 0
    evolve_phase: int = 0
    potential_rank: int = 0
    favor_percent: int | None = None
    skin_id: str | None = None
    avatar_url: str | None = None
    main_skill_lvl: int = 1
    skills: list[ArknightsCharSkillOut] = Field(default_factory=list)
    equips: list[ArknightsCharEquipOut] = Field(default_factory=list)


class ArknightsCompareRoleOut(BaseModel):
    uid: str
    role_name: str
    channel_name: str


class ArknightsCompareRowOut(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None = None
    status: str  # ok | unbound | error | missing
    message: str | None = None
    uid: str | None = None
    role_name: str | None = None
    channel_name: str | None = None
    player_name: str | None = None
    player_level: int | None = None
    char_count: int = 0
    owned: dict[str, ArknightsOwnedCharOut] = Field(default_factory=dict)
    roles: list[ArknightsCompareRoleOut] = Field(default_factory=list)


class ArknightsBoxCompareOut(BaseModel):
    catalog: list[ArknightsOperatorOut] = Field(default_factory=list)
    catalog_version: str | None = None
    catalog_synced_at: str | None = None
    rows: list[ArknightsCompareRowOut] = Field(default_factory=list)


class ArknightsCompareCandidateOut(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None = None
    is_self: bool = False
    skland_bound: bool = False


class SklandStatusOut(BaseModel):
    bound: bool
    auto_checkin: bool | None = None
    checkin_hour: int | None = None
    checkin_minute: int | None = None
    bound_at: datetime | None = None
    last_checkin_at: datetime | None = None
    last_checkin_date: str | None = None
    last_checkin_ok: bool | None = None
    last_checkin_summary: str | None = None
    token_ok: bool | None = None
    token_error: str | None = None
    roles: list[SklandRoleOut] = Field(default_factory=list)
    today_results: list[CheckinResultItem] = Field(default_factory=list)
    # 兼容旧字段名（前端已切 today_results）
    today_logs: list[CheckinLogOut] = Field(default_factory=list)


class SklandQrStartResponse(BaseModel):
    scan_id: str
    scan_url: str
    qr_image: str
    expires_in: int = 180


class SklandQrPollResponse(BaseModel):
    status: str  # waiting | scanned | ok | expired | error
    message: str
    bound: bool = False
    auto_checkin: bool | None = None
    roles: list[SklandRoleOut] = Field(default_factory=list)


class ArknightsAttendanceDayOut(BaseModel):
    """签到周期第 N 天（非公历日期）。"""

    day: int
    claimed: bool
    awards: list[CheckinAwardItem] = Field(default_factory=list)


class ArknightsAttendanceCalendarOut(BaseModel):
    uid: str
    role_name: str
    channel_name: str
    claimed_days: int = 0
    total_days: int = 0
    has_today_claim: bool = False
    # 上游是否返回可信领取进度（B 服等常为 false）
    progress_reliable: bool = True
    days: list[ArknightsAttendanceDayOut] = Field(default_factory=list)
    roles: list[SklandRoleOut] = Field(default_factory=list)
    synced_at: str | None = None
    stale: bool = False

