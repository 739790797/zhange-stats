from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.checkin import CheckinAwardItem, CheckinResultItem


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


class EndfieldOperatorOut(BaseModel):
    char_id: str
    name: str
    rarity: int
    profession: str
    profession_label: str
    sort_order: int


class EndfieldCompareCandidateOut(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None = None
    game_role_name: str | None = None
    is_self: bool = False
    skland_bound: bool = False


class EndfieldCompareRoleOut(BaseModel):
    uid: str
    role_name: str
    channel_name: str = ""


class EndfieldCompareRowOut(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None = None
    status: str
    message: str | None = None
    uid: str | None = None
    role_name: str | None = None
    channel_name: str | None = None
    player_level: int | None = None
    synced_at: str | None = None
    char_count: int = 0
    owned: dict[str, EndfieldCharOut] = Field(default_factory=dict)
    roles: list[EndfieldCompareRoleOut] = Field(default_factory=list)


class EndfieldBoxCompareOut(BaseModel):
    catalog: list[EndfieldOperatorOut] = Field(default_factory=list)
    catalog_count: int = 0
    rows: list[EndfieldCompareRowOut] = Field(default_factory=list)


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
    token_ok: bool | None = None
    token_error: str | None = None
    roles: list[SklandRoleOut] = Field(default_factory=list)
    today_results: list[CheckinResultItem] = Field(default_factory=list)


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


class EndfieldAttendanceCalendarOut(ArknightsAttendanceCalendarOut):
    """终末地签到周期日历（字段同方舟）。"""


class InnDishRec(BaseModel):
    id: str
    name: str
    category: str
    category_name: str
    affix_ids: list[str] = Field(default_factory=list)
    affixes: list[str] = Field(default_factory=list)
    price: int = 0
    cook_seconds: int = 0
    ingredients: list[str] = Field(default_factory=list)
    unlock_level: int = 1
    unlock_topic_id: str = ""
    unlock_topic_star_num: int = 0
    unlocked: bool = True
    unlock_conditions: list[str] = Field(default_factory=list)


class InnMenuGroup(BaseModel):
    requirement_id: str
    text: str
    food_type: int = 1
    need: int = 0
    dishes: list[InnDishRec] = Field(default_factory=list)
    missing: int = 0


class InnChefRec(BaseModel):
    char_id: str
    name: str
    kitchen_index: int | None = None
    slot_label: str = ""
    notes: list[str] = Field(default_factory=list)


class InnChefTag(BaseModel):
    id: str
    label: str


class InnChefCatalogRec(BaseModel):
    char_id: str
    name: str
    tags: list[InnChefTag] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class InnObjectivePart(BaseModel):
    kind: Literal["text", "icon"]
    value: str


class InnStarOut(BaseModel):
    private_chef: bool = False
    star_scores: list[int] = Field(default_factory=list)
    kpi_cap: float = 0
    profit_cap: float = 0
    needs_objective: bool = False
    objective: str = ""
    objective_parts: list[InnObjectivePart] = Field(default_factory=list)
    estimate: str = ""


class InnTopicBrief(BaseModel):
    id: str
    name: str
    unlock_level: int = 1
    private_chef: bool = False


class InnExpansionBrief(BaseModel):
    id: str
    name: str
    unlock_level: int = 1
    cost: int = 0
    add_kitchen_num: int = 0
    add_kitchen_char_num: int = 0
    prerequisite_id: str = ""


class InnBonusTier(BaseModel):
    tier: int
    rare_rate_bonus: float


class InnTopicsOut(BaseModel):
    topics: list[InnTopicBrief] = Field(default_factory=list)
    expansions: list[InnExpansionBrief] = Field(default_factory=list)
    jsspsi_bonus_tiers: list[InnBonusTier] = Field(default_factory=list)


class InnQueryIn(BaseModel):
    level: int = Field(ge=1, le=4)
    expansions: list[str] = Field(default_factory=list, max_length=16)
    topic_id: str | None = Field(default=None, max_length=64)
    topic_stars: dict[str, int] = Field(default_factory=dict)
    jsspsi_bonus_tier: int = Field(default=1, ge=1, le=3)


class InnRecommendationsOut(BaseModel):
    topic_id: str
    topic_name: str
    menu: list[InnMenuGroup] = Field(default_factory=list)
    chefs: list[InnChefRec] = Field(default_factory=list)
    star: InnStarOut


class InnQueryOut(BaseModel):
    level: int
    topic_id: str | None = None
    kitchen_count: int = 1
    chef_slot_count: int = 1
    jsspsi_bonus_tier: int = 1
    jsspsi_rare_rate_bonus: float = 0
    dishes: list[InnDishRec] = Field(default_factory=list)
    drinks: list[InnDishRec] = Field(default_factory=list)
    chef_catalog: list[InnChefCatalogRec] = Field(default_factory=list)
    recommendations: InnRecommendationsOut | None = None


class InnPlanOut(BaseModel):
    topic_id: str
    topic_name: str
    level: int
    menu: list[InnMenuGroup] = Field(default_factory=list)
    chefs: list[InnChefRec] = Field(default_factory=list)
    star: InnStarOut


class GameScheduleEventOut(BaseModel):
    """game-schedule 活动条目（进行中 / 未开始）。"""

    id: str
    game: str
    title: str
    start_time: str
    end_time: str
    status: str
    banner: str | None = None
    link_url: str | None = None
    event_type: str | None = None


class GameScheduleCalendarOut(BaseModel):
    """明日方舟 / 终末地活动日历（代理 game-schedule）。"""

    game: str
    source: str = "game-schedule"
    synced_at: str | None = None
    stale: bool = False
    ongoing_count: int = 0
    upcoming_count: int = 0
    permanent_count: int = 0
    events: list[GameScheduleEventOut] = Field(default_factory=list)
    # 跨度过长的常驻/新手活动：单独列表，不进时间轴
    permanent_events: list[GameScheduleEventOut] = Field(default_factory=list)


class ArknightsRogueTopicOut(BaseModel):
    topic_id: str
    name: str
    selected: bool = False
    pic: str | None = None


class ArknightsRogueCharOut(BaseModel):
    char_id: str
    name: str
    rarity: int = 0
    level: int = 0
    evolve_phase: int = 0
    profession: str = ""


class ArknightsRogueRecordOut(BaseModel):
    record_id: str
    mode: str = ""
    mode_grade: int = 0
    success: bool = False
    score: int = 0
    ending_text: str = ""
    start_ts: str = ""
    end_ts: str = ""
    zone_count: int = 0
    node_count: int = 0
    relic_count: int = 0
    band_name: str = ""
    last_stage: str = ""
    is_collect: bool = False
    squad: list[ArknightsRogueCharOut] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ArknightsRogueOverviewOut(BaseModel):
    mode: str = ""
    mode_grade: int = 0
    score: int = 0
    bp_level: int = 0
    medal_current: int = 0
    medal_count: int = 0
    clear_difficulty: str = ""
    clear_grade: int = 0
    invest: int = 0
    relic: int = 0
    game_count: int = 0


class ArknightsRogueOut(BaseModel):
    uid: str
    role_name: str
    channel_name: str
    topic_id: str
    topic_name: str
    topics: list[ArknightsRogueTopicOut] = Field(default_factory=list)
    overview: ArknightsRogueOverviewOut
    records: list[ArknightsRogueRecordOut] = Field(default_factory=list)
    favour_records: list[ArknightsRogueRecordOut] = Field(default_factory=list)
    roles: list[SklandRoleOut] = Field(default_factory=list)
    synced_at: str | None = None
    stale: bool = False

