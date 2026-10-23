from __future__ import annotations

import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.core.deps import get_current_user
from app.core.timeutil import now_naive
from app.models.endfield import EndfieldAttendanceRaw, EndfieldBoxRaw
from app.models.member import Member
from app.models.skland import SklandBind
from app.models.user import User, UserRole
from app.services.skland import endfield_box_compare as compare
from app.services.skland.boxes import parse_endfield_box
from app.services.skland.endfield_catalog import parse_character_tables


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    yield session
    session.close()
    engine.dispose()


def _member(db, name: str, *, bound: bool = True) -> tuple[User, Member]:
    user = User(username=name, display_name=name, password_hash="x", role=UserRole.user)
    db.add(user)
    db.flush()
    member = Member(
        nickname=name,
        user_id=user.id,
        avatar_url=f"/uploads/avatars/{name}.png",
    )
    db.add(member)
    db.flush()
    if bound:
        db.add(SklandBind(member_id=member.id, token_enc="enc"))
    db.commit()
    return user, member


def _raw_box(role_id: str, uid: str, char_id: str = "chr_0004_pelica") -> str:
    return json.dumps(
        {
            "data": {
                "base": {
                    "roleId": role_id,
                    "uid": uid,
                    "serverId": "s1",
                    "name": "白衣",
                    "avatarUrl": "https://game.example/game-avatar.png",
                    "level": 45,
                    "charNum": 1,
                },
                "chars": [
                    {
                        # Account and character ids can differ from the stable
                        # catalog id; preserve all aliases for compare matching.
                        "id": "owned-instance-001",
                        "charId": char_id,
                        "level": 80,
                        "evolvePhase": 2,
                        "potentialLevel": 3,
                        "charData": {
                            "id": "runtime-character-id",
                            "name": "佩丽卡",
                            "rarity": 5,
                        },
                    }
                ],
            }
        },
        ensure_ascii=False,
    )


def _save_raw(db, member_id: int, role_id: str, uid: str) -> EndfieldBoxRaw:
    row = EndfieldBoxRaw(
        member_id=member_id,
        role_id=role_id,
        server_id="s1",
        uid=uid,
        raw_json=_raw_box(role_id, uid),
        synced_at=now_naive(),
    )
    db.add(row)
    db.commit()
    return row


def test_catalog_uses_gacha_roster_and_game_sort_order() -> None:
    rows = parse_character_tables(
        characters={
            "chr_b": {
                "name": {"id": 2},
                "engName": "Beta",
                "rarity": 5,
                "profession": 4,
                "sortOrder": 20,
            },
            "chr_a": {
                "name": {"id": 1},
                "engName": "Alpha",
                "rarity": 6,
                "profession": 4,
                "sortOrder": 10,
            },
            "chr_0002_endminm": {
                "name": "管理员",
                "engName": "Endministrator",
                "rarity": 6,
                "profession": 0,
                "sortOrder": 1,
            },
            "chr_9000_endmin": {
                "name": "剧情管理员",
                "engName": "NPC",
                "rarity": 6,
                "profession": 0,
                "sortOrder": 0,
            },
        },
        gacha_characters={"chr_a": {}, "chr_b": {}},
        professions={"4": {"profession": 4, "name": {"id": 40}}},
        i18n_payload={"1": "阿尔法", "2": "贝塔", "40": "先锋"},
    )

    assert [row["char_id"] for row in rows] == [
        "chr_0002_endminm",
        "chr_a",
        "chr_b",
    ]
    assert [row["name"] for row in rows] == ["管理员", "阿尔法", "贝塔"]
    assert rows[1]["profession_label"] == "先锋"
    assert rows[1]["rarity"] == 6


def test_compare_reads_other_members_from_cache_only(db, monkeypatch) -> None:
    viewer, _self = _member(db, "self")
    _other_user, other = _member(db, "other")
    raw = _save_raw(db, other.id, "role-other", "uid-other")
    monkeypatch.setattr(compare, "list_operators", lambda: [{"char_id": "chr_0004_pelica"}])

    def no_upstream(*_args, **_kwargs):
        pytest.fail("other members' credentials must never be used")

    monkeypatch.setattr(compare, "get_endfield_box_for_member", no_upstream)
    result = compare.build_box_compare(db, viewer, [other.id])

    assert result["catalog_count"] == 1
    row = result["rows"][0]
    assert row["status"] == "ok"
    assert row["uid"] == "uid-other"
    assert row["avatar_url"] == other.avatar_url
    assert set(row["owned"]) == {"chr_0004_pelica"}
    assert row["owned"]["chr_0004_pelica"].level == 80
    assert row["synced_at"] == raw.synced_at.isoformat()
    assert row["roles"][0]["role_name"] == "白衣"
    candidates = compare.list_compare_candidates(db, viewer)
    assert next(candidate for candidate in candidates if candidate["member_id"] == other.id)["game_role_name"] == "白衣"
    assert next(candidate for candidate in candidates if candidate["member_id"] == other.id)["avatar_url"] == other.avatar_url
    assert [candidate["member_id"] for candidate in candidates] == [
        viewer.member.id,
        other.id,
    ]


