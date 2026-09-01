"""地图自定义地名：slug 归并、点/框校验、CRUD / 接管。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.services.tarkov import places as svc


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_place_map_key_folds_variants() -> None:
    assert svc.place_map_key("night-factory") == "factory"
    assert svc.place_map_key("factory-night") == "factory"
    assert svc.place_map_key("the-lab-dark") == "the-lab"
    assert svc.place_map_key("ground-zero-21") == "ground-zero"
    assert svc.place_map_key("streets") == "streets-of-tarkov"
    assert svc.place_map_key("customs") == "customs"
    with pytest.raises(svc.TarkovMapPlacesError):
        svc.place_map_key("   ")


def test_create_point_and_list_shares_parent() -> None:
    db = _session()
    row = svc.create_place(
        db,
        "factory-night",
        {"kind": "point", "name": "泵房", "x": 10, "z": -4},
    )
    assert row["map_key"] == "factory"
    assert row["kind"] == "point"
    assert row["x2"] is None
    items = svc.list_places(db, "night-factory")
    assert [item["name"] for item in items] == ["泵房"]


def test_box_requires_corners_and_span() -> None:
    db = _session()
    with pytest.raises(svc.TarkovMapPlacesError, match="对角"):
        svc.create_place(
            db,
            "customs",
            {"kind": "box", "name": "宿舍", "x": 1, "z": 1},
        )
    with pytest.raises(svc.TarkovMapPlacesError, match="过小"):
        svc.create_place(
            db,
            "customs",
            {"kind": "box", "name": "宿舍", "x": 1, "z": 1, "x2": 1.1, "z2": 2},
        )
    row = svc.create_place(
        db,
        "customs",
        {"kind": "box", "name": "宿舍", "x": 1, "z": 1, "x2": 8, "z2": 6},
    )
    assert row["kind"] == "box"
    assert row["x2"] == 8
    assert row["z2"] == 6
    assert row["label_x"] is None
    assert row["label_z"] is None
    moved = svc.update_place(
        db,
        "customs",
        row["id"],
        {"label_x": 3.5, "label_z": 2},
    )
    assert moved["x"] == 1
    assert moved["z"] == 1
    assert moved["x2"] == 8
    assert moved["z2"] == 6
    assert moved["label_x"] == 3.5
    assert moved["label_z"] == 2


def test_point_drops_label_and_box_needs_pair() -> None:
    db = _session()
    point = svc.create_place(
        db,
        "woods",
        {"kind": "point", "name": "锯木厂", "x": 1, "z": 2, "label_x": 9, "label_z": 8},
    )
    assert point["label_x"] is None
    assert point["label_z"] is None
    box = svc.create_place(
        db,
        "woods",
        {"kind": "box", "name": "营区", "x": 0, "z": 0, "x2": 4, "z2": 4},
    )
    with pytest.raises(svc.TarkovMapPlacesError, match="成对"):
        svc.update_place(db, "woods", box["id"], {"label_x": 1})


def test_update_move_and_delete() -> None:
    db = _session()
    row = svc.create_place(
        db, "woods", {"kind": "point", "name": "锯木厂", "x": 0, "z": 0}
    )
    moved = svc.update_place(
        db, "woods", row["id"], {"x": 12.5, "z": -3}
    )
    assert moved["name"] == "锯木厂"
    assert moved["x"] == 12.5
    assert moved["z"] == -3
    svc.delete_place(db, "woods", row["id"])
    assert svc.list_places(db, "woods") == []
    with pytest.raises(svc.TarkovMapPlacesError) as exc:
        svc.delete_place(db, "woods", row["id"])
    assert exc.value.status_code == 404


def test_import_once_and_reject_second() -> None:
    db = _session()
    items = svc.import_places(
        db,
        "customs",
        [
            {"kind": "point", "name": "大红房", "x": 1, "z": 2, "size": 90},
            {"kind": "point", "name": "宿舍", "x": 3, "z": 4},
        ],
    )
    assert [row["name"] for row in items] == ["大红房", "宿舍"]
    assert items[0]["size"] == 90
    with pytest.raises(svc.TarkovMapPlacesError) as exc:
        svc.import_places(
            db, "customs", [{"kind": "point", "name": "再来", "x": 0, "z": 0}]
        )
    assert exc.value.status_code == 409


def test_name_keeps_centered_lines() -> None:
    db = _session()
    row = svc.create_place(
        db,
        "woods",
        {"kind": "point", "name": "  锯木厂  \n\n  北营  ", "x": 1, "z": 1},
    )
    assert row["name"] == "锯木厂\n北营"


def test_reject_blank_name_and_bad_kind() -> None:
    db = _session()
    with pytest.raises(svc.TarkovMapPlacesError, match="名称"):
        svc.create_place(db, "woods", {"kind": "point", "name": "  ", "x": 1, "z": 1})
    with pytest.raises(svc.TarkovMapPlacesError, match="类型"):
        svc.create_place(db, "woods", {"kind": "tile", "name": "瓦", "x": 1, "z": 1})


def test_shoreline_seed_matches_community_overlay() -> None:
    names = [row["name"] for row in svc.SHORELINE_SEED]
    assert "疗养院" in names
    assert "真别墅" in names
    assert "假别墅" in names
    assert "蓝铁皮" in names
    assert len(names) == len(set(names))
    assert len(svc.SHORELINE_SEED) == 22


def test_streets_seed_matches_dev_overlay() -> None:
    names = [row["name"] for row in svc.STREETS_OF_TARKOV_SEED]
    assert "红衣主教公寓" in names
    assert "Klimov Mall 交易中心" in names
    assert any("滨海大道" in name for name in names)
    assert any("大康科迪亚" in name for name in names)
    assert len(svc.STREETS_OF_TARKOV_SEED) == 47
    rows = svc.place_seed_rows("streets-of-tarkov", svc.STREETS_OF_TARKOV_SEED, now=None)
    assert rows[0]["map_key"] == "streets-of-tarkov"
    assert rows[0]["sort_order"] == 1
    assert rows[-1]["sort_order"] == 47
