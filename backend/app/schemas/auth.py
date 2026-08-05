from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import OrmModel


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

