from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from hashlib import sha256
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.skland import router
from app.core.database import Base, _build_engine, get_db
from app.core.security import create_access_token
from app.core.timeutil import now_naive, to_naive
from app.models.arknights import ArknightsBoxSnapshot
from app.models.arknights_stronghold import (
    StrongholdActivity,
    StrongholdMatch,
    StrongholdMatchAlias,
    StrongholdParticipant,
    StrongholdRecord,
    StrongholdRecordBond,
    StrongholdRecordAlias,
    StrongholdRole,
    StrongholdSyncControl,
    StrongholdSyncTarget,
    StrongholdVersion,
)
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member
from app.schemas.stronghold import StrongholdBattleData, StrongholdBondOut, StrongholdOperatorOut
from app.models.skland import SklandBind
from app.models.user import User
from app.services.checkin.role_prefs import PLATFORM_SKLAND, apply_role_memberships, ensure_prefs_for_roles
from app.services.platform_features import invalidate_feature_cache, save_feature_flags
from app.services.scheduler_config import load_scheduler_config
from app.services.skland import checkin, stronghold, stronghold_resources, stronghold_source, stronghold_sync
from app.services.skland.client import GAME_ARKNIGHTS, GAME_ENDFIELD, SklandApiError, SklandRole, SklandSession
from app.services.skland.stronghold_source import RoleBattle, StrongholdBatch

ROOT = "/skland/arknights/stronghold"
FEATURE = "skland.arknights.stronghold"
T0 = "2026-11-23T12:00:00Z"


