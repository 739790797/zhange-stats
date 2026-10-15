"""全量回源：整站 dump 后投影；单域失败继续，全挂才失败。"""

from __future__ import annotations

import json

import pytest

from app.services import scheduler_config as scheduler_config_svc
from app.services.tarkov import items as items_svc
from app.services.tarkov import overlay as overlay_svc
from app.services.tarkov import sync as full_sync
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov import upstream as upstream_svc


class _Db:
    """最小 session 替身：_apply_extras 读旧 extras、条件请求读校验头都要能查表。"""

    def __init__(self) -> None:
        self._inner = _RawDb()

    def __getattr__(self, name):  # noqa: ANN001, ANN204
        return getattr(self._inner, name)


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
    """overlay 现在一轮全量只下一次（download_overlay），落库走 persist_overlay。"""
    if fail:
        monkeypatch.setattr(
            overlay_svc,
            "download_overlay",
            lambda *_a, **_k: (_ for _ in ()).throw(
                overlay_svc.TarkovOverlayError("cdn down")
            ),
        )
        return
    monkeypatch.setattr(
        overlay_svc,
        "download_overlay",
        lambda *_a, **_k: ({"tasks": {}}, "2026-01-01T00:00:00+00:00"),
    )
    monkeypatch.setattr(
        overlay_svc,
        "persist_overlay",
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
        upstream_svc,
        "download_site_json",
        lambda **_k: upstream_svc.SiteDump(files=dump, upstream_times={}),
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


def test_sync_all_keeps_going_when_one_apply_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        upstream_svc,
        "download_site_json",
        lambda **_k: upstream_svc.SiteDump(
            files=_sample_dump(), upstream_times={}
        ),
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


def test_sync_all_projects_files_that_were_not_modified(monkeypatch) -> None:
    """304 的 items 不在本轮下载里，投影仍用库里上一份，不能报 dump 缺少 items。"""
    stored = {
        "data": {
            "items": {"a1": {"id": "a1"}},
            "skills": [{"id": "endurance"}],
            "playerLevels": [{"level": 1, "exp": 0}],
        }
    }
    files = {key: value for key, value in _sample_dump().items() if key != "items"}
    monkeypatch.setattr(
        upstream_svc,
        "download_site_json",
        lambda **_k: upstream_svc.SiteDump(
            files=files,
            upstream_times={"items": "2026-08-20T01:00:00+00:00"},
            unchanged=frozenset({"items"}),
        ),
    )
    monkeypatch.setattr(upstream_svc, "persist_site_json", lambda *_a, **_k: [])
    monkeypatch.setattr(upstream_svc, "load_raw", lambda *_a, **_k: stored)
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
    _stub_overlay_sync(monkeypatch)

    out = full_sync.sync_all_from_upstream(_Db(), game_mode="pvp")
    by_id = {row["id"]: row for row in out["domains"]}
    assert by_id["items"]["ok"] is True
    assert by_id["extras"]["ok"] is True
    assert "缺少" not in (by_id["items"].get("error") or "")


def test_sync_all_keeps_going_when_overlay_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        upstream_svc,
        "download_site_json",
        lambda **_k: upstream_svc.SiteDump(
            files=_sample_dump(), upstream_times={}
        ),
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


class _RawQuery:
    def __init__(self, session, model):  # noqa: ANN001
        self.session = session
        self.model = model
        self._rows = list(session.store.get(model, []))

    def options(self, *_a, **_k):  # noqa: ANN001
        return self

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


def test_pack_raw_json_leaves_small_payload_plain() -> None:
    text = json.dumps({"data": {"ok": True}}, ensure_ascii=False)
    assert upstream_svc._pack_raw_json(text) == text
    assert upstream_svc._RAW_JSON_GZIP_MIN_BYTES <= upstream_svc._RAW_JSON_PACKET_BUDGET
    assert upstream_svc._RAW_JSON_PACKET_BUDGET <= 12 * 1024 * 1024


def test_persist_raw_roundtrips_compressed_json(monkeypatch) -> None:
    """超过包预算的物品 dump 落成 gz1，读回仍是原对象；字节不变则不刷新 synced_at。"""
    from datetime import datetime

    from app.services.tarkov.game_mode import game_mode_scope

    monkeypatch.setattr(upstream_svc, "_RAW_JSON_GZIP_MIN_BYTES", 64)
    ticks = iter(
        [
            datetime(2026, 10, 15, 1, 31, 30),
            datetime(2026, 10, 15, 1, 32, 0),
        ]
    )
    monkeypatch.setattr(upstream_svc, "now_naive", lambda: next(ticks))
    db = _RawDb()
    payload = {"data": {"items": {"a1": {"name": "手枪式握把" * 40}}}}
    with game_mode_scope("pvp"):
        first = upstream_svc.persist_raw(
            db, "items", payload, source="json", note="n", changed=True
        )
        stored = _stored(db, "items")
        assert stored.startswith("gz1:")
        assert "手枪式握把" not in stored
        assert upstream_svc.load_raw(db, "items") == payload
        assert upstream_svc.decode_raw_json(json.dumps(payload, ensure_ascii=False)) == payload
        assert upstream_svc.decode_raw_json("gz1:@@@@") is None
        second = upstream_svc.persist_raw(db, "items", payload, source="json", note="n2")
    assert second["synced_at"] == first["synced_at"]


def test_pack_raw_json_refuses_packet_that_stays_oversized(monkeypatch) -> None:
    monkeypatch.setattr(upstream_svc, "_RAW_JSON_GZIP_MIN_BYTES", 1)
    monkeypatch.setattr(upstream_svc, "_RAW_JSON_PACKET_BUDGET", 8)
    with pytest.raises(upstream_svc.TarkovUpstreamError, match="单包上限"):
        upstream_svc._pack_raw_json("{" + ("x" * 40) + "}")


def test_persist_site_json_keeps_other_files_when_one_raw_exceeds_packet(
    monkeypatch,
) -> None:
    from app.services.tarkov.game_mode import game_mode_scope

    real = upstream_svc._pack_raw_json

    def pack(text: str) -> str:
        if "ONLY-ITEMS" in text:
            raise upstream_svc.TarkovUpstreamError("图鉴 raw 超过数据库单包上限")
        return real(text)

    monkeypatch.setattr(upstream_svc, "_pack_raw_json", pack)
    db = _RawDb()
    dump = _sample_dump()
    dump["items"] = {"data": {"items": {"a1": {"id": "ONLY-ITEMS"}}}}
    with game_mode_scope("pvp"):
        rows = upstream_svc.persist_site_json(db, dump)
    by_id = {row["id"]: row for row in rows}
    assert by_id["dump:items"]["ok"] is False
    assert "单包上限" in (by_id["dump:items"]["error"] or "")
    assert by_id["dump:maps"]["ok"] is True
    assert json.loads(_stored(db, "maps"))["data"]["maps"]["customs"]["normalizedName"] == "customs"


def test_persist_site_json_commit_failure_stays_short() -> None:
    from sqlalchemy.exc import OperationalError

    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()

    def boom() -> None:
        raise OperationalError("UPDATE", {}, Exception(2006, "MySQL server has gone away"))

    db.commit = boom  # type: ignore[method-assign]
    db.rollback = lambda: None  # type: ignore[method-assign]
    with (
        game_mode_scope("pvp"),
        pytest.raises(upstream_svc.TarkovUpstreamError, match="连接被断开"),
    ):
        upstream_svc.persist_site_json(db, _sample_dump())


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


def _stored(db, resource: str) -> str:
    """当前模式主文件 raw_json（直接读替身 session 里的行）。"""
    model = upstream_svc.RAW_MODELS[resource]
    row = next(
        r
        for r in db.store[model]
        if (getattr(r, "lang", "") or "") == ""
        and getattr(r, "mode_id", None) == upstream_svc.raw_row_id()
    )
    return row.raw_json


def _garbage_dump(**override: dict) -> dict:
    """200 但内容退化的响应：{"data":{}} / {"errors":[...]} / 空 items。"""
    dump = _sample_dump()
    dump.update(override)
    return dump


def test_persist_site_json_keeps_last_good_items_on_empty_body() -> None:
    """{"data":{}} 这类 200 空响应不能覆盖上一份好 items（生产图鉴曾整份被抹）。"""
    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()
    with game_mode_scope("pvp"):
        upstream_svc.persist_site_json(db, _sample_dump())
        good_items = _stored(db, "items")
        good_maps = _stored(db, "maps")
        rows = upstream_svc.persist_site_json(
            db,
            _garbage_dump(
                items={"data": {}},
                maps={"data": {"maps": {}, "mobs": {}}},
                tasks={"data": {"tasks": {}}},
                traders={"data": {}},
                hideout={"data": {}},
            ),
        )
    by_id = {row["id"]: row for row in rows}
    assert by_id["dump:items"]["ok"] is False
    assert by_id["dump:items"]["status"] == "error"
    assert "保留" in (by_id["dump:items"]["error"] or "")
    assert by_id["dump:maps"]["ok"] is False
    assert by_id["dump:tasks"]["ok"] is False
    assert by_id["dump:traders"]["ok"] is False
    assert by_id["dump:hideout"]["ok"] is False
    # 好 raw 原样留着
    assert _stored(db, "items") == good_items
    assert _stored(db, "maps") == good_maps


def test_persist_site_json_rejects_error_envelope() -> None:
    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()
    with game_mode_scope("pvp"):
        upstream_svc.persist_site_json(db, _sample_dump())
        good = _stored(db, "tasks")
        rows = upstream_svc.persist_site_json(
            db, {"tasks": {"errors": [{"message": "boom"}]}}
        )
    by_id = {row["id"]: row for row in rows}
    assert by_id["dump:tasks"]["ok"] is False
    assert _stored(db, "tasks") == good


def test_persist_site_json_accepts_empty_barters_list() -> None:
    """barters / crafts 空数组是合法状态，不能当成「内容不完整」。"""
    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()
    with game_mode_scope("pvp"):
        rows = upstream_svc.persist_site_json(
            db, {"barters": {"data": []}, "crafts": {"data": []}}
        )
    by_id = {row["id"]: row for row in rows}
    assert by_id["dump:barters"]["ok"] is True
    assert by_id["dump:crafts"]["ok"] is True


def test_persist_site_json_skips_locale_that_lost_its_content() -> None:
    """locale 只剩 {"data":{}} 时别把 zh 行抹空（译文是叠加在主文件上的）。"""
    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()
    dump = _sample_dump()
    dump["items_zh"] = {"data": {"a1 Name": "测试物"}}
    with game_mode_scope("pvp"):
        upstream_svc.persist_site_json(db, dump)
        zh_row = next(
            r
            for r in db.store[upstream_svc.RAW_MODELS["items"]]
            if (r.lang or "") == "zh"
        )
        good_zh = zh_row.raw_json
        rows = upstream_svc.persist_site_json(
            db, {**dump, "items_zh": {"data": {}}}
        )
    by_id = {row["id"]: row for row in rows}
    assert by_id["dump:items_zh"]["ok"] is False
    zh_row = next(
        r
        for r in db.store[upstream_svc.RAW_MODELS["items"]]
        if (r.lang or "") == "zh"
    )
    assert zh_row.raw_json == good_zh


def test_merge_extras_keeps_fields_missing_from_this_dump() -> None:
    """extras 只写这次真下到的字段：dump 缺 items 时别把上一份技能抹成空。"""
    previous = {"skills": [{"id": "endurance"}], "fleaMarket": {"x": 1}}
    incoming = {"lootContainers": {}, "achievements": {}}
    merged = upstream_svc.merge_extras(previous, incoming)
    assert merged["skills"] == [{"id": "endurance"}]
    assert merged["fleaMarket"] == {"x": 1}
    assert merged["achievements"] == {}


def _all_validators() -> dict[str, str]:
    """每个 dump 文件都给一个校验头（键与 download_site_json 里的 key 一致）。"""
    return {
        upstream_svc.resource_key(resource, lang=res_lang): "2026-08-20T01:00:00+00:00"
        for resource, res_lang, _domain_id in upstream_svc.site_dump_specs(lang="zh")
    }


def test_download_site_json_uses_stored_validator_and_keeps_304(monkeypatch) -> None:
    """带条件请求：304 的文件不进 files，也不该被当成失败。"""
    class _Resp:
        def __init__(self, status, content=b"", headers=None):  # noqa: ANN001
            self.status_code = status
            self.content = content
            self.headers = headers or {}

    sent: list[dict] = []

    def fake_response(url, *, headers=None, **_kwargs):  # noqa: ANN001
        sent.append({"url": url, "headers": headers or {}})
        if url.endswith("/items"):
            return _Resp(304)
        return _Resp(200, json.dumps({"data": {"maps": {}}}).encode(), {})

    monkeypatch.setattr(upstream_svc, "download_response", fake_response)
    site = upstream_svc.download_site_json(validators=_all_validators())
    items_call = next(c for c in sent if c["url"].endswith("/items"))
    assert items_call["headers"]["If-Modified-Since"] == "Thu, 20 Aug 2026 01:00:00 GMT"
    assert "items" in site.unchanged
    assert "items" not in site.files
    assert site.upstream_times["items"] == "2026-08-20T01:00:00+00:00"


def test_download_site_json_raises_when_nothing_usable(monkeypatch) -> None:
    """没有一份完整资源、也没有 304：整站不可用。"""
    class _Resp:
        status_code = 200
        headers: dict = {}

        def __init__(self, content: bytes) -> None:
            self.content = content

    monkeypatch.setattr(
        upstream_svc,
        "download_response",
        lambda *_a, **_k: _Resp(b'{"data": {}}'),
    )
    with pytest.raises(upstream_svc.TarkovUpstreamError, match="全站为空"):
        upstream_svc.download_site_json(validators=_all_validators())


def test_persist_raw_skips_the_old_blob_compare_when_upstream_changed(
    monkeypatch,
) -> None:
    """changed=True：上游确认换过字节，不必再把上一份 17MB 读出来比对。"""
    from app.services.tarkov.game_mode import game_mode_scope

    db = _RawDb()
    payload = {"data": {"maps": {"customs": {"normalizedName": "customs"}}}}
    with game_mode_scope("pvp"):
        upstream_svc.persist_raw(db, "maps", payload, source="json", note="first")
        loads: list[bool] = []
        real = upstream_svc.load_raw_row

        def spy(dbc, resource, **kwargs):  # noqa: ANN001
            loads.append(bool(kwargs.get("with_json")))
            return real(dbc, resource, **kwargs)

        monkeypatch.setattr(upstream_svc, "load_raw_row", spy)
        upstream_svc.persist_raw(
            db, "maps", payload, source="json", note="second", changed=True
        )
    assert loads == [False]


def test_scheduler_drops_removed_per_domain_jobs() -> None:
    from app.core.file_config import write_json

    write_json(
        "jobs",
        {
            "tarkov_items_sync": {"enabled": True, "hour": 4, "minute": 30},
            "tarkov_tasks_sync": {"enabled": True, "hour": 4, "minute": 35},
        },
    )
    out = scheduler_config_svc.load_scheduler_config()
    assert out["tarkov_full_sync"]["enabled"] is True
    assert "tarkov_items_sync" not in out
    assert "tarkov_tasks_sync" not in out


def test_site_dump_specs_cover_main_and_locale() -> None:
    specs = upstream_svc.site_dump_specs(lang="zh")
    ids = [row[2] for row in specs]
    assert ids[0] == "dump:items"
    assert "dump:items_zh" in ids
    assert "dump:barters" in ids
    assert len(specs) == len(upstream_svc.JSON_RESOURCES) + len(upstream_svc.JSON_LOCALES)


def test_download_site_json_emits_file_progress(monkeypatch) -> None:
    def fake_resource(resource, lang=None, on_bytes=None):  # noqa: ANN001
        if on_bytes:
            on_bytes(3, 10)
            on_bytes(10, 10)
        return _sample_dump()[upstream_svc.resource_key(resource, lang=lang)], None

    monkeypatch.setattr(upstream_svc, "download_json_resource", fake_resource)
    events: list[dict] = []
    site = upstream_svc.download_site_json(
        on_progress=lambda event: events.append(event)
    )
    dump = site.files
    assert dump["items"]["data"]["items"]
    assert dump["items_zh"] == {"data": {}}
    assert any(
        event["file"] == "items" and event["bytes"] == 3 and not event["done"]
        for event in events
    )
    assert any(
        event["domain_id"] == "dump:items" and event["done"] for event in events
    )
    assert any(event["file"] == "items_zh" for event in events)
    specs = upstream_svc.site_dump_specs(lang="zh")
    ids = [row[2] for row in specs]
    assert ids[0] == "dump:items"
    assert "dump:items_zh" in ids
    assert "dump:barters" in ids
    assert len(specs) == len(upstream_svc.JSON_RESOURCES) + len(upstream_svc.JSON_LOCALES)


def test_format_full_sync_message() -> None:
    assert full_sync.format_full_sync_message("start") == "正在全量更新…"
    assert (
        full_sync.format_full_sync_message("download", file="items", index=2, total=12)
        == "正在下载 items（2/12）"
    )
    assert full_sync.format_full_sync_message("overlay") == "正在下载 overlay…"


def test_planned_full_sync_domains_include_dump_and_apply() -> None:
    rows = full_sync.planned_full_sync_domains(("pvp",), lang="zh")
    ids = [row["id"] for row in rows]
    assert ids[0] == "dump:items"
    assert "overlay" in ids
    assert "extras" in ids
    assert "locks" in ids
    assert all(row["status"] == "pending" and row["mode"] == "pvp" for row in rows)


def test_sync_emits_download_progress(monkeypatch) -> None:
    dump = _sample_dump()

    def fake_download(*, lang="zh", on_progress=None, validators=None):  # noqa: ARG001
        if on_progress:
            on_progress(
                {
                    "phase": "download",
                    "file": "items",
                    "domain_id": "dump:items",
                    "index": 1,
                    "total": 12,
                    "bytes": 40,
                    "total_bytes": 80,
                    "done": False,
                    "error": None,
                }
            )
            on_progress(
                {
                    "phase": "download",
                    "file": "items",
                    "domain_id": "dump:items",
                    "index": 1,
                    "total": 12,
                    "bytes": 80,
                    "total_bytes": 80,
                    "done": True,
                    "error": None,
                }
            )
        return upstream_svc.SiteDump(files=dump, upstream_times={})

    monkeypatch.setattr(upstream_svc, "download_site_json", fake_download)
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
    monkeypatch.setattr(items_svc, "rebuild_from_raw", lambda *_a, **_k: _ok())
    _stub_overlay_sync(monkeypatch)

    events: list[tuple[str, dict]] = []

    def progress(message: str, stats: dict) -> None:
        events.append((message, stats))

    out = full_sync.sync_all_from_upstream(_Db(), game_mode="pvp", progress=progress)
    assert out["failed_count"] == 0
    assert events[0][1]["phase"] == "start"
    assert events[0][1]["domains"]
    download_stats = [stats for _msg, stats in events if stats.get("phase") == "download"]
    assert download_stats
    assert any(stats.get("file") == "items" for stats in download_stats)
    live = next(
        row
        for stats in download_stats
        for row in stats["domains"]
        if row["id"] == "dump:items" and row.get("status") == "downloading"
    )
    assert live["bytes"] == 40
    assert live["total_bytes"] == 80
    assert events[-1][1]["phase"] == "done"
    assert events[-1][1]["percent"] == 100
