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
    password: str = Field(min_length=6, max_length=72)
    steam_id: str | None = Field(default=None, max_length=512)


class UserAdminUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=6, max_length=72)
    steam_id: str | None = Field(default=None, max_length=512)


class MemberProfileOut(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None
    steam_id: str | None
    steam_persona_name: str | None = None
    steam_friends_public: bool | None = None
    steam_friends_synced_at: datetime | None = None
    cs2_auth_code: str | None = None
    cs2_known_code: str | None = None
    cs2_sync_ready: bool = False
    user_id: int | None = None
    username: str | None = None
    email: str | None = None
    display_name: str | None = None
    joined_at: datetime


class MemberProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    steam_id: str | None = Field(default=None, max_length=512)
    cs2_auth_code: str | None = Field(default=None, max_length=64)
    cs2_known_code: str | None = Field(default=None, max_length=64)


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
    visibility: SteamVisibilityMeta | None = None


class SteamDaySessionItem(BaseModel):
    id: int
    member_id: int
    member_nickname: str
    avatar_url: str | None
    steam_app_id: str
    game_name: str
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


class SteamDayResponse(BaseModel):
    date: str
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
    started_at: datetime
    last_seen_at: datetime
    duration_seconds: int


class SteamFriendItem(BaseModel):
    steam_id: str
    persona_name: str
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


class Cs2PlayerStats(BaseModel):
    kills: int = 0
    deaths: int = 0
    kd_ratio: float | None = None
    wins: int = 0
    mvps: int = 0
    headshot_kills: int = 0
    headshot_pct: float | None = None
    accuracy_pct: float | None = None
    time_played_seconds: int = 0
    planted_bombs: int = 0
    defused_bombs: int = 0
    shots_fired: int = 0
    shots_hit: int = 0


class Cs2PlayerRow(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None = None
    steam_id: str | None = None
    status: str
    message: str | None = None
    stats: Cs2PlayerStats | None = None


class Cs2OverviewResponse(BaseModel):
    app_id: int
    member_count: int
    steam_bound_count: int
    ok_count: int
    players: list[Cs2PlayerRow]


class Cs2MatchPlayerOut(BaseModel):
    steam_id: str
    member_id: int | None = None
    nickname: str | None = None
    avatar_url: str | None = None
    team: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    mvps: int | None = None
    score: int | None = None
    damage: int | None = None
    won: bool | None = None
    persona_name: str | None = None


class Cs2MatchOut(BaseModel):
    match_id: str
    share_code: str | None = None
    map_name: str | None = None
    played_at: datetime | None = None
    score_team0: int | None = None
    score_team1: int | None = None
    demo_url: str | None = None
    enriched: bool = False
    my_stats: Cs2MatchPlayerOut | None = None
    players: list[Cs2MatchPlayerOut] = []


class Cs2TogetherMatchOut(BaseModel):
    match_id: str
    share_code: str | None = None
    map_name: str | None = None
    played_at: datetime | None = None
    score_team0: int | None = None
    score_team1: int | None = None
    enriched: bool = False
    circled_players: list[Cs2MatchPlayerOut] = []


class Cs2SyncResult(BaseModel):
    status: str
    message: str | None = None
    stats: dict[str, Any] | None = None
