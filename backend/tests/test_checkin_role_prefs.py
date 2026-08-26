"""checkin_role_prefs 纯函数 / 轻量逻辑单测。"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.checkin.role_prefs import (
    enrich_result_dicts,
    matches_role_filter,
    role_key,
)


def test_role_key_strips() -> None:
    assert role_key(" arknights ", " 123 ") == ("arknights", "123")


def test_matches_role_filter() -> None:
    keys = {("arknights", "1"), ("endfield", "2")}
    assert matches_role_filter("arknights", "1", keys)
    assert not matches_role_filter("arknights", "9", keys)
    assert matches_role_filter("arknights", "9", None)


def test_enrich_result_dicts_defaults_off() -> None:
    results = [
        {
            "game_code": "arknights",
            "role_uid": "u1",
            "status": "pending",
            "message": "x",
        }
    ]
    out = enrich_result_dicts(results, {})
    assert out[0]["included"] is False
    assert out[0]["auto_checkin"] is False
    assert out[0]["checkin_hour"] is None


def test_enrich_result_dicts_from_pref() -> None:
    pref = SimpleNamespace(
        included=True, enabled=True, checkin_hour=8, checkin_minute=30
    )
    results = [{"game_code": "arknights", "role_uid": "u1", "status": "ok", "message": "x"}]
    out = enrich_result_dicts(results, {("arknights", "u1"): pref})  # type: ignore[arg-type]
    assert out[0]["included"] is True
    assert out[0]["auto_checkin"] is True
    assert out[0]["checkin_hour"] == 8
    assert out[0]["checkin_minute"] == 30


def test_filter_included_results() -> None:
    from app.services.checkin.role_prefs import filter_included_results

    rows = [
        {"game_code": "a", "role_uid": "1", "included": True},
        {"game_code": "a", "role_uid": "2", "included": False},
    ]
    assert filter_included_results(rows) == [rows[0]]


def test_build_membership_tree_from_roles() -> None:
    from app.services.checkin.role_prefs import build_membership_tree_from_roles

    pref = SimpleNamespace(included=True)
    nodes = build_membership_tree_from_roles(
        platform="skland",
        roles=[
            {
                "game_code": "arknights",
                "game_name": "明日方舟",
                "uid": "1",
                "role_name": "A",
                "channel_name": "官服",
            }
        ],
        pref_map={("arknights", "1"): pref},  # type: ignore[arg-type]
    )
    assert len(nodes) == 1
    assert nodes[0]["included"] is True
    assert nodes[0]["role_uid"] == "1"


def test_today_done_from_logs_role_keys() -> None:
    from app.services.checkin.common import today_done_from_logs

    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *a, **k):
            return self

        def all(self):
            return self._rows

    class FakeDb:
        def __init__(self, rows):
            self._rows = rows

        def query(self, model):
            return FakeQuery(self._rows)

    rows = [
        SimpleNamespace(
            game_code="arknights",
            game_name="方舟",
            role_uid="1",
            role_name="A",
            channel_name="官服",
            status="ok",
            message="ok",
            awards_text=None,
            awards_json=None,
        ),
        SimpleNamespace(
            game_code="endfield",
            game_name="终末地",
            role_uid="2",
            role_name="B",
            channel_name="国服",
            status="pending",
            message="未签",
            awards_text=None,
            awards_json=None,
        ),
    ]
    db = FakeDb(rows)
    log_model = SimpleNamespace(member_id=None, checkin_date=None)
    done = today_done_from_logs(
        db,
        log_model,
        member_id=1,
        checkin_date="2026-08-26",
        role_keys={("arknights", "1")},
    )
    assert done is not None
    assert len(done) == 1
    assert done[0].role_uid == "1"
    assert (
        today_done_from_logs(
            db,
            log_model,
            member_id=1,
            checkin_date="2026-08-26",
            role_keys={("arknights", "1"), ("endfield", "2")},
        )
        is None
    )
