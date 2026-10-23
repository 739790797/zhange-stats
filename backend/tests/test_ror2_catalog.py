"""雨中冒险 2：Wiki 模块落库后再解析，坏的一份不覆盖旧行。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.biz_logging import clear_log_until_change
from app.models.guide_raw import GuideRaw
from app.models.guide_token_translation import GuideTokenTranslation, GuideTokenTranslationSync
from app.services import platform_features as pf
from app.services.guide_raw.pipeline import RawSpec, upsert_raw
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
from app.services.ror2.projection import catalog_response
from app.services.ror2.schemas import Ror2CatalogOut, Ror2ItemOut, Ror2StatOut
from app.services.ror2.wiki import (
    WIKI_API,
    PIPELINE,
    fetch_module,
    get_catalog,
    module_text,
    module_titles_from_query,
    reset_catalog_memo,
    sync_wiki,
)
from app.services.ror2.weblate import RESOURCE as WEBLATE_RESOURCE, dump_snapshot
from app.services.ror2.wiki import translated_catalog
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
		{ Stat = "Attack Speed", Value = "15%", Stack = "Linear", Add = "+15%" },
		{ Stat = "Damage", Value = "0", Stack = "Linear", Add = "0" }
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
			BaseAcceleration = 40,
			Mass = 100,
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

_SKILLS = """
local skills = {
  ["Double Tap"] = { Name = "Double Tap", Desc = "Rapidly shoot.", Type = "Primary" },
}
local p = {}
p.skills = skills
return p
"""

_LORE = """
local lore = {}
lore["Commando"] = { Type = "Survivors", Desc = "The soldier ducked." }
lore["Soldier's Syringe"] = { Type = "Items", Desc = "The soldier hid a needle." }
lore["Brilliant Behemoth"] = { Type = "Items", Desc = "The huge beast waited." }
local p = {}
p.lore = lore
return p
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
    "skills": _SKILLS,
    "lore": _LORE,
}


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    GuideTokenTranslation.__table__.create(engine)
    GuideTokenTranslationSync.__table__.create(engine)
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
    assert commando.acceleration == 40
    assert commando.mass == 100
    assert commando.armor == 0
    assert commando.umbra == "Cornered Gunslinger"
    assert commando.image_url.endswith("Commando.png")


def test_module_list_reads_titles_and_rejects_other_namespaces() -> None:
    titles = module_titles_from_query(
        {"query": {"allpages": [{"title": "Module:Navbox"}, {"title": "Module:Items/Data"}]}}
    )
    assert titles == ["Module:Navbox", "Module:Items/Data"]
    with pytest.raises(Ror2WikiError, match="不是模块"):
        module_titles_from_query({"query": {"allpages": [{"title": "Commando"}]}})


def test_extra_modules_are_stored_without_replacing_catalog_files(db: Session) -> None:
    calls = {"n": 0}

    def fetch(spec: RawSpec) -> str:
        calls["n"] += 1
        if spec.resource == "module/Navbox":
            return "return {}"
        return _FIXTURES[spec.resource]

    results = sync_wiki(
        db,
        fetch=fetch,
        list_modules=lambda: ["Module:Items/Data", "Module:Navbox"],
    )
    assert any(str(row["resource"]).startswith("其余模块 1 份") for row in results)
    row = db.query(GuideRaw).filter_by(game="ror2", resource="module/Navbox").one()
    assert "return {}" in row.raw_body
    assert db.query(GuideRaw).filter_by(game="ror2", resource="module/Items/Data").one_or_none() is None
    assert calls["n"] == len(PIPELINE.specs) + 1


def test_failed_extra_module_keeps_the_previous_copy(db: Session) -> None:
    def fetch(spec: RawSpec) -> str:
        if spec.resource == "module/Navbox":
            return "return { nav = true }"
        return _FIXTURES[spec.resource]

    sync_wiki(db, fetch=fetch, list_modules=lambda: ["Module:Navbox"])
    kept = db.query(GuideRaw).filter_by(game="ror2", resource="module/Navbox").one().synced_at

    def broken(spec: RawSpec) -> str:
        if spec.resource == "module/Navbox":
            raise Ror2WikiError("navbox down")
        return _FIXTURES[spec.resource]

    with pytest.raises(Ror2WikiError, match="navbox down"):
        sync_wiki(db, fetch=broken, list_modules=lambda: ["Module:Navbox"])
    db.expire_all()
    row = db.query(GuideRaw).filter_by(game="ror2", resource="module/Navbox").one()
    assert row.synced_at == kept
    assert "nav = true" in row.raw_body


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



