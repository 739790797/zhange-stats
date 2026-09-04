"""全量回源：整站 dump 后投影；单域失败继续，全挂才失败。"""

from __future__ import annotations

import json

from app.services import scheduler_config as scheduler_config_svc
from app.services.tarkov import bosses as bosses_svc
from app.services.tarkov import guides as guides_svc
from app.services.tarkov import items as items_svc
from app.services.tarkov import key_packs as key_packs_svc
from app.services.tarkov import overlay as overlay_svc
from app.services.tarkov import sync as full_sync
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov import traders as traders_svc
from app.services.tarkov import upstream as upstream_svc


class _Db:
    pass


def _sample_dump() -> dict:
    return {
        "items": {
            "data": {
                "items": {"a1": {"id": "a1"}},
                "skills": [{"id": "endurance"}],
                "playerLevels": [{"level": 1, "exp": 0}],
            }
        },
        "items_zh": {"data": {}},
        "maps": {
            "data": {
                "maps": {
                    "customs": {
                        "normalizedName": "customs",
                        "locks": [{"key": "dorm-114"}],
                        "accessKeys": [],
                    }
                },
                "mobs": {"reshala": {"id": "reshala"}},
                "lootContainers": {},
            }
        },
        "maps_zh": {"data": {}},
        "tasks": {
            "data": {
                "tasks": {"t1": {"id": "t1", "name": "Task"}},
                "achievements": {},
            }
        },
        "tasks_zh": {"data": {}},
        "traders": {"data": {"prapor": {"normalizedName": "prapor", "levels": []}}},
        "traders_zh": {"data": {}},
        "hideout": {"data": {"bitcoin-farm": {"id": "bf"}}},
        "hideout_zh": {"data": {}},
        "barters": {"data": []},
        "crafts": {"data": []},
    }


def _ok(source: str = "json") -> dict:
    return {"source": source, "synced_at": "t"}


def _stub_overlay_sync(monkeypatch, *, fail: bool = False) -> None:
    if fail:
        monkeypatch.setattr(
            overlay_svc,
            "sync_overlay",
            lambda *_a, **_k: (_ for _ in ()).throw(
                overlay_svc.TarkovOverlayError("cdn down")
            ),
        )
        return
    monkeypatch.setattr(
        overlay_svc,
        "sync_overlay",
        lambda *_a, **_k: {
            "id": "overlay",
            "ok": True,
            "source": overlay_svc.SOURCE_OVERLAY,
            "synced_at": "t",
            "error": None,
        },
    )


def test_sync_all_dumps_json_then_applies(monkeypatch) -> None:
    dump = _sample_dump()
    calls: list[str] = []

    monkeypatch.setattr(
        upstream_svc, "download_site_json", lambda **_k: (dump, {})
    )
    monkeypatch.setattr(
        upstream_svc,
        "persist_site_json",
        lambda *_a, **_k: [
            {
                "id": "dump:items",
                "ok": True,
                "source": "json.tarkov.dev",
                "synced_at": "t",
                "error": None,
            }
        ],
    )
    monkeypatch.setattr(
        upstream_svc,
        "persist_raw",
        lambda *_a, **_k: {
            "id": "extras",
            "ok": True,
            "source": "json.tarkov.dev",
            "synced_at": "t",
            "error": None,
        },
    )
    monkeypatch.setattr(
        items_svc,
        "rebuild_from_raw",
        lambda *_a, **_k: calls.append("items") or _ok(),
    )
    _stub_overlay_sync(monkeypatch)
    key_packs_svc._lock_cache.clear()

    out = full_sync.sync_all_from_upstream(_Db(), game_mode="pvp")
    assert out["failed_count"] == 0
    assert out["message"] == "ok"
    assert calls == ["items"]
    ids = [row["id"] for row in out["domains"]]
    assert "dump:items" in ids
    assert "items" in ids
    assert "maps" in ids
    assert "locks" in ids
    assert "overlay" in ids
    assert "extras" in ids
    assert key_packs_svc._lock_cache


