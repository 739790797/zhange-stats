from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.skland.endfield_inn.load import InnInvalidInput
from app.services.skland.endfield_inn.match import clauses_for, matches_perfect
from app.services.skland.endfield_inn.plan import build_inn_query, build_plan, list_topics


def _topic(
    topic_id: str,
    objective_type: int,
    *,
    requirement_id: str = "req_menu",
    objective_requirement: str = "req_target",
    objective_result: str = "",
    topic_type: int = 1,
    target: int = 2,
) -> dict:
    params = [{"valueStringList": [objective_requirement]}] if objective_requirement else []
    if objective_result:
        params = [{"valueStringList": [objective_result]}]
    return {
        "id": topic_id,
        "name": {"text": topic_id},
        "unlockLevel": 1,
        "sortId": int(topic_id.rsplit("_", 1)[-1]) if topic_id.rsplit("_", 1)[-1].isdigit() else 1,
        "hotAffix": ["sour"],
        "hotCategory": ["cuisine"],
        "requirementList": [requirement_id],
        "requirementNum": [3],
        "objectiveConditionType": objective_type,
        "objectiveDesc": {"text": "五星目标"},
        "objectiveParameters": params,
        "oProgressToCompare": target,
        "starRequiredScore": [100, 200],
        "topicKPIScoreLimit": 100,
        "topicProfitScoreLimit": 50,
        "topicType": topic_type,
        "overrideSpecialGuestLimit": 0,
        "overridePlayTime": 0,
        "overrideOrderTime": 0,
        "overrideFoodEatingTime": 0,
    }


