"""幸存者详情：词条段落、技能模块和日志模块拼在一起。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.biz_logging import clear_log_until_change
from app.models.guide_raw import GuideRaw
from app.models.guide_token_translation import GuideTokenTranslation, GuideTokenTranslationSync
from app.services.guide_raw.pipeline import RawSpec, upsert_raw
from app.services.ror2.catalog import Ror2WikiError
from app.services.ror2.lang import apply_survivor_detail_language
from app.services.ror2.schemas import Ror2SkillGroupOut, Ror2SkillOut, Ror2SurvivorOut
from app.services.ror2.survivor_page import (
    Ror2MissingSurvivor,
    accept_survivor_page,
    build_survivor_detail,
    survivor_page_resource,
)
from app.services.ror2.weblate import RESOURCE as WEBLATE_RESOURCE, dump_snapshot
from app.services.ror2.wiki import (
    fetch_wiki_text,
    get_survivor_detail,
    reset_catalog_memo,
    sync_survivor_pages,
    sync_wiki,
    translated_detail,
)
from tests.test_ror2_catalog import _FIXTURES

_PAGE = """
{{SurvivorPage}}
The '''{{PAGENAME}}''' is a playable [[Survivors|character]].

==Skills==
{{SkillType|Primary|
{{Skill
| name = Double Tap
| type = Primary
| cooldown =
| proc = 1.0
| notes =
* Shoots 6 times.
* Falls off via [[Damage#Damage_Falloff|default projectile falloff]].
}}
}}
{{SkillType|Secondary|
{{Skill
| name = Phase Blast
| cooldown = 3s
| proc = 0.5 x 8
| notes =
* Buckshot.
}}
}}

== Behaviors ==
''Only when AI controls him.''

# '''Use secondary''': within 10m.
# '''Chase''': no requirements.

== Tips ==
* Reset accuracy.
** Jump during the slide.

==Lore==
{{Lore}}

==Version History==
<div>
;[[Hallowed Concepts]]
*Major Content
**Added Sabotage
<hr>
; [[Anniversary Update]]
*Gameplay Changes
**Damage up
</div>

==Gallery==
{|
|[[File:Commando_-_Default.png|256px]]
|[[File:Commando_-_Hornet.png|256px]]
|-
|[[File:commando Default 360.gif|256px]]
|[[File:commando Hornet 360.gif|256px]]
|-
|[[File:Default Commando.png|32px]] Default
|{{SotS}}[[File:Hornet.png|32px]] Hornet
|}

==Trivia==
*Original character.
<gallery>
File:Commando - UnusedSotV.png|Unused skin
</gallery>
"""

_SKILLS = {
    "Double Tap": {"Desc": "Rapidly shoot for {{Color|d|100% damage}}.", "Unlock": ""},
    "Phase Blast": {"Desc": "Two blasts.", "Unlock": "Commando: Rolling Thunder"},
}

_LORE = {"Commando": {"Desc": "The soldier ducked.\n\nHe counted."}}


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
def _clear() -> None:
    clear_log_until_change()
    reset_catalog_memo()
    yield
    clear_log_until_change()
    reset_catalog_memo()


def _survivor() -> Ror2SurvivorOut:
    return Ror2SurvivorOut(
        name="Commando",
        description="Module blurb.",
        umbra="Cornered Gunslinger",
        phrase_escape="..and so he left.",
        phrase_vanish="..and so he vanished.",
        health=110,
        health_per_level=33,
        regen=1,
        regen_per_level=0.2,
        damage=12,
        damage_per_level=2.4,
        speed=7,
        acceleration=None,
        mass=100,
        armor=0,
        wiki_url="https://riskofrain2.wiki.gg/wiki/Commando",
        image_url="https://riskofrain2.wiki.gg/images/Commando.png",
    )


def test_detail_keeps_wiki_sections_and_module_skill_text() -> None:
    detail = build_survivor_detail(_survivor(), _PAGE, _SKILLS, _LORE)
    assert "<b>Commando</b>" in detail.summary
    assert "character" in detail.summary
    assert detail.lore == "The soldier ducked.\n\nHe counted."
    primary, secondary = detail.skills
    assert primary.skill_type == "Primary"
    tap = primary.skills[0]
    assert tap.proc == "1.0"
    assert tap.cooldown == ""
    assert tap.description == "Rapidly shoot for <style=cIsDamage>100% damage</style>."
    assert [item.text for item in tap.notes] == ["Shoots 6 times.", "Falls off via default projectile falloff."]
    assert tap.image_url.endswith("/Double_Tap.png")
    blast = secondary.skills[0]
    assert blast.cooldown == "3s"
    assert blast.unlock == "Commando: Rolling Thunder"
    assert detail.behaviors[0].text == "<i>Only when AI controls him.</i>"
    assert detail.behaviors[1].kind == "ol"
    assert detail.behaviors[1].items[0].text == "<b>Use secondary</b>: within 10m."
    assert detail.tips[0].items[0].children[0].text == "Jump during the slide."
    assert [group.version for group in detail.history] == ["Hallowed Concepts", "Anniversary Update"]
    assert detail.history[0].items[0].children[0].text == "Added Sabotage"
    assert detail.gallery[1].expansion == "SotS"
    assert detail.gallery[1].caption == "Hornet"
    assert detail.gallery[1].spin_url.endswith("/commando_Hornet_360.gif")
    assert detail.trivia[0].items[0].text == "Original character."
    assert detail.trivia[1].images[0].caption == "Unused skin"


def test_detail_language_uses_lore_and_skill_descriptions() -> None:
    skills = {
        "Double Tap": {"Desc": "Rapidly shoot for {{Color|d|100% damage}}.", "Type": "Primary"},
        "Phase Blast": {"Desc": "Two blasts for {{Color|d|8x200% damage}}.", "Type": "Secondary"},
    }
    detail = build_survivor_detail(_survivor(), _PAGE, skills, _LORE)
    detail.skills.append(
        Ror2SkillGroupOut(
            skill_type="Utility",
            skills=[
                Ror2SkillOut(name="Tactical Dive", skill_type="Utility", description="Roll a short distance."),
                Ror2SkillOut(name="Tactical Slide", skill_type="Utility", description="Slide a short distance."),
            ],
        )
    )
    apply_survivor_detail_language(
        detail,
        {
            "COMMANDO_BODY_LORE": "士兵缩身躲避。",
            "COMMANDO_PRIMARY_NAME": "双击",
            "COMMANDO_PRIMARY_DESCRIPTION": "造成<style=cIsDamage>100%的伤害</style>。",
            "COMMANDO_SECONDARY_ALT1_NAME": "相位爆破",
            "COMMANDO_SECONDARY_ALT1_DESCRIPTION": "合计造成<style=cIsDamage>8x200%的伤害</style>。",
            "COMMANDO_UTILITY_NAME": "战术俯冲",
            "COMMANDO_UTILITY_DESCRIPTION": "翻滚一小段距离。",
            "COMMANDO_UTILITY_ALT_NAME": "战术滑行",
            "COMMANDO_UTILITY_ALT_DESCRIPTION": "滑行一小段距离。",
        },
    )
    assert detail.lore_zh == "士兵缩身躲避。"
    assert detail.lore == "The soldier ducked.\n\nHe counted."
    tap = detail.skills[0].skills[0]
    assert tap.name == "Double Tap"
    assert tap.name_zh == "双击"
    assert "100%的伤害" in tap.description_zh
    blast = detail.skills[1].skills[0]
    assert blast.name_zh == "相位爆破"
    assert detail.skills[2].skills[0].name_zh == "战术俯冲"
    assert detail.skills[2].skills[1].name_zh == "战术滑行"
    mage = build_survivor_detail(
        Ror2SurvivorOut(name="Artificer", wiki_url="https://riskofrain2.wiki.gg/wiki/Artificer"),
        "{{SurvivorPage}}\n",
        {},
        {},
    )
    mage.skills = [
        Ror2SkillGroupOut(
            skill_type="Primary",
            skills=[
                Ror2SkillOut(name="Flame Bolt", skill_type="Primary", description="Fire a bolt for 280% damage. Hold up to 4."),
                Ror2SkillOut(name="Plasma Bolt", skill_type="Primary", description="Fire a bolt for 280% damage that explodes. Hold up to 4."),
            ],
        )
    ]
    apply_survivor_detail_language(
        mage,
        {
            "MAGE_PRIMARY_FIRE_NAME": "火炎弹",
            "MAGE_PRIMARY_FIRE_DESCRIPTION": "造成280%的伤害。最多可发射4次。",
            "MAGE_PRIMARY_LIGHTNING_NAME": "等离子弹",
            "MAGE_PRIMARY_LIGHTNING_DESCRIPTION": "造成280%的伤害并引爆。最多发射4次。",
        },
    )
    assert mage.skills[0].skills[0].name_zh == "火炎弹"
    assert mage.skills[0].skills[1].name_zh == "等离子弹"
    rex = build_survivor_detail(
        Ror2SurvivorOut(name="REX", wiki_url="https://riskofrain2.wiki.gg/wiki/REX"),
        "{{SurvivorPage}}\n",
        {},
        {},
    )
    rex.skills = [
        Ror2SkillGroupOut(
            skill_type="Secondary",
            skills=[
                Ror2SkillOut(
                    name="DIRECTIVE: Drill",
                    skill_type="Secondary",
                    description="Raining down for 450% damage per second.",
                ),
                Ror2SkillOut(
                    name="Seed Barrage",
                    skill_type="Secondary",
                    description="15% HP. Launch a mortar for 450% damage.",
                ),
            ],
        )
    ]
    apply_survivor_detail_language(
        rex,
        {
            "TREEBOT_BODY_LORE": "雷克斯的日志。",
            "TREEBOT_SECONDARY_NAME": "种子大炮",
            "TREEBOT_SECONDARY_DESCRIPTION": "15%生命值。造成450%的伤害。",
            "TREEBOT_SECONDARY_ALT1_NAME": "命令：钻孔",
            "TREEBOT_SECONDARY_ALT1_DESCRIPTION": "造成每秒450%的伤害。",
        },
    )
    assert rex.lore_zh == "雷克斯的日志。"
    void = build_survivor_detail(
        Ror2SurvivorOut(name="Void Fiend", wiki_url="https://riskofrain2.wiki.gg/wiki/Void_Fiend"),
        "{{SurvivorPage}}\n",
        {},
        {},
    )
    void.skills = [
        Ror2SkillGroupOut(
            skill_type="Primary",
            skills=[Ror2SkillOut(name="Corrupted Drown", skill_type="Primary", description="Fire a short-range beam for 2000% damage.")],
        )
    ]
    acolyte = build_survivor_detail(
        Ror2SurvivorOut(name="Acolyte", wiki_url="https://riskofrain2.wiki.gg/wiki/Acolyte"),
        "{{SurvivorPage}}\n",
        {},
        {},
    )
    acolyte.skills = [
        Ror2SkillGroupOut(
            skill_type="Primary",
            skills=[
                Ror2SkillOut(
                    name="Torrential Slash",
                    skill_type="Primary",
                    description="Slash forwards, firing a wave of energy for 300% damage.",
                )
            ],
        )
    ]
    apply_survivor_detail_language(
        void,
        {
            "VOIDSURVIVOR_PRIMARY_NAME": "「溺亡」",
            "VOIDSURVIVOR_PRIMARY_DESCRIPTION": "发射远程光束。",
            "VOIDSURVIVOR_PRIMARY_UPRADE_TOOLTIP": "<style=cKeywordName>【腐化升级】</style>转化成2000%伤害的短程光束。",
        },
    )
    apply_survivor_detail_language(
        acolyte,
        {
            "LILREAPER_PRIMARY_NAME": "狂暴斩击",
            "LILREAPER_PRIMARY_DESCRIPTION": "向前斩击，造成300%伤害。",
        },
    )
    assert void.skills[0].skills[0].name_zh == "「溺亡」"
    assert "腐化升级" in void.skills[0].skills[0].description_zh
    assert "远程光束" not in void.skills[0].skills[0].description_zh
    assert acolyte.skills[0].skills[0].name_zh == "狂暴斩击"
    assert rex.skills[0].skills[0].name_zh == "命令：钻孔"
    assert rex.skills[0].skills[1].name_zh == "种子大炮"


def test_page_without_survivor_template_is_rejected() -> None:
    with pytest.raises(Ror2WikiError, match="不是幸存者词条"):
        accept_survivor_page("==Skills==\n")


def test_detail_fetches_a_missing_page_once(db: Session) -> None:
    def fetch(spec: RawSpec) -> str:
        return _FIXTURES[spec.resource]

    sync_wiki(db, fetch=fetch)
    calls = {"n": 0}

    def fetch_page(name: str) -> str:
        calls["n"] += 1
        assert name == "Commando"
        return _PAGE

    detail = get_survivor_detail(db, "Commando", fetch_page=fetch_page)
    again = get_survivor_detail(db, "Commando", fetch_page=fetch_page)
    assert calls["n"] == 1
    assert again.summary == detail.summary
    assert detail.skills[0].skills[0].name == "Double Tap"
    with pytest.raises(Ror2MissingSurvivor):
        get_survivor_detail(db, "Nobody", fetch_page=fetch_page)



def test_translated_detail_falls_back_to_source_and_applies_approved_tokens(db: Session) -> None:
    sync_wiki(db, fetch=lambda spec: _FIXTURES[spec.resource])
    upsert_raw(
        db,
        "ror2",
        survivor_page_resource("Commando"),
        "https://riskofrain2.wiki.gg/wiki/Commando",
        _PAGE,
    )
    upsert_raw(
        db,
        "ror2",
        WEBLATE_RESOURCE,
        "https://weblate.invalid/ror2",
        dump_snapshot(
            {
                "survivors.Survivors.Commando.Name": {
                    "source": "Commando",
                    "target": "指挥官",
                    "state": "approved",
                },
                "lore.lore.Commando.Desc": {
                    "source": "The soldier ducked.",
                    "target": "士兵躲开了。",
                    "state": "approved",
                },
                "skills.skills.Double Tap.Name": {
                    "source": "Double Tap",
                    "target": "双击",
                    "state": "approved",
                },
            },
            {
                "survivors.Survivors.Commando.Name": "Commando",
                "lore.lore.Commando.Desc": "The soldier ducked.",
                "skills.skills.Double Tap.Name": "Double Tap",
            },
        ),
    )

    detail = translated_detail(db, "Commando")
    assert detail.name.text == "指挥官"
    assert detail.name.original == "Commando"
    assert detail.name.token == "survivors.Survivors.Commando.Name"
    assert "playable" in detail.summary.original
    assert detail.summary.text == detail.summary.original
    assert detail.summary.token is None
    assert detail.lore.text == "士兵躲开了。"
    assert detail.lore.original == "The soldier ducked."
    assert detail.lore.token == "lore.lore.Commando.Desc"
    primary = detail.skills[0].skills[0]
    assert primary.name.text == "双击"
    assert primary.name.original == "Double Tap"
    assert primary.name.token == "skills.skills.Double Tap.Name"
    assert primary.description.text
    assert primary.description.text == primary.description.original


def test_page_sync_keeps_going_when_one_page_fails(db: Session) -> None:
    sync_wiki(db, fetch=lambda spec: _FIXTURES[spec.resource])

    def fetch_page(name: str) -> str:
        raise Ror2WikiError(f"{name} down")

    results = sync_survivor_pages(db, fetch_page=fetch_page)
    assert results[0]["ok"] is False
    assert "down" in str(results[0]["error"])


def test_fetch_wiki_text_rejects_offsite_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("should not request")

    monkeypatch.setattr("app.services.ror2.wiki.http_request", fail)
    with pytest.raises(Ror2WikiError, match="拒绝的页面名"):
        fetch_wiki_text("https://example.invalid/Commando")