def test_compare_reconciles_owned_character_by_unique_catalog_name() -> None:
    box = parse_endfield_box(
        {
            "data": {
                "base": {"uid": "uid", "name": "玩家"},
                "chars": [
                    {
                        "id": "instance-character-id",
                        "charData": {"id": "runtime-character-id", "name": "佩丽卡"},
                    }
                ],
            }
        }
    )

    compare._align_box_char_ids(
        box,
        [{"char_id": "chr_0004_pelica", "name": "佩丽卡"}],
    )

    assert box.chars[0].char_id == "chr_0004_pelica"


def test_other_member_uid_must_be_in_cached_roles(db, monkeypatch) -> None:
    viewer, _self = _member(db, "self")
    _other_user, other = _member(db, "other")
    _save_raw(db, other.id, "role-other", "uid-other")
    monkeypatch.setattr(compare, "list_operators", lambda: [])
    monkeypatch.setattr(
        compare,
        "get_endfield_box_for_member",
        lambda *_args, **_kwargs: pytest.fail("must not fetch another member"),
    )

    row = compare.build_box_compare(
        db, viewer, [other.id], role_uids={other.id: "unknown-uid"}
    )["rows"][0]
    assert row["status"] == "error"
    assert row["owned"] == {}
    assert [role["uid"] for role in row["roles"]] == ["uid-other"]


def test_endfield_role_history_can_be_selected_without_box_snapshot(db, monkeypatch) -> None:
    viewer, _self = _member(db, "self")
    _other_user, other = _member(db, "other")
    db.add(
        EndfieldAttendanceRaw(
            member_id=other.id,
            role_id="role-other",
            server_id="s1",
            uid="uid-other",
            role_name="他人角色",
            channel_name="官服",
            raw_json="{}",
            synced_at=now_naive(),
        )
    )
    db.commit()
    monkeypatch.setattr(compare, "list_operators", lambda: [])
    monkeypatch.setattr(
        compare,
        "get_endfield_box_for_member",
        lambda *_args, **_kwargs: pytest.fail("must not fetch another member"),
    )

    candidates = compare.list_compare_candidates(db, viewer)
    row = compare.build_box_compare(db, viewer, [other.id])["rows"][0]

    assert [candidate["member_id"] for candidate in candidates] == [
        viewer.member.id,
        other.id,
    ]
    assert row["status"] == "no_snapshot"
    assert row["message"].startswith("暂无养成快照")
    assert [role["uid"] for role in row["roles"]] == ["uid-other"]


def _client(monkeypatch, db, viewer: User) -> TestClient:
    from app.api.skland import endfield as api
    from app.core import platform_deps

    monkeypatch.setattr(platform_deps, "is_feature_enabled", lambda _db, _feature: True)
    app = FastAPI()
    app.include_router(api.router, prefix="/api/skland")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: viewer
    return TestClient(app)


def test_compare_endpoints_are_registered_and_validate_role_uids(db, monkeypatch) -> None:
    viewer, member = _member(db, "self")
    client = _client(monkeypatch, db, viewer)
    invalid = client.get(
        "/api/skland/endfield/box/compare",
        params={"member_ids": str(member.id), "role_uids": "1:<script>"},
    )

    assert invalid.status_code == 400
    paths = client.app.openapi()["paths"]
    assert "/api/skland/endfield/box/compare-candidates" in paths
    assert "/api/skland/endfield/box/compare" in paths


def test_compare_api_serializes_catalog_and_progress(db, monkeypatch) -> None:
    from app.api.skland import endfield as api

    viewer, member = _member(db, "self")
    monkeypatch.setattr(
        api,
        "build_box_compare",
        lambda *_args, **_kwargs: {
            "catalog": [
                {
                    "char_id": "chr_0004_pelica",
                    "name": "佩丽卡",
                    "rarity": 5,
                    "profession": "4",
                    "profession_label": "先锋",
                    "sort_order": 4,
                }
            ],
            "catalog_count": 1,
            "rows": [
                {
                    "member_id": member.id,
                    "nickname": "self",
                    "avatar_url": "/uploads/avatars/self.png",
                    "status": "ok",
                    "message": None,
                    "uid": "uid-self",
                    "owned": {},
                    "roles": [],
                }
            ],
        },
    )
    response = _client(monkeypatch, db, viewer).get(
        "/api/skland/endfield/box/compare", params={"member_ids": str(member.id)}
    )

    assert response.status_code == 200, response.text
    assert response.json()["catalog"][0]["sort_order"] == 4
    assert response.json()["rows"][0]["avatar_url"] == "/uploads/avatars/self.png"
    assert response.json()["rows"][0]["uid"] == "uid-self"
    assert response.json()["rows"][0]["owned"] == {}
