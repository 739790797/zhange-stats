"""逃离塔科夫枪械：上游 raw 落库 → parse 派生读模型。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovGun, TarkovGunMeta, TarkovGunRaw
from app.services.tarkov_ammo import (
    SOURCE_GRAPHQL,
    SOURCE_JSON_API,
    TARKOV_GRAPHQL_URL,
    TARKOV_JSON_ITEMS_LOCALE_URL,
    TARKOV_JSON_ITEMS_URL,
    TarkovAmmoError,
    _http_request,
    normalize_caliber,
)

logger = logging.getLogger(__name__)

META_ROW_ID = 1
RAW_ROW_ID = 1
GUN_JOB_KEY = "tarkov_gun_sync"
DOWNLOAD_TIMEOUT = 120

# BSG itemCategories.normalizedName under weapon
_WEAPON_CLASS_IDS: dict[str, str] = {
    "5447b5f14bdc2d61278b4567": "assault-rifle",
    "5447b5cf4bdc2d65278b4567": "handgun",
    "5447b6094bdc2dc3278b4567": "shotgun",
    "5447b6254bdc2dc3278b4568": "sniper-rifle",
    "5447b5fc4bdc2d87278b4567": "assault-carbine",
    "5447b6194bdc2d67278b4567": "marksman-rifle",
    "5447b5e04bdc2d62278b4567": "smg",
    "5447bed64bdc2d97278b4568": "machinegun",
    "5447bedf4bdc2d87278b4568": "grenade-launcher",
    "617f1ef5e8b54b0998387733": "revolver",
    "67446d4f04141c10630604e7": "rocket-launcher",
}

_GUN_QUERY = """
query GunSync($lang: LanguageCode) {
  items(types: [gun], lang: $lang) {
    id
    name
    shortName
    iconLink
    baseImageLink
    types
    categories {
      id
      normalizedName
    }
    properties {
      __typename
      ... on ItemPropertiesWeapon {
        caliber
        fireRate
        ergonomics
        recoilVertical
        recoilHorizontal
        effectiveDistance
        fireModes
        defaultAmmo { id }
        allowedAmmo { id }
      }
    }
  }
}
""".strip()


class TarkovGunError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class GunUpstreamBundle:
    source: str
    payload: dict[str, Any]
    note: str


def _item_id_list(raw: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if isinstance(entry, str) and entry.strip():
            out.append(entry.strip()[:64])
        elif isinstance(entry, dict):
            iid = str(entry.get("id") or "").strip()
            if iid:
                out.append(iid[:64])
    return out


def _weapon_class_from_categories(
    categories: Any,
    *,
    category_index: dict[str, str] | None = None,
) -> str:
    """只取上游 categories 中已知武器大类；没有就不填。"""
    if not isinstance(categories, list):
        return ""
    for entry in categories:
        if isinstance(entry, str):
            mapped = _WEAPON_CLASS_IDS.get(entry)
            if mapped:
                return mapped
            if category_index and entry in category_index:
                norm = category_index[entry]
                if norm in _WEAPON_CLASS_IDS.values():
                    return norm
            continue
        if not isinstance(entry, dict):
            continue
        cid = str(entry.get("id") or "").strip()
        if cid in _WEAPON_CLASS_IDS:
            return _WEAPON_CLASS_IDS[cid]
        norm = str(entry.get("normalizedName") or "").strip()
        if norm in _WEAPON_CLASS_IDS.values():
            return norm
    return ""


def _is_special_slot_gun(raw: dict[str, Any]) -> bool:
    """上游 types 含 specialSlot：特殊栏道具（信号弹等），不进枪械读模型。"""
    types = raw.get("types") or []
    return isinstance(types, list) and "specialSlot" in types


def _row_from_weapon_item(
    raw: dict[str, Any],
    *,
    locale: dict[str, Any] | None = None,
    category_index: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    types = raw.get("types") or []
    if isinstance(types, list) and "preset" in types:
        return None
    if _is_special_slot_gun(raw):
        return None
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    typename = str(props.get("__typename") or props.get("propertiesType") or "")
    if typename and typename != "ItemPropertiesWeapon":
        return None
    # json dump: weapons always have caliber on props
    if not props and not raw.get("id"):
        return None
    item_id = str(raw.get("id") or "").strip()
    if not item_id:
        return None
    locale = locale or {}
    name = str(
        locale.get(f"{item_id} Name")
        or raw.get("name")
        or locale.get(f"{item_id} ShortName")
        or raw.get("shortName")
        or ""
    ).strip()
    short_name = str(
        locale.get(f"{item_id} ShortName") or raw.get("shortName") or ""
    ).strip()
    # json.tarkov.dev 无 locale 时 name 常为 "<id> Name" 占位，不可当真名
    if name.endswith(" Name") and item_id in name:
        name = short_name
    if short_name.endswith(" ShortName") and item_id in short_name:
        short_name = ""
    if not name:
        name = short_name or item_id

    default_ammo = props.get("defaultAmmo")
    if isinstance(default_ammo, dict):
        default_ammo_id = str(default_ammo.get("id") or "").strip()
    else:
        default_ammo_id = str(default_ammo or "").strip()

    fire_modes = props.get("fireModes") if isinstance(props.get("fireModes"), list) else []
    fire_modes = [str(m) for m in fire_modes if m is not None]

    return {
        "item_id": item_id[:64],
        "name": name[:128],
        "short_name": short_name[:64],
        "caliber": normalize_caliber(
            None if props.get("caliber") is None else str(props.get("caliber") or "")
        )[:64],
        "weapon_class": _weapon_class_from_categories(
            raw.get("categories"),
            category_index=category_index,
        )[:64],
        "fire_rate": _as_int(props.get("fireRate")),
        "ergonomics": _as_float(props.get("ergonomics")),
        "recoil_vertical": _as_int(props.get("recoilVertical")),
        "recoil_horizontal": _as_int(props.get("recoilHorizontal")),
        "effective_distance": _as_int(props.get("effectiveDistance")),
        "fire_modes": fire_modes,
        "default_ammo_id": default_ammo_id[:64],
        "allowed_ammo_ids": _item_id_list(props.get("allowedAmmo")),
        "icon_link": str(
            raw.get("baseImageLink") or raw.get("iconLink") or ""
        )[:512],
    }


def _as_int(value: Any) -> int:
    """仅在上游给了可解析数值时写入；缺失保持 0（列非空约束），不臆造其它值。"""
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_graphql_guns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    errors = payload.get("errors")
    if errors:
        raise TarkovGunError(f"tarkov.dev GraphQL 错误: {errors}")
    data = payload.get("data") or {}
    rows_raw = data.get("items")
    if not isinstance(rows_raw, list):
        raise TarkovGunError("tarkov.dev guns 响应无效")
    rows: list[dict[str, Any]] = []
    for raw in rows_raw:
        if not isinstance(raw, dict):
            continue
        props = raw.get("properties")
        if not isinstance(props, dict):
            continue
        if props.get("__typename") not in (None, "ItemPropertiesWeapon"):
            # some guns may omit typename in odd payloads; require weapon fields
            if props.get("caliber") is None and props.get("fireRate") is None:
                continue
        row = _row_from_weapon_item(raw)
        if row:
            rows.append(row)
    return rows


def parse_json_api_guns(
    payload: dict[str, Any],
    *,
    locale: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        raise TarkovGunError("json.tarkov.dev items 响应无效")
    items_raw = data.get("items")
    if isinstance(items_raw, dict):
        items_iter = items_raw.values()
    elif isinstance(items_raw, list):
        items_iter = items_raw
    else:
        raise TarkovGunError("json.tarkov.dev items 缺少 items 字段")

    category_index: dict[str, str] = {}
    cats = data.get("itemCategories")
    if isinstance(cats, dict):
        for cid, meta in cats.items():
            if not isinstance(meta, dict):
                continue
            norm = str(meta.get("normalizedName") or "").strip()
            if norm:
                category_index[str(cid)] = norm

    rows: list[dict[str, Any]] = []
    for raw in items_iter:
        if not isinstance(raw, dict):
            continue
        types = raw.get("types") or []
        if not isinstance(types, list) or "gun" not in types:
            continue
        props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
        if props.get("propertiesType") != "ItemPropertiesWeapon":
            continue
        row = _row_from_weapon_item(
            raw, locale=locale, category_index=category_index
        )
        if row:
            rows.append(row)
    return rows


def parse_gun_raw(source: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    src = (source or "").strip()
    if src == SOURCE_GRAPHQL:
        return parse_graphql_guns(payload)
    if src == SOURCE_JSON_API:
        items_payload = payload.get("items")
        if not isinstance(items_payload, dict):
            raise TarkovGunError("json.tarkov.dev raw 缺少 items")
        locale = payload.get("locale")
        if locale is not None and not isinstance(locale, dict):
            locale = None
        return parse_json_api_guns(items_payload, locale=locale)
    raise TarkovGunError(f"未知枪械 raw 来源: {src or '—'}")


def download_graphql_guns(*, lang: str = "zh") -> GunUpstreamBundle:
    attempts: list[dict[str, Any] | None] = [{"lang": lang}, None]
    last_error: TarkovGunError | None = None
    for variables in attempts:
        body_obj: dict[str, Any] = {"query": _GUN_QUERY}
        if variables is not None:
            body_obj["variables"] = variables
        else:
            body_obj["query"] = _GUN_QUERY.replace(
                "query GunSync($lang: LanguageCode) {\n  items(types: [gun], lang: $lang) {",
                "query GunSync {\n  items(types: [gun]) {",
            )
        body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
        try:
            raw = _http_request(
                TARKOV_GRAPHQL_URL,
                method="POST",
                body=body,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=DOWNLOAD_TIMEOUT,
            )
            payload = json.loads(raw.decode("utf-8"))
        except TarkovAmmoError as exc:
            last_error = TarkovGunError(str(exc))
            continue
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = TarkovGunError("tarkov.dev 枪械响应解析失败")
            last_error.__cause__ = exc
            continue
        if not isinstance(payload, dict):
            last_error = TarkovGunError("tarkov.dev 枪械响应格式无效")
            continue
        try:
            rows = parse_graphql_guns(payload)
        except TarkovGunError as exc:
            last_error = exc
            continue
        if not rows:
            last_error = TarkovGunError("tarkov.dev guns 为空")
            continue
        return GunUpstreamBundle(
            source=SOURCE_GRAPHQL,
            payload=payload,
            note="api.tarkov.dev GraphQL items(type:gun)",
        )
    if last_error:
        raise last_error
    raise TarkovGunError("tarkov.dev guns 拉取失败")


def download_json_api_guns(*, lang: str = "zh") -> GunUpstreamBundle:
    try:
        raw = _http_request(TARKOV_JSON_ITEMS_URL, timeout=180)
    except TarkovAmmoError as exc:
        raise TarkovGunError(str(exc)) from exc
    try:
        items_payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovGunError("json.tarkov.dev items 解析失败") from exc
    if not isinstance(items_payload, dict):
        raise TarkovGunError("json.tarkov.dev items 格式无效")

    locale: dict[str, Any] | None = None
    try:
        loc_raw = _http_request(
            TARKOV_JSON_ITEMS_LOCALE_URL.format(lang=lang),
            timeout=60,
        )
        loc_payload = json.loads(loc_raw.decode("utf-8"))
        if isinstance(loc_payload, dict) and isinstance(loc_payload.get("data"), dict):
            locale = loc_payload["data"]
    except TarkovAmmoError:
        logger.warning("json.tarkov.dev items_%s locale unavailable", lang)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("json.tarkov.dev items_%s locale parse failed", lang)

    envelope: dict[str, Any] = {"items": items_payload, "locale": locale}
    rows = parse_gun_raw(SOURCE_JSON_API, envelope)
    if not rows:
        raise TarkovGunError("json.tarkov.dev 未解析到枪械")
    return GunUpstreamBundle(
        source=SOURCE_JSON_API,
        payload=envelope,
        note="json.tarkov.dev/regular/items (guns)",
    )


def gun_count(db: Session) -> int:
    return db.query(TarkovGun).count()


def get_gun_meta(db: Session) -> TarkovGunMeta | None:
    return (
        db.query(TarkovGunMeta)
        .filter(TarkovGunMeta.id == META_ROW_ID)
        .one_or_none()
    )


def get_gun_raw(db: Session) -> TarkovGunRaw | None:
    return (
        db.query(TarkovGunRaw)
        .filter(TarkovGunRaw.id == RAW_ROW_ID)
        .one_or_none()
    )


def list_guns(db: Session) -> list[TarkovGun]:
    return (
        db.query(TarkovGun)
        .order_by(
            TarkovGun.caliber.asc(),
            TarkovGun.name.asc(),
        )
        .all()
    )


def _upsert_gun_raw(
    db: Session,
    *,
    source: str,
    payload: dict[str, Any],
    note: str,
    synced_at,
) -> None:
    raw_json = json.dumps(payload, ensure_ascii=False)
    row = get_gun_raw(db)
    if row is None:
        db.add(
            TarkovGunRaw(
                id=RAW_ROW_ID,
                source=source,
                raw_json=raw_json,
                synced_at=synced_at,
                note=note,
            )
        )
    else:
        row.source = source
        row.raw_json = raw_json
        row.synced_at = synced_at
        row.note = note


def _replace_derived_gun_rows(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    source: str,
    note: str,
    synced_at,
) -> None:
    if not rows:
        raise TarkovGunError("未解析到枪械数据")
    db.query(TarkovGun).delete()
    for row in rows:
        db.add(
            TarkovGun(
                item_id=row["item_id"],
                name=row["name"],
                short_name=row["short_name"],
                caliber=row["caliber"],
                weapon_class=row["weapon_class"],
                fire_rate=row["fire_rate"],
                ergonomics=row["ergonomics"],
                recoil_vertical=row["recoil_vertical"],
                recoil_horizontal=row["recoil_horizontal"],
                effective_distance=row["effective_distance"],
                fire_modes_json=json.dumps(row["fire_modes"], ensure_ascii=False),
                default_ammo_id=row["default_ammo_id"],
                allowed_ammo_json=json.dumps(
                    row["allowed_ammo_ids"], ensure_ascii=False
                ),
                icon_link=row["icon_link"],
                updated_at=synced_at,
            )
        )
    meta = get_gun_meta(db)
    if meta is None:
        meta = TarkovGunMeta(id=META_ROW_ID)
        db.add(meta)
    meta.source = source
    meta.gun_count = len(rows)
    meta.synced_at = synced_at
    meta.note = note


def persist_gun_bundle(db: Session, bundle: GunUpstreamBundle) -> dict[str, Any]:
    rows = parse_gun_raw(bundle.source, bundle.payload)
    if not rows:
        raise TarkovGunError("未解析到枪械数据")
    now = now_naive()
    _upsert_gun_raw(
        db,
        source=bundle.source,
        payload=bundle.payload,
        note=bundle.note,
        synced_at=now,
    )
    _replace_derived_gun_rows(
        db,
        rows,
        source=bundle.source,
        note=bundle.note,
        synced_at=now,
    )
    db.commit()
    logger.info("tarkov guns synced: %s rows via %s", len(rows), bundle.source)
    return {
        "gun_count": len(rows),
        "source": bundle.source,
        "synced_at": now.isoformat() if now else None,
    }


def rebuild_guns_from_raw(db: Session) -> dict[str, Any]:
    row = get_gun_raw(db)
    if row is None:
        raise TarkovGunError("无枪械 raw，无法重算")
    try:
        payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TarkovGunError("枪械 raw_json 无效") from exc
    if not isinstance(payload, dict):
        raise TarkovGunError("枪械 raw_json 格式无效")
    rows = parse_gun_raw(row.source, payload)
    now = now_naive()
    note = row.note or f"rebuild from raw ({row.source})"
    _replace_derived_gun_rows(
        db,
        rows,
        source=row.source,
        note=note,
        synced_at=now,
    )
    db.commit()
    return {
        "gun_count": len(rows),
        "source": row.source,
        "synced_at": now.isoformat() if now else None,
    }


def ensure_guns(db: Session) -> list[TarkovGun]:
    if gun_count(db) == 0:
        if get_gun_raw(db) is not None:
            try:
                rebuild_guns_from_raw(db)
            except TarkovGunError as exc:
                logger.warning("rebuild guns from raw failed, syncing: %s", exc)
                sync_from_upstream(db)
        else:
            sync_from_upstream(db)
    return list_guns(db)


def sync_from_upstream(db: Session) -> dict[str, Any]:
    logger.info("syncing tarkov guns from upstream")
    errors: list[str] = []
    try:
        return persist_gun_bundle(db, download_graphql_guns(lang="zh"))
    except TarkovGunError as exc:
        errors.append(f"graphql: {exc}")
        logger.warning("tarkov.dev GraphQL gun sync failed: %s", exc)
    try:
        bundle = download_json_api_guns(lang="zh")
        note = bundle.note
        if errors:
            note = f"{note} (fallback; {errors[0][:160]})"
        return persist_gun_bundle(
            db,
            GunUpstreamBundle(source=bundle.source, payload=bundle.payload, note=note),
        )
    except TarkovGunError as exc:
        detail = "；".join(errors) if errors else str(exc)
        raise TarkovGunError(f"枪械同步失败：{detail}；json 亦失败: {exc}") from None


def gun_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    job = JobRun(job_key=GUN_JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_from_upstream(db)
        job.status = "ok"
        job.message = json.dumps(
            {
                "gun_count": result.get("gun_count"),
                "source": result.get("source"),
            },
            ensure_ascii=False,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov gun sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
