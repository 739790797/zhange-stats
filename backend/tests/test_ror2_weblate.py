"""Weblate 快照：已审且原文指纹一致才显示。游戏中文只作为建议。"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.guide_raw import GuideRaw
from app.models.guide_token_translation import GuideTokenTranslation, GuideTokenTranslationSync
from app.services.ror2.schemas import Ror2CatalogOut, Ror2ItemOut, Ror2SkillGroupOut, Ror2SkillOut, Ror2SurvivorDetailOut, Ror2SurvivorOut
from app.services.ror2.strings import (
    apply_catalog,
    apply_detail,
    fingerprint,
    prefill_catalog,
    prefill_detail,
    resolve_catalog_texts,
)
from app.services.platform_features import invalidate_feature_cache, load_feature_flags
from app.services.scheduler_config import load_scheduler_config
from app.services.ror2.weblate import (
    WeblateError,
    accept_snapshot,
    list_units,
    RESOURCE as WEBLATE_RESOURCE,
    load_snapshot,
    normalize_base_url,
    select_suggestions,
    sync_weblate,
    weblate_revision,
    weblate_settings,
)


class _Response:
    def __init__(self, payload: dict, status: int = 200):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self) -> dict:
        return self._payload


def _sources(units: dict[str, dict[str, str]]) -> dict[str, str]:
    return {
        key: row["source"]
        for key, row in units.items()
        if isinstance(row, dict) and isinstance(row.get("source"), str)
    }


def _catalog() -> Ror2CatalogOut:
    return Ror2CatalogOut(
        source="https://riskofrain2.wiki.gg/",
        fetched_at="2026-10-16T00:00:00",
        items=[
            Ror2ItemOut(
                name="Soldier's Syringe",
                description="Increases attack speed.",
                internal_name="ITEM_SYRINGE",
                wiki_url="https://riskofrain2.wiki.gg/wiki/Soldier%27s_Syringe",
            ),
            Ror2ItemOut(
                name="Will-o'-the-wisp",
                internal_name="ITEM_EXPODEONDEATH",
                wiki_url="https://riskofrain2.wiki.gg/wiki/Will-o%27-the-wisp",
            ),
        ],
        equipment=[],
        survivors=[
            Ror2SurvivorOut(name="Commando", wiki_url="https://riskofrain2.wiki.gg/wiki/Commando"),
        ],
    )


def test_old_language_job_keeps_its_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.scheduler_config.read_json",
        lambda _name: {
            "scheduler": {
                "ror2_lang_sync": {"enabled": False, "hour": 3, "minute": 15, "lang_dir": "D:/old"},
            }
        },
    )
    job = load_scheduler_config()["ror2_weblate_sync"]
    assert job == {"enabled": False, "hour": 3, "minute": 15}


def test_old_language_feature_flag_follows_the_new_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.platform_features.read_json",
        lambda _name: {"features": {"guides.ror2.lang_sync": False}},
    )
    invalidate_feature_cache()
    assert load_feature_flags()["guides.ror2.weblate_sync"] is False
    invalidate_feature_cache()


def test_fingerprint_pins_newlines_trailing_space_and_composition() -> None:
    assert fingerprint("A \r\n\nB \n") == fingerprint("A\n\nB")
    assert fingerprint("e\u0301") == fingerprint("\u00e9")


def test_approved_translation_hides_when_the_wiki_source_changes() -> None:
    catalog = _catalog()
    units = {
        "items.items.ITEM_SYRINGE.name": {
            "source": "Soldier's Syringe",
            "target": "士兵的注射器",
            "state": "approved",
        },
        "items.items.ITEM_SYRINGE.Desc": {
            "source": "Old description",
            "target": "旧说明",
            "state": "approved",
        },
    }
    apply_catalog(catalog, units, _sources(units))
    syringe = catalog.items[0]
    assert syringe.name_zh == "士兵的注射器"
    assert syringe.name == "Soldier's Syringe"
    assert syringe.description_zh == ""


def test_approved_game_contexts_backfill_catalog_fields() -> None:
    from app.services.ror2.schemas import Ror2ArtifactOut

    catalog = _catalog()
    catalog.equipment = [
        Ror2ItemOut(
            name="Royal Capacitor",
            internal_name="EQUIPMENT_LIGHTNING",
            wiki_url="https://riskofrain2.wiki.gg/wiki/Royal_Capacitor",
        )
    ]
    catalog.artifacts = [
        Ror2ArtifactOut(
            name="Command",
            description="Choose your items.",
            wiki_url="https://riskofrain2.wiki.gg/wiki/Artifact_of_Command",
        )
    ]
    units = {
        "items.items.ITEM_SYRINGE.name": {
            "source": "Soldier's Syringe",
            "target": "士兵的注射器",
            "state": "approved",
        },
        "items.items.ITEM_SYRINGE.Desc": {
            "source": "Increases attack speed.",
            "target": "提高攻击速度。",
            "state": "approved",
        },
        "equipment.equipment.EQUIPMENT_LIGHTNING.name": {
            "source": "Royal Capacitor",
            "target": "皇家电容器",
            "state": "approved",
        },
        "survivors.Survivors.Commando.Name": {
            "source": "Commando",
            "target": "指挥官",
            "state": "approved",
        },
        "artifacts.artifact.Command.Desc": {
            "source": "Choose your items.",
            "target": "选择你的物品。",
            "state": "approved",
        },
    }

    apply_catalog(catalog, units, _sources(units))

    assert catalog.items[0].name_zh == "士兵的注射器"
    assert catalog.items[0].description_zh == "提高攻击速度。"
    assert catalog.equipment[0].name_zh == "皇家电容器"
    assert catalog.survivors[0].name_zh == "指挥官"
    assert catalog.artifacts[0].description_zh == "选择你的物品。"


def test_context_backfill_disambiguates_shared_localization_tokens() -> None:
    catalog = _catalog()
    catalog.items = [
        Ror2ItemOut(
            name="Variant One",
            description="First description.",
            internal_name="ITEM_SHARED",
            wiki_url="https://riskofrain2.wiki.gg/wiki/Variant_One",
        ),
        Ror2ItemOut(
            name="Variant Two",
            description="Second description.",
            internal_name="ITEM_SHARED",
            wiki_url="https://riskofrain2.wiki.gg/wiki/Variant_Two",
        ),
    ]
    units = {
        "items.items.ITEM_SHARED.Variant One.Desc": {
            "source": "First description.",
            "target": "第一条说明。",
            "state": "approved",
        },
        "items.items.Variant Two.ITEM_SHARED.Desc": {
            "source": "Second description.",
            "target": "第二条说明。",
            "state": "approved",
        },
    }

    apply_catalog(catalog, units, _sources(units))

    assert [row.description_zh for row in catalog.items] == ["第一条说明。", "第二条说明。"]


def test_context_backfill_normalizes_wiki_markup_but_keeps_rendered_tags() -> None:
    catalog = _catalog()
    catalog.items[0].description = "<style=cIsDamage>70% damage</style>."
    units = {
        "items.items.ITEM_SYRINGE.Desc": {
            "source": "{{Color|d|70% damage}}.",
            "target": "{{Color|d|造成70%伤害}}。",
            "state": "approved",
        }
    }

    apply_catalog(catalog, units, _sources(units))

    assert catalog.items[0].description_zh == "<style=cIsDamage>造成70%伤害</style>。"


def test_context_backfill_resolves_skill_and_survivor_lore() -> None:
    detail = Ror2SurvivorDetailOut(
        name="Commando",
        wiki_url="https://riskofrain2.wiki.gg/wiki/Commando",
        lore="<style=cIsHealing>Personal log.</style>",
        skills=[
            Ror2SkillGroupOut(
                skill_type="Primary",
                skills=[
                    Ror2SkillOut(
                        name="Auto-Nailgun",
                        skill_type="Primary",
                        description="Fire nails for <style=cIsDamage>70% damage</style>.",
                    )
                ],
            )
        ],
    )
    units = {
        "skills.skills.Auto-Nailgun.Name": {
            "source": "Auto-Nailgun",
            "target": "自动钉枪",
            "state": "approved",
        },
        "skills.skills.Auto-Nailgun.Desc": {
            "source": "Fire nails for {{Color|d|70% damage}}.",
            "target": "发射钉子造成{{Color|d|70%伤害}}。",
            "state": "approved",
        },
        "lore.lore.Commando.Desc": {
            "source": "{{Color|h|Personal log.}}",
            "target": "{{Color|h|个人日志。}}",
            "state": "approved",
        },
    }

    apply_detail(detail, units, _sources(units))

    skill = detail.skills[0].skills[0]
    assert skill.name_zh == "自动钉枪"
    assert skill.description_zh == "发射钉子造成<style=cIsDamage>70%伤害</style>。"
    assert detail.lore_zh == "<style=cIsHealing>个人日志。</style>"


def test_context_backfill_accepts_only_current_approved_field_aliases() -> None:
    catalog = _catalog()
    units = {
        "items.items.ITEM_SYRINGE.Desc": {
            "source": "A different source.",
            "target": "过期译文。",
            "state": "approved",
        },
        "items.items.ITEM_SYRINGE.Description": {
            "source": "Increases attack speed.",
            "target": "有效译文。",
            "state": "approved",
        },
        "items.items.ITEM_SYRINGE.description": {
            "source": "Increases attack speed.",
            "target": "未审核译文。",
            "state": "suggested",
        },
    }

    apply_catalog(catalog, units, _sources(units))

    assert catalog.items[0].description_zh == "有效译文。"


def test_context_backfill_rejects_stale_and_unapproved_units() -> None:
    catalog = _catalog()
    units = {
        "items.items.ITEM_SYRINGE.Desc": {
            "source": "A different source.",
            "target": "过期译文。",
            "state": "approved",
        },
        "items.items.ITEM_SYRINGE.Description": {
            "source": "Increases attack speed.",
            "target": "未审核译文。",
            "state": "suggested",
        },
    }

    apply_catalog(catalog, units, _sources(units))

    assert catalog.items[0].description_zh == ""


def test_context_backfill_rejects_conflicting_field_aliases() -> None:
    catalog = _catalog()
    units = {
        "items.items.ITEM_SYRINGE.Desc": {
            "source": "Increases attack speed.",
            "target": "译文一。",
            "state": "approved",
        },
        "items.items.ITEM_SYRINGE.Description": {
            "source": "Increases attack speed.",
            "target": "译文二。",
            "state": "approved",
        },
    }

    apply_catalog(catalog, units, _sources(units))

    assert catalog.items[0].description_zh == ""


def test_prefill_uses_the_wiki_token_and_does_not_approve_itself() -> None:
    catalog = _catalog()
    suggestions = prefill_catalog(
        catalog,
        {
            "ITEM_SYRINGE_NAME": "士兵的注射器",
            "ITEM_EXPLODEONDEATH_NAME": "鬼火",
            "COMMANDO_BODY_NAME": "指挥官",
        },
    )
    assert suggestions["item.ITEM_SYRINGE.name"] == "士兵的注射器"
    assert suggestions["item.ITEM_EXPODEONDEATH.name"] == "鬼火"
    assert suggestions["survivor.Commando.name"] == "指挥官"
    assert catalog.items[0].name_zh == ""
    assert catalog.survivors[0].name_zh == ""


def test_prefill_detail_suggests_lore_and_skill_without_writing_the_page() -> None:
    detail = Ror2SurvivorDetailOut(
        name="Commando",
        wiki_url="https://riskofrain2.wiki.gg/wiki/Commando",
        lore="The soldier ducked.",
        skills=[
            Ror2SkillGroupOut(
                skill_type="Primary",
                skills=[Ror2SkillOut(name="Double Tap", skill_type="Primary", description="Rapidly shoot for 100% damage.")],
            )
        ],
    )
    suggestions = prefill_detail(
        detail,
        {
            "COMMANDO_BODY_LORE": "士兵缩身躲避。",
            "COMMANDO_PRIMARY_NAME": "双击",
            "COMMANDO_PRIMARY_DESCRIPTION": "造成100%的伤害。",
        },
    )
    assert suggestions["survivor.Commando.lore"] == "士兵缩身躲避。"
    assert suggestions["skill.Commando.Double Tap.name"] == "双击"
    assert "100%的伤害" in suggestions["skill.Commando.Double Tap.desc"]
    assert detail.lore_zh == ""
    assert detail.skills[0].skills[0].name_zh == ""


def test_select_suggestions_skips_filled_and_pending_units() -> None:
    chosen = select_suggestions(
        [
            {"context": "item.ITEM_SYRINGE.name", "target": ["士兵的注射器"], "pending": False},
            {"context": "survivor.Commando.name", "target": [""], "pending": True},
            {"context": "item.ITEM_SYRINGE.desc", "target": [], "pending": False},
        ],
        {
            "item.ITEM_SYRINGE.name": "士兵的注射器",
            "survivor.Commando.name": "指挥官",
            "item.ITEM_SYRINGE.desc": "提高攻击速度。",
            "survivor.Huntress.name": "猎手",
        },
    )
    assert chosen == {
        "item.ITEM_SYRINGE.desc": "提高攻击速度。",
        "survivor.Huntress.name": "猎手",
    }


def test_snapshot_rejects_unapproved_units() -> None:
    with pytest.raises(WeblateError, match="已审"):
        accept_snapshot(
            json.dumps(
                {
                    "version": 2,
                    "sources": {"items.ITEM_SYRINGE.name": "Soldier's Syringe"},
                    "units": {
                        "items.ITEM_SYRINGE.name": {
                            "source": "Soldier's Syringe",
                            "target": "士兵的注射器",
                            "state": "fuzzy",
                        }
                    },
                }
            )
        )


def test_legacy_v1_snapshot_keeps_approved_translations_and_real_contexts() -> None:
    from app.services.guide_raw.pipeline import upsert_raw
    from app.services.ror2.strings import resolve_context_text

    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    GuideTokenTranslationSync.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    context = "items.ITEM_SYRINGE.Desc"
    body = json.dumps(
        {
            "version": 1,
            "units": {
                context: {
                    "source": "Increases attack speed.",
                    "target": "提高攻击速度。",
                    "state": "approved",
                }
            },
        },
        ensure_ascii=False,
    )
    upsert_raw(db, "ror2", WEBLATE_RESOURCE, "local legacy fixture", body)

    try:
        snapshot = load_snapshot(db)
        assert snapshot.sources == {context: "Increases attack speed."}
        assert snapshot.units[context] == {
            "source": "Increases attack speed.",
            "target": "提高攻击速度。",
            "state": "approved",
        }
        resolved = resolve_context_text(
            "Increases attack speed.", context, snapshot.sources, snapshot.units
        )
        assert resolved.text == "提高攻击速度。"
        assert resolved.original == "Increases attack speed."
        assert resolved.token == context

        stale = resolve_context_text("A changed source", context, snapshot.sources, snapshot.units)
        assert stale.text == "A changed source"
        assert stale.token is None
    finally:
        db.close()
        engine.dispose()


def test_legacy_v1_snapshot_with_unapproved_entry_fails_closed() -> None:
    from app.services.guide_raw.pipeline import upsert_raw

    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    GuideTokenTranslationSync.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    body = json.dumps(
        {
            "version": 1,
            "units": {
                "items.ITEM_SYRINGE.Desc": {
                    "source": "Increases attack speed.",
                    "target": "未审核译文",
                    "state": "pending",
                }
            },
        },
        ensure_ascii=False,
    )
    upsert_raw(db, "ror2", WEBLATE_RESOURCE, "local legacy fixture", body)

    try:
        snapshot = load_snapshot(db)
        assert snapshot.sources == {}
        assert snapshot.units == {}
    finally:
        db.close()
        engine.dispose()


def test_legacy_snapshot_rejects_boolean_version() -> None:
    from app.services.guide_raw.pipeline import upsert_raw

    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    GuideTokenTranslationSync.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    body = json.dumps(
        {
            "version": True,
            "units": {
                "items.ITEM_SYRINGE.Desc": {
                    "source": "Increases attack speed.",
                    "target": "提高攻击速度。",
                    "state": "approved",
                }
            },
        },
        ensure_ascii=False,
    )
    upsert_raw(db, "ror2", WEBLATE_RESOURCE, "local legacy fixture", body)

    try:
        snapshot = load_snapshot(db)
        assert snapshot.sources == {}
        assert snapshot.units == {}
    finally:
        db.close()
        engine.dispose()


def test_weblate_url_requires_https_except_loopback() -> None:
    assert normalize_base_url("https://weblate.example.com/path/") == "https://weblate.example.com/path"
    assert normalize_base_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"
    with pytest.raises(WeblateError, match="https"):
        normalize_base_url("http://weblate.example.com")
    with pytest.raises(WeblateError, match="令牌"):
        normalize_base_url("https://token@weblate.example.com")
    with pytest.raises(WeblateError, match="查询"):
        normalize_base_url("https://weblate.example.com/base?next=/other")
    with pytest.raises(WeblateError, match="格式"):
        normalize_base_url("https://weblate.example.com:invalid")


def test_settings_require_a_complete_component(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.integrations_config.load_integrations", lambda _db=None: {})
    with pytest.raises(WeblateError, match="还没有配置"):
        weblate_settings()


def test_list_units_rejects_an_offsite_page() -> None:
    def client(method: str, url: str, **_kwargs: object) -> _Response:
        assert method == "GET"
        return _Response({"results": [], "next": "https://evil.example/api/units/"})

    with pytest.raises(WeblateError, match="站外"):
        list_units(
            {
                "base": "https://weblate.example.com",
                "token": "secret-token",
                "project": "zhange",
                "component": "ror2",
            },
            client=client,
        )


def test_weblate_get_rejects_redirect_even_if_body_looks_valid() -> None:
    def client(method: str, _url: str, **_kwargs: object) -> _Response:
        assert method == "GET"
        return _Response({"count": 0, "results": [], "next": None}, status=302)

    with pytest.raises(WeblateError, match="HTTP 302"):
        list_units(
            {
                "base": "https://weblate.example.com",
                "token": "secret-token",
                "project": "zhange",
                "component": "ror2",
            },
            client=client,
        )


def test_weblate_upload_rejects_redirect_even_if_body_looks_successful() -> None:
    from app.services.ror2.weblate import upload_json

    def client(method: str, _url: str, **_kwargs: object) -> _Response:
        assert method == "POST"
        return _Response(
            {"result": True, "accepted": 1, "skipped": 0, "not_found": 0, "total": 1},
            status=302,
        )

    with pytest.raises(WeblateError, match="HTTP 302"):
        upload_json(
            {
                "base": "https://weblate.example.com",
                "token": "secret-token",
                "project": "zhange",
                "component": "ror2",
            },
            "zh_Hans",
            "suggest",
            {"items.ITEM.Desc": "译文"},
            client=client,
        )


def test_upload_is_split_so_a_proxy_can_finish_each_request() -> None:
    from app.services.ror2.weblate import _batches

    strings = {f"k{i}": "字" * 100 for i in range(10)}
    batches = _batches(strings, max_bytes=500)
    assert len(batches) > 1
    assert sum(len(batch) for batch in batches) == 10


def test_lua_module_strings_follow_the_token_and_skip_codes() -> None:
    from app.services.ror2.units import extract_units

    body = """