def test_translated_catalog_uses_source_fallback_and_approved_token_units(db: Session) -> None:
    sync_wiki(db, fetch=lambda spec: _FIXTURES[spec.resource])

    source_catalog = translated_catalog(db)
    assert source_catalog.fetched_at
    assert source_catalog.items
    assert source_catalog.survivors
    syringe = next(row for row in source_catalog.items if row.name.original == "Soldier's Syringe")
    assert syringe.name.text == "Soldier's Syringe"
    assert syringe.name.token is None
    assert syringe.lore.text == "The soldier hid a needle."
    assert syringe.lore.original == "The soldier hid a needle."
    assert syringe.lore.token is None
    assert syringe.description.text
    commando = next(row for row in source_catalog.survivors if row.name.original == "Commando")
    assert commando.name.token is None

    upsert_raw(
        db,
        "ror2",
        WEBLATE_RESOURCE,
        "https://weblate.invalid/ror2",
        dump_snapshot(
            {
                "items.items.ITEM_SYRINGE.name": {
                    "source": syringe.name.original,
                    "target": "士兵的注射器",
                    "state": "approved",
                },
                "items.items.ITEM_SYRINGE.Rarity": {
                    "source": "Common",
                    "target": "普通",
                    "state": "approved",
                },
                "items.items.ITEM_SYRINGE.Stats.2.Stack": {
                    "source": "Linear",
                    "target": "线性二",
                    "state": "approved",
                },
                "lore.lore.Soldier's Syringe.Desc": {
                    "source": syringe.lore.original,
                    "target": "士兵把针藏了起来。",
                    "state": "approved",
                },
                "survivors.Survivors.Commando.Name": {
                    "source": commando.name.original,
                    "target": "指挥官",
                    "state": "approved",
                },
            },
            {
                "items.items.ITEM_SYRINGE.name": syringe.name.original,
                "items.items.ITEM_SYRINGE.Rarity": "Common",
                "items.items.ITEM_SYRINGE.Stats.1.Stack": "Linear",
                "items.items.ITEM_SYRINGE.Stats.2.Stack": "Linear",
                "items.items.ITEM_BEHEMOTH.Rarity": "Legendary",
                "lore.lore.Soldier's Syringe.Desc": syringe.lore.original,
                "lore.lore.Brilliant Behemoth.Desc": "The huge beast waited.",
                "survivors.Survivors.Commando.Name": commando.name.original,
            },
        ),
    )

    localized_catalog = translated_catalog(db)
    localized_syringe = next(row for row in localized_catalog.items if row.name.original == "Soldier's Syringe")
    localized_commando = next(row for row in localized_catalog.survivors if row.name.original == "Commando")
    assert localized_syringe.name.text == "士兵的注射器"
    assert localized_syringe.name.original == "Soldier's Syringe"
    assert localized_syringe.name.token == "items.items.ITEM_SYRINGE.name"
    assert localized_syringe.rarity.text == "普通"
    assert localized_syringe.rarity.original == "Common"
    assert localized_syringe.rarity.token == "items.items.ITEM_SYRINGE.Rarity"
    assert localized_syringe.stats[0].stack.text == "Linear"
    assert localized_syringe.stats[0].stack.token == "items.items.ITEM_SYRINGE.Stats.1.Stack"
    assert localized_syringe.stats[1].stack.text == "线性二"
    assert localized_syringe.stats[1].stack.original == "Linear"
    assert localized_syringe.stats[1].stack.token == "items.items.ITEM_SYRINGE.Stats.2.Stack"
    assert localized_syringe.lore.text == "士兵把针藏了起来。"
    assert localized_syringe.lore.original == "The soldier hid a needle."
    assert localized_syringe.lore.token == "lore.lore.Soldier's Syringe.Desc"
    behemoth = next(row for row in localized_catalog.items if row.name.original == "Brilliant Behemoth")
    assert behemoth.rarity.text == "Legendary"
    assert behemoth.rarity.original == "Legendary"
    assert behemoth.rarity.token == "items.items.ITEM_BEHEMOTH.Rarity"
    assert behemoth.lore.text == "The huge beast waited."
    assert behemoth.lore.original == "The huge beast waited."
    assert behemoth.lore.token == "lore.lore.Brilliant Behemoth.Desc"
    assert localized_syringe.description.text == syringe.description.text
    assert localized_syringe.name.token is not None
    assert localized_commando.name.text == "指挥官"
    assert localized_commando.name.token == "survivors.Survivors.Commando.Name"