@pytest.fixture
def endfield_root(tmp_path: Path) -> Path:
    table_cfg = tmp_path / "TableCfg"
    table_cfg.mkdir()
    topics = {
        "inn_topic_1": _topic("inn_topic_1", 16004),
        "inn_topic_2": _topic("inn_topic_2", 16005),
        "inn_topic_3": _topic(
            "inn_topic_3",
            16007,
            objective_requirement="",
            objective_result="E_InnManagementServeSpecialGuestResultType_Normal",
        ),
        "inn_topic_4": _topic(
            "inn_topic_4",
            16007,
            objective_requirement="",
            objective_result="E_InnManagementServeSpecialGuestResultType_Perfect",
        ),
        "inn_topic_5": _topic("inn_topic_5", 16009, target=400),
        "inn_topic_6": _topic("inn_topic_6", 16010),
        "inn_topic_7": _topic("inn_topic_7", 16012),
        "inn_topic_15": _topic(
            "inn_topic_15",
            2147483647,
            requirement_id="req_menu",
            objective_requirement="",
            topic_type=2,
        ),
        "inn_topic_drink": _topic(
            "inn_topic_drink",
            2147483647,
            requirement_id="req_drink",
            objective_requirement="",
        ),
    }
    requirements = {
        "req_menu": {
            "boolFlag": True,
            "describe": ["d_category", "d_affix", "d_meat_1", "d_meat_2"],
            "foodType": 1,
        },
        "req_target": {
            "boolFlag": True,
            "describe": ["d_category", "d_affix", "d_meat_1", "d_meat_2"],
            "foodType": 1,
        },
        "req_drink": {
            "boolFlag": True,
            "describe": ["d_drink"],
            "foodType": 2,
        },
        "req_or": {
            "boolFlag": False,
            "describe": ["d_category", "d_affix"],
            "foodType": 1,
        },
    }
    describes = {
        "d_category": {"category": "cuisine", "affix": "", "ingredient": "", "boolFlag": True},
        "d_affix": {"category": "", "affix": "salty", "ingredient": "", "boolFlag": True},
        "d_meat_1": {"category": "", "affix": "", "ingredient": "item_meat_1", "boolFlag": True},
        "d_meat_2": {"category": "", "affix": "", "ingredient": "item_meat_2", "boolFlag": True},
        "d_negative": {"category": "", "affix": "salty", "ingredient": "", "boolFlag": False},
        "d_drink": {"category": "drink", "affix": "sour", "ingredient": "", "boolFlag": True},
    }
    dishes = {
        "dish_meat_1": {
            "id": "dish_meat_1",
            "category": "cuisine",
            "affix": ["salty"],
            "ingredient": ["item_meat_1"],
            "price": 100,
            "timeCost": 10,
            "unlockLevel": 0,
        },
        "dish_meat_2": {
            "id": "dish_meat_2",
            "category": "cuisine",
            "affix": ["salty"],
            "ingredient": ["item_meat_2"],
            "price": 200,
            "timeCost": 20,
            "unlockLevel": 0,
        },
        "dish_wrong_affix": {
            "id": "dish_wrong_affix",
            "category": "cuisine",
            "affix": ["sweet"],
            "ingredient": ["item_meat_1"],
            "price": 300,
            "timeCost": 1,
            "unlockLevel": 0,
        },
        "dish_wrong_category": {
            "id": "dish_wrong_category",
            "category": "soup",
            "affix": ["salty"],
            "ingredient": ["item_meat_1"],
            "price": 400,
            "timeCost": 2,
            "unlockLevel": 0,
        },
        "dish_locked": {
            "id": "dish_locked",
            "category": "cuisine",
            "affix": ["salty"],
            "ingredient": ["item_meat_1"],
            "price": 500,
            "timeCost": 3,
            "unlockLevel": 3,
        },
        "dish_topic_locked": {
            "id": "dish_topic_locked",
            "category": "cuisine",
            "affix": ["salty"],
            "ingredient": ["item_meat_1"],
            "price": 500,
            "timeCost": 4,
            "unlockLevel": 0,
            "unlockTopicId": "inn_topic_1",
            "unlockTopicStarNum": 2,
        },
    }
    rows = {
        "InnTopicTable.json": topics,
        "InnRequirementTable.json": requirements,
        "InnDescribeTable.json": describes,
        "InnDishTable.json": dishes,
        "InnDrinkTable.json": {
            "drink_good": {
                "id": "drink_good",
                "affix": ["sour"],
                "price": 80,
                "unlockLevel": 0,
            }
        },
        "InnAffixTable.json": {},
        "InnDishCategoryTable.json": {
            "cuisine": {"name": {"text": "菜肴"}},
            "soup": {"name": {"text": "汤羹"}},
            "drink": {"name": {"text": "饮料"}},
        },
        "InnCharSkillTable.json": {
            "chr_fixture_cook": {"list": ["skill_category", "skill_tip", "skill_rare"]},
            "chr_fixture_cook2": {"list": ["skill_category", "skill_rare"]},
            "chr_fixture_cook3": {"list": ["skill_category", "skill_rare"]},
            "chr_blocked": {"list": ["skill_category"]},
            "chr_not_cook": {"list": ["skill_category"]},
        },
        "InnSkillTable.json": {
            "skill_category": {
                "skillType": 0,
                "unlockLevel": 0,
                "parameters": [
                    {"valueStringList": ["cuisine"]},
                    {"valueFloatList": [0.1]},
                ],
            },
            "skill_tip": {
                "skillType": 1,
                "unlockLevel": 3,
                "parameters": [
                    {"valueStringList": ["sour"]},
                    {"valueFloatList": [0.05]},
                ],
            },
            "skill_rare": {
                "skillType": 2,
                "unlockLevel": 0,
                "parameters": [{"valueFloatList": [0.05]}],
            },
        },
        "InnLevelTable.json": {
            str(level): {
                "usableDishType": ["cuisine", "soup"],
                "kitchenStuffNum": 1,
                "deskNum": 2,
                "specialGuestLimit": 2,
                "tipRate": 0.2,
            }
            for level in range(1, 5)
        },
        "InnExpansionTable.json": {
            "expand_1": {"unlockLevel": 1, "addKitchenNum": 1, "name": {"text": "厨房扩建"}},
            "expand_3": {
                "unlockLevel": 3,
                "addKitchenNum": 2,
                "prerequisiteId": "expand_1",
                "name": {"text": "高级厨房"},
            },
            "expand_chef": {"unlockLevel": 3, "addKitchenCharNum": 1, "name": {"text": "增加厨师位"}},
        },
        "InnManagementConst.json": {
            "initKitchenNum": 1,
            "jsspsiFirstStageSkillParam": 0.03,
            "jsspsiSecondStageSkillParam": 0.05,
            "jsspsiThirdStageSkillParam": 0.08,
            "notAllowedKitchenChar": ["chr_blocked"],
            "playTime": 60,
            "orderTime": 5,
            "foodEatingTime": 8,
            "guestLeaveTime": 2,
            "rushUnlockLevel": 3,
        },
        "InnCharTable.json": {
            "chr_fixture_cook": {"charId": "chr_fixture_cook"},
            "chr_fixture_cook2": {"charId": "chr_fixture_cook2"},
            "chr_fixture_cook3": {"charId": "chr_fixture_cook3"},
            "chr_blocked": {"charId": "chr_blocked"},
        },
    }
    for name, payload in rows.items():
        (table_cfg / name).write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_condition_flags_and_ingredient_tier_merge() -> None:
    describes = {
        "category": {"category": "cuisine", "affix": "", "ingredient": "", "boolFlag": True},
        "affix": {"category": "", "affix": "salty", "ingredient": "", "boolFlag": True},
        "meat_1": {"category": "", "affix": "", "ingredient": "meat_1", "boolFlag": True},
        "meat_2": {"category": "", "affix": "", "ingredient": "meat_2", "boolFlag": True},
        "not_salty": {"category": "", "affix": "salty", "ingredient": "", "boolFlag": False},
    }
    requirement = {"boolFlag": True, "describe": ["category", "affix", "meat_1", "meat_2"]}
    clauses = clauses_for(requirement, describes)
    assert len(clauses) == 3
    assert clauses[-1]["ingredients"] == ["meat_1", "meat_2"]
    assert matches_perfect(
        {"category": "cuisine", "affix": ["salty"], "ingredients": ["meat_2"]},
        clauses,
        requirement_flag=True,
    )
    assert not matches_perfect(
        {"category": "cuisine", "affix": ["sweet"], "ingredients": ["meat_2"]},
        clauses,
        requirement_flag=True,
    )
    negative = clauses_for({"describe": ["not_salty"]}, describes)
    assert matches_perfect({"affix": ["sweet"]}, negative)
    assert not matches_perfect({"affix": ["salty"]}, negative)

    or_requirement = {"boolFlag": False, "describe": ["category", "affix"]}
    or_clauses = clauses_for(or_requirement, describes)
    item = {"category": "soup", "affix": ["salty"], "ingredients": []}
    assert matches_perfect(item, or_clauses, requirement_flag=False)
    assert not matches_perfect(item, or_clauses, requirement_flag=True)