@pytest.fixture(params=["sqlite", "mariadb"] if os.getenv("ZHANGE_TEST_STRONGHOLD_MYSQL_URL") else ["sqlite"])
def env(request, monkeypatch, tmp_path):
    if request.param == "mariadb":
        # A dedicated, empty test database. Never edit the actual application database.
        engine = create_engine(os.environ["ZHANGE_TEST_STRONGHOLD_MYSQL_URL"])
    else:
        engine = _build_engine(f"sqlite:///{tmp_path / 'stronghold.sqlite'}")

    tables = [
        model.__table__
        for model in (
            User,
            Member,
            SklandBind,
            ArknightsBoxSnapshot,
            StrongholdMatch,
            StrongholdMatchAlias,
            StrongholdRole,
            StrongholdParticipant,
            StrongholdRecord,
            StrongholdRecordBond,
            StrongholdRecordAlias,
            StrongholdVersion,
            StrongholdActivity,
            StrongholdSyncTarget,
            StrongholdSyncControl,
        )
    ]
    from app.models.skland import SklandAttendanceRaw, SklandCheckinLog

    for model in (*checkin.skland_adapter.member_raw_models, SklandAttendanceRaw, SklandCheckinLog, CheckinRolePref):
        if model.__table__ not in tables:
            tables.append(model.__table__)
    Base.metadata.create_all(engine, tables=tables)
    invalidate_feature_cache()

    def session():
        with Session(engine, autoflush=False) as db:
            yield db

    upstream = {
        1: [("1", "101"), ("1", "111")],
        2: [("2", "101")],
        3: [("1", "202")],
        4: [],
        5: [("2", "101")],
    }
    rows = {}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = session

    with Session(engine) as db:
        for idx, name in enumerate(("甲", "乙", "丙", "观众", "重复绑定"), start=1):
            user = User(id=idx, username=f"user-{idx}", display_name=name, password_hash="placeholder")
            db.add(user)
            db.flush()
            db.add(Member(id=idx, user_id=idx, nickname=name))
            db.flush()
            if upstream[idx]:
                db.add(SklandBind(id=idx, member_id=idx, token_enc=checkin.encrypt_secret(f"token-{idx}")))
                db.add_all(
                    CheckinRolePref(
                        platform=PLATFORM_SKLAND, member_id=idx, game_code=GAME_ARKNIGHTS, role_uid=uid, included=True
                    )
                    for uid in {uid for _, uid in upstream[idx]}
                )
        db.commit()

    def skland_session(db, bind):
        member_id = bind.member_id
        db.commit()
        return SimpleNamespace(member_id=member_id)

    monkeypatch.setattr(stronghold_sync, "_session_for_bind", skland_session)
    monkeypatch.setattr(stronghold, "today", lambda: date(2026, 11, 23))
    monkeypatch.setattr(stronghold_sync, "discover_activity_versions", lambda: [])
    monkeypatch.setattr(stronghold_sync, "archive_assets", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(stronghold_sync, "randint", lambda *_: 0)
    monkeypatch.setattr(
        stronghold_sync, "list_roles", lambda session: [_role(pair) for pair in upstream[session.member_id]]
    )
    monkeypatch.setattr(stronghold_source, "fetch_official_resources", lambda *_: {})
    monkeypatch.setattr(
        stronghold_source,
        "official_source",
        lambda _, role, activity_id, versions: StrongholdBatch(
            rows.get((role.channel_master_id, role.uid), []), bool(versions)
        ),
    )

    def persist(member, channel, uid):
        assert (channel, uid) in upstream[member]
        with Session(engine, autoflush=False) as db:
            bind = checkin.get_bind_for_member(db, member)
            return stronghold.persist_battles(
                db, member, bind.id, bind.token_enc, _role((channel, uid)), rows[(channel, uid)]
            )

    def tick():
        with Session(engine, autoflush=False) as db:
            return stronghold_sync._run_tick(db, load_scheduler_config(db)[stronghold_sync.JOB_ID])

    def set_joined(member, uid, included, game=GAME_ARKNIGHTS):
        with Session(engine, autoflush=False) as db:
            bind = db.get(SklandBind, member)
            ensure_prefs_for_roles(db, platform=PLATFORM_SKLAND, member_id=member, bind=bind, roles=[(game, uid)])
            apply_role_memberships(
                db,
                platform=PLATFORM_SKLAND,
                member_id=member,
                bind=bind,
                roles=[{"game_code": game, "role_uid": uid, "included": included}],
            )

    with TestClient(app) as client:

        def request_as(member, method, path, **kwargs):
            headers = {}
            if member:
                token = create_access_token(f"user-{member}", expires_minutes=5, user_id=member)
                headers["Authorization"] = f"Bearer {token}"
            return client.request(method, ROOT + path, headers=headers, **kwargs)

        def sync(member, channel, uid):
            return request_as(member, "POST", "/sync", json={"channel_id": channel, "uid": uid})

        def get(member, path="/community", params=None):
            response = request_as(member, "GET", path, params=params)
            assert response.status_code == 200, response.text
            return response.json()

        yield SimpleNamespace(
            engine=engine,
            rows=rows,
            app=app,
            request=request_as,
            sync=sync,
            persist=persist,
            tick=tick,
            set_joined=set_joined,
            upstream=upstream,
            get=get,
            enable=lambda: save_feature_flags(None, {FEATURE: True}),
        )
    invalidate_feature_cache()
    Base.metadata.drop_all(engine, tables=tables)
    engine.dispose()


A = ("1", "101")
B = ("2", "101")
C = ("1", "202")
ALT_A = ("1", "111")
START = "2026-11-23T11:00:00Z"
ICON = "https://web.hycdn.cn/arknights/game/assets/auto_chess/bond_icon/steadShip.png"


def _bond(bond_id="a", layer=100, active=True, scope="role"):
    return StrongholdBondOut(
        bond_id=bond_id, name=f"盟约 {bond_id}", layer=layer, active=active, layer_scope=scope, icon_url=ICON
    )


def _role(pair):
    channel, uid = pair
    return SklandRole(GAME_ARKNIGHTS, "明日方舟", uid, f"角色 {uid}", "渠道", channel)


def _battle(
    role,
    key="record-a",
    *,
    mode="multi",
    scene="scene-a",
    season="s1",
    version="V3_1",
    difficulty="abyss",
    start=START,
    end=T0,
    passed=True,
    team_passed=True,
    rounds=15,
    bonds=None,
    strategy_id=None,
):
    return RoleBattle(
        upstream_view_id=f"{role[1]}-{key}",
        season_id=season,
        season_label="规程",
        difficulty_id=difficulty,
        difficulty_label="终极模拟" if difficulty == "abyss" else "其他难度",
        ended_at=end,
        mode_type=mode,
        completed=passed,
        pass_round=rounds,
        strategy_id=strategy_id,
        strategy_name="昆图斯",
        scene_id=scene,
        version_id=version,
        battle=StrongholdBattleData(started_at=start, team_completed=team_passed, trophy_before=10, trophy_after=18),
        bonds=bonds,
    )


def _ids(env, member):
    return [row["id"] for row in env.get(member, "/me")["records"]]


def test_flag_auth_validation_and_removed_approval_api(env, monkeypatch):
    assert env.request(4, "GET", "/community").status_code == 403
    env.enable()
    assert env.request(None, "GET", "/community").status_code == 401
    assert env.get(4)["matches"] == []
    assert env.request(4, "GET", "/community").headers["cache-control"] == "private, no-store"
    assert env.request(1, "GET", "/reports/no").status_code == 422
    assert env.request(4, "GET", "/community", params={"season": "bad id"}).status_code == 422
    assert env.request(4, "GET", "/community", params={"offset": 10**20}).status_code == 422
    assert env.request(4, "GET", "/community", params={"date": "2026-02-30"}).status_code == 422
    paths = env.app.openapi()["paths"]
    assert not any("sharing" in path or "link-consent" in path for path in paths)
    assert "/skland/arknights/rogue" not in paths
    monkeypatch.setattr(stronghold_source, "official_source", None)

    def forbidden(*_):
        raise AssertionError("Credential access without an available adapter")

    monkeypatch.setattr(stronghold_sync, "_session_for_bind", forbidden)
    assert env.get(1, "/me")["sync_available"] is False
    assert env.sync(1, *A).status_code == 503
    save_feature_flags(None, {"skland.arknights": False})
    assert env.request(4, "GET", "/community").status_code == 403


@pytest.mark.parametrize("order", [(1, 2), (2, 1), None])
def test_joint_scene_match_is_unique_and_keeps_both_perspectives(env, order):
    env.enable()
    env.rows.update(
        {
            A: [
                _battle(
                    A,
                    "a",
                    passed=False,
                    team_passed=False,
                    end="2026-11-23T11:45:00Z",
                    bonds=[_bond(layer=301, scope="unknown")],
                )
            ],
            B: [_battle(B, "b", bonds=[_bond(layer=397, scope="unknown")])],
        }
    )
    participants = {1: A, 2: B}
    if order is None:
        barrier = Barrier(2)

        def parallel(member):
            barrier.wait(timeout=8)
            return env.persist(member, *participants[member])

        with ThreadPoolExecutor(max_workers=2) as workers:
            imported = list(workers.map(parallel, participants))
    else:
        imported = [env.persist(member, *participants[member]) for member in order]
    assert sorted(out.new_matches for out in imported) == [0, 1]
    assert [out.new_records for out in imported] == [1, 1]
    diary = env.get(4)
    assert diary["total"] == diary["coverage"]["matches"] == 1
    assert "provisional_matches" not in diary["coverage"]
    assert diary["coverage"]["records"] == diary["coverage"]["records_with_unknown_layers"] == 2
    assert diary["coverage"]["roles_with_layers"] == 2
    (layers,) = diary["layers"]
    assert layers["layers"] == 698 and layers["team_layers"] is None
    assert [(c["member"]["id"], c["layers"]) for c in layers["contributors"]] == [(2, 397), (1, 301)]
    assert [(row["bond_id"], row["matches"]) for row in diary["popular_bonds"]] == [("a", 1)]
    assert [(r["member"]["id"], r["matches"], r["wins"]) for r in diary["ranking"]] == [(1, 1, 0), (2, 1, 1)]
    match = diary["matches"][0]
    assert match["ended_at"] == "2026-11-23T20:00:00+08:00"
    assert match["success"] and "provisional" not in match
    assert [p["id"] for p in match["participants"]] == [1, 2]
    report = env.get(4, f"/reports/{match['id']}")
    assert report["success"] is True
    assert [v["completed"] for v in report["views"]] == [False, True]
    assert [v["bonds"][0]["layer"] for v in report["views"]] == [301, 397]
    assert [v["battle"]["team_completed"] for v in report["views"]] == [False, True]
    assert all("uid" not in v and "scene_id" not in v and "source_view_key" not in v for v in report["views"])
    assert env.request(4, "GET", f"/views/{report['views'][0]['id']}").status_code == 404
    assert env.get(1, f"/reports/{match['id']}")["my_record_id"] == report["views"][0]["id"]
    with Session(env.engine) as db:
        assert db.scalar(select(func.count()).select_from(StrongholdMatch)) == 1
        assert db.scalar(select(func.count()).select_from(StrongholdRecord)) == 2


@pytest.mark.parametrize(
    ("last_a", "last_b", "expected"),
    [(False, True, None), (None, None, True), (False, None, False), (None, False, False)],
)
def test_team_result_uses_latest_known_settlement_without_affecting_personal_wins(env, last_a, last_b, expected):
    env.enable()
    env.rows[A] = [_battle(A, "recent-a", passed=False, team_passed=last_a)]
    env.rows[B] = [_battle(B, "recent-b", passed=False, team_passed=last_b)]
    env.rows[C] = [_battle(C, "earlier", passed=False, team_passed=True, end="2026-11-23T11:45:00Z")]
    for member, role in ((1, A), (2, B), (3, C)):
        env.persist(member, *role)

    diary = env.get(4)
    (match,) = diary["matches"]
    assert match["success"] is expected
    assert env.get(4, f"/reports/{match['id']}")["success"] is expected
    assert match["ended_at"] == "2026-11-23T20:00:00+08:00"
    assert [(r["member"]["id"], r["matches"], r["wins"]) for r in diary["ranking"]] == [
        (1, 1, 0),
        (2, 1, 0),
        (3, 1, 0),
    ]
    for result, success in (("complete", True), ("interrupted", False)):
        filtered = env.get(4, params={"result": result})
        assert filtered["total"] == filtered["coverage"]["matches"] == int(expected is success)
        assert filtered["matches"] == ([match] if expected is success else [])


def test_missing_scene_skips_only_that_record(env):
    env.enable()
    env.rows[A] = [_battle(A, "missing", scene=None), _battle(A, "known", scene="known")]
    imported = env.persist(1, *A)
    assert (imported.records_seen, imported.skipped, imported.new_matches, imported.new_records) == (2, 1, 1, 1)
    assert env.get(4)["total"] == 1


def test_legacy_id_backfills_and_aliases_without_losing_perspectives(env):
    env.enable()
    env.rows[A] = [_battle(A, "a")]
    env.persist(1, *A)
    old = env.get(4)["matches"][0]["id"]
    view = _ids(env, 1)[0]
    with Session(env.engine) as db:
        orphan = db.get(StrongholdMatch, old)
        orphan.scene_key, orphan.source_key, orphan.version_id = None, "legacy-digest", None
        db.get(StrongholdRecord, view).version_id = None
        db.commit()
    env.rows[B] = [_battle(B, "b")]
    env.persist(2, *B)
    assert env.get(4)["total"] == 2
    imported = env.persist(1, *A)
    assert (imported.new_matches, imported.new_records) == (0, 0)
    assert env.get(4)["total"] == 1
    canonical = env.get(4)["matches"][0]
    assert env.get(4, f"/reports/{old}")["id"] == canonical["id"]
    assert _ids(env, 1) == [view]
    assert canonical["version_key"] == "s1:V3_1"
    assert env.persist(1, *A).new_records == 0


@pytest.mark.parametrize("override", [{"version": "V3_2"}, {"start": "2026-11-23T11:00:01Z"}])
def test_auxiliary_fields_do_not_split_the_same_scene(env, override):
    env.enable()
    env.rows.update({A: [_battle(A, "a")], B: [_battle(B, "b", **override)]})
    assert env.persist(1, *A).new_matches == 1
    assert env.persist(2, *B).new_matches == 0
    assert env.get(4)["coverage"]["matches"] == 1


def test_reused_scene_and_role_view_ids_are_separate_across_activities(env):
    env.enable()
    env.rows[A] = [_battle(A, "a"), _battle(A, "a", season="s2")]
    imported = env.persist(1, *A)
    assert (imported.records_seen, imported.new_matches, imported.new_records) == (2, 2, 2)
    ids = set()
    for activity in ("s1", "s2"):
        params = {"version": f"{activity}:V3_1"}
        (match,) = env.get(4, params=params)["matches"]
        (view,) = env.get(1, "/me", params=params)["records"]
        assert view["match_id"] == match["id"]
        ids.add(match["id"])
    assert len(ids) == 2


def test_legacy_unscoped_match_is_reused_only_for_its_own_activity(env):
    env.enable()
    env.rows.update({A: [_battle(A, "a")], B: [_battle(B, "b")], C: [_battle(C, "c", season="s2")]})
    env.persist(1, *A)
    (old,) = env.get(4)["matches"]
    with Session(env.engine) as db:
        unscoped = sha256(b"scene:scene-a").hexdigest()
        match = db.get(StrongholdMatch, old["id"])
        match.source_key = match.scene_key = unscoped
        db.commit()

    assert env.persist(2, *B).new_matches == 0
    env.persist(3, *C)
    (view_id,) = _ids(env, 3)
    with Session(env.engine) as db:
        view = db.get(StrongholdRecord, view_id)
        wrong_match = db.get(StrongholdMatch, view.match_id)
        view.match_id = old["id"]
        db.flush()
        db.delete(wrong_match)
        db.commit()

    assert env.get(4, params={"version": "s2:V3_1"})["total"] == 0
    imported = env.persist(3, *C)
    assert (imported.new_matches, imported.new_records) == (1, 0)
    assert _ids(env, 3) == [view_id]
    (restored,) = env.get(4, params={"version": "s2:V3_1"})["matches"]
    assert env.get(3, f"/views/{view_id}")["match_id"] == restored["id"]
    assert [person["id"] for person in env.get(4, f"/reports/{old['id']}")["participants"]] == [1, 2]


def test_older_snapshot_cannot_overwrite_newer_settlement_across_batches(env):
    env.enable()
    older = _battle(A, "old", end="2026-11-23T11:45:00Z", passed=False, team_passed=False, rounds=5)
    newer = _battle(A, "new", rounds=18)
    env.rows[A] = [older]
    env.persist(1, *A)
    (view_id,) = _ids(env, 1)
    (match,) = env.get(4)["matches"]
    path = f"/reports/{match['id']}"

    env.rows[A] = [newer]
    env.persist(1, *A)
    expected = env.get(4, path)
    assert expected["success"] is True and expected["ended_at"] == "2026-11-23T20:00:00+08:00"
    assert expected["views"][0]["pass_round"] == 18
    assert _ids(env, 1) == [view_id]

    env.rows[A] = [older]
    imported = env.persist(1, *A)
    assert (imported.new_matches, imported.new_records) == (0, 0)
    assert env.get(4, path) == expected

    corrected = _battle(A, "new", passed=False, team_passed=False, rounds=17)
    env.rows[A] = [corrected]
    env.persist(1, *A)
    report = env.get(4, path)
    assert report["success"] is False and report["views"][0]["pass_round"] == 17
    assert _ids(env, 1) == [view_id]


@pytest.mark.parametrize("legacy_is_newer", [False, True])
def test_relink_keeps_newest_duplicate_and_both_public_links(env, legacy_is_newer):
    env.enable()
    older_end = "2026-11-23T11:55:00Z"
    legacy = _battle(A, "legacy", end=T0 if legacy_is_newer else older_end, rounds=18 if legacy_is_newer else 5)
    canonical = _battle(A, "canonical", end=older_end if legacy_is_newer else T0, rounds=5 if legacy_is_newer else 18)
    env.rows[A] = [legacy]
    env.persist(1, *A)
    (old_match,) = env.get(4)["matches"]
    (old_view,) = _ids(env, 1)
    with Session(env.engine) as db:
        match = db.get(StrongholdMatch, old_match["id"])
        match.scene_key, match.source_key = None, "pre-scene-source-key"
        db.commit()

    env.rows[A] = [canonical]
    env.persist(1, *A)
    new_view = next(view for view in _ids(env, 1) if view != old_view)
    new_match = env.get(1, f"/views/{new_view}")["match_id"]
    env.rows[A] = [_battle(A, "legacy", end="2026-11-23T11:45:00Z", rounds=3)]
    env.persist(1, *A)

    assert env.get(4)["total"] == 1
    report = env.get(4, f"/reports/{old_match['id']}")
    assert report["id"] == new_match and report["ended_at"] == "2026-11-23T20:00:00+08:00"
    assert [view["pass_round"] for view in report["views"]] == [18]
    assert env.get(1, f"/views/{old_view}") == env.get(1, f"/views/{new_view}")


def test_unbind_replace_and_rebind_preserve_history_and_prevent_reinsert(env, monkeypatch):
    env.enable()
    env.rows[A] = [_battle(A, "solo-a", mode="single", bonds=[_bond()])]
    first = env.persist(1, *A)
    old_diary = env.get(4)
    old_record = _ids(env, 1)
    with Session(env.engine) as db:
        checkin.unbind_skland(db, db.get(Member, 1))
        assert db.get(SklandBind, 1) is None
    assert _ids(env, 1) == old_record
    assert env.get(4) == old_diary
    assert env.sync(1, *A).status_code == 404
    monkeypatch.setattr(checkin, "login_with_token", lambda _: SklandSession("fixture", "fixture"))
    monkeypatch.setattr(checkin, "list_roles", lambda *_: [_role(A)])
    monkeypatch.setattr(checkin, "after_bind", lambda *_: None)
    for token in ("rebound", "replaced"):
        with Session(env.engine) as db:
            checkin.bind_skland(db, db.get(Member, 1), token)
        env.set_joined(1, A[1], True)
        assert env.get(1, "/me")["sync_status"][0]["state"] == "queued"
        second = env.persist(1, *A)
        assert second.role_id == first.role_id
        assert second.new_matches == second.new_records == 0
        assert _ids(env, 1) == old_record
        assert env.get(4) == old_diary


def test_diary_filters_apply_to_every_metric_and_use_beijing_end_date(env):
    env.enable()
    env.rows[A] = [
        _battle(
            A,
            "solo",
            mode="single",
            scene="scene-solo",
            end="2026-11-23T15:59:59Z",
            difficulty="normal",
            bonds=[_bond(layer=80)],
            strategy_id="solo",
            team_passed=False,
        ),
        _battle(
            A,
            "after-midnight",
            scene="scene-midnight",
            start="2026-11-23T15:59:00Z",
            end="2026-11-23T16:00:00Z",
            mode="single",
        ),
        _battle(
            A,
            "joint",
            rounds=16,
            bonds=[_bond(layer=55, scope="unknown"), _bond("b", layer=0), _bond("missing", layer=None)],
            strategy_id="joint-a",
            team_passed=False,
        ),
    ]
    env.rows[ALT_A] = [_battle(ALT_A, "joint-alt", rounds=17, team_passed=False)]
    env.rows[B] = [_battle(B, "joint-b", rounds=None, bonds=[_bond(layer=0, scope="unknown")], team_passed=False)]
    for member, role, expected in [(1, A, 3), (1, ALT_A, 1), (2, B, 1)]:
        assert env.persist(member, *role).new_records == expected
    with Session(env.engine) as db:
        version = db.get(StrongholdVersion, ("s1", "V3_1"))
        version.catalog = {"bond": {"never": {"name": "未出现盟约"}}}
        db.commit()
    diary = env.get(4)
    assert diary["total"] == 2 and diary["coverage"]["matches"] == 2
    assert [r["ended_at"] for r in diary["matches"]] == ["2026-11-23T23:59:59+08:00", "2026-11-23T20:00:00+08:00"]
    assert [(r["member"]["id"], r["matches"], r["wins"], r["rounds"]) for r in diary["ranking"]] == [
        (1, 2, 2, 32),
        (2, 1, 1, None),
    ]
    assert [(row["bond_id"], row["layers"]) for row in diary["layers"]] == [("a", 135), ("b", 0)]
    assert [(c["member"]["id"], c["layers"]) for c in diary["layers"][0]["contributors"]] == [(1, 135), (2, 0)]
    assert diary["popular_bonds"][0]["matches"] == 2

    params = {
        "version": "s1:V3_1",
        "date": "2026-11-23",
        "difficulty": "abyss",
        "mode": "multi",
        "result": "interrupted",
    }
    filtered = env.get(4, params=params)
    assert filtered["selected_version_key"] == "s1:V3_1"
    assert filtered["total"] == filtered["coverage"]["matches"] == 1
    assert filtered["matches"] == diary["matches"][1:]
    assert filtered["matches"][0]["success"] is False
    assert [(r["member"]["id"], r["matches"], r["wins"], r["rounds"]) for r in filtered["ranking"]] == [
        (1, 1, 1, 17),
        (2, 1, 1, None),
    ]
    assert [(row["strategy_id"], row["count"]) for row in filtered["strategies"]] == [("joint-a", 1)]
    assert [(row["bond_id"], row["layers"]) for row in filtered["layers"]] == [("a", 55), ("b", 0)]
    assert [(row["bond_id"], row["matches"]) for row in filtered["popular_bonds"]] == [
        ("a", 1),
        ("b", 1),
        ("missing", 1),
    ]
    assert {row["bond_id"]: row["layers"] for row in filtered["covenants"]} == {
        "a": 55,
        "b": 0,
        "missing": None,
        "never": 0,
    }
    assert {scope["difficulty_id"] for scope in filtered["scopes"]} == {"abyss", "normal"}

    for changed in (
        {"version": "s1:other"},
        {"date": "2026-11-24"},
        {"difficulty": "normal"},
        {"mode": "single"},
        {"result": "complete"},
        {"season": "other"},
        {"member": 3},
    ):
        empty = env.get(4, params={**params, **changed})
        assert empty["total"] == empty["coverage"]["matches"] == 0
        assert not any(empty[key] for key in ("matches", "ranking", "popular_bonds", "layers", "strategies"))
        assert all(row["layers"] == 0 and row["matches"] == 0 for row in empty["covenants"])
    legacy_member = env.get(4, params={"member": 2})
    for key in ("total", "matches", "ranking", "popular_bonds", "layers", "coverage", "strategies", "covenants"):
        assert legacy_member[key] == filtered[key]
    assert env.get(4, params={"result": "complete"})["matches"] == diary["matches"][:1]
    assert env.get(4, params={"date": "2026-11-24"})["coverage"]["matches"] == 1
    assert env.get(4, params={"date": "2026-11-22"})["coverage"]["matches"] == 0


def test_diary_ranks_members_by_distinct_matches_across_pages(env):
    env.enable()
    env.rows[A] = [_battle(A, "winner")]
    env.rows[ALT_A] = [_battle(ALT_A, "same-match", passed=False)]
    env.rows[B] = [
        _battle(B, "interrupted", mode="single", scene="interrupted", end="2026-11-23T12:30:00Z", passed=False),
        _battle(B, "unknown", mode="single", scene="unknown", end="2026-11-23T12:15:00Z", passed=None),
    ]
    for member, role in ((1, A), (1, ALT_A), (2, B)):
        env.persist(member, *role)

    diary = env.get(4)
    assert [row["success"] for row in diary["matches"]] == [False, None, True]
    assert [(r["rank"], r["member"]["id"], r["matches"]) for r in diary["ranking"]] == [(1, 2, 2), (2, 1, 1)]
    assert diary["ranking"][1]["member"]["role_names"] == [_role(A).role_name, _role(ALT_A).role_name]
    page = env.get(4, params={"offset": 2, "limit": 1})
    assert page["matches"] == diary["matches"][2:]
    assert page["ranking"] == diary["ranking"]

    for result, member in (("complete", 1), ("interrupted", 2)):
        (leader,) = env.get(4, params={"result": result})["ranking"]
        assert (leader["rank"], leader["member"]["id"], leader["matches"]) == (1, member, 1)


def test_diary_strategy_pie_counts_all_matches_and_each_distinct_role_view(env):
    env.enable()
    env.rows[A] = [
        _battle(A, strategy_id="frequent"),
        *[_battle(A, f"solo-{i}", scene=f"solo-{i}", mode="single", strategy_id="frequent") for i in range(13)],
        _battle(A, "old", scene="old", version="old", strategy_id="frequent"),
        _battle(A, "missing", scene="missing", mode="single"),
    ]
    env.persist(1, *A)
    env.rows[B] = [_battle(B, strategy_id="rare"), _battle(B, "conflict", scene="conflict", strategy_id="rare")]
    env.persist(2, *B)
    env.rows[B][1] = _battle(B, "conflict", scene="conflict", strategy_id="frequent")
    env.persist(5, *B)
    label = "游戏内策略名"
    with Session(env.engine) as db:
        version = db.get(StrongholdVersion, ("s1", "V3_1"))
        version.catalog = {
            "game": {"strategy": {"frequent": {"name": label}}},
            "strategy": {"frequent": {"name": "发起者", "description": "版本效果说明", "icon_url": ICON}},
        }
        db.get(Member, 1).avatar_url = "/site-avatar.png"
        db.commit()

    diary = env.get(4, params={"limit": 1})
    assert len(diary["matches"]) == 1 and diary["coverage"]["matches"] == 17
    assert diary["ranking"][0]["member"]["avatar_url"] == "/site-avatar.png"
    assert [(row["version_key"], row["strategy_id"], row["count"]) for row in diary["strategies"]] == [
        ("s1:V3_1", "frequent", 14),
        ("s1:V3_1", "rare", 1),
        ("s1:old", "frequent", 1),
    ]
    main = diary["strategies"][0]
    assert (main["name"], main["description"], main["icon_url"]) == (label, "版本效果说明", ICON)
    params = {"version": "s1:V3_1", "mode": "single", "result": "complete"}
    filtered = env.get(4, params=params)
    assert len(filtered["matches"]) == 12 and filtered["total"] == filtered["coverage"]["matches"] == 14
    assert [(row["strategy_id"], row["count"]) for row in filtered["strategies"]] == [("frequent", 13)]
    next_page = env.get(4, params={**params, "offset": 12})
    assert len(next_page["matches"]) == 2
    assert not {row["id"] for row in filtered["matches"]} & {row["id"] for row in next_page["matches"]}
    assert {**next_page, "matches": filtered["matches"]} == filtered
    assert env.get(4, params={"date": "2026-11-22"})["strategies"] == []


def test_diary_covenants_include_version_catalog_and_distinguish_zero_from_missing(env):
    env.enable()
    env.rows[A] = [
        _battle(
            A, bonds=[_bond("active", 75), _bond("missing", None), _bond("zero", 0), _bond("team", 12, scope="team")]
        ),
        _battle(
            A, "solo", scene="solo", mode="single", bonds=[_bond("active", 45), _bond("inactive", 200, active=False)]
        ),
    ]
    env.persist(1, *A)
    with Session(env.engine) as db:
        version = db.get(StrongholdVersion, ("s1", "V3_1"))
        version.catalog = {
            "bond": {"active": {"name": "版本盟约", "description": "版本盟约效果"}, "inactive": {"name": "未激活"}},
            "game": {"bond": {"catalog-only": {"name": "游戏资料盟约", "icon_url": ICON}}},
        }
        unpublished_in_records = stronghold_resources.ensure_version(db, "s1", "old")
        unpublished_in_records.catalog = {"bond": {"archived": {"name": "历史盟约"}}}
        db.commit()

    diary = env.get(4, params={"version": "s1:V3_1", "limit": 1})
    assert [(row["bond_id"], row["layers"], row["matches"]) for row in diary["covenants"]] == [
        ("active", 120, 2),
        ("catalog-only", 0, 0),
        ("inactive", 0, 0),
        ("missing", None, 1),
        ("team", None, 1),
        ("zero", 0, 1),
    ]
    assert diary["covenants"][0]["description"] == "版本盟约效果"
    assert diary["covenants"][1]["icon_url"] == ICON
    assert next(row for row in diary["layers"] if row["bond_id"] == "team")["team_layers"] == 12
    empty_day = env.get(4, params={"date": "2026-11-22"})
    assert empty_day["coverage"]["matches"] == 0
    assert [(row["bond_id"], row["layers"]) for row in empty_day["covenants"]] == [
        ("active", 0),
        ("catalog-only", 0),
        ("inactive", 0),
        ("archived", 0),
    ]


def test_known_team_layers_are_separate_and_duplicate_game_role_is_unattributed(env):
    env.enable()
    env.rows[A] = [_battle(A, "a", bonds=[_bond("team", 250, scope="team")])]
    env.rows[B] = [_battle(B, "b", bonds=[_bond("team", 250, scope="team"), _bond("role", 115)])]
    env.rows[C] = [_battle(C, "c", bonds=[_bond("team", 100)])]
    for member, role in [(1, A), (2, B), (3, C), (5, B)]:
        assert env.persist(member, *role).new_records == 1
    diary = env.get(4)
    assert diary["total"] == 1
    role, mixed = diary["layers"]
    assert (role["layers"], role["unattributed_layers"], role["team_layers"], role["contributors"]) == (
        115,
        115,
        None,
        [],
    )
    assert (mixed["layers"], mixed["unattributed_layers"], mixed["team_layers"]) == (100, 0, 250)
    assert [(c["member"]["id"], c["layers"]) for c in mixed["contributors"]] == [(3, 100)]
    assert all(b["matches"] == 1 for b in diary["popular_bonds"])


def test_report_groups_four_game_roles_by_channel_and_uid_without_exposing_uid(env):
    env.enable()
    env.rows.update({role: [_battle(role, f"seat-{i}")] for i, role in enumerate((A, ALT_A, B, C))})
    for member, role in ((1, A), (1, ALT_A), (2, B), (3, C), (5, B)):
        env.persist(member, *role)

    (match,) = env.get(2)["matches"]
    assert match["views"] == []
    report = env.get(2, f"/reports/{match['id']}")
    groups = {}
    for view in report["views"]:
        groups.setdefault(view["player_group_id"], []).append(view)
        assert "uid" not in view and "channel_id" not in view
        assert view["is_own"] == (view["author"]["id"] == 2)
    assert len(groups) == 4
    for group, views in groups.items():
        assert group == views[0]["id"]
    assert sorted(len(views) for views in groups.values()) == [1, 1, 1, 2]
    own = next(view for view in report["views"] if view["id"] == report["my_record_id"])
    assert own["is_own"] and own["role_name"] == "角色 101"
    assert {view["author"]["id"] for view in groups[own["player_group_id"]]} == {2, 5}
    assert env.get(2, f"/views/{own['id']}")["is_own"] is True
    other = env.get(4, f"/reports/{match['id']}")
    assert other["my_record_id"] is None and all(not view["is_own"] for view in other["views"])

    with Session(env.engine) as db:
        db.get(User, 3).anonymized_at = now_naive()
        db.commit()
    visible = env.get(2, f"/reports/{match['id']}")["views"]
    assert len({view["player_group_id"] for view in visible}) == 3
    assert all(view["author"]["id"] != 3 for view in visible)


def test_daily_layers_require_activation_and_keep_conflicting_role_values_out(env):
    env.enable()
    env.rows[A] = [_battle(A, "a", bonds=[_bond("zero", 0, scope="unknown"), _bond("inactive", 500, active=False)])]
    env.rows[B] = [
        _battle(B, "b", bonds=[_bond("conflict", 20, scope="unknown"), _bond("missing", None), _bond("valid", 15)])
    ]
    for member, role in ((1, A), (2, B)):
        env.persist(member, *role)
    env.rows[B] = [_battle(B, "b", bonds=[_bond("conflict", 30), _bond("valid", 15, scope="unknown")])]
    env.persist(5, *B)

    diary = env.get(4)
    assert diary["coverage"]["roles_with_conflicting_layers"] == 1
    assert diary["coverage"]["records"] == diary["coverage"]["roles_with_layers"] == 2
    assert [(row["bond_id"], row["layers"], row["unattributed_layers"]) for row in diary["layers"]] == [
        ("valid", 15, 15),
        ("zero", 0, 0),
    ]
    assert {row["bond_id"] for row in diary["popular_bonds"]} == {"conflict", "missing", "valid", "zero"}


def test_conflicting_or_wrong_role_batch_writes_nothing(env):
    env.enable()
    valid = _battle(A, "a")
    for invalid in (_battle(C, "a"), _battle(A, "a", passed=False), _battle(A, "a", scene="other")):
        env.rows[A] = [valid, invalid]
        with pytest.raises(stronghold.StrongholdError) as exc:
            env.persist(1, *A)
        assert exc.value.status_code == 502
        assert env.get(4)["total"] == 0
    newer = _battle(A, "second-view-same-scene")
    older = _battle(A, "a", end="2026-11-23T11:45:00Z")
    conflicting = older.model_copy(update={"completed": False})
    env.rows[A] = [newer, older, conflicting]
    with pytest.raises(stronghold.StrongholdError):
        env.persist(1, *A)
    assert env.get(4)["total"] == 0
    env.rows[A] = [valid, _battle(A, "second-view-same-scene")]
    assert env.persist(1, *A).new_matches == 1
    assert env.get(4)["total"] == 1


def test_local_zero_and_unknown_results_stay_distinct(env):
    env.enable()
    env.rows[A] = [
        _battle(A, "local", mode="local", bonds=[_bond(layer=0)]),
        _battle(A, "unknown", scene="other", mode="single", passed=None, team_passed=None),
    ]
    env.persist(1, *A)
    mine = env.get(1, "/me")
    assert mine["total"] == 2 and mine["known_results"] == 1 and mine["wins"] == 1
    assert env.get(1, "/me", params={"result": "complete"})["total"] == 1
    assert env.get(1, "/me", params={"result": "unknown"})["total"] == 1
    local = next(row for row in mine["records"] if row["mode_type"] == "local")
    assert env.get(1, f"/views/{local['id']}")["bonds"][0]["layer"] == 0


def test_unknown_mode_and_outcome_do_not_use_the_new_match_placeholder(env):
    env.enable()
    env.rows[A] = [_battle(A, "unknown", mode=None, passed=None, team_passed=None, rounds=None)]
    env.persist(1, *A)
    (match,) = env.get(4)["matches"]
    path = f"/reports/{match['id']}"
    assert match["success"] is None
    assert env.get(4, path)["success"] is None
    assert env.get(4, params={"result": "complete"})["total"] == 0
    assert env.get(4, params={"result": "interrupted"})["total"] == 0
    assert env.request(4, "GET", "/community", params={"result": "unknown"}).status_code == 422
    assert env.get(1, "/me", params={"result": "unknown"})["records"][0]["completed"] is None

    with Session(env.engine) as db:
        legacy = db.get(StrongholdMatch, match["id"])
        legacy.source_key = "pre-scene-source-key"
        legacy.scene_key = None
        legacy.success = True
        db.commit()
    assert env.get(4, path)["success"] is True
    assert [row["id"] for row in env.get(4, params={"result": "complete"})["matches"]] == [match["id"]]


def test_anonymized_site_member_drops_out_of_history(env):
    env.enable()
    env.rows[A] = [_battle(A, "solo", mode="single")]
    assert env.persist(1, *A).new_records == 1
    match = env.get(4)["matches"][0]
    with Session(env.engine) as db:
        db.get(User, 1).anonymized_at = now_naive()
        db.commit()
    assert env.get(4)["total"] == 0
    assert env.get(4, params={"result": "complete"})["total"] == 0
    assert env.request(4, "GET", f"/reports/{match['id']}").status_code == 404


def test_latest_version_follows_opening_time_not_selected_date_or_matching_results(env, monkeypatch):
    env.enable()
    monkeypatch.setattr(stronghold, "now_naive", lambda: datetime(2026, 11, 23, 22))
    params = {"version": "latest", "difficulty": "abyss", "result": "complete"}
    no_version = env.get(4, params=params)
    assert no_version["selected_version_key"] is None and no_version["total"] == 0
    assert no_version["covenants"] == []

    env.rows[A] = [
        _battle(A, "older-play", scene="older-play", version="Z_older", end="2026-11-23T11:30:00Z"),
        _battle(A, "newer-play", scene="newer-play", version="A_recent"),
    ]
    env.persist(1, *A)
    with Session(env.engine) as db:
        future = stronghold_resources.ensure_version(db, "s1", "future")
        future.starts_at = datetime(2026, 11, 24)
        db.commit()
    fallback = env.get(4, params=params)
    assert fallback["selected_version_key"] == "s1:A_recent" and fallback["total"] == 1

    with Session(env.engine) as db:
        db.get(StrongholdVersion, ("s1", "Z_older")).starts_at = datetime(2026, 11, 20)
        current = stronghold_resources.ensure_version(db, "s1", "A_open")
        current.starts_at = datetime(2026, 11, 22)
        current.catalog = {"bond": {"new-only": {"name": "新版本盟约"}}}
        db.commit()
    for day in (None, "2026-11-21"):
        current_day = env.get(4, params={**params, **({"date": day} if day else {})})
        assert current_day["date"] == (day or "2026-11-23")
        assert current_day["selected_version_key"] == "s1:A_open"
        assert current_day["total"] == current_day["coverage"]["matches"] == 0
        assert [(row["bond_id"], row["layers"]) for row in current_day["covenants"]] == [("new-only", 0)]
    assert env.get(4, params={"version": "s1:Z_older"})["total"] == 1
    all_versions = env.get(4)
    assert all_versions["selected_version_key"] is None and all_versions["total"] == 2
    assert env.request(1, "GET", "/me", params={"version": "latest"}).status_code == 422


def test_version_scope_groups_daily_statistics_and_retains_archived_effects(env):
    from app.services.skland.stronghold_resources import save_resources

    env.enable()
    env.rows[A] = [
        _battle(A, "old", scene="old", version="old", bonds=[_bond(layer=90)]),
        _battle(A, "new", scene="new", version="new", bonds=[_bond(layer=30)]),
    ]
    env.persist(1, *A)
    with Session(env.engine, autoflush=False) as db:
        now = datetime(2026, 11, 24)
        for version in ("old", "new"):
            save_resources(
                db,
                "s1",
                {
                    version: {
                        "versionInfo": {
                            "activityId": "s1",
                            "seasonName": version,
                            "endTime": "2026-11-24T00:00:00+08:00",
                        },
                        "bondInfo": {"a": {"name": version, "desc": f"效果 {version}", "icon": ICON}},
                    }
                },
                now,
            )
        db.commit()
        save_resources(db, "s1", {"old": {"bondInfo": {"a": {"desc": "新的说明"}}}}, now)
        db.commit()
    all_versions = env.get(4)
    assert [(row["version_key"], row["layers"]) for row in all_versions["layers"]] == [("s1:old", 90), ("s1:new", 30)]
    old = env.get(4, params={"version": "s1:old"})
    assert old["total"] == 1 and old["ranking"][0]["wins"] == 1
    assert old["layers"][0]["description"] == "效果 old"
    assert old["matches"][0]["version"]["label"] == "old"
    assert len(old["versions"]) == 2
    assert env.get(1, "/me", params={"version": "s1:new"})["total"] == 1


def test_role_names_preserve_suffix_and_follow_each_participating_role(env, monkeypatch):
    names = {A: "雪地#1871", ALT_A: "罗德岛小号#2019", B: "渠道服角色#0001"}
    env.enable()
    monkeypatch.setitem(
        globals(), "_role", lambda pair: SklandRole(GAME_ARKNIGHTS, "明日方舟", pair[1], names[pair], "渠道", pair[0])
    )
    for member, pair in ((1, A), (1, ALT_A), (2, B)):
        env.rows[pair] = [_battle(pair, str(member), bonds=[_bond(layer=10)])]
        env.persist(member, *pair)

    diary = env.get(4)
    (match,) = diary["matches"]
    expected = {1: sorted((names[A], names[ALT_A])), 2: [names[B]]}
    assert {row["id"]: row["role_names"] for row in match["participants"]} == expected
    assert [(row["member"]["id"], row["wins"]) for row in diary["ranking"]] == [(1, 1), (2, 1)]
    assert {row["member"]["id"]: row["member"]["role_names"] for row in diary["ranking"]} == expected
    assert {row["member"]["id"]: row["layers"] for row in diary["layers"][0]["contributors"]} == {1: 20, 2: 10}
    filtered = env.get(4, params={"member": 1, "offset": 12})
    assert filtered["matches"] == [] and filtered["filtered_role_names"] == expected[1]
    views = env.get(4, f"/reports/{match['id']}")["views"]
    assert sorted(view["role_name"] for view in views) == sorted(names.values())
    assert not any("uid" in view for view in views)
    own_view = next(view for view in views if view["role_name"] == names[ALT_A])
    assert env.get(1, f"/views/{own_view['id']}")["role_name"] == names[ALT_A]


def test_old_reports_resolve_full_names_from_box_and_checkin_without_crossing_roles(env, monkeypatch):
    from app.models.skland import SklandAttendanceRaw, SklandCheckinLog

    env.enable()
    source_names = {A: "测试博士", ALT_A: "111", B: "测试博士"}
    monkeypatch.setitem(
        globals(),
        "_role",
        lambda pair: SklandRole(GAME_ARKNIGHTS, "明日方舟", pair[1], source_names[pair], "", pair[0]),
    )
    for member, pair in ((1, A), (1, ALT_A), (2, B), (5, B)):
        env.rows[pair] = [_battle(pair, f"role-{member}", bonds=[_bond(layer=10)])]
        env.persist(member, *pair)
    with Session(env.engine) as db:
        db.add(
            ArknightsBoxSnapshot(
                member_id=1,
                uid=A[1],
                sync_date=date(2026, 11, 23),
                payload_json=json.dumps(
                    {
                        "status": "ok",
                        "uid": A[1],
                        "role_name": "测试博士",
                        "channel_master_id": "1",
                        "player_name": "测试博士#1259",
                        "roles": [
                            {"uid": ALT_A[1], "channel_name": "官服", "role_name": "第二角色#0088"},
                            {"uid": B[1], "channel_name": "B服", "role_name": "测试博士#6666"},
                        ],
                    }
                ),
            )
        )
        db.add(
            SklandAttendanceRaw(member_id=2, uid=B[1], role_name="测试博士#9999", channel_name="官服", raw_json="{}")
        )
        db.add(
            SklandCheckinLog(
                member_id=2,
                bind_id=2,
                game_code=GAME_ARKNIGHTS,
                game_name="明日方舟",
                role_uid=B[1],
                role_name="测试博士#2222",
                channel_name="bilibili服",
                status="success",
                checkin_date=date(2026, 11, 23),
            )
        )
        db.commit()

    diary = env.get(4)
    (match,) = diary["matches"]
    expected = {1: ["测试博士#1259", "第二角色#0088"], 2: ["测试博士#2222"], 5: ["测试博士"]}
    assert {row["id"]: row["role_names"] for row in match["participants"]} == expected
    assert {row["member"]["id"]: row["member"]["role_names"] for row in diary["ranking"]} == expected
    views = env.get(4, f"/reports/{match['id']}")["views"]
    assert sorted(view["role_name"] for view in views) == sorted(name for names in expected.values() for name in names)
    assert all("uid" not in view for view in views)
    own = env.get(1, "/me")
    assert [role["role_name"] for role in own["roles"]] == expected[1]
    view = next(view for view in views if view["role_name"] == "测试博士#1259")
    assert env.get(1, f"/views/{view['id']}")["role_name"] == "测试博士#1259"

    # Cached identities must not reverse a verified rename from the binding list.
    source_names[A] = "已改名"
    env.persist(1, *A)
    assert env.get(1, f"/views/{view['id']}")["role_name"] == "已改名"


def test_report_resolves_current_discovered_name_before_any_new_history_sync(env, monkeypatch):
    env.enable()
    env.upstream[1].append(B)
    monkeypatch.setitem(
        globals(), "_role", lambda pair: SklandRole(GAME_ARKNIGHTS, "明日方舟", pair[1], pair[1], "", pair[0])
    )
    role_ids = {}
    for member, pair in ((1, A), (1, B), (2, B), (5, B)):
        env.rows[pair] = [_battle(pair, str(member))]
        role_ids[member, pair] = env.persist(member, *pair).role_id

    with Session(env.engine) as db:
        for member, pair, name, current in (
            (1, A, "官服博士#0197", True),
            (1, B, "渠道服博士#1259", True),
            (2, B, "旧绑定#9999", False),
        ):
            db.add(
                StrongholdSyncTarget(
                    bind_id=member,
                    channel_id=pair[0],
                    uid=pair[1],
                    role_name=name,
                    binding_key=stronghold_sync._key(db.get(SklandBind, member)) if current else "old",
                    due_at=now_naive(),
                    status="queued",
                )
            )
        db.commit()

    diary = env.get(4)
    (match,) = diary["matches"]
    expected = {1: ["官服博士#0197", "渠道服博士#1259"], 2: [], 5: []}
    assert {person["id"]: person["role_names"] for person in match["participants"]} == expected
    report = env.get(1, f"/reports/{match['id']}")
    own = {view["own_role_id"]: view for view in report["views"] if view["is_own"]}
    assert {role_id: view["role_name"] for role_id, view in own.items()} == dict(
        zip((role_ids[1, A], role_ids[1, B]), expected[1], strict=True)
    )
    assert all(
        view["role_name"] is None and view["own_role_id"] is None for view in report["views"] if not view["is_own"]
    )
    assert all(
        view["own_role_id"] is None and "uid" not in view for view in env.get(4, f"/reports/{match['id']}")["views"]
    )
    old = env.get(1, f"/views/{own[role_ids[1, B]]['id']}")
    assert (old["role_name"], old["own_role_id"]) == ("渠道服博士#1259", role_ids[1, B])


def test_game_catalog_enriches_only_the_matching_battle_version(env, monkeypatch):
    env.enable()
    game_data = {
        "autoChessData": {
            "versionInfoDict": {"V3_1": {"activityId": "s1", "versionId": "V3_1"}},
            "bandDataDict": {"band_takecare": {"bandName": "华法琳"}},
            "bondInfoDict": {"yanShip": {"isPower": True}, "suntShip": {"isHiddenCharList": True}},
            "bossInfoDict": {"boss_test": {"enemyId": "enemy_test"}},
        },
        "activity": {
            "AUTOCHESS": {
                "s1": {
                    "V3_1": {
                        "bandDataListDict": {
                            "band_takecare": {
                                "bandId": "band_takecare",
                                "totalHp": 24,
                                "bandDesc": r"【重点监护】\n<@ba.vup>友方增益</>\n<标准模拟>初始效果",
                            }
                        },
                        "bondInfoDict": {
                            "yanShip": {
                                "bondId": "yanShip",
                                "name": "炎",
                                "desc": "同版游戏表效果",
                                "activeCount": 3,
                                "activeConditionTemplate": "count_threshold_upward",
                                "chessIdList": ["amiya", "signal_piece"],
                            },
                            "suntShip": {"bondId": "suntShip", "name": "绝技", "chessIdList": []},
                        },
                        "charShopChessDatas": {
                            "amiya": {
                                "goldenChessId": "signal_piece",
                                "charId": "char_002_amiya",
                                "chessLevel": 2,
                                "defaultUniEquipId": "uniequip_test",
                            }
                        },
                        "chessNormalIdLookupDict": {"amiya": "amiya", "signal_piece": "amiya"},
                        "charChessDataDict": {
                            "amiya": {"isGolden": False},
                            "signal_piece": {
                                "isGolden": True,
                                "status": {"skillLevel": 2, "equipLevel": 3},
                                "garrisonIds": ["garrison_test"],
                            },
                        },
                        "garrisonDataDict": {"garrison_test": {"eventTypeDesc": "持续叠加", "description": "特性效果"}},
                        "bossInfoDict": {"boss_test": {}},
                    }
                }
            }
        },
    }
    tables = {
        "activity_table.json": game_data,
        "character_table.json": {"char_002_amiya": {"name": "阿米娅", "skills": [{"skillId": "sk_test"}]}},
        "skill_table.json": {
            "sk_test": {
                "levels": [
                    {"name": "技能名", "description": "等级一"},
                    {
                        "name": "技能名",
                        "description": "攻击力+<@ba.vup>{attack@atk:0%}</>",
                        "blackboard": [{"key": "attack@atk", "value": 0.4}],
                    },
                ]
            }
        },
        "uniequip_table.json": {
            "equipDict": {"uniequip_test": {"uniEquipName": "模组名", "uniEquipIcon": "uniequip_test"}}
        },
        "battle_equip_table.json": {
            "uniequip_test": {
                "phases": [
                    {
                        "equipLevel": 3,
                        "attributeBlackboard": [{"key": "atk", "value": 55}],
                        "parts": [
                            {
                                "overrideTraitDataBundle": {
                                    "candidates": [
                                        {
                                            "additionalDescription": "获得{sp}点技力并<$ba.sluggish>停顿</>",
                                            "blackboard": [{"key": "sp", "value": 1}],
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ]
            }
        },
        "enemy_handbook_table.json": {"enemyData": {"enemy_test": {"name": "测试首领"}}},
    }
    monkeypatch.setattr(stronghold_resources, "read_repo_text", lambda _, path: json.dumps(tables[path.split("/")[-1]]))
    with Session(env.engine, autoflush=False) as db:
        ((activity, version, meta, catalog),) = stronghold_resources.discover_activity_versions()
        now = datetime(2026, 11, 24)
        row = stronghold_resources.ensure_version(db, activity, version, meta)
        stronghold_resources.save_game_catalog(row, catalog, now)
        stronghold_resources.save_resources(
            db,
            activity,
            {
                version: {
                    "bandInfo": {"band_takecare": {"name": "华法琳"}},
                    "bondInfo": {"yanShip": {"desc": "同版森空岛说明"}},
                }
            },
            now,
        )
        db.commit()

    env.rows[A] = [
        _battle(
            A,
            tag,
            scene=tag,
            version=tag,
            bonds=[
                StrongholdBondOut(bond_id="yanShip", layer=0, active=False),
                StrongholdBondOut(bond_id="suntShip", active=True),
            ],
        ).model_copy(
            update={
                "strategy_id": "band_takecare",
                "strategy_name": None,
                "battle": StrongholdBattleData(bosses=[{"id": "boss_test", "killed": True}]),
                "roster": [
                    StrongholdOperatorOut(id="amiya", phase=2, equipment=[]),
                    StrongholdOperatorOut(id="signal_piece", phase=2, skill_id="sk_test", module_id="uniequip_test"),
                    StrongholdOperatorOut(id="fake_gold", phase=2),
                ],
            }
        )
        for tag in ("V3_1", "old")
    ]
    env.persist(1, *A)
    diary = env.get(4)
    reports = {row["version_key"]: env.get(4, f"/reports/{row['id']}")["views"][0] for row in diary["matches"]}
    current = reports["s1:V3_1"]
    assert (current["strategy_name"], current["strategy_promoter"], current["strategy_initial_hp"]) == (
        "重点监护",
        "华法琳",
        24,
    )
    assert current["battle"]["strategy_description"] == "友方增益\n<标准模拟>初始效果"
    assert current["battle"]["strategy_icon_url"].endswith("/band_icon/band_takecare.png")
    bond, hidden = current["bonds"]
    assert (bond["name"], bond["is_core"], bond["activation_count"], bond["activation_rule"]) == (
        "炎",
        True,
        3,
        "at_least",
    )
    assert (bond["active"], bond["layer"], bond["description"]) == (False, 0, "同版森空岛说明")
    assert bond["icon_url"].endswith("/bond_icon/yanShip.png")
    assert bond["operators"] == [{"id": "amiya", "char_id": "char_002_amiya", "name": "阿米娅", "tier": 2}]
    assert hidden["show_operators"] is False and hidden["operators"] is None
    normal, elite, unknown = current["roster"]
    assert (normal["normal_chess_id"], normal["is_elite"], normal["equipment"]) == ("amiya", False, [])
    assert (elite["normal_chess_id"], elite["is_elite"], elite["equipment"]) == ("amiya", True, None)
    assert (unknown["normal_chess_id"], unknown["is_elite"]) == (None, None)
    assert normal["module"] is None and normal["skill"] is None  # configuration is not proof of an equipped module
    assert elite["skill"] == {
        "name": "技能名",
        "description": "攻击力+40%",
        "config_level": 2,
        "reference_level": 2,
        "icon_url": None,
    }
    assert elite["module"]["name"] == "模组名"
    assert elite["module"]["description"] == "攻击力 +55\n获得1点技力并停顿"
    assert elite["module"]["icon_url"].endswith("/uniequip/uniequip_test.png")
    assert elite["traits"][0]["description"] == "特性效果"
    assert current["battle"]["bosses"][0]["name"] == "测试首领"
    old = reports["s1:old"]
    assert old["strategy_promoter"] is None and old["strategy_initial_hp"] is None
    assert old["battle"]["strategy_description"] is None and old["bonds"][0]["operators"] is None
    assert all(unit["is_elite"] is None and unit["normal_chess_id"] is None for unit in old["roster"])
    assert all(unit["module"] is None and unit["skill"] is None for unit in old["roster"])
    assert old["battle"]["bosses"][0]["name"] is None


def test_frozen_game_catalog_backfills_operators_without_replacing_snapshot(env):
    now = datetime(2026, 11, 24)
    with Session(env.engine) as db:
        row = stronghold_resources.ensure_version(db, "s1", "archived")
        row.ends_at = now - timedelta(days=5)
        archived_effects = {"strategy": {"band": {"description": "历史效果"}}}
        units = {"signal_piece": {"normal_chess_id": "amiya", "is_elite": True}}
        row.catalog = {"game": archived_effects}
        stronghold_resources.save_game_catalog(
            row, {"strategy": {"band": {"description": "不可覆写"}}, "operator": units}, now
        )
        db.commit()
        assert row.catalog["game"] == {**archived_effects, "operator": units}
        stronghold_resources.save_game_catalog(row, {"operator": {"amiya": {"is_elite": False}}}, now)
        assert row.catalog["game"]["operator"] == units


def test_frozen_catalog_fills_missing_bond_affiliation_and_preserves_module_effects(env):
    now = datetime(2026, 11, 24)
    with Session(env.engine) as db:
        row = stronghold_resources.ensure_version(db, "s1", "archived")
        row.ends_at = now - timedelta(days=1)
        row.catalog = {"game": {"bond": {"precise": {"description": "原始效果", "operators": None}}}}
        members = [{"id": "chess_a", "char_id": "char_002_amiya", "name": "阿米娅", "tier": 1}]
        stronghold_resources.save_game_catalog(
            row,
            {
                "bond": {"precise": {"description": "新版效果", "operators": members}},
                "module": {"module_a": {"name": "旧模组", "levels": {"1": "旧效果"}}},
            },
            now,
        )
        stronghold_resources.save_game_catalog(
            row, {"module": {"module_a": {"name": "新名", "levels": {"1": "新效果"}}}}, now
        )
        assert stronghold_resources.display_entry(row, "bond", "precise") == {
            "description": "原始效果",
            "operators": members,
        }
        assert stronghold_resources.operator_effect(row, "module", "module_a", 1)["description"] == "旧效果"


def test_background_sync_discovers_all_bindings_and_enforces_manual_floor(env, monkeypatch):
    env.enable()
    now = [datetime(2026, 11, 23, 21)]
    monkeypatch.setattr(stronghold_sync, "now_naive", lambda: now[0])
    env.rows.update(
        {A: [_battle(A, "a")], B: [_battle(B, "b")], C: [_battle(C, "c", scene="old", end="2026-11-22T12:00:00Z")]}
    )
    assert env.sync(4, *A).status_code == 404
    assert env.get(1, "/me")["sync_status"][0]["state"] == "discovering"
    assert env.sync(1, *A).status_code == 202
    assert env.tick()
    assert env.tick()
    assert env.get(4)["total"] == 1
    assert env.sync(1, *B).status_code == 404
    own = next(row for row in env.get(1, "/me")["sync_status"] if row["uid"] == A[1])
    assert to_naive(datetime.fromisoformat(own["next_sync_at"])) == now[0] + timedelta(minutes=10)
    idle = env.get(3, "/me")["sync_status"][0]
    assert to_naive(datetime.fromisoformat(idle["next_sync_at"])) == now[0] + timedelta(minutes=30)
    queued = env.sync(1, *A).json()
    assert queued["state"] == "queued"
    assert to_naive(datetime.fromisoformat(queued["next_sync_at"])) == now[0] + timedelta(minutes=5)
    env.rows[A] = [_battle(A, "old", end="2026-11-23T09:00:00Z")]
    now[0] += timedelta(minutes=5)
    assert env.tick()
    assert env.get(4)["total"] == 1 and len(_ids(env, 1)) == 1
    own = next(row for row in env.get(1, "/me")["sync_status"] if row["uid"] == A[1])
    assert to_naive(datetime.fromisoformat(own["next_sync_at"])) == now[0] + timedelta(minutes=10)


def test_background_sync_handles_unarchived_versions_of_discarded_snapshots(env, monkeypatch):
    env.enable()
    monkeypatch.setattr(stronghold_sync, "now_naive", lambda: datetime(2026, 11, 23, 21))
    env.rows[A] = [
        _battle(A, "older", version="old", end="2026-11-23T11:55:00Z", rounds=5),
        _battle(A, "newer", version="new", rounds=18),
    ]
    assert env.sync(1, *A).status_code == 202
    assert env.tick()
    assert env.tick()
    (record,) = env.get(1, "/me")["records"]
    assert (record["version_key"], record["pass_round"]) == ("s1:new", 18)
    own = next(row for row in env.get(1, "/me")["sync_status"] if row["uid"] == A[1])
    assert own["state"] == "idle"
    with Session(env.engine) as db:
        assert db.get(StrongholdVersion, ("s1", "old")) is None


def test_enrollment_limits_sync_but_keeps_history(env, monkeypatch):
    env.enable()
    now = [datetime(2026, 11, 23, 21)]
    monkeypatch.setattr(stronghold_sync, "now_naive", lambda: now[0])
    selected = ("2", "303")
    env.upstream[1] = [A, selected]
    env.rows[A] = [_battle(A)]
    history_id = env.persist(1, *A).role_id
    env.set_joined(1, A[1], False)
    env.set_joined(1, ALT_A[1], False)
    env.set_joined(1, A[1], True, game=GAME_ENDFIELD)
    env.set_joined(1, selected[1], True)

    requests = []

    def fetch(session, role, **_):
        requests.append((session.member_id, role.channel_master_id, role.uid))
        return StrongholdBatch([], False)

    monkeypatch.setattr(stronghold_source, "official_source", fetch)
    assert env.sync(1, *A).json()["detail"] == "该明日方舟角色未加入本站"
    assert env.tick()
    env.tick()
    own = env.get(1, "/me")
    assert [(s["channel_id"], s["uid"]) for s in own["sync_status"]] == [selected]
    assert {request for request in requests if request[0] == 1} == {(1, *selected)}
    assert env.sync(1, *selected).status_code == 202

    env.set_joined(1, selected[1], False)
    assert env.get(1, "/me")["sync_status"] == []
    assert env.sync(1, *selected).status_code == 404
    now[0] += timedelta(minutes=6)
    requests.clear()
    env.tick()
    assert all(request[0] != 1 for request in requests)
    assert env.get(1, "/me", params={"role_id": history_id})["total"] == 1
    with pytest.raises(stronghold.StrongholdError, match="未加入本站"):
        env.persist(1, *A)


def test_rate_limit_stops_site_traffic_and_invalid_auth_pauses_binding(env, monkeypatch):
    env.enable()
    now = [datetime(2026, 11, 23, 21)]
    monkeypatch.setattr(stronghold_sync, "now_naive", lambda: now[0])
    attempts = []

    def blocked(session, **_):
        attempts.append(session.member_id)
        raise SklandApiError("limit", code=429, retry_after="600")

    monkeypatch.setattr(stronghold_source, "official_source", blocked)
    env.sync(1, *A)
    env.tick()
    env.tick()
    assert len(attempts) == 1
    with Session(env.engine) as db:
        assert db.get(StrongholdSyncControl, 1).retry_until == now[0] + timedelta(minutes=10)
    now[0] += timedelta(minutes=10)
    monkeypatch.setattr(stronghold_source, "official_source", lambda *_, **__: StrongholdBatch([], False))
    env.tick()
    env.tick()

    def expired(session, **_):
        attempts.append(session.member_id)
        raise SklandApiError("expired", code=401)

    monkeypatch.setattr(stronghold_source, "official_source", expired)
    now[0] += timedelta(hours=1)
    env.tick()
    for member in (1, 2, 3, 5):
        assert {slot["state"] for slot in env.get(member, "/me")["sync_status"]} == {"reauth"}
    assert attempts.count(1) >= 2


def test_missing_game_data_repo_uses_known_activity(env, monkeypatch):
    from app.services.upstream_repos import REPO_ARKNIGHTS, RepoNotSyncedError

    def not_synced():
        raise RepoNotSyncedError(REPO_ARKNIGHTS)

    monkeypatch.setattr(stronghold_sync, "discover_activity_versions", not_synced)
    env.enable()
    env.rows[A] = [_battle(A)]
    env.sync(1, *A)
    env.tick()
    env.tick()
    assert env.get(4)["coverage"]["matches"] == 1
    with Session(env.engine) as db:
        assert db.get(StrongholdActivity, stronghold_source._ACTIVITY_ID) is not None


def test_archived_image_retains_digest_and_mime_when_upstream_is_unavailable(env, tmp_path, monkeypatch):
    from io import BytesIO

    import httpx
    from PIL import Image

    from app.services.skland import stronghold_resources as resources

    env.enable()
    generated = BytesIO()
    Image.new("RGBA", (4, 4)).save(generated, format="PNG")
    monkeypatch.setattr(resources, "_asset_dir", lambda: tmp_path / "archived-assets")
    hits = []

    def fetch(method, url, **kwargs):
        hits.append(url)
        assert method == "GET" and not kwargs["follow_redirects"]
        return httpx.Response(200, headers={"Content-Type": "image/png"}, content=generated.getvalue())

    monkeypatch.setattr(resources, "http_request", fetch)
    env.rows[A] = [_battle(A, bonds=[_bond()])]
    env.persist(1, *A)
    with Session(env.engine, autoflush=False) as db:
        resources.save_resources(
            db,
            "s1",
            {
                "V3_1": {
                    "bondInfo": {"a": {"name": "测试盟约", "desc": "<@ba.vup>叠层效果</>", "icon": ICON}},
                }
            },
            datetime(2026, 11, 24),
        )
        db.commit()
        assert resources.archive_assets(db) == 1
        assert resources.archive_assets(db) == 0
    assert hits == [ICON]
    version = env.get(4)["versions"][0]
    assert version["emblem_url"].startswith("/api" + ROOT + "/assets/")
    assert env.get(4)["layers"][0]["description"] == "叠层效果"
    local = env.request(None, "GET", version["emblem_url"].removeprefix("/api" + ROOT))
    assert local.content == generated.getvalue()
    assert local.headers["content-type"] == "image/png"
    assert local.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert env.request(1, "GET", "/assets/" + "0" * 64).status_code == 404