local items = {}
items["Soldier's Syringe"] = {
  Quote = "Increase attack speed.",
  Desc = "Increases attack speed by 15%.",
  LocalizationInternalName = "ITEM_SYRINGE",
  ID = "Syringe",
  Image = "Syringe.png",
}
return items
"""
    units = extract_units("items", body)
    assert units["items.ITEM_SYRINGE.name"] == "Soldier's Syringe"
    assert units["items.ITEM_SYRINGE.Quote"] == "Increase attack speed."
    assert "15%" in units["items.ITEM_SYRINGE.Desc"]
    assert "ITEM_SYRINGE" not in units.values()
    assert not any(value.endswith(".png") for value in units.values())


def test_shared_token_keeps_the_wiki_name_in_the_id() -> None:
    from app.services.ror2.units import extract_units

    body = """
local Monsters = {
  ["Anima Harvester"] = { LocalizationInternalName = "REAPER_BODY", Name = "Anima Harvester" },
  ["Anima Harvester (Phase 2)"] = { LocalizationInternalName = "REAPER_BODY", Name = "Anima Harvester (Phase 2)" },
}
return { Monsters = Monsters }
"""
    units = extract_units("enemies", body)
    assert units["enemies.Monsters.REAPER_BODY.Anima Harvester.name"] == "Anima Harvester"
    assert units["enemies.Monsters.REAPER_BODY.Anima Harvester (Phase 2).name"] == "Anima Harvester (Phase 2)"


def test_unparsed_module_splits_on_blank_lines() -> None:
    from app.services.ror2.units import extract_units

    units = extract_units("module/Navbox/doc", "== Use ==\n\nFirst paragraph.\n\nSecond paragraph.")
    assert units["module/Navbox/doc.1"] == "== Use =="
    assert units["module/Navbox/doc.2"] == "First paragraph."
    assert units["module/Navbox/doc.3"] == "Second paragraph."


def test_sync_persists_normalized_weblate_units_and_keeps_wiki_raws(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.guide_raw.pipeline import load_row, upsert_raw
    from app.services.ror2.weblate import dump_snapshot, load_units

    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    GuideTokenTranslation.__table__.create(engine)
    GuideTokenTranslationSync.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    source = """
