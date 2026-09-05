"""账号级 3×4 收集摆放：按 PVP/PVE 分开，覆盖写入并对齐勾选。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserCollectionPlacement
from app.models.user import User, UserRole
from app.services.tarkov import collection_layout as layout
from app.services.tarkov import collection_owns as owns
from app.services.tarkov.game_mode import reset_game_mode, use_game_mode


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session, username: str) -> User:
    row = User(
        username=username,
        display_name=username,
        password_hash="x",
        role=UserRole.user,
    )
    db.add(row)
    db.flush()
    return row


def test_replace_layout_keeps_coords_and_syncs_owns() -> None:
    db = _session()
    user = _user(db, "a")
    token = use_game_mode("pvp")
    try:
        owns.add_own(db, user, "gone")
        rows = layout.replace_layout(
            db,
            user,
            [
                {"item_id": "a", "col": 1, "row": 2, "rotated": True},
                {"itemId": "b", "col": 0, "row": 0},
                {"item_id": "bad", "col": -1, "row": 0},
                {"item_id": "far", "col": 14, "row": 0},
                {"item_id": "a", "col": 3, "row": 3},
                "",
            ],
        )
        assert rows == {
            "placements": [
                {"item_id": "b", "col": 0, "row": 0, "rotated": False},
                {"item_id": "a", "col": 1, "row": 2, "rotated": True},
            ],
            "saved": True,
        }
        assert owns.list_item_ids(db, user.id) == ["a", "b"]
        again = layout.replace_layout(db, user, [{"item_id": "b", "col": 2, "row": 1}])
        assert again == {
            "placements": [
                {"item_id": "b", "col": 2, "row": 1, "rotated": False},
            ],
            "saved": True,
        }
        assert owns.list_item_ids(db, user.id) == ["b"]
    finally:
        reset_game_mode(token)


def test_pvp_and_pve_layouts_are_separate() -> None:
    db = _session()
    user = _user(db, "a")
    pvp = use_game_mode("pvp")
    try:
        layout.replace_layout(db, user, [{"item_id": "pvp-only", "col": 0, "row": 0}])
    finally:
        reset_game_mode(pvp)
    pve = use_game_mode("pve")
    try:
        layout.replace_layout(db, user, [{"item_id": "pve-only", "col": 1, "row": 1}])
        assert layout.list_placements(db, user.id) == [
            {"item_id": "pve-only", "col": 1, "row": 1, "rotated": False}
        ]
    finally:
        reset_game_mode(pve)
    assert layout.list_placements(db, user.id, game_mode="pvp") == [
        {"item_id": "pvp-only", "col": 0, "row": 0, "rotated": False}
    ]


def test_empty_replace_is_saved() -> None:
    db = _session()
    user = _user(db, "a")
    token = use_game_mode("pvp")
    try:
        assert layout.get_layout(db, user.id) == {"placements": [], "saved": False}
        emptied = layout.replace_layout(db, user, [])
        assert emptied == {"placements": [], "saved": True}
        layout.replace_layout(db, user, [{"item_id": "a", "col": 0, "row": 0}])
        cleared = layout.replace_layout(db, user, [])
        assert cleared == {"placements": [], "saved": True}
        assert owns.list_item_ids(db, user.id) == []
        assert layout.has_saved_layout(db, user.id) is True
    finally:
        reset_game_mode(token)


def test_existing_placements_count_as_saved_without_marker() -> None:
    db = _session()
    user = _user(db, "a")
    db.add(
        TarkovUserCollectionPlacement(
            user_id=user.id,
            game_mode="pvp",
            item_id="legacy",
            col=0,
            row=0,
            rotated=False,
            updated_at=now_naive(),
        )
    )
    db.flush()
    token = use_game_mode("pvp")
    try:
        assert layout.get_layout(db, user.id) == {
            "placements": [
                {"item_id": "legacy", "col": 0, "row": 0, "rotated": False}
            ],
            "saved": True,
        }
    finally:
        reset_game_mode(token)
