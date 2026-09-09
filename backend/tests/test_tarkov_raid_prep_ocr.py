"""局前任务 OCR：裁切、行解析、闭集匹配。不打 RapidOCR。"""

from __future__ import annotations

import io

from PIL import Image

from app.services.ocr.types import NamedEngine
from app.services.tarkov.raid_prep_ocr import (
    compact_ocr_text,
    extract_task_name_from_ocr_line,
    is_likely_location_or_status_line,
    is_near_widescreen,
    is_preferred_size,
    list_crop_rect,
    load_image,
    match_raid_prep_tasks,
    merge_ocr_raw_texts,
    normalize_ocr_text,
    ocr_catalog_short_name,
    ocr_guess_part_info,
    ocr_hit_rank,
    parse_ocr_task_lines,
    recognize_image,
)


def _rgb(width: int, height: int, color: tuple[int, int, int] = (20, 20, 20)) -> Image.Image:
    return Image.new("RGB", (width, height), color)


class _FakeEngine:
    def __init__(self, lines: list[str]) -> None:
        self.lines = list(lines)
        self.calls = 0

    def recognize(self, image: Image.Image) -> list[str]:
        self.calls += 1
        _ = image
        return list(self.lines)


def test_normalize_ocr_text_strips_spaces_and_punct() -> None:
    assert normalize_ocr_text("  Debut — 初出茅庐 ") == "debut初出茅庐"
    assert normalize_ocr_text("全角：测试") == "全角测试"


def test_compact_ocr_text_aligns_part_naming() -> None:
    assert compact_ocr_text("医疗隐私-5") == "医疗隐私5"
    assert compact_ocr_text("医疗隐私 - Part 5") == "医疗隐私5"
    assert ocr_hit_rank("医疗隐私-5", "医疗隐私 - Part 5") == 0
    assert ocr_hit_rank("塔科夫神射手-3", "塔科夫神射手 - Part 3") == 0
    hits = match_raid_prep_tasks(
        ["塔科夫神射手-3"],
        [{"id": "4", "name": "塔科夫神射手 - Part 3"}],
    )
    assert len(hits) == 1


def test_extract_task_name_from_table_row() -> None:
    assert (
        extract_task_name_from_ocr_line(
            "加 。 消失的线人                                                 灯塔          进行中!              %%"
        )
        == "消失的线人"
    )
    assert (
        extract_task_name_from_ocr_line(
            "圆 。 钞人之路 - 管理者                      灯塔     进行中!       8%"
        )
        == "钞人之路 - 管理者"
    )


def test_parse_ocr_task_lines_drops_ui_noise() -> None:
    lines = parse_ocr_task_lines(
        "\n".join(["任务", "初出茅庐", "  补给  ", "进行中", "12%", "射击练习"])
    )
    assert lines == ["初出茅庐", "补给", "射击练习"]


def test_parse_realistic_table_output() -> None:
    raw = """加 。 消失的线人                                                 灯塔          进行中!              %%
加 网事                                                      海岸线         进行中!              2X%
轩 。 状良之针                                                                      任意地点            进行中!                    8%"""
    lines = parse_ocr_task_lines(raw)
    assert "消失的线人" in lines
    assert any("状良之针" in line for line in lines)


def test_layout_helpers() -> None:
    assert is_preferred_size(1920, 1080)
    assert is_preferred_size(2560, 1440)
    assert not is_preferred_size(1024, 576)
    assert is_near_widescreen(1024, 576)
    assert not is_near_widescreen(1920, 1200)
    a = list_crop_rect(1920, 1080)
    b = list_crop_rect(2560, 1440)
    assert abs(a[0] / 1920 - b[0] / 2560) < 0.01
    assert abs(a[2] / 1920 - b[2] / 2560) < 0.01


_CATALOG = [
    {"id": "1", "name": "初出茅庐", "normalized_name": "debut"},
    {"id": "2", "name": "射击练习", "normalized_name": "shooting-caleb"},
    {"id": "3", "name": "补给", "normalized_name": "shortage"},
    {"id": "4", "name": "补给短缺", "normalized_name": "shortage-2"},
    {"id": "5", "name": "消失的线人", "normalized_name": "missing-cinformant"},
    {"id": "6", "name": "善良之针", "normalized_name": "colleagues-part-3"},
    {"id": "7", "name": "医疗隐私 - Part 5", "normalized_name": "health-care-privacy-5"},
    {"id": "8", "name": "猎人之路 - 管理者", "normalized_name": "the-huntsman-path-administrator"},
]