local items = {}
items["Syringe"] = {
  Desc = "attack speed",
  Quote = "a medical tool",
  Unlock = "complete a stage",
  LocalizationInternalName = "ITEM_SYRINGE",
}
return items
"""
    upsert_raw(db, "ror2", "items", "https://riskofrain2.wiki.gg/wiki/Module:Items/Data", source)
    upsert_raw(
        db,
        "ror2",
        WEBLATE_RESOURCE,
        "https://weblate.example.com/projects/zhange/ror2/zh_Hans/",
        dump_snapshot(
            {"items.ITEM_SYRINGE.name": {"source": "Syringe", "target": "旧译名", "state": "approved"}},
            {"items.ITEM_SYRINGE.name": "Syringe"},
        ),
    )
    calls: list[str] = []

    def client(method: str, url: str, **kwargs: object) -> _Response:
        calls.append(method)
        if method == "POST":
            content = kwargs.get("content")
            assert isinstance(content, bytes)
            assert b"items.ITEM_SYRINGE.Desc" in content
            assert b"items.ITEM_SYRINGE.Unlock" in content
            assert b'"attack speed"' in content
            assert b'name="method"' in content
            assert b"\r\nadd\r\n" in content
            return _Response({"result": True, "accepted": 4, "skipped": 0, "not_found": 0, "total": 4})
        return _Response(
            {
                "results": [
                    {
                        "context": "items.ITEM_SYRINGE.Desc",
                        "source": ["attack speed"],
                        "target": ["攻击速度"],
                        "approved": True,
                        "fuzzy": False,
                    },
                    {
                        "context": "items.ITEM_SYRINGE.Quote",
                        "source": ["a medical tool"],
                        "target": ["待审译文"],
                        "approved": False,
                        "pending": True,
                        "fuzzy": False,
                    },
                    {
                        "context": "items.ITEM_SYRINGE.Unlock",
                        "source": ["complete a stage"],
                        "target": [""],
                        "approved": False,
                        "fuzzy": False,
                    },
                    {
                        "context": "items.ITEM_SYRINGE.name",
                        "source": ["Syringe"],
                        "target": ["旧名"],
                        "approved": True,
                        "fuzzy": False,
                    },
                ],
                "next": None,
            }
        )

    monkeypatch.setattr("app.services.ror2.wiki.PIPELINE.missing", lambda _db: False)
    cfg = {
        "base": "https://weblate.example.com",
        "token": "secret-token",
        "project": "zhange",
        "component": "ror2",
    }
    monkeypatch.setattr("app.services.ror2.weblate.weblate_settings", lambda: cfg)

    report = sync_weblate(db, client=client)
    assert report == "原文 4 条，Weblate 源单元 4 条，已审 2 条"
    assert calls == ["GET"]
    sync_state = db.get(GuideTokenTranslationSync, ("ror2", "zh_Hans"))
    assert sync_state is not None
    assert len(sync_state.source_manifest_fingerprint or "") == 64

    # Matching source units are only polled; no source upload is needed.
    assert sync_weblate(db, client=client) == report
    assert calls == ["GET", "GET"]
    revision = weblate_revision(db)
    assert len(revision) == 64
    assert db.query(GuideTokenTranslation).count() == 4
    assert load_row(db, "ror2", "items") is not None
    assert load_row(db, "ror2", WEBLATE_RESOURCE) is None

    db.close()
    db = sessionmaker(bind=engine)()
    try:
        snapshot = load_snapshot(db)
        assert snapshot.sources["items.ITEM_SYRINGE.Quote"] == "a medical tool"
        units = load_units(db)
        assert units["items.ITEM_SYRINGE.Desc"]["target"] == "攻击速度"
        assert units["items.ITEM_SYRINGE.Desc"]["state"] == "approved"
        assert units["items.ITEM_SYRINGE.Quote"]["state"] == "pending"
        assert units["items.ITEM_SYRINGE.Quote"]["target"] == "待审译文"
        assert units["items.ITEM_SYRINGE.Unlock"]["state"] == "untranslated"
        assert units["items.ITEM_SYRINGE.Unlock"]["target"] == ""
        assert units["items.ITEM_SYRINGE.name"]["source"] == "Syringe"
        assert weblate_revision(db) == revision
    finally:
        db.close()


def test_failed_weblate_refresh_preserves_the_previous_local_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.guide_raw.pipeline import upsert_raw
    from app.services.ror2.weblate import _store_snapshot

    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    GuideTokenTranslation.__table__.create(engine)
    GuideTokenTranslationSync.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    source = 'local items = {}\nitems["Syringe"] = { Desc = "attack speed", LocalizationInternalName = "ITEM_SYRINGE" }\nreturn items'
    upsert_raw(db, "ror2", "items", "https://riskofrain2.wiki.gg/wiki/Module:Items/Data", source)
    cfg = {
        "base": "https://weblate.example.com",
        "token": "secret-token",
        "project": "zhange",
        "component": "ror2",
    }
    old = {
        "items.ITEM_SYRINGE.Desc": {
            "source": "attack speed",
            "target": "攻击速度",
            "state": "approved",
        }
    }
    _store_snapshot(db, old, cfg)
    old_revision = weblate_revision(db)
    monkeypatch.setattr("app.services.ror2.wiki.PIPELINE.missing", lambda _db: False)
    monkeypatch.setattr("app.services.ror2.weblate.weblate_settings", lambda: cfg)

    def failing_client(method: str, _url: str, **_kwargs: object) -> _Response:
        if method == "POST":
            return _Response({"result": True, "accepted": 2, "skipped": 0, "not_found": 0, "total": 2})
        return _Response({"detail": "temporary"}, status=502)

    with pytest.raises(WeblateError, match="HTTP 502"):
        sync_weblate(db, client=failing_client)
    db.close()
    db = sessionmaker(bind=engine)()
    try:
        assert weblate_revision(db) == old_revision
        snapshot = load_snapshot(db)
        assert snapshot.units["items.ITEM_SYRINGE.Desc"]["target"] == "攻击速度"
    finally:
        db.close()


def test_list_units_rejects_a_truncated_page_count() -> None:
    def client(method: str, _url: str, **_kwargs: object) -> _Response:
        assert method == "GET"
        return _Response({"count": 2, "results": [{"context": "one"}], "next": None})

    with pytest.raises(WeblateError, match="分页不完整"):
        list_units(
            {
                "base": "https://weblate.example.com",
                "token": "secret-token",
                "project": "zhange",
                "component": "ror2",
            },
            client=client,
        )


def test_text_projection_needs_a_current_real_source_context() -> None:
    catalog = _catalog()
    context = "items.items.ITEM_SYRINGE.name"
    slot_id = "item.ITEM_SYRINGE.name"
    original = "Soldier's Syringe"
    approved = {context: {"source": original, "target": "士兵的注射器", "state": "approved"}}

    translated = resolve_catalog_texts(catalog, {context: original}, approved)[slot_id]
    assert translated.text == "士兵的注射器"
    assert translated.original == original
    assert translated.token == context

    untranslated = resolve_catalog_texts(catalog, {context: original}, {})[slot_id]
    assert untranslated.text == original
    assert untranslated.original == original
    assert untranslated.token == context

    pending = {
        context: {"source": original, "target": "待审核译文", "state": "suggested"}
    }
    pending_text = resolve_catalog_texts(catalog, {context: original}, pending)[slot_id]
    assert pending_text.text == original
    assert pending_text.token == context

    stale = resolve_catalog_texts(
        catalog,
        {context: "A renamed source"},
        {context: {"source": "A renamed source", "target": "旧译文", "state": "approved"}},
    )[slot_id]
    assert stale.text == original
    assert stale.token is None

    missing = resolve_catalog_texts(catalog, {}, approved)[slot_id]
    assert missing.text == original
    assert missing.token is None


def test_unmapped_text_context_lookup_preindexes_source_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.ror2 import strings

    slots = [
        strings.StringSlot(f"local.{index}", f"Semantic text {index}", lambda _text: None)
        for index in range(10)
    ]
    sources = {f"module/{index}.paragraph.1": f"Unrelated text {index}" for index in range(490)}
    sources.update(
        {f"wiki-page/Items.section.common.column.{index}": f"Semantic text {index}" for index in range(10)}
    )
    rendered_count = 0
    original_render = strings._render_source

    def count_render(text: str, source_format: str) -> str:
        nonlocal rendered_count
        rendered_count += 1
        return original_render(text, source_format)

    monkeypatch.setattr(strings, "_render_source", count_render)
    resolved = strings._resolve_slots(slots, sources, {})

    assert all(resolved[f"local.{index}"].token for index in range(10))
    assert rendered_count <= len(sources) + 4 * len(slots)


def test_article_heading_and_table_contexts_are_semantic_and_stable() -> None:
    from app.services.ror2.units import extract_units

    resource = "wiki-page/Items"
    first = """Lead paragraph.