def test_sync_all_keeps_going_when_one_apply_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        upstream_svc, "download_site_json", lambda **_k: (_sample_dump(), {})
    )
    monkeypatch.setattr(
        upstream_svc,
        "persist_site_json",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        upstream_svc,
        "persist_raw",
        lambda *_a, **_k: {
            "id": "extras",
            "ok": True,
            "source": "json.tarkov.dev",
            "synced_at": "t",
            "error": None,
        },
    )
    monkeypatch.setattr(items_svc, "rebuild_from_raw", lambda *_a, **_k: _ok())
    monkeypatch.setattr(
        tasks_svc,
        "_tasks_map",
        lambda *_a, **_k: (_ for _ in ()).throw(tasks_svc.TarkovTasksError("tasks down")),
    )
    _stub_overlay_sync(monkeypatch)

    out = full_sync.sync_all_from_upstream(_Db(), game_mode="pvp")
    assert out["message"] == "partial"
    by_id = {row["id"]: row for row in out["domains"]}
    assert by_id["tasks"]["ok"] is False
    assert "tasks down" in (by_id["tasks"]["error"] or "")
    assert by_id["items"]["ok"] is True
    assert by_id["overlay"]["ok"] is True
    assert by_id["extras"]["ok"] is True


def test_sync_all_keeps_going_when_overlay_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        upstream_svc, "download_site_json", lambda **_k: (_sample_dump(), {})
    )
    monkeypatch.setattr(upstream_svc, "persist_site_json", lambda *_a, **_k: [])
    monkeypatch.setattr(
        upstream_svc,
        "persist_raw",
        lambda *_a, **_k: {
            "id": "extras",
            "ok": True,
            "source": "json.tarkov.dev",
            "synced_at": "t",
            "error": None,
        },
    )
    monkeypatch.setattr(items_svc, "rebuild_from_raw", lambda *_a, **_k: _ok())
    _stub_overlay_sync(monkeypatch, fail=True)

    out = full_sync.sync_all_from_upstream(_Db(), game_mode="pvp")
    assert out["message"] == "partial"
    by_id = {row["id"]: row for row in out["domains"]}
    assert by_id["overlay"]["ok"] is False
    assert "cdn down" in (by_id["overlay"]["error"] or "")
    assert by_id["items"]["ok"] is True
    assert by_id["extras"]["ok"] is True


def test_sync_all_raises_when_dump_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        upstream_svc,
        "download_site_json",
        lambda **_k: (_ for _ in ()).throw(upstream_svc.TarkovUpstreamError("no dump")),
    )
    try:
        full_sync.sync_all_from_upstream(_Db(), game_mode="pvp")
    except full_sync.TarkovFullSyncError as exc:
        assert "全量同步失败" in str(exc)
        assert "no dump" in str(exc)
    else:
        raise AssertionError("expected TarkovFullSyncError")


class _SchedulerRow:
    def __init__(self, value: str) -> None:
        self.value = value


class _SchedulerQuery:
    def __init__(self, row: _SchedulerRow | None) -> None:
        self._row = row

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._row


class _SchedulerDb:
    def __init__(self, stored: dict | None) -> None:
        self._row = None if stored is None else _SchedulerRow(json.dumps(stored))

    def query(self, *_a, **_k):
        return _SchedulerQuery(self._row)


class _RawQuery:
    def __init__(self, session, model):  # noqa: ANN001
        self.session = session
        self.model = model
        self._rows = list(session.store.get(model, []))

    def filter(self, *args, **_k):  # noqa: ANN001
        for expr in args:
            left = getattr(expr, "left", None)
            key = getattr(left, "key", None) or getattr(left, "name", None)
            right = getattr(expr, "right", None)
            value = getattr(right, "value", right)
            if key:
                self._rows = [
                    r for r in self._rows if getattr(r, key, None) == value
                ]
        return self

    def one_or_none(self):
        return self._rows[0] if self._rows else None


class _RawDb:
    def __init__(self) -> None:
        self.store = {model: [] for model in upstream_svc.RAW_MODELS.values()}

    def query(self, model):  # noqa: ANN001
        return _RawQuery(self, model)

    def add(self, obj):  # noqa: ANN001
        bucket = self.store.setdefault(type(obj), [])
        bucket[:] = [
            row
            for row in bucket
            if not (
                getattr(row, "mode_id", None) == getattr(obj, "mode_id", None)
                and (getattr(row, "lang", "") or "") == (getattr(obj, "lang", "") or "")
            )
        ]
        bucket.append(obj)

    def commit(self) -> None:
        return None


def test_load_main_payload_merges_locale() -> None:
    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()
    dump = _sample_dump()
    dump["items_zh"] = {"data": {"a1 Name": "测试物"}}
    with game_mode_scope("pvp"):
        upstream_svc.persist_site_json(db, dump)
        source, payload, synced, note = upstream_svc.load_main_payload(db, "items")
    assert source
    assert synced
    assert payload["data"]["items"]["a1"]["id"] == "a1"
    assert payload["locale"]["a1 Name"] == "测试物"
    main = next(
        row
        for row in db.store[upstream_svc.RAW_MODELS["items"]]
        if (row.lang or "") == ""
    )
    assert "locale" not in json.loads(main.raw_json)


