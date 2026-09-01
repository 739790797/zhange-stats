"""管理员全站地图地名：点 / 框，按互动图 normalizedName 共用。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovMapPlace
from app.services.tarkov.maps import VARIANT_PARENT, resolve_map_slug

PLACE_KINDS = ("point", "box")
NAME_MAX = 64
FLOOR_MAX = 64
SIZE_DEFAULT = 80
SIZE_MIN = 20
SIZE_MAX = 200
COORD_ABS_MAX = 10_000
BOX_MIN_SPAN = 0.5
IMPORT_MAX = 200
MAP_KEY_MAX = 64

# 与 frontend/src/lib/tarkovMapPlaceLabels.ts 海岸线社区表对齐，迁移种入。
SHORELINE_SEED: list[dict[str, Any]] = [
    {"name": "疗养院", "x": -258.2, "z": -71.2, "size": 100},
    {"name": "行政楼", "x": -252, "z": -146},
    {"name": "西楼", "x": -171, "z": -83},
    {"name": "东楼", "x": -329, "z": -83},
    {"name": "停车场", "x": -85, "z": -32},
    {"name": "假别墅", "x": 162, "z": 86},
    {"name": "真别墅", "x": 96, "z": 108},
    {"name": "蓝铁皮", "x": 52, "z": 134},
    {"name": "红白电塔", "x": -708.9, "z": 93.91},
    {"name": "雷达站", "x": -496, "z": 257},
    {"name": "变电站", "x": -215.8, "z": 178.4},
    {"name": "加油站", "x": -189.3, "z": 420},
    {"name": "沼泽", "x": 326, "z": -118.5},
    {"name": "村落", "x": 418.4, "z": 118},
    {"name": "小屋", "x": 288, "z": 144},
    {"name": "坦克桥", "x": -355, "z": 188},
    {"name": "码头", "x": -338.6, "z": 525},
    {"name": "灯塔", "x": 216, "z": 424},
    {"name": "公交站", "x": -96, "z": -6},
    {"name": "地堡", "x": -153, "z": -290},
    {"name": "吊车", "x": -625, "z": 484},
    {"name": "农场", "x": -622, "z": -202},
]


class TarkovMapPlacesError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def place_map_key(slug: str) -> str:
    key = resolve_map_slug(slug)
    if not key or len(key) > MAP_KEY_MAX:
        raise TarkovMapPlacesError("地图 slug 无效")
    return VARIANT_PARENT.get(key, key)


def _as_float(raw: Any, label: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise TarkovMapPlacesError(f"{label} 无效") from exc
    if abs(value) > COORD_ABS_MAX:
        raise TarkovMapPlacesError(f"{label} 超出范围")
    return value


def _as_optional_float(raw: Any, label: str) -> float | None:
    if raw is None or raw == "":
        return None
    return _as_float(raw, label)


def _normalize_name(raw: Any) -> str:
    lines = [
        part.strip()
        for part in str(raw or "").replace("\r\n", "\n").split("\n")
    ]
    name = "\n".join(part for part in lines if part)
    if not name:
        raise TarkovMapPlacesError("地点名称不能为空")
    if len(name) > NAME_MAX:
        raise TarkovMapPlacesError(f"地点名称最多 {NAME_MAX} 字")
    return name


def _normalize_kind(raw: Any) -> str:
    kind = str(raw or "point").strip().lower()
    if kind not in PLACE_KINDS:
        raise TarkovMapPlacesError("地点类型须为 point 或 box")
    return kind


def _normalize_floor(raw: Any) -> str:
    floor = str(raw or "").strip()
    if len(floor) > FLOOR_MAX:
        raise TarkovMapPlacesError("高度层名称过长")
    return floor


def _normalize_size(raw: Any) -> int:
    if raw is None or raw == "":
        return SIZE_DEFAULT
    try:
        size = int(raw)
    except (TypeError, ValueError) as exc:
        raise TarkovMapPlacesError("字号无效") from exc
    if size < SIZE_MIN or size > SIZE_MAX:
        raise TarkovMapPlacesError(f"字号须在 {SIZE_MIN}–{SIZE_MAX}")
    return size


def _geometry(
    kind: str,
    x: float,
    z: float,
    x2: float | None,
    z2: float | None,
) -> tuple[float, float, float | None, float | None]:
    if kind == "point":
        return x, z, None, None
    if x2 is None or z2 is None:
        raise TarkovMapPlacesError("框选须给出对角坐标")
    if abs(x2 - x) < BOX_MIN_SPAN or abs(z2 - z) < BOX_MIN_SPAN:
        raise TarkovMapPlacesError("框选区域过小")
    return x, z, x2, z2


def _label_xy(
    kind: str,
    raw: dict[str, Any],
) -> tuple[float | None, float | None]:
    if kind == "point":
        return None, None
    label_x = _as_optional_float(raw.get("label_x"), "label_x")
    label_z = _as_optional_float(raw.get("label_z"), "label_z")
    if (label_x is None) != (label_z is None):
        raise TarkovMapPlacesError("标注坐标须成对")
    return label_x, label_z


def _row_out(row: TarkovMapPlace) -> dict[str, Any]:
    return {
        "id": row.id,
        "map_key": row.map_key,
        "kind": row.kind,
        "name": row.name,
        "x": row.x,
        "z": row.z,
        "x2": row.x2,
        "z2": row.z2,
        "label_x": row.label_x,
        "label_z": row.label_z,
        "size": row.size,
        "floor": row.floor,
        "sort_order": row.sort_order,
    }


def _parse_item(raw: dict[str, Any]) -> dict[str, Any]:
    kind = _normalize_kind(raw.get("kind"))
    x, z, x2, z2 = _geometry(
        kind,
        _as_float(raw.get("x"), "x"),
        _as_float(raw.get("z"), "z"),
        _as_optional_float(raw.get("x2"), "x2"),
        _as_optional_float(raw.get("z2"), "z2"),
    )
    label_x, label_z = _label_xy(kind, raw)
    return {
        "kind": kind,
        "name": _normalize_name(raw.get("name")),
        "x": x,
        "z": z,
        "x2": x2,
        "z2": z2,
        "label_x": label_x,
        "label_z": label_z,
        "size": _normalize_size(raw.get("size")),
        "floor": _normalize_floor(raw.get("floor")),
    }


def _next_sort(db: Session, map_key: str) -> int:
    current = (
        db.query(func.max(TarkovMapPlace.sort_order))
        .filter(TarkovMapPlace.map_key == map_key)
        .scalar()
    )
    return int(current or 0) + 1


def list_places(db: Session, slug: str) -> list[dict[str, Any]]:
    key = place_map_key(slug)
    rows = (
        db.query(TarkovMapPlace)
        .filter(TarkovMapPlace.map_key == key)
        .order_by(TarkovMapPlace.sort_order.asc(), TarkovMapPlace.id.asc())
        .all()
    )
    return [_row_out(row) for row in rows]


def _get_owned(db: Session, slug: str, place_id: int) -> TarkovMapPlace:
    key = place_map_key(slug)
    row = db.get(TarkovMapPlace, place_id)
    if row is None or row.map_key != key:
        raise TarkovMapPlacesError("未找到地点", 404)
    return row


def create_place(db: Session, slug: str, raw: dict[str, Any]) -> dict[str, Any]:
    key = place_map_key(slug)
    item = _parse_item(raw)
    now = now_naive()
    row = TarkovMapPlace(
        map_key=key,
        sort_order=_next_sort(db, key),
        created_at=now,
        updated_at=now,
        **item,
    )
    db.add(row)
    db.flush()
    return _row_out(row)


def update_place(
    db: Session,
    slug: str,
    place_id: int,
    raw: dict[str, Any],
) -> dict[str, Any]:
    row = _get_owned(db, slug, place_id)
    merged = {
        "kind": raw["kind"] if "kind" in raw else row.kind,
        "name": raw["name"] if "name" in raw else row.name,
        "x": raw["x"] if "x" in raw else row.x,
        "z": raw["z"] if "z" in raw else row.z,
        "x2": raw["x2"] if "x2" in raw else row.x2,
        "z2": raw["z2"] if "z2" in raw else row.z2,
        "label_x": raw["label_x"] if "label_x" in raw else row.label_x,
        "label_z": raw["label_z"] if "label_z" in raw else row.label_z,
        "size": raw["size"] if "size" in raw else row.size,
        "floor": raw["floor"] if "floor" in raw else row.floor,
    }
    item = _parse_item(merged)
    row.kind = item["kind"]
    row.name = item["name"]
    row.x = item["x"]
    row.z = item["z"]
    row.x2 = item["x2"]
    row.z2 = item["z2"]
    row.label_x = item["label_x"]
    row.label_z = item["label_z"]
    row.size = item["size"]
    row.floor = item["floor"]
    row.updated_at = now_naive()
    db.flush()
    return _row_out(row)


def delete_place(db: Session, slug: str, place_id: int) -> None:
    row = _get_owned(db, slug, place_id)
    db.delete(row)
    db.flush()


def import_places(
    db: Session,
    slug: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    key = place_map_key(slug)
    existing = (
        db.query(TarkovMapPlace.id)
        .filter(TarkovMapPlace.map_key == key)
        .first()
    )
    if existing is not None:
        raise TarkovMapPlacesError("此地已有自定义地名", 409)
    if len(items) > IMPORT_MAX:
        raise TarkovMapPlacesError(f"一次最多接管 {IMPORT_MAX} 个地点")
    parsed = [_parse_item(item) for item in items]
    if not parsed:
        raise TarkovMapPlacesError("没有可接管的地点")
    now = now_naive()
    for index, item in enumerate(parsed, start=1):
        db.add(
            TarkovMapPlace(
                map_key=key,
                sort_order=index,
                created_at=now,
                updated_at=now,
                **item,
            )
        )
    db.flush()
    return list_places(db, slug)
