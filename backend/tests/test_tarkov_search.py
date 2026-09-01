"""Unit tests for tarkov site-wide search matching / ranking."""

from __future__ import annotations

from app.services.tarkov import catalog as catalog
from app.services.tarkov import search as search
from app.services.tarkov import tasks as tasks
from app.services.tarkov.ammo import SOURCE_JSON_API

from tests.test_tarkov_catalog import _json_envelope
from tests.test_tarkov_tasks import _envelope as _task_envelope


def test_hit_rank_prefers_exact_compact_name():
    assert search.hit_rank("医疗隐私-1", "医疗隐私-1") == 0
    assert search.hit_rank("医疗隐私-1", "医疗隐私 - Part 1") == 3
    assert search.hit_rank("医疗隐私-1", "Health Care Privacy - Part 1") is None
    assert search.hit_rank("6B13", "6B13 装甲", "6B13") == 0
    assert search.hit_rank("  ", "anything") is None


def test_pick_hits_ranks_exact_before_token_match():
    rows = [
        {"id": "a", "name": "医疗隐私 - Part 1"},
        {"id": "b", "name": "医疗隐私-1"},
        {"id": "c", "name": "其他医疗隐私任务"},
    ]
    picked, total = search.pick_hits(rows, "医疗隐私-1", ("name",), limit=10)
    assert total == 2
    assert [r["id"] for r in picked] == ["b", "a"]


def test_pick_hits_matches_catalog_short_name():
    rows = catalog.parse_catalog_items(SOURCE_JSON_API, _json_envelope())
    picked, total = search.pick_hits(
        rows, "6B13", ("name", "short_name", "id"), limit=10
    )
    assert total == 1
    assert picked[0]["id"] == "ar1"


def test_pick_hits_matches_task_locale_name():
    rows = tasks.parse_task_rows(_task_envelope())
    picked, total = search.pick_hits(
        rows, "首秀", ("name", "normalized_name", "id"), limit=10
    )
    assert total == 1
    assert picked[0]["id"] == "t1"


def test_boss_search_alias_matches_community_name():
    rows = search._boss_search_rows(
        [{"slug": "reshala", "name": "Reshala", "maps_label": "海关"}]
    )
    assert rows[0]["search_alias"] == "沙拉"
    picked, total = search.pick_hits(
        rows,
        "沙拉",
        ("name", "search_alias", "slug", "id", "maps_label"),
        limit=10,
    )
    assert total == 1
    assert picked[0]["slug"] == "reshala"


def test_search_site_blank_query_skips_db():
    out = search.search_site(None, "  ")  # type: ignore[arg-type]
    assert out["q"] == ""
    assert out["items"] == []
    assert out["task_count"] == 0