def test_persist_site_json_writes_eight_raw_tables() -> None:
    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()
    with game_mode_scope("pvp"):
        rows = upstream_svc.persist_site_json(db, _sample_dump())
        extras = upstream_svc.persist_raw(
            db,
            upstream_svc.EXTRAS_RESOURCE,
            {"skills": []},
            source="json.tarkov.dev",
            note="json.tarkov.dev/regular extras",
        )
        overlay = upstream_svc.persist_raw(
            db,
            overlay_svc.OVERLAY_RESOURCE,
            {"tasks": {}},
            source=overlay_svc.SOURCE_OVERLAY,
            note="overlay",
        )
    assert extras["ok"] is True
    assert overlay["ok"] is True
    ok_ids = {row["id"] for row in rows if row["ok"]}
    assert "dump:items" in ok_ids
    assert "dump:maps" in ok_ids
    assert "dump:hideout" in ok_ids
    assert "dump:barters" in ok_ids
    assert "dump:crafts" in ok_ids
    filled = {
        name
        for name, model in upstream_svc.RAW_MODELS.items()
        if db.store.get(model)
    }
    assert filled == set(upstream_svc.RAW_MODELS)


def test_persist_raw_keeps_synced_at_when_payload_unchanged(monkeypatch) -> None:
    from datetime import datetime

    from app.services.tarkov.game_mode import game_mode_scope

    ticks = iter(
        [
            datetime(2026, 1, 1, 12, 0, 0),
            datetime(2026, 1, 1, 12, 0, 5),
            datetime(2026, 1, 1, 12, 0, 10),
        ]
    )
    monkeypatch.setattr(upstream_svc, "now_naive", lambda: next(ticks))
    db = _RawDb()
    payload = {"data": {"maps": {"customs": {"normalizedName": "customs"}}}}
    with game_mode_scope("pvp"):
        first = upstream_svc.persist_raw(
            db,
            "maps",
            payload,
            source="json.tarkov.dev",
            note="first",
        )
        second = upstream_svc.persist_raw(
            db,
            "maps",
            payload,
            source="json.tarkov.dev",
            note="second",
        )
        changed = upstream_svc.persist_raw(
            db,
            "maps",
            {"data": {"maps": {"factory": {"normalizedName": "factory"}}}},
            source="json.tarkov.dev",
            note="third",
        )
    assert first["synced_at"] == second["synced_at"]
    assert first["synced_at"] == "2026-01-01T12:00:00"
    assert changed["synced_at"] == "2026-01-01T12:00:10"


def test_persist_site_json_records_upstream_last_modified() -> None:
    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()
    with game_mode_scope("pvp"):
        rows = upstream_svc.persist_site_json(
            db,
            _sample_dump(),
            upstream_times={"items": "2026-08-26T09:01:54+00:00"},
        )
    by_id = {row["id"]: row for row in rows}
    assert by_id["dump:items"]["upstream_at"] == "2026-08-26T09:01:54+00:00"
    assert by_id["dump:items"]["mode"] == "pvp"
    items = next(
        row
        for row in db.store[upstream_svc.RAW_MODELS["items"]]
        if (row.lang or "") == ""
    )
    assert "上游 2026-08-26T09:01:54+00:00" in (items.note or "")


def test_extras_from_site_dump_pulls_nested_catalogs() -> None:
    extras = upstream_svc.extras_from_site_dump(_sample_dump())
    assert extras["skills"] == [{"id": "endurance"}]
    assert extras["playerLevels"] == [{"level": 1, "exp": 0}]
    assert extras["lootContainers"] == {}
    assert extras["achievements"] == {}


def test_scheduler_drops_removed_per_domain_jobs() -> None:
    stored = {
        "tarkov_items_sync": {"enabled": True, "hour": 4, "minute": 30},
        "tarkov_tasks_sync": {"enabled": True, "hour": 4, "minute": 35},
    }
    out = scheduler_config_svc.load_scheduler_config(_SchedulerDb(stored))
    assert out["tarkov_full_sync"]["enabled"] is True
    assert "tarkov_items_sync" not in out
    assert "tarkov_tasks_sync" not in out
