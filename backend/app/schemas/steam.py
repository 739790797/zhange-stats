from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    mode: str = "site_members"
    self_member_id: int
    steam_bound: bool
    visible_member_count: int = 0
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