def test_match_exact_chinese_names() -> None:
    assert [
        row.id
        for row in match_raid_prep_tasks(["初出茅庐", "射击练习"], _CATALOG)
    ] == ["1", "2"]


def test_match_table_rows_and_typos() -> None:
    hits = [
        row.name
        for row in match_raid_prep_tasks(
            [
                "加 。 消失的线人                                                 灯塔          进行中!",
                "轩 。 状良之针                                                 任意地点        进行中!",
                "圆 。 钞人之路 - 管理者                      灯塔     进行中!",
            ],
            _CATALOG,
        )
    ]
    assert "消失的线人" in hits
    assert "善良之针" in hits
    assert "猎人之路 - 管理者" in hits


def test_match_compact_part_numbering() -> None:
    hits = match_raid_prep_tasks(
        ["除   契。渤。 医疗隐私-5                                                     工厂"],
        _CATALOG,
    )
    assert [row.id for row in hits] == ["7"]


def test_match_unique_fuzzy_typo() -> None:
    hits = match_raid_prep_tasks(
        ["初出芽庐"],
        [{"id": "1", "name": "初出茅庐", "normalized_name": "debut"}],
    )
    assert [row.id for row in hits] == ["1"]


def test_match_ignores_unknown_lines() -> None:
    assert match_raid_prep_tasks(["不存在的任务"], _CATALOG) == []


def test_match_sample1_streets_single_column() -> None:
    catalog = [
        {"id": "1", "name": "高效秘诀"},
        {"id": "2", "name": "你被盯上了"},
        {"id": "3", "name": "奢靡人生"},
        {"id": "4", "name": "塔科夫神射手 - Part 3"},
        {"id": "5", "name": "人口普查"},
        {"id": "6", "name": "妥善保管"},
        {"id": "7", "name": "别开枪！"},
        {"id": "8", "name": "猎人之路 - 大动作"},
    ]
    sample = """高效秘决

你被盯上了

奢摩人生

塔科夫神射手-3

人口普查

轨养保管

别开枪!

猎人之路 - 大动作

浇科夫街区

进行中!

0%"""
    hits = [
        row.name
        for row in match_raid_prep_tasks(parse_ocr_task_lines(sample), catalog)
    ]
    for name in (
        "高效秘诀",
        "你被盯上了",
        "奢靡人生",
        "人口普查",
        "妥善保管",
        "别开枪！",
        "猎人之路 - 大动作",
        "塔科夫神射手 - Part 3",
    ):
        assert name in hits
    assert len(hits) >= 7


def test_match_sample2_mixed() -> None:
    catalog = [
        {"id": "1", "name": "此路不通"},
        {"id": "2", "name": "单程票"},
        {"id": "3", "name": "急诊室的故事"},
        {"id": "4", "name": "卫生标准 - Part 1"},
        {"id": "5", "name": "城市的解药"},
        {"id": "6", "name": "一般储备"},
        {"id": "7", "name": "直播 - Part 1"},
    ]
    sample = """此路不通

单程票

急诊室的故事

卫生标准

城市的解药

般储备

直播 -1

灯塔

进行中!"""
    hits = [
        row.name
        for row in match_raid_prep_tasks(parse_ocr_task_lines(sample), catalog)
    ]
    for name in ("此路不通", "单程票", "急诊室的故事", "城市的解药", "一般储备"):
        assert name in hits
    assert len(hits) >= 5


def test_filters_location_only_lines() -> None:
    assert is_likely_location_or_status_line("浇科夫街区")
    assert is_likely_location_or_status_line("进行中!")
    assert not is_likely_location_or_status_line("人口普查")


def test_shoreline_dual_pass_does_not_hit_balance_of_power() -> None:
    catalog = [
        {"id": "1", "name": "湿活 - Part 1", "normalized_name": "wet-job-part-1"},
        {"id": "2", "name": "邪教 - Part 1", "normalized_name": "the-cult-part-1"},
        {"id": "3", "name": "化学橱柜", "normalized_name": "pharmacist"},
        {"id": "4", "name": "恶意环伺", "normalized_name": "painkiller"},
        {"id": "5", "name": "引路先驱", "normalized_name": "guide"},
        {"id": "6", "name": "背景调查", "normalized_name": "background-check"},
        {
            "id": "9",
            "name": "平衡之力 - Part 1 (PVE)",
            "normalized_name": "balance-of-power-part-1-pve",
        },
    ]
    lines = merge_ocr_raw_texts(
        "得太\n\n宕教\n\n化学橱柜\n\n恶意环体",
        '各而"1\n\n宕教\n\n化学橱柜\n\n恶意环伺',
    )
    hits = [row.id for row in match_raid_prep_tasks(lines, catalog)]
    assert "各而 - 1" in lines
    assert "化学橱柜" in lines
    assert {"1", "2", "3", "4"}.issubset(set(hits))
    assert "9" not in hits
    assert len(hits) >= 4


