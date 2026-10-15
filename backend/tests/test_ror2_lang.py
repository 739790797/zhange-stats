"""官方 zh-CN 目录：只收这个文件夹，并按 wiki 令牌核对覆盖。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.guide_raw import GuideRaw
from app.services.ror2.catalog import Ror2WikiError
from app.services.ror2.lang import (
    Ror2LangError,
    coverage_report,
    ensure_lang_dir,
    lang_file_sort_key,
    string_table,
    sync_lang,
)
from app.services.ror2.schemas import Ror2CatalogOut, Ror2ItemOut, Ror2SurvivorOut


def _strings(names: dict[str, str]) -> str:
    return json.dumps({"strings": names}, ensure_ascii=False)


def _write_lang(root: Path, output: dict[str, str], extra: dict[str, str] | None = None) -> Path:
    folder = root / "zh-CN"
    folder.mkdir()
    (folder / "language.json").write_text('{"language": "zh-CN"}', encoding="utf-8")
    (folder / "output.json").write_text(_strings(output), encoding="utf-8")
    if extra is not None:
        (folder / "DLC4.json").write_text(_strings(extra), encoding="utf-8")
    return folder


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


def test_sync_follows_folder_as_it_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "zh-CN"
    folder.mkdir()
    (folder / "language.json").write_text('{"language": "zh-CN"}', encoding="utf-8")
    (folder / "DLC1.json").write_text(_strings({"ITEM_SYRINGE_NAME": "旧名"}), encoding="utf-8")
    (folder / "DLC3.json").write_text(_strings({"ITEM_SYRINGE_DESC": "旧说明"}), encoding="utf-8")
    (folder / "Items.json").write_text(_strings({"ITEM_SYRINGE_PICKUP": "拾取"}), encoding="utf-8")
    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    db: Session = sessionmaker(bind=engine)()
    monkeypatch.setattr("app.services.ror2.wiki.PIPELINE.missing", lambda _db: False)
    monkeypatch.setattr("app.services.ror2.wiki.get_catalog", lambda _db: _catalog())

    first = sync_lang(db, folder)
    assert "读取 Items.json、DLC1.json、DLC3.json" in first
    assert sorted(row.resource for row in db.query(GuideRaw).all()) == [
        "zh-CN/DLC1.json",
        "zh-CN/DLC3.json",
        "zh-CN/Items.json",
    ]

    for path in folder.glob("*.json"):
        if path.name != "language.json":
            path.unlink()
    (folder / "output.json").write_text(
        _strings({"ITEM_SYRINGE_NAME": "士兵的注射器", "ITEM_SYRINGE_DESC": "提高攻击速度。"}),
        encoding="utf-8",
    )
    (folder / "DLC4.json").write_text(
        _strings({"ITEM_SYRINGE_NAME": "新注射器"}),
        encoding="utf-8",
    )
    second = sync_lang(db, folder)
    assert "读取 output.json、DLC4.json" in second
    assert "已去掉：" in second
    assert sorted(row.resource for row in db.query(GuideRaw).all()) == [
        "zh-CN/DLC4.json",
        "zh-CN/output.json",
    ]
    db.close()


def test_lang_dir_must_be_zh_cn(tmp_path: Path) -> None:
    folder = tmp_path / "en"
    folder.mkdir()
    (folder / "output.json").write_text("{}", encoding="utf-8")
    with pytest.raises(Ror2LangError, match="zh-CN"):
        ensure_lang_dir(folder)


def test_coverage_counts_name_desc_and_pickup() -> None:
    strings = {
        "ITEM_SYRINGE_NAME": "士兵的注射器",
        "ITEM_SYRINGE_DESC": "提高攻击速度。",
        "EQUIPMENT_SCANNER_NAME": "雷达扫描器",
    }
    report = coverage_report(_catalog(), strings)
    assert "items 有令牌 1/2，NAME 1/1，DESC 1/1，PICKUP 0/1" in report
    assert "wiki 无令牌：BurnNearby" in report
    assert "equipment 有令牌 1/1，NAME 1/1，DESC 0/1，PICKUP 0/1" in report
    assert "缺 NAME：EQUIPMENT_SCANNER" not in report
    assert "DESC 0/1" in report
    assert "survivors 1，wiki 模块没有 LocalizationInternalName" in report


def test_sync_lang_stores_files_and_reports_gaps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _write_lang(
        tmp_path,
        {"ITEM_SYRINGE_NAME": "士兵的注射器", "ITEM_SYRINGE_DESC": "提高攻击速度。"},
        {"EQUIPMENT_SCANNER_NAME": "雷达扫描器", "EQUIPMENT_SCANNER_DESC": "显示交互物。"},
    )
    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    db: Session = sessionmaker(bind=engine)()
    monkeypatch.setattr(
        "app.services.ror2.wiki.PIPELINE.missing",
        lambda _db: False,
    )
    monkeypatch.setattr(
        "app.services.ror2.wiki.get_catalog",
        lambda _db: _catalog(),
    )
    report = sync_lang(db, folder)
    names = sorted(row.resource for row in db.query(GuideRaw).all())
    assert names == ["zh-CN/DLC4.json", "zh-CN/output.json"]
    assert "NAME 1/1，DESC 1/1，PICKUP 0/1" in report
    assert "EQUIPMENT_SCANNER" not in report.split("缺 NAME")[-1] if "缺 NAME" in report else True
    db.close()


def test_sync_lang_refuses_wiki_gap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _write_lang(tmp_path, {"ITEM_SYRINGE_NAME": "士兵的注射器"})
    engine = create_engine("sqlite://")
    GuideRaw.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr("app.services.ror2.wiki.PIPELINE.missing", lambda _db: True)
    with pytest.raises(Ror2WikiError, match="还没有落库"):
        sync_lang(db, folder)
    db.close()
