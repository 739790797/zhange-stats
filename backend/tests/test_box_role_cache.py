"""box_role_cache：从 raw 表还原角色列表。"""

from __future__ import annotations

from types import SimpleNamespace

from app.models.arknights_rogue import ArknightsRogueRaw
from app.models.skland import SklandAttendanceRaw, SklandCheckinLog
from app.services.box_role_cache import (
    skland_arknights_roles_from_raws,
    skland_endfield_roles_from_raws,
)
from app.services.skland.client import GAME_ARKNIGHTS, GAME_ENDFIELD


class _Query:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self._rows


class _Db:
    def __init__(self, by_model: dict) -> None:
        self._by_model = by_model

    def query(self, model):
        return _Query(self._by_model.get(model, []))


def test_skland_endfield_roles_from_raws() -> None:
    row = SimpleNamespace(
        uid="u1",
        role_id="r1",
        server_id="s1",
    )
    db = SimpleNamespace(
        query=lambda _model: SimpleNamespace(
            filter=lambda *args, **kwargs: SimpleNamespace(
                order_by=lambda *_a: SimpleNamespace(all=lambda: [row])
            )
        )
    )
    roles = skland_endfield_roles_from_raws(db, 1)  # type: ignore[arg-type]
    assert roles is not None
    assert len(roles) == 1
    assert roles[0].game_code == GAME_ENDFIELD
    assert roles[0].role_id == "r1"


def test_skland_arknights_roles_from_rogue_raws_use_checkin_logs() -> None:
    rogue = SimpleNamespace(uid="289253581")
    log = SimpleNamespace(
        role_uid="289253581",
        role_name="白衣#5820",
        channel_name="bilibili服",
        checked_at="2026-09-09",
    )
    db = _Db(
        {
            SklandAttendanceRaw: [],
            ArknightsRogueRaw: [rogue],
            SklandCheckinLog: [log],
        }
    )
    roles = skland_arknights_roles_from_raws(db, 1)  # type: ignore[arg-type]
    assert roles is not None
    assert len(roles) == 1
    assert roles[0].game_code == GAME_ARKNIGHTS
    assert roles[0].uid == "289253581"
    assert roles[0].role_name == "白衣#5820"
    assert roles[0].channel_name == "B服"


def test_skland_arknights_roles_from_attendance_keep_names() -> None:
    attendance = SimpleNamespace(
        uid="1",
        role_name="白衣#5820",
        channel_name="官服",
    )
    db = _Db(
        {
            SklandAttendanceRaw: [attendance],
            ArknightsRogueRaw: [],
            SklandCheckinLog: [],
        }
    )
    roles = skland_arknights_roles_from_raws(db, 1)  # type: ignore[arg-type]
    assert roles is not None
    assert roles[0].role_name == "白衣#5820"
    assert roles[0].channel_name == "官服"


def test_skland_arknights_roles_none_without_raws() -> None:
    db = _Db(
        {
            SklandAttendanceRaw: [],
            ArknightsRogueRaw: [],
            SklandCheckinLog: [],
        }
    )
    assert skland_arknights_roles_from_raws(db, 1) is None  # type: ignore[arg-type]