def test_preserves_part_suffix_from_quotes() -> None:
    assert extract_task_name_from_ocr_line('各而"1') == "各而 - 1"
    assert ocr_guess_part_info("各而 - 1") == ("各而", "1")


def test_rejects_suffix_only_part_matches() -> None:
    catalog = [
        {"id": "1", "name": "湿活 - Part 1"},
        {"id": "9", "name": "平衡之力 - Part 1 (PVE)"},
    ]
    assert [row.id for row in match_raid_prep_tasks(["之力1"], catalog)] == []
    assert [row.id for row in match_raid_prep_tasks(["平稀之力1"], catalog)] == ["9"]
    assert [row.id for row in match_raid_prep_tasks(["湿1"], catalog)] == ["1"]
    assert [row.id for row in match_raid_prep_tasks(["湿活1"], catalog)] == ["1"]


def test_short_catalog_names_against_typos() -> None:
    assert ocr_catalog_short_name("邪教 - Part 1") == "邪教"
    assert [
        row.id
        for row in match_raid_prep_tasks(
            ["宕教"], [{"id": "2", "name": "邪教 - Part 1"}]
        )
    ] == ["2"]


def test_lighthouse_hermit_dual_pass() -> None:
    assert extract_task_name_from_ocr_line("国 酌 士 灯塔") == "酌 士"
    catalog = [
        {"id": "1", "name": "消失的线人"},
        {"id": "2", "name": "猎人之路 - 管理者"},
        {"id": "3", "name": "隐士"},
    ]
    lines = merge_ocr_raw_texts(
        "回 。 消失 的 线 人 灯塔\n贺 。 菏 人 之 路 - 管理 者 灯塔\n贺 | 肌 十 灯塔",
        "辆 。 消失 的 线 人 灯塔\n贺 。 落 人 之 路 - 管理 者 灯塔\n国 酌 士 灯塔",
    )
    hits = [row.name for row in match_raid_prep_tasks(lines, catalog)]
    assert "消失的线人" in hits
    assert "猎人之路 - 管理者" in hits
    assert "隐士" in hits


def test_recognize_skips_ocr_when_not_widescreen() -> None:
    engine = _FakeEngine(["初出茅庐"])
    result = recognize_image(
        _rgb(640, 480),
        [{"id": "1", "name": "初出茅庐"}],
        recognizers=[NamedEngine(name="paddle", engine=engine)],
    )
    assert result["widescreen"] is False
    assert result["matches"] == []
    assert engine.calls == 0


def test_recognize_crops_and_matches_with_fake_engine() -> None:
    engine = _FakeEngine(["初出茅庐", "射击练习"])
    result = recognize_image(
        _rgb(1920, 1080),
        [
            {"id": "1", "name": "初出茅庐"},
            {"id": "2", "name": "射击练习"},
        ],
        recognizers=[NamedEngine(name="paddle", engine=engine)],
    )
    assert result["widescreen"] is True
    assert result["preferred_size"] is True
    assert result["engines"] == ["paddle"]
    assert [row["id"] for row in result["matches"]] == ["1", "2"]
    assert engine.calls == 2  # 正图 + 反色


def test_load_image_rejects_empty() -> None:
    from app.services.tarkov.raid_prep_ocr import TarkovRaidPrepOcrError

    try:
        load_image(b"")
        raise AssertionError("expected error")
    except TarkovRaidPrepOcrError as exc:
        assert "粘贴" in exc.message


def test_openapi_has_raid_prep_recognize() -> None:
    from app.main import app

    schema = app.openapi()
    path = (schema.get("paths") or {}).get("/api/guides/tarkov/raid-prep/recognize") or {}
    assert path.get("post") is not None
    components = (schema.get("components") or {}).get("schemas") or {}
    assert "TarkovRaidPrepOcrOut" in components