def test_menu_filters_by_level_and_food_type_and_reports_shortage(endfield_root: Path) -> None:
    plan = build_plan("inn_topic_1", 1, root=endfield_root)
    group = plan["menu"][0]
    assert {dish["id"] for dish in group["dishes"]} == {"dish_meat_1", "dish_meat_2"}
    assert group["missing"] == 1

    drinks = build_plan("inn_topic_drink", 1, root=endfield_root)
    assert [dish["id"] for dish in drinks["menu"][0]["dishes"]] == ["drink_good"]


def test_chef_roster_skills_values_and_expansion_validation(endfield_root: Path) -> None:
    low = build_plan("inn_topic_1", 2, ["expand_1"], root=endfield_root)
    assert [chef["char_id"] for chef in low["chefs"]] == ["chr_fixture_cook", "chr_fixture_cook2"]
    notes = low["chefs"][0]["notes"]
    assert "菜肴加速 +10%" in notes
    assert "稀有出餐率 +5%" in notes
    assert any("小费 +5%" in note and "3 级后生效" in note for note in notes)
    assert low["star"]["estimate"].find("后厨 2 口") >= 0

    high = build_plan("inn_topic_1", 3, root=endfield_root)
    assert any("酸小费 +5%" == note for note in high["chefs"][0]["notes"])
    with pytest.raises(InnInvalidInput, match="需客栈 3 级"):
        build_plan("inn_topic_1", 2, ["expand_3"], root=endfield_root)
    with pytest.raises(InnInvalidInput, match="未知扩建"):
        build_plan("inn_topic_1", 4, ["unlisted"], root=endfield_root)


def test_objective_estimates_cover_all_six_conditions_and_private_topic(endfield_root: Path) -> None:
    sell = build_plan("inn_topic_1", 1, root=endfield_root)["star"]
    assert "最快符合条件菜谱 10 秒" in sell["estimate"]
    assert sell["needs_objective"] is True

    rare = build_plan("inn_topic_2", 1, root=endfield_root)["star"]["estimate"]
    assert "稀有标签" in rare

    normal = build_plan("inn_topic_3", 1, root=endfield_root)["star"]["estimate"]
    perfect = build_plan("inn_topic_4", 1, root=endfield_root)["star"]["estimate"]
    assert "普通接待即可" in normal
    assert "完美接待" in perfect

    revenue = build_plan("inn_topic_5", 1, root=endfield_root)["star"]["estimate"]
    assert "至少成功售出 2 单" in revenue

    blaze = build_plan("inn_topic_6", 1, root=endfield_root)["star"]["estimate"]
    assert "客栈 3 级解锁" in blaze

    streak = build_plan("inn_topic_7", 1, root=endfield_root)["star"]["estimate"]
    assert "大约能接待 8 位" in streak

    private = build_plan("inn_topic_15", 4, root=endfield_root)["star"]
    assert private["private_chef"] is True
    assert private["objective"] == "没有星级奖励"


