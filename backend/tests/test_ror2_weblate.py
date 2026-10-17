"""Weblate 快照：已审且原文指纹一致才显示。游戏中文只作为建议。"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.guide_raw import GuideRaw
from app.services.ror2.schemas import Ror2CatalogOut, Ror2ItemOut, Ror2SkillGroupOut, Ror2SkillOut, Ror2SurvivorDetailOut, Ror2SurvivorOut
from app.services.ror2.strings import apply_catalog, fingerprint, prefill_catalog, prefill_detail
from app.services.platform_features import invalidate_feature_cache, load_feature_flags
from app.services.scheduler_config import load_scheduler_config
from app.services.ror2.weblate import (
    WeblateError,
    accept_snapshot,
    list_units,
    normalize_base_url,
    select_suggestions,
    sync_weblate,
    weblate_settings,
)


class _Response:
    def __init__(self, payload: dict, status: int = 200):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self) -> dict:
        return self._payload


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
        "item.ITEM_SYRINGE.name": {
            "source": "Soldier's Syringe",
            "target": "士兵的注射器",
            "state": "approved",
        },
        "item.ITEM_SYRINGE.desc": {
            "source": "Old description",
            "target": "旧说明",
            "state": "approved",
        },
    }
    apply_catalog(catalog, units)
    syringe = catalog.items[0]
    assert syringe.name_zh == "士兵的注射器"
    assert syringe.name == "Soldier's Syringe"
    assert syringe.description_zh == ""


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
                    "version": 1,
                    "units": {
                        "item.ITEM_SYRINGE.name": {
                            "source": "Soldier's Syringe",
                            "target": "士兵的注射器",
                            "state": "fuzzy",
                        }
                    },
                }
            )
        )


def test_weblate_url_requires_https_except_loopback() -> None:
    assert normalize_base_url("https://weblate.example.com/path/") == "https://weblate.example.com/path"
    assert normalize_base_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"
    with pytest.raises(WeblateError, match="https"):
        normalize_base_url("http://weblate.example.com")
    with pytest.raises(WeblateError, match="令牌"):
        normalize_base_url("https://token@weblate.example.com")


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


def test_sync_stores_each_approved_file_in_the_source_format(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.guide_raw.pipeline import upsert_raw
    from app.services.ror2.weblate import load_units

    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    source = """
local items = {}
items["Syringe"] = { Desc = "attack speed", LocalizationInternalName = "ITEM_SYRINGE" }
return items
"""
    upsert_raw(db, "ror2", "items", "https://riskofrain2.wiki.gg/wiki/Module:Items/Data", source)
    calls: list[str] = []

    def client(method: str, url: str, **kwargs: object) -> _Response:
        calls.append(method)
        if method == "POST":
            content = kwargs.get("content")
            assert isinstance(content, bytes)
            assert b"items.ITEM_SYRINGE.Desc" in content
            assert b"attack speed" in content
            assert b'name="method"' in content
            assert b"\r\nadd\r\n" in content
            return _Response({"result": True, "accepted": 2, "skipped": 0, "not_found": 0, "total": 2})
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
                        "context": "items.ITEM_SYRINGE.name",
                        "source": ["Old Syringe"],
                        "target": ["旧名"],
                        "approved": True,
                        "fuzzy": False,
                    },
                ],
                "next": None,
            }
        )

    monkeypatch.setattr("app.services.ror2.wiki.PIPELINE.missing", lambda _db: False)
    monkeypatch.setattr(
        "app.services.ror2.weblate.weblate_settings",
        lambda: {
            "base": "https://weblate.example.com",
            "token": "secret-token",
            "project": "zhange",
            "component": "ror2",
        },
    )

    report = sync_weblate(db, client=client)
    assert report == "原文 2 条，已审 1 条"
    assert calls == ["POST", "GET"]
    units = load_units(db)
    assert units["items.ITEM_SYRINGE.Desc"]["target"] == "攻击速度"
    assert "items.ITEM_SYRINGE.name" not in units
    db.close()
