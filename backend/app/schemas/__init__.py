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


class UserRoleUpdate(BaseModel):
    role: str = Field(pattern="^(user|admin)$")


class MemberProfileOut(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None
    steam_id: str | None
    user_id: int | None = None
    username: str | None = None
    email: str | None = None
    display_name: str | None = None
    joined_at: datetime


class MemberProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    steam_id: str | None = Field(default=None, max_length=32)


# ---- Steam / Play sessions ----
class SteamCalendarCell(BaseModel):
    date: str
    total_seconds: int
    session_count: int


class SteamCalendarResponse(BaseModel):
    granularity: str
    range_start: str
    range_end: str
    cells: list[SteamCalendarCell]
    total_seconds: int


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


class SteamDayResponse(BaseModel):
    date: str
    sessions: list[SteamDaySessionItem]
    by_member: list[SteamDayMemberSummary]
    total_seconds: int


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
