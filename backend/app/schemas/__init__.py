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
    display_name: str
    is_admin: bool
    created_at: datetime


# ---- Member ----
class MemberCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)
    avatar_url: str | None = None
    user_id: int | None = None


class MemberUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    avatar_url: str | None = None
    user_id: int | None = None


class MemberOut(OrmModel):
    id: int
    nickname: str
    avatar_url: str | None
    user_id: int | None
    joined_at: datetime


# ---- Game ----
class GameCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    platform: str = Field(default="", max_length=64)
    icon_url: str | None = None


class GameUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    platform: str | None = None
    icon_url: str | None = None


class GameOut(OrmModel):
    id: int
    name: str
    platform: str
    icon_url: str | None
    created_at: datetime


# ---- Match Record ----
class RecordCreate(BaseModel):
    member_id: int
    game_id: int
    played_at: datetime
    result: str = "unknown"
    mode: str | None = None
    stats: dict[str, Any] | None = None
    raw_text: str | None = None
    source: str = "manual"


class RecordUpdate(BaseModel):
    member_id: int | None = None
    game_id: int | None = None
    played_at: datetime | None = None
    result: str | None = None
    mode: str | None = None
    stats: dict[str, Any] | None = None
    raw_text: str | None = None


class RecordOut(OrmModel):
    id: int
    member_id: int
    game_id: int
    played_at: datetime
    result: str
    mode: str | None
    stats: dict[str, Any] | None
    raw_text: str | None
    source: str
    created_at: datetime
    member_nickname: str | None = None
    game_name: str | None = None


# ---- Stats ----
class RecentRecordItem(BaseModel):
    id: int
    member_nickname: str
    game_name: str
    result: str
    played_at: datetime
    mode: str | None = None


class WeekStarItem(BaseModel):
    member_id: int
    member_nickname: str
    wins: int
    total: int
    win_rate: float


class WinRateOverview(BaseModel):
    total_matches: int
    wins: int
    losses: int
    draws: int
    win_rate: float


class OverviewResponse(BaseModel):
    recent_records: list[RecentRecordItem]
    week_star: WeekStarItem | None
    win_rate: WinRateOverview


class LeaderboardItem(BaseModel):
    rank: int
    member_id: int
    member_nickname: str
    avatar_url: str | None
    wins: int
    losses: int
    draws: int
    total: int
    win_rate: float


class LeaderboardResponse(BaseModel):
    items: list[LeaderboardItem]
    game_id: int | None
    range: str


class TrendPoint(BaseModel):
    date: str
    wins: int
    total: int
    win_rate: float


class MemberStatsResponse(BaseModel):
    member: MemberOut
    total_matches: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    recent_records: list[RecentRecordItem]
    trend: list[TrendPoint]