def test_rarity_and_stack_tokens_fail_closed_without_exact_context_path() -> None:
    mapped = Ror2ItemOut(
        name="Mapped Item",
        rarity="Common",
        internal_name="ITEM_MAPPED",
        wiki_url="https://example.test/mapped",
        stats=[Ror2StatOut(label="Stack", stack="Linear")],
    )
    synthetic = Ror2ItemOut(
        name="Synthetic Item",
        rarity="Common",
        internal_name="ITEM_SYNTHETIC",
        wiki_url="https://example.test/synthetic",
    )
    catalog = Ror2CatalogOut(
        source="https://example.test/",
        fetched_at="",
        items=[mapped, synthetic],
        equipment=[],
        survivors=[],
    )
    sources = {
        "items.items.ITEM_MAPPED.Rarity": "Common",
        "items.items.ITEM_MAPPED.Stats.1.Stack": "Linear",
    }
    units = {
        "items.items.ITEM_MAPPED.Rarity": {
            "source": "Common",
            "target": "普通",
            "state": "approved",
        },
        "items.items.ITEM_MAPPED.Stats.1.Stack": {
            "source": "Linear",
            "target": "线性",
            "state": "approved",
        },
    }

    response = catalog_response(catalog, sources, units, [])

    assert response.items[0].rarity.text == "普通"
    assert response.items[0].rarity.token == "items.items.ITEM_MAPPED.Rarity"
    assert response.items[0].stats[0].stack.text == "Linear"
    assert response.items[0].stats[0].stack.token is None
    assert response.items[1].rarity.text == "Common"
    assert response.items[1].rarity.token is None


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


@pytest.mark.parametrize(
    ("statuses", "should_succeed", "expected_calls", "expected_delays", "error_match"),
    [
        ([502, 200], True, 2, [1.0], None),
        ([502, 502], False, 2, [1.0], "HTTP 502"),
        ([404], False, 1, [], "HTTP 404"),
    ],
)
def test_fetch_module_retries_gateway_errors_once(
    monkeypatch: pytest.MonkeyPatch,
    statuses: list[int],
    should_succeed: bool,
    expected_calls: int,
    expected_delays: list[float],
    error_match: str | None,
) -> None:
    calls = 0
    delays: list[float] = []
    responses = iter(statuses)

    class _Resp:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

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

    def fake(_method: str, _url: str, **_kwargs: object) -> _Resp:
        nonlocal calls
        calls += 1
        return _Resp(next(responses))

    monkeypatch.setattr("app.services.ror2.wiki.http_request", fake)
    monkeypatch.setattr("app.services.ror2.wiki.time.sleep", delays.append)

    if should_succeed:
        assert "Soldier" in fetch_module("Module:Items/Data")
    else:
        assert error_match is not None
        with pytest.raises(Ror2WikiError, match=error_match):
            fetch_module("Module:Items/Data")

    assert calls == expected_calls
    assert delays == expected_delays

def test_module_text_rejects_missing_page() -> None:
    with pytest.raises(Ror2WikiError, match="没有"):
        module_text({"query": {"pages": [{"missing": True}]}}, "Module:Items/Data")


def test_feature_is_a_game_under_guides() -> None:
    roots = {str(node["id"]): node for node in pf.FEATURE_TREE}
    children = roots["guides"]["children"]
    ror2 = next(child for child in children if child["id"] == "guides.ror2")
    assert [child["job_id"] for child in ror2["children"]] == [
        "ror2_wiki_sync",
        "ror2_weblate_sync",
    ]
    assert pf.default_features()["guides.ror2"] is True
    assert pf.default_features()["guides.ror2.wiki_sync"] is True


def test_catalog_route_is_registered() -> None:
    from app.main import app

    assert "/api/guides/ror2/catalog" in app.openapi()["paths"]


