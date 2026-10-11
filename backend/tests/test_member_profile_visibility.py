"""GET /api/members/{id}/profile：本人与管理员看全量；其他登录用户只拿显示名、头像、是否已绑与 Steam 公开资料。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.profile import member_profile
from app.core.database import Base, get_db
from app.core.security import create_user_access_token
from app.models.exilium import ExiliumBind
from app.models.kujiequ import KujiequBind
from app.models.mihoyo import MihoyoBind
from app.models.skland import SklandBind
from app.models.taygedo import TaygedoBind
from app.models.user import User, UserRole
from app.schemas import MemberProfileOut
from app.services.member_sync import ensure_user_member

PUBLIC_FIELDS = {
    "member_id",
    "nickname",
    "avatar_url",
    "steam_persona_name",
    "steam_avatar_url",
    "skland_bound",
    "taygedo_bound",
    "exilium_bound",
    "kujiequ_bound",
    "mihoyo_bound",
    "qq_bound",
    "display_name",
    "joined_at",
}

PRIVATE_VALUES = {
    "steam_id": "76561198000000001",
    "skland_auto_checkin": True,
    "taygedo_auto_checkin": True,
    "taygedo_phone_mask": "138****0001",
    "exilium_auto_checkin": True,
    "exilium_phone_mask": "138****0002",
    "kujiequ_auto_checkin": False,
    "kujiequ_phone_mask": "138****0003",
    "mihoyo_auto_checkin": True,
    "mihoyo_phone_mask": "138****0004",
    "qq_nickname": "owner-qq",
    "qq_avatar_url": "https://q.qlogo.cn/owner.png",
    "username": "owner_login",
    "email": "owner@example.com",
}
PRIVATE_FIELDS = set(PRIVATE_VALUES) | {"user_id"}


def _user(db, username: str, role: UserRole, email: str | None = None) -> User:
    user = User(
        username=username,
        email=email,
        display_name=f"{username}-shown",
        password_hash="unused",
        role=role,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    def _db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    api = FastAPI()
    api.include_router(member_profile.router, prefix="/api")
    api.dependency_overrides[get_db] = _db

    with SessionLocal() as db:
        owner = _user(db, "owner_login", UserRole.user, email="owner@example.com")
        stranger = _user(db, "stranger", UserRole.user, email="stranger@example.com")
        admin = _user(db, "boss", UserRole.admin, email="boss@example.com")
        member = ensure_user_member(db, owner)
        member.avatar_url = "/uploads/avatars/1.jpg"
        member.steam_id = PRIVATE_VALUES["steam_id"]
        member.steam_persona_name = "OwnerOnSteam"
        member.steam_avatar_url = "https://avatars.steamstatic.com/owner.jpg"
        member.qq_openid = "OPENID-OWNER"
        member.qq_nickname = PRIVATE_VALUES["qq_nickname"]
        member.qq_avatar_url = PRIVATE_VALUES["qq_avatar_url"]
        db.add_all(
            [
                SklandBind(member_id=member.id, token_enc="x", auto_checkin=True),
                TaygedoBind(
                    member_id=member.id,
                    credentials_enc="x",
                    auto_checkin=True,
                    phone_mask=PRIVATE_VALUES["taygedo_phone_mask"],
                ),
                ExiliumBind(
                    member_id=member.id,
                    credentials_enc="x",
                    auto_checkin=True,
                    phone_mask=PRIVATE_VALUES["exilium_phone_mask"],
                ),
                KujiequBind(
                    member_id=member.id,
                    credentials_enc="x",
                    auto_checkin=False,
                    phone_mask=PRIVATE_VALUES["kujiequ_phone_mask"],
                ),
                MihoyoBind(
                    member_id=member.id,
                    credentials_enc="x",
                    auto_checkin=True,
                    phone_mask=PRIVATE_VALUES["mihoyo_phone_mask"],
                ),
            ]
        )
        db.commit()
        tokens = {
            "owner": create_user_access_token(owner),
            "stranger": create_user_access_token(stranger),
            "admin": create_user_access_token(admin),
        }
        ids = {"member": member.id, "owner": owner.id}
    yield TestClient(api), tokens, ids
    engine.dispose()


def _profile(client: TestClient, token: str | None, member_id: int):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(f"/api/members/{member_id}/profile", headers=headers)


def test_every_profile_field_is_classified() -> None:
    assert PUBLIC_FIELDS | PRIVATE_FIELDS == set(MemberProfileOut.model_fields)
    assert not PUBLIC_FIELDS & PRIVATE_FIELDS


@pytest.mark.parametrize("field", sorted(PRIVATE_FIELDS))
def test_other_members_do_not_see_private_field(env, field: str) -> None:
    client, tokens, ids = env
    res = _profile(client, tokens["stranger"], ids["member"])
    assert res.status_code == 200
    assert res.json()[field] is None


def test_other_members_still_see_public_fields(env) -> None:
    client, tokens, ids = env
    body = _profile(client, tokens["stranger"], ids["member"]).json()
    assert {k: body[k] for k in PUBLIC_FIELDS - {"joined_at"}} == {
        "member_id": ids["member"],
        "nickname": "owner_login-shown",
        "avatar_url": "/uploads/avatars/1.jpg",
        "steam_persona_name": "OwnerOnSteam",
        "steam_avatar_url": "https://avatars.steamstatic.com/owner.jpg",
        "skland_bound": True,
        "taygedo_bound": True,
        "exilium_bound": True,
        "kujiequ_bound": True,
        "mihoyo_bound": True,
        "qq_bound": True,
        "display_name": "owner_login-shown",
    }
    assert body["joined_at"]


@pytest.mark.parametrize("viewer", ["owner", "admin"])
def test_owner_and_admin_see_every_private_field(env, viewer: str) -> None:
    client, tokens, ids = env
    res = _profile(client, tokens[viewer], ids["member"])
    assert res.status_code == 200
    body = res.json()
    assert {k: body[k] for k in PRIVATE_VALUES} == PRIVATE_VALUES
    assert body["user_id"] == ids["owner"]


def test_profile_needs_login_and_an_existing_member(env) -> None:
    client, tokens, ids = env
    assert _profile(client, None, ids["member"]).status_code == 401
    assert _profile(client, tokens["stranger"], ids["member"] + 999).status_code == 404
