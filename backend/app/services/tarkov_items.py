"""逃离塔科夫物品：一次回源 → items raw → 同时派生弹药/枪械。

流程：
  上游 ──(回源一次)──► tarkov_items_raws ──(parse)──► tarkov_ammo + tarkov_guns
失败不覆盖已有成功 raw；任一派生表为空时可先从 raw 重算再回源。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovAmmo, TarkovItemsMeta, TarkovItemsRaw
from app.services import tarkov_ammo as ammo_svc
from app.services import tarkov_guns as gun_svc
from app.services.tarkov_ammo import SOURCE_GRAPHQL, SOURCE_JSON_API

logger = logging.getLogger(__name__)

META_ROW_ID = 1
RAW_ROW_ID = 1
ITEMS_JOB_KEY = "tarkov_items_sync"

# GraphQL split 信封标记（ammo/guns 各自一份 GraphQL 响应）
GRAPHQL_SPLIT_FORMAT = "graphql_split"


class TarkovItemsError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class ItemsUpstreamBundle:
    source: str
    payload: dict[str, Any]
    note: str


def get_items_raw(db: Session) -> TarkovItemsRaw | None:
    return (
        db.query(TarkovItemsRaw)
        .filter(TarkovItemsRaw.id == RAW_ROW_ID)
        .one_or_none()
    )


def get_items_meta(db: Session) -> TarkovItemsMeta | None:
    return (
        db.query(TarkovItemsMeta)
        .filter(TarkovItemsMeta.id == META_ROW_ID)
        .one_or_none()
    )


def parse_items_payload(
    source: str, payload: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """从共享 raw 解析弹药行与枪械行。"""
    src = (source or "").strip()
    if src == SOURCE_GRAPHQL and payload.get("format") == GRAPHQL_SPLIT_FORMAT:
        ammo_payload = payload.get("ammo")
        guns_payload = payload.get("guns")
        if not isinstance(ammo_payload, dict) or not isinstance(guns_payload, dict):
            raise TarkovItemsError("GraphQL split 信封缺少 ammo/guns")
        try:
            ammo_rows = ammo_svc.parse_ammo_raw(SOURCE_GRAPHQL, ammo_payload)
            gun_rows = gun_svc.parse_gun_raw(SOURCE_GRAPHQL, guns_payload)
        except (ammo_svc.TarkovAmmoError, gun_svc.TarkovGunError) as exc:
            raise TarkovItemsError(str(exc)) from exc
        return ammo_rows, gun_rows

    if src == SOURCE_JSON_API:
        try:
            ammo_rows = ammo_svc.parse_ammo_raw(SOURCE_JSON_API, payload)
            gun_rows = gun_svc.parse_gun_raw(SOURCE_JSON_API, payload)
        except (ammo_svc.TarkovAmmoError, gun_svc.TarkovGunError) as exc:
            raise TarkovItemsError(str(exc)) from exc
        return ammo_rows, gun_rows

    # 兼容迁移：旧 gun/ammo json 信封可能仍标 graphql 但实际是 json
    if isinstance(payload.get("items"), dict):
        try:
            ammo_rows = ammo_svc.parse_ammo_raw(SOURCE_JSON_API, payload)
            gun_rows = gun_svc.parse_gun_raw(SOURCE_JSON_API, payload)
        except (ammo_svc.TarkovAmmoError, gun_svc.TarkovGunError) as exc:
            raise TarkovItemsError(str(exc)) from exc
        return ammo_rows, gun_rows

    raise TarkovItemsError(f"未知物品 raw 来源: {src or '—'}")


def download_graphql_items(*, lang: str = "zh") -> ItemsUpstreamBundle:
    """分别拉 GraphQL ammo + guns，合成一份 split 信封（仍算一次同步任务）。"""
    try:
        ammo_bundle = ammo_svc.download_graphql_ammo(lang=lang)
        guns_bundle = gun_svc.download_graphql_guns(lang=lang)
    except ammo_svc.TarkovAmmoError as exc:
        raise TarkovItemsError(f"graphql ammo: {exc}") from exc
    except gun_svc.TarkovGunError as exc:
        raise TarkovItemsError(f"graphql guns: {exc}") from exc

    return ItemsUpstreamBundle(
        source=SOURCE_GRAPHQL,
        payload={
            "format": GRAPHQL_SPLIT_FORMAT,
            "ammo": ammo_bundle.payload,
            "guns": guns_bundle.payload,
        },
        note="api.tarkov.dev GraphQL ammo + items(type:gun)",
    )


def download_json_api_items(*, lang: str = "zh") -> ItemsUpstreamBundle:
    """json.tarkov.dev/regular/items 一次下载，弹药与枪械共用。"""
    try:
        # 复用弹药下载（信封与枪械侧一致）
        bundle = ammo_svc.download_json_api_ammo(lang=lang)
    except ammo_svc.TarkovAmmoError as exc:
        raise TarkovItemsError(str(exc)) from exc
    return ItemsUpstreamBundle(
        source=SOURCE_JSON_API,
        payload=bundle.payload,
        note="json.tarkov.dev/regular/items",
    )


def _upsert_items_raw(
    db: Session,
    *,
    source: str,
    payload: dict[str, Any],
    note: str,
    synced_at,
) -> None:
    raw_json = json.dumps(payload, ensure_ascii=False)
    row = get_items_raw(db)
    if row is None:
        db.add(
            TarkovItemsRaw(
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


def _upsert_items_meta(
    db: Session,
    *,
    source: str,
    ammo_count: int,
    gun_count: int,
    note: str,
    synced_at,
) -> None:
    meta = get_items_meta(db)
    if meta is None:
        meta = TarkovItemsMeta(id=META_ROW_ID)
        db.add(meta)
    meta.source = source
    meta.ammo_count = ammo_count
    meta.gun_count = gun_count
    meta.synced_at = synced_at
    meta.note = note


def persist_items_bundle(db: Session, bundle: ItemsUpstreamBundle) -> dict[str, Any]:
    ammo_rows, gun_rows = parse_items_payload(bundle.source, bundle.payload)
    if not ammo_rows:
        raise TarkovItemsError("未解析到弹药数据")
    if not gun_rows:
        raise TarkovItemsError("未解析到枪械数据")

    now = now_naive()
    _upsert_items_raw(
        db,
        source=bundle.source,
        payload=bundle.payload,
        note=bundle.note,
        synced_at=now,
    )
    ammo_svc.replace_derived_ammo_rows(
        db,
        ammo_rows,
        source=bundle.source,
        note=bundle.note,
        synced_at=now,
    )
    gun_svc.replace_derived_gun_rows(
        db,
        gun_rows,
        source=bundle.source,
        note=bundle.note,
        synced_at=now,
    )
    _upsert_items_meta(
        db,
        source=bundle.source,
        ammo_count=len(ammo_rows),
        gun_count=len(gun_rows),
        note=bundle.note,
        synced_at=now,
    )
    db.commit()
    logger.info(
        "tarkov items synced: ammo=%s guns=%s via %s",
        len(ammo_rows),
        len(gun_rows),
        bundle.source,
    )
    return {
        "ammo_count": len(ammo_rows),
        "gun_count": len(gun_rows),
        "source": bundle.source,
        "synced_at": now.isoformat() if now else None,
    }


def rebuild_from_raw(db: Session) -> dict[str, Any]:
    row = get_items_raw(db)
    if row is None:
        raise TarkovItemsError("无物品 raw，无法重算")
    try:
        payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TarkovItemsError("物品 raw_json 无效") from exc
    if not isinstance(payload, dict):
        raise TarkovItemsError("物品 raw_json 格式无效")

    ammo_rows, gun_rows = parse_items_payload(row.source, payload)
    if not ammo_rows:
        raise TarkovItemsError("未解析到弹药数据")
    if not gun_rows:
        raise TarkovItemsError("未解析到枪械数据")

    now = now_naive()
    note = row.note or f"rebuild from raw ({row.source})"
    ammo_svc.replace_derived_ammo_rows(
        db,
        ammo_rows,
        source=row.source,
        note=note,
        synced_at=now,
    )
    gun_svc.replace_derived_gun_rows(
        db,
        gun_rows,
        source=row.source,
        note=note,
        synced_at=now,
    )
    _upsert_items_meta(
        db,
        source=row.source,
        ammo_count=len(ammo_rows),
        gun_count=len(gun_rows),
        note=note,
        synced_at=now,
    )
    db.commit()
    return {
        "ammo_count": len(ammo_rows),
        "gun_count": len(gun_rows),
        "source": row.source,
        "synced_at": now.isoformat() if now else None,
    }


def sync_from_upstream(db: Session) -> dict[str, Any]:
    """优先 GraphQL split；失败回退 json.tarkov.dev 整包 items（一次下载）。"""
    logger.info("syncing tarkov items from upstream")
    errors: list[str] = []

    try:
        return persist_items_bundle(db, download_graphql_items(lang="zh"))
    except TarkovItemsError as exc:
        errors.append(f"graphql: {exc}")
        logger.warning("tarkov.dev GraphQL items sync failed: %s", exc)

    try:
        bundle = download_json_api_items(lang="zh")
        note = bundle.note
        if errors:
            note = f"{note} (fallback; {errors[0][:160]})"
        return persist_items_bundle(
            db,
            ItemsUpstreamBundle(source=bundle.source, payload=bundle.payload, note=note),
        )
    except TarkovItemsError as exc:
        detail = "；".join(errors) if errors else str(exc)
        raise TarkovItemsError(f"物品同步失败：{detail}；json 亦失败: {exc}") from None


def ensure_items(db: Session) -> None:
    """弹药或枪械派生为空时：优先 raw 重算，否则回源一次。

    弹药已有行但 icon 全空时（例如新加 icon_link 列），有 raw 则重算一次。
    """
    need_ammo = ammo_svc.ammo_count(db) == 0
    need_guns = gun_svc.gun_count(db) == 0
    icons_missing = False
    if not need_ammo:
        with_icon = (
            db.query(TarkovAmmo)
            .filter(TarkovAmmo.icon_link != "")
            .count()
        )
        icons_missing = with_icon == 0

    if not need_ammo and not need_guns and not icons_missing:
        return
    if get_items_raw(db) is not None:
        try:
            rebuild_from_raw(db)
            return
        except TarkovItemsError as exc:
            logger.warning("rebuild items from raw failed, syncing: %s", exc)
    if need_ammo or need_guns:
        sync_from_upstream(db)


def get_ammo_item_detail(db: Session, item_id: str) -> dict[str, Any]:
    """从 items raw 取出单条弹药的完整 item + properties（读库优先）。"""
    item_id = (item_id or "").strip()
    if not item_id:
        raise TarkovItemsError("弹药 id 无效")

    ensure_items(db)
    if (
        db.query(TarkovAmmo.item_id)
        .filter(TarkovAmmo.item_id == item_id)
        .one_or_none()
        is None
    ):
        raise TarkovItemsError(f"未找到弹药: {item_id}")

    row = get_items_raw(db)
    if row is None:
        raise TarkovItemsError("无物品 raw")
    try:
        payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TarkovItemsError("物品 raw_json 无效") from exc
    if not isinstance(payload, dict):
        raise TarkovItemsError("物品 raw_json 格式无效")

    detail = _extract_ammo_item_detail(row.source, payload, item_id)
    if detail is None:
        raise TarkovItemsError(f"未找到弹药: {item_id}")
    detail["source"] = row.source
    return detail


def _locale_map(payload: dict[str, Any]) -> dict[str, Any]:
    locale = payload.get("locale")
    if isinstance(locale, dict):
        data = locale.get("data")
        if isinstance(data, dict):
            return data
        return locale
    return {}


def _json_items_map(payload: dict[str, Any]) -> dict[str, Any]:
    items_blob = payload.get("items")
    if not isinstance(items_blob, dict):
        return {}
    data = items_blob.get("data") if isinstance(items_blob.get("data"), dict) else items_blob
    if not isinstance(data, dict):
        return {}
    items = data.get("items") if isinstance(data.get("items"), dict) else data
    return items if isinstance(items, dict) else {}


def _extract_ammo_item_detail(
    source: str,
    payload: dict[str, Any],
    item_id: str,
) -> dict[str, Any] | None:
    src = (source or "").strip()
    if src == SOURCE_GRAPHQL and payload.get("format") == GRAPHQL_SPLIT_FORMAT:
        ammo_payload = payload.get("ammo")
        if not isinstance(ammo_payload, dict):
            return None
        data = ammo_payload.get("data") if isinstance(ammo_payload.get("data"), dict) else {}
        rows = data.get("ammo") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return None
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            item = raw.get("item") if isinstance(raw.get("item"), dict) else {}
            if str(item.get("id") or "").strip() != item_id:
                continue
            props = {
                k: v
                for k, v in raw.items()
                if k != "item" and v is not None
            }
            item_out = {k: v for k, v in item.items() if v is not None}
            return {
                "id": item_id,
                "name": str(item_out.get("name") or item_id),
                "short_name": str(item_out.get("shortName") or ""),
                "description": str(item_out.get("description") or ""),
                "item": item_out,
                "properties": props,
            }
        return None

    # json.tarkov.dev 信封（含兼容旧 raw）
    items = _json_items_map(payload)
    raw = items.get(item_id)
    if not isinstance(raw, dict):
        return None
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    if props.get("propertiesType") not in (None, "ItemPropertiesAmmo"):
        # 仍允许返回：只要 id 在弹药派生表会先校验；这里宽松
        pass
    locale = _locale_map(payload)
    name = str(
        locale.get(f"{item_id} Name")
        or raw.get("name")
        or locale.get(f"{item_id} ShortName")
        or raw.get("shortName")
        or item_id
    )
    short_name = str(
        locale.get(f"{item_id} ShortName") or raw.get("shortName") or ""
    )
    description = str(
        locale.get(f"{item_id} Description") or raw.get("description") or ""
    )
    if description.endswith(" Description") and item_id in description:
        description = ""
    item_out = {k: v for k, v in raw.items() if k != "properties"}
    item_out["name"] = name
    item_out["shortName"] = short_name
    if description:
        item_out["description"] = description
    elif "description" in item_out and str(item_out["description"]).endswith(
        " Description"
    ):
        item_out.pop("description", None)
    return {
        "id": item_id,
        "name": name,
        "short_name": short_name,
        "description": description,
        "item": item_out,
        "properties": dict(props) if isinstance(props, dict) else {},
    }


def items_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    job = JobRun(job_key=ITEMS_JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_from_upstream(db)
        job.status = "ok"
        job.message = json.dumps(
            {
                "ammo_count": result.get("ammo_count"),
                "gun_count": result.get("gun_count"),
                "source": result.get("source"),
            },
            ensure_ascii=False,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov items sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
