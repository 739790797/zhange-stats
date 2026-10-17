"""已落库的游戏中文：只用于给 Weblate 提建议。"""

from __future__ import annotations

import json

from app.services.ror2.lang import apply_item_language, apply_survivor_language, lang_file_sort_key, string_table
from app.services.ror2.schemas import Ror2CatalogOut, Ror2ItemOut, Ror2SurvivorOut


def _strings(names: dict[str, str]) -> str:
    return json.dumps({"strings": names}, ensure_ascii=False)



def _catalog() -> Ror2CatalogOut:
    return Ror2CatalogOut(
        source="https://riskofrain2.wiki.gg/",
        fetched_at="2026-10-15T00:00:00",
        items=[
            Ror2ItemOut(
                name="Soldier's Syringe",
                internal_name="ITEM_SYRINGE",
                wiki_url="https://riskofrain2.wiki.gg/wiki/Soldier's_Syringe",
            ),
            Ror2ItemOut(
                name="BurnNearby",
                wiki_url="https://riskofrain2.wiki.gg/wiki/BurnNearby",
            ),
        ],
        equipment=[
            Ror2ItemOut(
                name="Radar Scanner",
                internal_name="EQUIPMENT_SCANNER",
                wiki_url="https://riskofrain2.wiki.gg/wiki/Radar_Scanner",
            )
        ],
        survivors=[
            Ror2SurvivorOut(
                name="Commando",
                wiki_url="https://riskofrain2.wiki.gg/wiki/Commando",
            )
        ],
    )


def test_string_table_reads_strings_object() -> None:
    table = string_table(
        _strings({"ITEM_SYRINGE_NAME": "士兵的注射器", "not_a_token": "x"}),
        "output.json",
    )
    assert table == {"ITEM_SYRINGE_NAME": "士兵的注射器"}


def test_lang_file_order_puts_base_before_numbered_dlc() -> None:
    names = [
        "DLC10.json",
        "Items.json",
        "DLC2.json",
        "output.json",
        "DLC4.json",
        "Equipment.json",
    ]
    assert sorted(names, key=lang_file_sort_key) == [
        "output.json",
        "Equipment.json",
        "Items.json",
        "DLC2.json",
        "DLC4.json",
        "DLC10.json",
    ]


def test_item_language_overlays_name_desc_and_pickup() -> None:
    catalog = _catalog()
    syringe = catalog.items[0]
    syringe.description = "Increases attack speed."
    syringe.quote = "Attack speed."
    apply_item_language(
        catalog.items + catalog.equipment,
        {
            "ITEM_SYRINGE_NAME": "士兵的注射器",
            "ITEM_SYRINGE_DESC": "提高<style=cIsDamage>攻击速度</style>。",
            "ITEM_SYRINGE_PICKUP": "提高攻击速度。",
            "EQUIPMENT_SCANNER_NAME": "雷达扫描器",
        },
    )
    assert syringe.name == "Soldier's Syringe"
    assert syringe.description == "Increases attack speed."
    assert syringe.quote == "Attack speed."
    assert syringe.name_zh == "士兵的注射器"
    assert syringe.description_zh == "提高<style=cIsDamage>攻击速度</style>。"
    assert catalog.items[1].name == "BurnNearby"
    assert catalog.items[1].name_zh == ""
    assert catalog.equipment[0].name == "Radar Scanner"
    assert catalog.equipment[0].name_zh == "雷达扫描器"
    assert catalog.equipment[0].description_zh == ""
    assert catalog.survivors[0].name == "Commando"
    assert catalog.survivors[0].name_zh == ""


def test_survivor_language_uses_body_tokens_and_keeps_english() -> None:
    catalog = _catalog()
    catalog.survivors.extend(
        [
            Ror2SurvivorOut(name="MUL-T", wiki_url="https://riskofrain2.wiki.gg/wiki/MUL-T"),
            Ror2SurvivorOut(name="Operator", wiki_url="https://riskofrain2.wiki.gg/wiki/Operator"),
            Ror2SurvivorOut(name="Guest", wiki_url="https://riskofrain2.wiki.gg/wiki/Guest"),
        ]
    )
    apply_survivor_language(
        catalog.survivors,
        {
            "COMMANDO_BODY_NAME": "指挥官",
            "TOOLBOT_BODY_NAME": "多功能枪兵",
            "DRONETECH_BODY_NAME": "操作员",
        },
    )
    commando, mult, operator, guest = catalog.survivors
    assert commando.name == "Commando"
    assert commando.name_zh == "指挥官"
    assert mult.name == "MUL-T"
    assert mult.name_zh == "多功能枪兵"
    assert operator.name == "Operator"
    assert operator.name_zh == "操作员"
    assert guest.name_zh == ""


def test_item_language_uses_confirmed_token_aliases() -> None:
    wisp = Ror2ItemOut(
        name="Will-o'-the-wisp",
        internal_name="ITEM_EXPODEONDEATH",
        description="lava pillar",
        wiki_url="https://riskofrain2.wiki.gg/wiki/Will-o'-the-wisp",
    )
    lantern = Ror2ItemOut(
        name="Bolstering Lantern",
        internal_name="ITEM_LOWERHEALTHHIGHERDAMAGE",
        wiki_url="https://riskofrain2.wiki.gg/wiki/Bolstering_Lantern",
    )
    whispers = Ror2ItemOut(
        name="Sonorous Whispers",
        internal_name="ITEM_RESETCHESTS",
        wiki_url="https://riskofrain2.wiki.gg/wiki/Sonorous_Whispers",
    )
    antlers = Ror2ItemOut(
        name="Elusive Antlers",
        internal_name="ITEM_NEGATEATTACK",
        wiki_url="https://riskofrain2.wiki.gg/wiki/Elusive_Antlers",
    )
    alpha = Ror2ItemOut(
        name="Berzerkers Pauldron (Alpha)",
        internal_name="ITEM_WARCRYONCOMBAT",
        wiki_url="https://riskofrain2.wiki.gg/wiki/Berzerkers_Pauldron_(Alpha)",
    )
    apply_item_language(
        [wisp, lantern, whispers, antlers, alpha],
        {
            "ITEM_EXPLODEONDEATH_NAME": "鬼火",
            "ITEM_EXPLODEONDEATH_DESC": "击杀时召唤熔岩柱。",
            "ITEM_ATTACKSPEEDPERNEARBYALLYORENEMY_NAME": "强化提灯",
            "ITEM_ITEMDROPCHANCEONKILL_NAME": "嘹亮低语",
            "ITEM_SPEEDBOOSTPICKUP_NAME": "难以捉摸的鹿角",
            "ITEM_WARCRYONMULTIKILL_NAME": "狂战士肩甲",
        },
    )
    assert wisp.name_zh == "鬼火"
    assert wisp.description_zh == "击杀时召唤熔岩柱。"
    assert wisp.name == "Will-o'-the-wisp"
    assert lantern.name_zh == "强化提灯"
    assert whispers.name_zh == "嘹亮低语"
    assert antlers.name_zh == "难以捉摸的鹿角"
    assert alpha.name_zh == ""