== Common ==
{| class=wikitable
! Item !! Description !! Stack
|-
| Syringe || Increase speed || Linear
|}

=== Notes ===
More text."""
    reformatted = """Lead paragraph.


== Common ==
{| class=wikitable
! Item !! Description !! Stack
|-
| Syringe || Increase speed || Linear
|}
=== Notes ===

More text."""
    units = extract_units(resource, first)
    assert units == extract_units(resource, reformatted)
    assert units[f"{resource}.title"] == "Items"
    assert units[f"{resource}.section.common.title"] == "Common"
    assert units[f"{resource}.section.common.table.item.column.item"] == "Item"
    assert units[f"{resource}.section.common.table.item.column.description"] == "Description"
    assert units[f"{resource}.section.common.table.item.column.stack"] == "Stack"
    assert not any(key.rsplit(".", 1)[-1].isdigit() for key in units)



def test_weblate_api_path_validation_keeps_a_reverse_proxy_prefix() -> None:
    from app.services.ror2.weblate import same_origin

    base = "https://weblate.example.com/tools/weblate"
    assert same_origin("https://weblate.example.com/tools/weblate/api/units/10/", base)
    assert not same_origin("https://weblate.example.com/tools/weblate-evil/api/units/10/", base)
    assert not same_origin("https://evil.example.com/tools/weblate/api/units/10/", base)
    assert not same_origin("https://[invalid/tools/weblate/api/units/10/", base)
    assert not same_origin("https://weblate.example.com/tools/weblate/api/../../admin/", base)
    assert not same_origin("https://weblate.example.com/tools/weblate/api/%2e%2e/admin/", base)
    assert not same_origin("https://weblate.example.com/tools/weblate/api/%252e%252e/admin/", base)


def test_weblate_api_requests_do_not_follow_redirects() -> None:
    from app.services.ror2.weblate import _send

    cfg = {"base": "https://weblate.example.com", "token": "secret-token"}
    captured: dict[str, object] = {}

    def client(method: str, url: str, **kwargs: object) -> _Response:
        captured.update(kwargs)
        return _Response({"ok": True})

    _send(cfg, "GET", "https://weblate.example.com/api/units/", client=client)
    assert captured["follow_redirects"] is False


def test_edit_source_unit_uses_source_endpoint_and_content_hash() -> None:
    from app.services.ror2.weblate import _edit_source_unit

    cfg = {
        "base": "https://weblate.example.com/tools/weblate",
        "token": "secret-token",
        "project": "zhange",
        "component": "ror2",
    }

    def client(method: str, url: str, **kwargs: object) -> _Response:
        assert method == "POST"
        assert url == "https://weblate.example.com/tools/weblate/api/units/17/source/"
        assert kwargs["json"] == {"source": ["New source"], "content_hash": 731}
        return _Response({}, status=200)

    _edit_source_unit(cfg, "17", "items.ITEM.Desc", "New source", content_hash=731, client=client)


def test_source_manifest_repair_adds_missing_units_and_edits_changed_units() -> None:
    from app.services.ror2.weblate import _repair_source_manifest

    cfg = {
        "base": "https://weblate.example.com/tools/weblate",
        "token": "secret-token",
        "project": "zhange",
        "component": "ror2",
    }
    calls: list[tuple[str, str]] = []

    def client(method: str, url: str, **kwargs: object) -> _Response:
        calls.append((method, url))
        if url.endswith("/api/translations/zhange/ror2/en/file/"):
            content = kwargs["content"]
            assert method == "POST"
            assert isinstance(content, bytes)
            assert b'"missing.key": "Fresh source"' in content
            assert b'"existing.key"' not in content
            assert b"\r\nadd\r\n" in content
            return _Response({"result": True, "accepted": 1, "skipped": 0, "not_found": 0, "total": 1})
        assert method == "POST"
        assert url.endswith("/api/units/17/source/")
        assert kwargs["json"] == {"source": ["Updated source"], "content_hash": 321}
        return _Response({}, status=200)

    _repair_source_manifest(
        cfg,
        {"existing.key": "Updated source", "missing.key": "Fresh source"},
        [{"id": 17, "context": "existing.key", "source": ["Old source"], "content_hash": 321}],
        client=client,
    )

    assert [method for method, _url in calls] == ["POST", "POST"]
    assert calls[0][1].endswith("/api/translations/zhange/ror2/en/file/")
    assert calls[1][1].endswith("/api/units/17/source/")
    assert all("replace" not in url for _method, url in calls)


def test_approved_translation_must_keep_rich_tags_placeholders_and_linebreaks() -> None:
    from app.services.ror2.strings import resolve_context_text

    context = "items.ITEM_EXAMPLE.Desc"
    source = "Deals %s damage to {0}: {{Color|d|Hit}}.\nContinue."
    valid = "对 {0} 造成 %s 点伤害：<style=cIsDamage>命中</style>。\n继续。"
    resolved = resolve_context_text(
        source,
        context,
        {context: source},
        {context: {"source": source, "target": valid, "state": "approved"}},
        source_format="inline",
    )
    assert resolved.text == valid
    assert resolved.token == context

    wrong_tag = valid.replace("style=cIsDamage", "color=#D64545")
    rejected_tag = resolve_context_text(
        source,
        context,
        {context: source},
        {context: {"source": source, "target": wrong_tag, "state": "approved"}},
        source_format="inline",
    )
    assert rejected_tag.text == source
    assert rejected_tag.token == context

    wrong_placeholder = valid.replace("{0}", "{1}").replace("%s", "%d")
    rejected_placeholder = resolve_context_text(
        source,
        context,
        {context: source},
        {context: {"source": source, "target": wrong_placeholder, "state": "approved"}},
        source_format="inline",
    )
    assert rejected_placeholder.text == source
    assert rejected_placeholder.token == context

    wrong_linebreak = valid.replace("\n", " ")
    rejected_linebreak = resolve_context_text(
        source,
        context,
        {context: source},
        {context: {"source": source, "target": wrong_linebreak, "state": "approved"}},
        source_format="inline",
    )
    assert rejected_linebreak.text == source
    assert rejected_linebreak.token == context

def test_approved_translation_allows_reordered_and_split_equivalent_tags() -> None:
    from app.services.ror2.strings import resolve_context_text

    context = "items.ITEM_TAG_ORDER.Desc"
    source = "Add {{Color|u|+1}} {{Stack|(+1 per stack)}} charge of your {{Color|u|Secondary skill}}."
    translated = "为<style=cIsUtility>次要技能</style>增加<style=cIsUtility>1次</style><style=cStack>（每层增加1次）</style>充能。"
    resolved = resolve_context_text(
        source,
        context,
        {context: source},
        {context: {"source": source, "target": translated, "state": "approved"}},
        source_format="inline",
    )
    assert resolved.text == translated

    # One source emphasis span may be split across reordered Chinese words.
    split_source = "Within {{Color|u|range}}."
    split_target = "<style=cIsUtility>适用范围</style>：<style=cIsUtility>全程有效</style>。"
    split = resolve_context_text(
        split_source,
        context,
        {context: split_source},
        {context: {"source": split_source, "target": split_target, "state": "approved"}},
        source_format="inline",
    )
    assert split.text == split_target
def test_wiki_expansion_pages_emit_only_a_stable_title_unit() -> None:
    from app.services.ror2.strings import Ror2StringError
    from app.services.ror2.units import extract_units

    resource = "wiki-expansion/SotV"
    body = "== Wiki-only section ==\n{|\n! Item !! Description\n|}"
    assert extract_units(resource, body) == {
        f"{resource}.title": "Survivors of the Void",
    }
    with pytest.raises(Ror2StringError, match="无法识别的资料片"):
        extract_units("wiki-expansion/Unknown", "page body")
    with pytest.raises(Ror2StringError, match="正文为空"):
        extract_units(resource, "  ")


def test_wiki_table_context_ids_do_not_confuse_prefixes_or_repeated_captions() -> None:
    from app.services.ror2.units import extract_units

    resource = "wiki-page/Items"
    body = """== Loot ==
{|
|+ Item
! Name
|}
{|
|+ Items
! Name
|}
{|
|+ Item
! Name
|}"""
    units = extract_units(resource, body)

    assert units[f"{resource}.section.loot.table.item.caption"] == "Item"
    assert units[f"{resource}.section.loot.table.items.caption"] == "Items"
    assert units[f"{resource}.section.loot.table.item~2.caption"] == "Item"


def test_article_unit_extraction_rejects_unclosed_wikitable() -> None:
    from app.services.ror2.strings import Ror2StringError
    from app.services.ror2.units import extract_units

    with pytest.raises(Ror2StringError, match="没有结束标记"):
        extract_units("wiki-page/Items", "== Common ==\n{|\n! Item !! Description")

def test_wiki_source_change_edits_one_weblate_unit_and_keeps_snapshot_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.guide_raw.pipeline import upsert_raw
    from app.services.ror2.weblate import _source_manifest_fingerprint, _store_snapshot

    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    GuideTokenTranslation.__table__.create(engine)
    GuideTokenTranslationSync.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    old_module = '''local items = {}
items["Syringe"] = {
    Desc = "Old source",
    LocalizationInternalName = "ITEM_SYRINGE",
}
return items'''
    new_module = old_module.replace("Old source", "New source")
    upsert_raw(db, "ror2", "items", "https://riskofrain2.wiki.gg/wiki/Module:Items/Data", new_module)
    cfg = {
        "base": "https://weblate.example.com/tools/weblate",
        "token": "secret-token",
        "project": "zhange",
        "component": "ror2",
    }
    old_units = {
        "items.ITEM_SYRINGE.name": {"source": "Syringe", "target": "注射器", "state": "approved"},
        "items.ITEM_SYRINGE.Desc": {"source": "Old source", "target": "旧译文", "state": "approved"},
    }
    old_sources = {context: row["source"] for context, row in old_units.items()}
    _store_snapshot(
        db,
        old_units,
        cfg,
        source_manifest_fingerprint=_source_manifest_fingerprint(old_sources),
    )
    server_sources = dict(old_sources)
    calls: list[str] = []

    def client(method: str, url: str, **kwargs: object) -> _Response:
        calls.append(method)
        if url.endswith("/api/translations/zhange/ror2/en/file/"):
            content = kwargs["content"]
            assert method == "POST"
            assert isinstance(content, bytes)
            assert b"Old source" not in content
            assert b"New source" in content
            assert b"\r\nadd\r\n" in content
            return _Response({"result": False, "accepted": 0, "skipped": 2, "not_found": 0, "total": 2})
        if method == "POST":
            assert url == "https://weblate.example.com/tools/weblate/api/units/52/source/"
            assert kwargs["json"] == {"source": ["New source"], "content_hash": 52}
            server_sources["items.ITEM_SYRINGE.Desc"] = "New source"
            return _Response({}, status=200)
        assert method == "GET"
        assert url.startswith("https://weblate.example.com/tools/weblate/api/")
        return _Response(
            {
                "count": 2,
                "results": [
                    {
                        "id": 51,
                        "context": "items.ITEM_SYRINGE.name",
                        "content_hash": 51,
                        "source": [server_sources["items.ITEM_SYRINGE.name"]],
                        "target": ["注射器"],
                        "approved": True,
                        "fuzzy": False,
                    },
                    {
                        "id": 52,
                        "context": "items.ITEM_SYRINGE.Desc",
                        "content_hash": 52,
                        "source": [server_sources["items.ITEM_SYRINGE.Desc"]],
                        "target": ["旧译文"],
                        "approved": False,
                        "fuzzy": server_sources["items.ITEM_SYRINGE.Desc"] == "New source",
                    },
                ],
                "next": None,
            }
        )

    monkeypatch.setattr("app.services.ror2.wiki.PIPELINE.missing", lambda _db: False)
    monkeypatch.setattr("app.services.ror2.weblate.weblate_settings", lambda: cfg)
    old_revision = weblate_revision(db)

    try:
        report = sync_weblate(db, client=client)
        assert calls == ["GET", "POST", "GET"]
        assert report == "原文 2 条，Weblate 源单元 2 条，已审 1 条"
        snapshot = load_snapshot(db)
        assert snapshot.sources["items.ITEM_SYRINGE.Desc"] == "New source"
        assert snapshot.units["items.ITEM_SYRINGE.Desc"]["target"] == "旧译文"
        assert snapshot.units["items.ITEM_SYRINGE.Desc"]["state"] == "fuzzy"
        assert weblate_revision(db) != old_revision
    finally:
        db.close()
        engine.dispose()

def test_source_manifest_repair_requires_content_hash_for_source_edits() -> None:
    from app.services.ror2.weblate import _repair_source_manifest

    cfg = {
        "base": "https://weblate.example.com",
        "token": "secret-token",
        "project": "zhange",
        "component": "ror2",
    }

    def client(_method: str, _url: str, **_kwargs: object) -> _Response:
        pytest.fail("source edit must not be attempted without the optimistic-lock hash")

    with pytest.raises(WeblateError, match="content_hash"):
        _repair_source_manifest(
            cfg,
            {"items.ITEM.Desc": "New source"},
            [{"id": 17, "context": "items.ITEM.Desc", "source": ["Old source"]}],
            client=client,
        )


def test_unsupported_source_edit_fails_closed_without_file_replace() -> None:
    from app.services.ror2.weblate import _edit_source_unit

    cfg = {
        "base": "https://weblate.example.com",
        "token": "secret-token",
        "project": "zhange",
        "component": "ror2",
    }

    def client(method: str, url: str, **_kwargs: object) -> _Response:
        assert method == "POST"
        assert url.endswith("/api/units/17/source/")
        return _Response({"detail": "source edit unavailable"}, status=405)

    with pytest.raises(WeblateError, match="未使用会替换文件的上传方式"):
        _edit_source_unit(
            cfg,
            "17",
            "items.ITEM.Desc",
            "New source",
            content_hash=17,
            client=client,
        )
