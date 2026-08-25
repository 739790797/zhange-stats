from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import OrmModel


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
    steam_bound: bool = False
    skland_bound: bool = False
    taygedo_bound: bool = False
    exilium_bound: bool = False
    kujiequ_bound: bool = False
    mihoyo_bound: bool = False
    qq_bound: bool = False


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
    role: str | None = Field(default=None, description="user | admin")
    is_admin: bool | None = None


class MemberProfileOut(BaseModel):
    member_id: int
    nickname: str
    avatar_url: str | None
    steam_id: str | None
    steam_persona_name: str | None = None
    steam_avatar_url: str | None = None
    skland_bound: bool = False
    skland_auto_checkin: bool | None = None
    taygedo_bound: bool = False
    taygedo_auto_checkin: bool | None = None
    taygedo_phone_mask: str | None = None
    exilium_bound: bool = False
    exilium_auto_checkin: bool | None = None
    exilium_phone_mask: str | None = None
    kujiequ_bound: bool = False
    kujiequ_auto_checkin: bool | None = None
    kujiequ_phone_mask: str | None = None
    mihoyo_bound: bool = False
    mihoyo_auto_checkin: bool | None = None
    mihoyo_phone_mask: str | None = None
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
