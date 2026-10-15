"""雨中冒险 2：Wiki 模块落库后再解析，坏的一份不覆盖旧行。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.biz_logging import clear_log_until_change
from app.models.guide_raw import GuideRaw
from app.services import platform_features as pf
from app.services.guide_raw.pipeline import RawSpec
from app.services.ror2.catalog import (
    Ror2WikiError,
    artifacts_from_module,
    challenges_from_module,
    drones_from_module,
    environments_from_module,
    interactables_from_module,
    items_from_module,
    monsters_from_module,
    survivors_from_module,
)
from app.services.ror2.wiki import (
    WIKI_API,
    PIPELINE,
    fetch_module,
    get_catalog,
    module_text,
    reset_catalog_memo,
    sync_wiki,
)
from app.services.ror2.wikitext import plain_wikitext

_ITEMS = """
local p = {}
local items = {}
-- 行注释
items["Soldier's Syringe"] = {
	Rarity = "Common",
	Quote = "Increase attack speed.",
	Desc = "Increases {{Color|d|attack speed}} by {{Color|d|15%}} {{Stack|(+15% per stack)}}.",
	Category = { "Damage", "BrotherBlacklist" },
	ID = "Syringe",
	Stats = {
		{ Stat = "Attack Speed", Value = "15%", Stack = "Linear", Add = "+15%" }
	},
	LocalizationInternalName = "ITEM_SYRINGE",
}
items["Brilliant Behemoth"] = {
	Rarity = "Legendary",
	Quote = "All your attacks explode!",
	Desc = "Explode for {{Color|d|{{Stack|60%}}}}.",
	Category = { "Damage" },
	ID = "Behemoth",
	LocalizationInternalName = "ITEM_BEHEMOTH",
}
items["Hidden Cache"] = {
	Rarity = "Common",
	Quote = "nope",
	Desc = "hidden",
	Category = { "Hidden" },
	LocalizationInternalName = "ITEM_HIDDEN",
}
items["Old"] = {
	Rarity = "Unused (Common)",
	Quote = "old",
	Desc = "old",
	Unused = true,
	LocalizationInternalName = "ITEM_OLD",
}
items["No Picture"] = {
	Rarity = "Boss",
	Quote = "quiet",
	Desc = "plain",
	NoIcon = true,
	LocalizationInternalName = "ITEM_NOPIC",
}
p.items = items
return p
"""

_EQUIPMENT = """
local p = {}
local equipment = {}
equipment["Radar Scanner"] = {
	Rarity = "Equipment",
	Quote = "Reveal nearby interactables.",
	Desc = "Reveal all interactables within 500m for 10 seconds.",
	Cooldown = 45,
	ID = "Scanner",
	LocalizationInternalName = "EQUIPMENT_SCANNER",
}
equipment["Jar of Souls"] = {
	Rarity = "Unused",
	Quote = "no",
	Desc = "no",
	LocalizationInternalName = "EQUIPMENT_UNUSED",
}
p.equipment = equipment
return p
"""

_SURVIVORS = """
--[[
  长注释
]]
return {
	Survivors = {
		["Commando"] = {
			Name = "Commando",
			Image = "Commando.png",
			BaseHealth = 110,
			ScalingHealth = 33,
			BaseDamage = 12,
			ScalingDamage = 2.4,
			BaseHealthRegen = 1,
			ScalingHealthRegen = 0.2,
			BaseSpeed = 7,
			BaseArmor = 0,
			Description = "Reliable.",
			Umbra = "Cornered Gunslinger",
			PhraseEscape = "..and so he left.",
		},
	},
}
"""

_ENEMIES = """
return {
  Monsters = {
    ["Beetle"] = { Name = "Beetle", Type = "Normal", BaseHealth = 80, Image = "Beetle.png", Link = "Beetle" },
    ["Watcher"] = { Name = "Watcher", Type = "DoNotInclude", Category = { Masterless } },
  },
  Drones = {
    ["Gunner Drone"] = {
      Name = "Gunner Drone",
      Quote = "Pew.",
      Desc = "Shoots.",
      Type = "Drone",
      BaseCost = 40,
      Currency = "Gold",
      Image = "Gunner Drone.png",
    },
  },
}
"""

_ENVIRONMENTS = """
local p = {}
local Environments = {
  ["Distant Roost"] = {
    Name = "Distant Roost",
    Stage = "1",
    SubName = "Ground Zero",
    Description = "Fog.",
    Image = "Distant Roost.png",
  },
}
p.Environments = Environments
p.SOTS_ONLY = SOTS_ONLY
return p
"""

_CHALLENGES = """
return {
  challenges = {
    ["Bookworm"] = { Type = "Equipment", Unlock = { "Radar Scanner" }, Desc = "Collect logs.", Coins = "2" },
  },
}
"""

_INTERACTABLES = """
return {
  interactables = {
    { Name = "Gunner Drone", Category = "Drones", Effect = "Ally", Purchase = { Type = "Gold", Cost = 40 } },
    { Name = "Shrine of Chance", Category = "Shrines", Effect = "Item" },
    { Name = "Newt Altar", Category = "Environment Specific", NameLink = "Newt Altars", Effect = "Portal" },
  },
}
"""

_ARTIFACTS = """
return {
  artifact = {
    ["Spite"] = { Desc = "Bombs.", Code = { "▲●▲", "●●●", "▲●▲" }, Internal = "Bombs" },
  },
}
"""

_FIXTURES = {
    "items": _ITEMS,
    "equipment": _EQUIPMENT,
    "survivors": _SURVIVORS,
    "enemies": _ENEMIES,
    "environments": _ENVIRONMENTS,
    "challenges": _CHALLENGES,
    "interactables": _INTERACTABLES,
    "artifacts": _ARTIFACTS,
}


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clear_log_repeat() -> None:
    clear_log_until_change()
    reset_catalog_memo()
    yield
    clear_log_until_change()
    reset_catalog_memo()


def _fetch_ok(calls: dict[str, int]) -> object:
    def fetch(spec: RawSpec) -> str:
        calls["n"] += 1
        return _FIXTURES[spec.resource]

    return fetch


def test_plain_wikitext_keeps_visible_template_text() -> None:
    text = plain_wikitext(
        "Increases {{Color|d|attack speed}} by {{Color|d|15%}} {{Stack|(+15% per stack)}}."
    )
    assert text == (
        "Increases <style=cIsDamage>attack speed</style> by "
        "<style=cIsDamage>15%</style> <style=cStack>(+15% per stack)</style>."
    )
    assert plain_wikitext("{{Color|d|{{Stack|60%}}}}") == (
        "<style=cIsDamage><style=cStack>60%</style></style>"
    )
    assert plain_wikitext("See [[Items|the list]].") == "See the list."
    assert plain_wikitext("{{SotV}}") == ""
    assert plain_wikitext("'''x''' <script>alert(1)</script>") == "x alert(1)"
    assert plain_wikitext("{{Color|d|underlined|-}}") == "<u><style=cIsDamage>underlined</style></u>"
    assert plain_wikitext("{{Color|hallowed|Hallowed}}") == "<color=#9368F9>Hallowed</color>"
    assert plain_wikitext("{{Color|lunar|Lunar}}") == "<color=#307FFF>Lunar</color>"
    assert plain_wikitext("{{Color|#FF7F7F|BUT}}") == "<color=#FF7F7F>BUT</color>"


def test_items_keep_every_module_entry_and_strip_markup() -> None:
    rows = items_from_module(_ITEMS)
    assert [row.name for row in rows] == [
        "Hidden Cache",
        "Soldier's Syringe",
        "Brilliant Behemoth",
        "No Picture",
        "Old",
    ]
    syringe = next(row for row in rows if row.name == "Soldier's Syringe")
    assert syringe.rarity == "Common"
    assert syringe.description == (
        "Increases <style=cIsDamage>attack speed</style> by "
        "<style=cIsDamage>15%</style> <style=cStack>(+15% per stack)</style>."
    )
    assert syringe.categories == ["Damage", "BrotherBlacklist"]
    assert syringe.code == "Syringe"
    assert syringe.internal_name == "ITEM_SYRINGE"
    assert syringe.stats[0].label == "Attack Speed"
    assert syringe.stats[0].add == "+15%"
    assert syringe.wiki_url == "https://riskofrain2.wiki.gg/wiki/Soldier's_Syringe"
    assert syringe.image_url == "https://riskofrain2.wiki.gg/images/Soldier's_Syringe.png"
    assert next(row for row in rows if row.name == "No Picture").image_url is None
    assert next(row for row in rows if row.name == "Brilliant Behemoth").description == (
        "Explode for <style=cIsDamage><style=cStack>60%</style></style>."
    )
    assert next(row for row in rows if row.name == "Old").rarity == "Unused (Common)"
    assert next(row for row in rows if row.name == "Hidden Cache").categories == ["Hidden"]


def test_catalog_rejects_a_module_slot_that_is_not_an_entry() -> None:
    src = """
    return {
      items = {
        ["Shown"] = { Rarity = "Common", Desc = "a" },
        count = 1,
      }
    }
    """
    with pytest.raises(Ror2WikiError, match="无法对应"):
        items_from_module(src)


def test_catalog_keeps_internal_and_unused_entries() -> None:
    src = """
    return {
      items = {
        ["Shown"] = { Rarity = "Common", Desc = "a" },
        ["Secret"] = {
          Rarity = "Unused",
          Desc = "b",
          Unused = true,
          Internal = true,
          Category = { "Hidden" },
        },
      }
    }
    """
    rows = items_from_module(src)
    assert [row.name for row in rows] == ["Shown", "Secret"]
    assert rows[1].rarity == "Unused"
    assert rows[1].categories == ["Hidden"]


def test_directory_modules_keep_every_entry() -> None:
    assert [row.name for row in monsters_from_module(_ENEMIES)] == ["Watcher", "Beetle"]
    assert len(drones_from_module(_ENEMIES)) == 1
    assert len(environments_from_module(_ENVIRONMENTS)) == 1
    assert challenges_from_module(_CHALLENGES)[0].kind == "Equipment"
    rows = interactables_from_module(_INTERACTABLES)
    assert len(rows) == 3
    assert rows[1].wiki_url == "https://riskofrain2.wiki.gg/wiki/Newt_Altars"
    assert artifacts_from_module(_ARTIFACTS)[0].name == "Spite"
    assert artifacts_from_module(_ARTIFACTS)[0].image_url == (
        "https://riskofrain2.wiki.gg/images/Artifact_of_Spite.png"
    )


def test_survivors_keep_scaling_stats() -> None:
    rows = survivors_from_module(_SURVIVORS)
    assert len(rows) == 1
    commando = rows[0]
    assert commando.health == 110
    assert commando.health_per_level == 33
    assert commando.damage_per_level == 2.4
    assert commando.armor == 0
    assert commando.umbra == "Cornered Gunslinger"
    assert commando.image_url.endswith("Commando.png")


def test_catalog_reads_database_and_skips_refetch(db: Session) -> None:
    calls = {"n": 0}
    fetch = _fetch_ok(calls)
    sync_wiki(db, fetch=fetch)
    first = get_catalog(db, fetch=fetch)
    again = get_catalog(db, fetch=fetch)
    assert calls["n"] == len(PIPELINE.specs)
    assert again.fetched_at == first.fetched_at
    assert len(first.items) == 5
    assert [row.name for row in first.equipment] == ["Radar Scanner", "Jar of Souls"]
    assert first.equipment[0].cooldown == "45"
    assert first.equipment[0].rarity == "Equipment"
    assert first.survivors[0].name == "Commando"
    assert [row.name for row in first.monsters] == ["Watcher", "Beetle"]
    assert first.monsters[0].categories == ["Masterless"]
    assert first.drones[0].name == "Gunner Drone"
    assert first.drones[0].cost == "40 Gold"
    assert first.environments[0].stage == "1"
    assert first.challenges[0].unlock == ["Radar Scanner"]
    assert [row.name for row in first.interactables] == ["Gunner Drone", "Newt Altar", "Shrine of Chance"]
    assert first.interactables[1].wiki_url.endswith("/wiki/Newt_Altars")
    assert first.artifacts[0].code == ["▲●▲", "●●●", "▲●▲"]
    assert first.source == "https://riskofrain2.wiki.gg/"


def test_bad_module_does_not_replace_stored_raw(db: Session) -> None:
    sync_wiki(db, fetch=_fetch_ok({"n": 0}))
    stored = db.query(GuideRaw).filter_by(game="ror2", resource="items").one()
    kept = stored.synced_at

    def fetch(spec: RawSpec) -> str:
        if spec.resource == "items":
            return "this is not lua"
        return _FIXTURES[spec.resource]

    with pytest.raises(Ror2WikiError):
        sync_wiki(db, fetch=fetch)
    db.expire_all()
    row = db.query(GuideRaw).filter_by(game="ror2", resource="items").one()
    assert row.synced_at == kept
    assert "Soldier" in row.raw_body
    catalog = get_catalog(db, fetch=fetch)
    assert len(catalog.items) == 5
    assert catalog.items[1].name == "Soldier's Syringe"


def test_empty_database_does_not_hammer_after_failure(db: Session) -> None:
    calls = {"n": 0}

    def fetch(_spec: RawSpec) -> str:
        calls["n"] += 1
        raise Ror2WikiError("down")

    with pytest.raises(Ror2WikiError, match="down"):
        get_catalog(db, fetch=fetch)
    assert calls["n"] == len(PIPELINE.specs)
    with pytest.raises(Ror2WikiError):
        get_catalog(db, fetch=fetch)
    assert calls["n"] == len(PIPELINE.specs)


def test_fetch_module_only_calls_wiki_api(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class _Resp:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "query": {
                    "pages": [
                        {
                            "title": "Module:Items/Data",
                            "revisions": [{"slots": {"main": {"content": _ITEMS}}}],
                        }
                    ]
                }
            }

    def fake(method: str, url: str, **kwargs: object) -> _Resp:
        seen["method"] = method
        seen["url"] = url
        seen["params"] = kwargs.get("params")
        seen["headers"] = kwargs.get("headers")
        return _Resp()

    monkeypatch.setattr("app.services.ror2.wiki.http_request", fake)
    assert "Soldier" in fetch_module("Module:Items/Data")
    assert seen["url"] == WIKI_API
    params = seen["params"]
    assert isinstance(params, dict)
    assert params["titles"] == "Module:Items/Data"
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert "riskofrain2.wiki.gg" in str(headers.get("User-Agent"))
    with pytest.raises(Ror2WikiError):
        fetch_module("https://example.invalid/items")


def test_module_text_rejects_missing_page() -> None:
    with pytest.raises(Ror2WikiError, match="没有"):
        module_text({"query": {"pages": [{"missing": True}]}}, "Module:Items/Data")


def test_feature_is_a_game_under_guides() -> None:
    roots = {str(node["id"]): node for node in pf.FEATURE_TREE}
    children = roots["guides"]["children"]
    ror2 = next(child for child in children if child["id"] == "guides.ror2")
    assert [child["job_id"] for child in ror2["children"]] == [
        "ror2_wiki_sync",
        "ror2_lang_sync",
    ]
    assert pf.default_features()["guides.ror2"] is True
    assert pf.default_features()["guides.ror2.wiki_sync"] is True


def test_catalog_route_is_registered() -> None:
    from app.main import app

    assert "/api/guides/ror2/catalog" in app.openapi()["paths"]