def test_article_page_sync_failure_preserves_previous_raw(db: Session) -> None:
    from app.services.guide_raw.codec import unpack_raw_text
    from app.services.ror2.wiki import sync_wiki_articles
    from app.services.ror2.wiki_structure import article_resource, WIKI_ARTICLE_TITLES

    resource = article_resource("Items")
    prior = "== Cached ==\n{|\n! Item !! Description\n|}"
    upsert_raw(db, "ror2", resource, "https://riskofrain2.wiki.gg/wiki/Items", prior)
    old_row = db.query(GuideRaw).filter_by(game="ror2", resource=resource).one()
    old_synced_at = old_row.synced_at

    def fetch_page(title: str) -> str:
        if title == "Items":
            return ""
        return "== Overview ==\n{|\n! Name !! Description\n|}"

    results = sync_wiki_articles(db, fetch_page=fetch_page)
    assert len(results) == len(WIKI_ARTICLE_TITLES)
    failed = next(row for row in results if row["resource"] == resource)
    assert failed["ok"] is False
    kept = db.query(GuideRaw).filter_by(game="ror2", resource=resource).one()
    assert kept.synced_at == old_synced_at
    assert unpack_raw_text(kept.raw_body) == prior

def test_expansion_title_sync_keeps_previous_raw_and_projects_only_title(db: Session) -> None:
    from app.services.guide_raw.codec import unpack_raw_text
    from app.services.ror2.wiki import stored_wiki_articles, sync_wiki_expansion_pages
    from app.services.ror2.wiki_structure import WIKI_EXPANSION_TITLES, expansion_resource

    code = "SotV"
    title = WIKI_EXPANSION_TITLES[code]
    resource = expansion_resource(code)
    prior = "cached official page body"
    upsert_raw(db, "ror2", resource, f"https://riskofrain2.wiki.gg/wiki/{title.replace(' ', '_')}", prior)
    old_row = db.query(GuideRaw).filter_by(game="ror2", resource=resource).one()
    old_synced_at = old_row.synced_at

    def fetch_page(page_title: str) -> str:
        if page_title == title:
            return ""
        return f"== {page_title} ==\n{{|\n! Name !! Description\n|}}"

    results = sync_wiki_expansion_pages(db, fetch_page=fetch_page)
    assert len(results) == len(WIKI_EXPANSION_TITLES)
    failed = next(row for row in results if row["resource"] == resource)
    assert failed["ok"] is False
    kept = db.query(GuideRaw).filter_by(game="ror2", resource=resource).one()
    assert kept.synced_at == old_synced_at
    assert unpack_raw_text(kept.raw_body) == prior

    projected = [row for row in stored_wiki_articles(db) if row.id.startswith("expansion:")]
    assert {row.id for row in projected} == {
        f"expansion:{known_code}" for known_code in WIKI_EXPANSION_TITLES
    }
    assert all(row.sections == () for row in projected)
    source = next(row for row in projected if row.id == "expansion:SotV")
    assert source.title.context == "wiki-expansion/SotV.title"
    assert source.title.text == title


def test_article_page_sync_rejects_unclosed_table_and_keeps_previous_raw(db: Session) -> None:
    from app.services.guide_raw.codec import unpack_raw_text
    from app.services.ror2.wiki import sync_wiki_articles
    from app.services.ror2.wiki_structure import article_resource, WIKI_ARTICLE_TITLES

    resource = article_resource("Items")
    prior = "== Cached ==\n{|\n! Item !! Description\n|}"
    upsert_raw(db, "ror2", resource, "https://riskofrain2.wiki.gg/wiki/Items", prior)
    old_row = db.query(GuideRaw).filter_by(game="ror2", resource=resource).one()
    old_synced_at = old_row.synced_at

    def fetch_page(title: str) -> str:
        if title == "Items":
            return "== Common ==\n{|\n! Item !! Description"
        return "== Overview ==\n{|\n! Name !! Description\n|}"

    results = sync_wiki_articles(db, fetch_page=fetch_page)
    assert len(results) == len(WIKI_ARTICLE_TITLES)
    failed = next(row for row in results if row["resource"] == resource)
    assert failed["ok"] is False
    assert "没有结束标记" in str(failed["error"])
    kept = db.query(GuideRaw).filter_by(game="ror2", resource=resource).one()
    assert kept.synced_at == old_synced_at
    assert unpack_raw_text(kept.raw_body) == prior
