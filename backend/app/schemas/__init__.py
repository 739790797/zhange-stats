from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth ----
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(OrmModel):
    id: int
    username: str
    email: str | None = None
    display_name: str
    role: str
    is_admin: bool
    email_verified: bool = False
    avatar_url: str | None = None
    steam_id: str | None = None
    created_at: datetime


# ---- Member ----
class MemberOut(OrmModel):
    id: int
    nickname: str
    avatar_url: str | None
    user_id: int | None
    joined_at: datetime


class UserBrief(OrmModel):
    id: int
    username: str
    email: str | None = None
    display_name: str
    role: str
    is_admin: bool
    email_verified: bool = False
    member_id: int | None = None
    steam_id: str | None = None


class UserAdminCreate(BaseModel):
    email: str = Field(min_length=3, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=72)
    steam_id: str | None = Field(default=None, max_length=512)


class UserAdminUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    steam_id: str | None = Field(default=None, max_length=512)


class MemberProfileOut(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None
    steam_id: str | None
    steam_persona_name: str | None = None
    steam_friends_public: bool | None = None
    steam_friends_synced_at: datetime | None = None
    skland_bound: bool = False
    skland_auto_checkin: bool | None = None
    taygedo_bound: bool = False
    taygedo_auto_checkin: bool | None = None
    taygedo_phone_mask: str | None = None
    exilium_bound: bool = False
    exilium_auto_checkin: bool | None = None
    exilium_phone_mask: str | None = None
    qq_bound: bool = False
    qq_nickname: str | None = None
    qq_avatar_url: str | None = None
    user_id: int | None = None
    username: str | None = None
    email: str | None = None
    display_name: str | None = None
    joined_at: datetime


class MemberProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    steam_id: str | None = Field(default=None, max_length=512)


class QqOAuthStartResponse(BaseModel):
    url: str


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
    auto_checkin: bool


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


class SklandStatusOut(BaseModel):
    bound: bool
    auto_checkin: bool | None = None
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
    auto_checkin: bool


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
    phone_mask: str | None = None
    bound_at: datetime | None = None
    last_checkin_at: datetime | None = None
    last_checkin_date: str | None = None
    last_checkin_ok: bool | None = None
    last_checkin_summary: str | None = None
    token_ok: bool | None = None
    token_error: str | None = None
    roles: list[TaygedoRoleOut] = Field(default_factory=list)
    today_results: list[CheckinResultItem] = Field(default_factory=list)
    today_logs: list[CheckinLogOut] = Field(default_factory=list)


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
    auto_checkin: bool


class ExiliumRoleOut(BaseModel):
    game_code: str
    game_name: str
    uid: str
    role_name: str
    channel_name: str


ExiliumCheckinResultItem = CheckinResultItem
ExiliumCheckinResponse = CheckinResponse


class ExiliumStatusOut(BaseModel):
    bound: bool
    auto_checkin: bool | None = None
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


class SteamBindPreviewRequest(BaseModel):
    steam_input: str = Field(min_length=1, max_length=512)


class SteamBindPreviewResponse(BaseModel):
    steam_id: str
    persona_name: str | None = None
    avatar_url: str | None = None
    profile_url: str | None = None
    is_public: bool
    privacy_label: str
    message: str | None = None


class SteamOpenIdStartResponse(BaseModel):
    url: str


# ---- Steam / Play sessions ----
class SteamCalendarCell(BaseModel):
    date: str
    total_seconds: int
    session_count: int


class SteamCalendarMemberSeries(BaseModel):
    member_id: int
    member_nickname: str
    avatar_url: str | None = None
    total_seconds: int = 0
    cells: list[SteamCalendarCell] = Field(default_factory=list)


class SteamVisibilityMeta(BaseModel):
    mode: str = "steam_friends"
    self_member_id: int
    steam_bound: bool
    friends_list_public: bool | None = None
    friends_synced_at: datetime | None = None
    visible_friend_count: int = 0
    hint: str | None = None


class SteamCalendarResponse(BaseModel):
    granularity: str
    range_start: str
    range_end: str
    cells: list[SteamCalendarCell]
    total_seconds: int
    members: list[SteamCalendarMemberSeries] = Field(default_factory=list)
    visibility: SteamVisibilityMeta | None = None


class SteamDaySessionItem(BaseModel):
    id: int
    member_id: int
    member_nickname: str
    avatar_url: str | None
    steam_app_id: str
    game_name: str
    icon_url: str | None = None
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None
    duration_seconds: int
    is_ongoing: bool


class SteamDayMemberSummary(BaseModel):
    member_id: int
    member_nickname: str
    avatar_url: str | None
    total_seconds: int
    games: list[str]


class SteamTimelineSegment(BaseModel):
    status: str  # offline | online | playing
    steam_app_id: str | None = None
    game_name: str | None = None
    icon_url: str | None = None
    start_sec: int
    end_sec: int


class SteamTimelineRow(BaseModel):
    member_id: int
    member_nickname: str
    avatar_url: str | None
    segments: list[SteamTimelineSegment]


class SteamGameLegendItem(BaseModel):
    steam_app_id: str
    game_name: str
    icon_url: str | None = None


class SteamDayResponse(BaseModel):
    date: str
    range_start: str | None = None
    range_end: str | None = None
    span_seconds: int = 86400
    sessions: list[SteamDaySessionItem]
    by_member: list[SteamDayMemberSummary]
    total_seconds: int
    timeline: list[SteamTimelineRow] = Field(default_factory=list)
    games_legend: list[SteamGameLegendItem] = Field(default_factory=list)
    visibility: SteamVisibilityMeta | None = None


class SteamNowItem(BaseModel):
    id: int
    member_id: int
    member_nickname: str
    avatar_url: str | None
    steam_app_id: str
    game_name: str
    icon_url: str | None = None
    started_at: datetime
    last_seen_at: datetime
    duration_seconds: int


class SteamFriendItem(BaseModel):
    steam_id: str
    persona_name: str
    steam_persona_name: str | None = None
    friend_nickname: str | None = None
    avatar_url: str | None = None
    profile_url: str | None = None
    status: str  # offline | online | playing
    game_name: str | None = None
    steam_app_id: str | None = None
    friend_since: int | None = None
    member_id: int | None = None
    is_registered: bool = False


class SteamFriendsResponse(BaseModel):
    steam_bound: bool
    friends_list_public: bool | None = None
    friends_synced_at: datetime | None = None
    friend_count: int = 0
    sync_ok: bool = True
    synced: bool = False
    sync_interval_seconds: int = 900
    hint: str | None = None
    friends: list[SteamFriendItem] = Field(default_factory=list)


class SteamPollResult(BaseModel):
    status: str
    message: str | None = None
    stats: dict[str, Any] | None = None


class SteamAppStoreCard(BaseModel):
    steam_app_id: str
    name: str | None = None
    header_image: str | None = None
    capsule_image: str | None = None
    icon_url: str | None = None
    short_description: str | None = None
    is_free: bool = False
    currency: str | None = None
    initial_price: int | None = None
    final_price: int | None = None
    discount_percent: int = 0
    initial_formatted: str | None = None
    final_formatted: str | None = None
    store_url: str


class SteamAppIcon(BaseModel):
    steam_app_id: str
    icon_url: str | None = None


class SteamSessionBrief(BaseModel):
    id: int
    member_id: int
    member_nickname: str
    avatar_url: str | None = None
    steam_app_id: str
    game_name: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int
    is_ongoing: bool = False


class SteamOverviewResponse(BaseModel):
    member_count: int
    steam_bound_count: int
    week_play_seconds: int
    now_playing: list[SteamNowItem]
    recent_sessions: list[SteamSessionBrief]
    visibility: SteamVisibilityMeta | None = None


class PlayTrendPoint(BaseModel):
    date: str
    total_seconds: int
    session_count: int


class MemberPlayMember(BaseModel):
    id: int
    nickname: str
    avatar_url: str | None
    user_id: int | None
    joined_at: datetime
    steam_id: str | None = None


class MemberPlayStatsResponse(BaseModel):
    member: MemberPlayMember
    week_play_seconds: int
    month_play_seconds: int
    session_count: int
    trend: list[PlayTrendPoint]
    recent_sessions: list[SteamSessionBrief]