def test_topics_and_expansions_are_listed_from_fixture(endfield_root: Path) -> None:
    result = list_topics(root=endfield_root)
    assert len(result["topics"]) == 9
    assert {item["id"] for item in result["expansions"]} == {"expand_1", "expand_3", "expand_chef"}
    assert [item["rare_rate_bonus"] for item in result["jsspsi_bonus_tiers"]] == [0.03, 0.05, 0.08]


def test_catalog_includes_locked_recipes_and_unlock_conditions(endfield_root: Path) -> None:
    result = build_inn_query(level=1, root=endfield_root)
    assert result["recommendations"] is None
    dishes = {dish["id"]: dish for dish in result["dishes"]}
    assert dishes["dish_locked"]["unlocked"] is False
    assert dishes["dish_locked"]["unlock_conditions"] == ["客栈 3 级"]
    assert dishes["dish_topic_locked"]["unlocked"] is False
    assert dishes["dish_topic_locked"]["unlock_topic_star_num"] == 2
    assert dishes["dish_topic_locked"]["unlock_conditions"] == ["「inn_topic_1」主题达成 2 星"]


def test_kitchen_and_chef_recommendation_capacity_follow_expansions(endfield_root: Path) -> None:
    cases = (
        ([], (1, 1, 1)),
        (["expand_1"], (2, 2, 2)),
        (["expand_1", "expand_chef"], (2, 3, 3)),
        (["expand_1", "expand_3", "expand_chef"], (4, 5, 3)),
    )

    for expansions, expected in cases:
        result = build_inn_query(
            level=4,
            expansions=expansions,
            topic_id="inn_topic_1",
            root=endfield_root,
        )
        recommendations = result["recommendations"]
        assert recommendations is not None
        assert (
            result["kitchen_count"],
            result["chef_slot_count"],
            len(recommendations["chefs"]),
        ) == expected


def test_jsspsi_query_returns_each_data_driven_bonus_tier(endfield_root: Path) -> None:
    bonuses = [
        build_inn_query(level=4, jsspsi_bonus_tier=tier, root=endfield_root)["jsspsi_rare_rate_bonus"]
        for tier in (1, 2, 3)
    ]
    assert bonuses == [0.03, 0.05, 0.08]


def test_selected_topic_at_zero_stars_keeps_recommendations_but_filters_locked_recipes(endfield_root: Path) -> None:
    result = build_inn_query(
        level=3,
        topic_id="inn_topic_1",
        topic_stars={"inn_topic_1": 0},
        root=endfield_root,
    )

    assert result["recommendations"] is not None
    dishes = {dish["id"]: dish for dish in result["dishes"]}
    assert dishes["dish_topic_locked"]["unlocked"] is False
    assert all(
        dish["id"] != "dish_topic_locked" for group in result["recommendations"]["menu"] for dish in group["dishes"]
    )


def test_theme_stars_unlock_recipes_and_feed_topic_recommendations(endfield_root: Path) -> None:
    result = build_inn_query(
        level=3,
        expansions=["expand_1", "expand_chef"],
        topic_id="inn_topic_1",
        topic_stars={"inn_topic_1": 2},
        jsspsi_bonus_tier=3,
        root=endfield_root,
    )
    dishes = {dish["id"]: dish for dish in result["dishes"]}
    assert dishes["dish_topic_locked"]["unlocked"] is True
    assert result["kitchen_count"] == 2
    assert result["chef_slot_count"] == 3
    assert result["jsspsi_rare_rate_bonus"] == 0.08
    assert result["recommendations"] is not None
    assert len(result["recommendations"]["chefs"]) == 3
    assert any(
        dish["id"] == "dish_topic_locked" for group in result["recommendations"]["menu"] for dish in group["dishes"]
    )
    assert {tag["id"] for chef in result["chef_catalog"] for tag in chef["tags"]} >= {
        "category:cuisine",
        "affix:sour",
        "skill:rare_rate",
    }


def test_catalog_query_rejects_invalid_progress_and_expansion_prerequisites(endfield_root: Path) -> None:
    with pytest.raises(InnInvalidInput, match="0 至 5 星"):
        build_inn_query(level=4, topic_stars={"inn_topic_1": 6}, root=endfield_root)
    with pytest.raises(InnInvalidInput, match="未知主题星级"):
        build_inn_query(level=4, topic_stars={"unknown": 1}, root=endfield_root)
    with pytest.raises(InnInvalidInput, match="需先完成 expand_1"):
        build_inn_query(level=4, expansions=["expand_3"], root=endfield_root)
    with pytest.raises(InnInvalidInput, match="档位无效"):
        build_inn_query(level=4, jsspsi_bonus_tier=4, root=endfield_root)
