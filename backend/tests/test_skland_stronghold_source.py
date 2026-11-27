import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.services.skland import stronghold_source as source
from app.services.skland.client import GAME_ARKNIGHTS, SklandApiError, SklandRole, SklandSession

_ROLE = SklandRole(GAME_ARKNIGHTS, "明日方舟", "12345", "测试", "官服", "1")
_SESSION = SklandSession("fixture", "fixture")


@pytest.fixture
def fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "skland_stronghold_sample.json").read_text(encoding="utf-8")
    )


def test_signed_official_history_and_versioned_resource(fixture, monkeypatch):
    requested = []

    def get(method, url, **kwargs):
        requested.append(urlsplit(url))
        assert method == "GET" and kwargs["headers"]["sign"] and kwargs["follow_redirects"] is False
        if urlsplit(url).path.endswith("/resource"):
            return httpx.Response(200, json={"code": 0, "data": {"resources": fixture["resources"]}})
        content = base64.b64encode(json.dumps({"history": fixture["history"]}).encode()).decode()
        return httpx.Response(200, json={"code": 0, "data": {"content": content}}, headers={"X-Transformed": "Base64"})

    monkeypatch.setattr(source, "http_request", get)
    versions = source.fetch_official_resources(_SESSION, "act3autochess")
    batch = source.fetch_official_history(_SESSION, _ROLE, versions=versions)
    assert all(url.hostname == "zonai.skland.com" for url in requested)
    assert parse_qs(requested[1].query) == {"uid": ["12345"], "activityId": ["act3autochess"]}
    assert parse_qs(requested[0].query) == {"activityId": ["act3autochess"]}
    solo, multi = batch.records
    assert batch.resources_available and solo.mode_type == "single"
    assert solo.completed is False and solo.pass_round == 0
    assert solo.strategy_name == "二重奏" and solo.season_label == "测试赛季"
    assert solo.roster[0].char_id == "char_002_amiya" and solo.roster[0].level == 55
    assert solo.bonds[0].active and solo.bonds[0].layer == 0 and solo.bonds[0].layer_scope == "role"
    assert solo.bonds[1].active is False and solo.bonds[1].layer is None
    assert multi.mode_type == "multi" and multi.completed is None
    assert multi.bonds[0].layer == 20 and multi.bonds[0].layer_scope == "unknown"
    assert multi.roster == []


def test_official_battle_fields_and_asset_projection(fixture):
    solo, multi = source.parse_history(fixture, _ROLE, source._versions(fixture))
    assert multi.scene_id == "scene_sample" and multi.version_id == "version-a"
    assert (multi.ended_at - multi.battle.started_at).total_seconds() == 1800
    assert multi.battle.team_completed is True
    assert (multi.battle.trophy_before, multi.battle.trophy_after) == (643, 651)
    assert (multi.battle.coin_cost, multi.battle.sync_count, multi.battle.kill_count) == (164, 4, 280)
    assert solo.battle.title == "测试称号"
    assert solo.battle.strategy_icon_url.endswith("/band_icon/band_demo.png")
    assert solo.bonds[0].icon_url.endswith("/bond_icon/bond_demo.png")
    assert solo.bonds[1].icon_url is None
    operator = solo.roster[0]
    assert (operator.tier, operator.merge_level, operator.profession) == (3, 2, "CASTER")
    assert operator.branch_id == "corecaster"
    assert (operator.skill_id, operator.module_id) == ("skcom_charge_1", "uniequip_002_amiya")
    equipment = operator.equipment[0]
    assert (equipment.id, equipment.name, equipment.tier) == ("item_training", "测试道具", 2)
    assert equipment.icon_url.endswith("/equip_icon/equip_demo.png")
    trait = operator.traits[0]
    assert trait.icon_url.endswith("/trait_icon/trait_demo.png")
    assert trait.description == "受到一点伤害"
    boss = solo.battle.bosses[0]
    assert (boss.enemy_id, boss.killed, boss.hidden) == ("enemy_1234_test", True, False)


def test_optional_resources_fail_without_losing_official_records(fixture, monkeypatch):
    def get(_method, url, **_kwargs):
        if urlsplit(url).path.endswith("/resource"):
            return httpx.Response(503, json={"upstream": "untrusted"})
        return httpx.Response(200, json={"code": 0, "data": {"history": fixture["history"]}})

    monkeypatch.setattr(source, "http_request", get)
    with pytest.raises(SklandApiError):
        source.fetch_official_resources(_SESSION, "act3autochess")
    batch = source.fetch_official_history(_SESSION, _ROLE)
    assert not batch.resources_available
    assert batch.records[0].strategy_id == "strategy_a" and batch.records[0].strategy_name is None
    assert batch.records[0].roster[0].char_id == "char_002_amiya"
    assert batch.records[0].bonds[0].layer == 0


def test_effect_conditions_survive_format_cleanup_and_foreign_activity_is_ignored(fixture):
    resources = source._versions(fixture)
    resource = resources["version-a"]
    resource["bandInfo"]["strategy_a"]["desc"] = r"<@ba.vup>友方增益</>\n&lt;标准模拟&gt;额外效果"
    solo, _ = source.parse_history(fixture, _ROLE, resources)
    assert solo.battle.strategy_description == "友方增益\n<标准模拟>额外效果"
    resource["versionInfo"]["activityId"] = "another-activity"
    solo, _ = source.parse_history(fixture, _ROLE, resources)
    assert solo.strategy_name is None and solo.battle.strategy_description is None
    assert solo.bonds[0].layer == 0


@pytest.mark.parametrize("change", [{"id": "99999-match"}, {"gameEndTs": "unknown"}, {"activityId": None}])
def test_unverified_role_or_time_rejects_the_batch(fixture, change):
    fixture["history"]["records"][0].update(change)
    with pytest.raises(SklandApiError, match="缺少可验证"):
        source.parse_history(fixture, _ROLE, {})


def test_empty_history_is_not_the_same_as_an_unknown_response():
    assert source.parse_history({"history": {"records": []}}, _ROLE, {}) == []
    with pytest.raises(SklandApiError, match="未返回有效"):
        source.parse_history({"history": {}}, _ROLE, {})
