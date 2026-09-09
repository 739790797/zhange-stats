"""塔科夫上游整站 dump：json.tarkov.dev 全文件（含 extras 投影）。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import (
    TarkovBartersRaw,
    TarkovCatalogRawMixin,
    TarkovCraftsRaw,
    TarkovExtrasRaw,
    TarkovHideoutRaw,
    TarkovOverlayRaw,
    TarkovItemsRaw,
    TarkovMapsRaw,
    TarkovTasksRaw,
    TarkovTradersRaw,
)
from app.services.tarkov.ammo import SOURCE_JSON_API
from app.services.tarkov.game_mode import (
    json_api_prefix,
    json_resource_url,
    parse_game_mode,
    raw_row_id,
)
from app.services.tarkov.http import download_bytes_with_meta

logger = logging.getLogger(__name__)

RAW_LANG_MAIN = ""

JSON_RESOURCES: tuple[str, ...] = (
    "items",
    "maps",
    "tasks",
    "traders",
    "hideout",
    "barters",
    "crafts",
)
JSON_LOCALES: tuple[str, ...] = (
    "items",
    "maps",
    "tasks",
    "traders",
    "hideout",
)
EXTRAS_RESOURCE = "extras"

RAW_MODELS: dict[str, type[TarkovCatalogRawMixin]] = {
    "items": TarkovItemsRaw,
    "maps": TarkovMapsRaw,
    "tasks": TarkovTasksRaw,
    "traders": TarkovTradersRaw,
    "hideout": TarkovHideoutRaw,
    "barters": TarkovBartersRaw,
    "crafts": TarkovCraftsRaw,
    "extras": TarkovExtrasRaw,
    "overlay": TarkovOverlayRaw,
}

EXTRAS_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "items",
        (
            "skills",
            "playerLevels",
            "fleaMarket",
            "armorMaterials",
            "itemCategories",
            "handbookCategories",
            "mastering",
        ),
    ),
    ("maps", ("lootContainers", "stationaryWeapons")),
    ("tasks", ("achievements", "prestige", "questItems")),
)


class TarkovUpstreamError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


DumpProgress = Callable[[dict[str, Any]], None]
ByteProgress = Callable[[int, int | None], None]


def site_dump_specs(*, lang: str = "zh") -> list[tuple[str, str | None, str]]:
    """下载/落库顺序：(resource, lang 或 None, dump 域 id)。"""
    rows: list[tuple[str, str | None, str]] = [
        (resource, None, f"dump:{resource}") for resource in JSON_RESOURCES
    ]
    for resource in JSON_LOCALES:
        key = resource_key(resource, lang=lang)
        rows.append((resource, lang, f"dump:{key}"))
    return rows


def resource_key(resource: str, *, lang: str | None = None) -> str:
    if lang:
        return f"{resource}_{lang}"
    return resource


def normalize_raw_lang(lang: str | None) -> str:
    return (lang or "").strip()


def raw_model(resource: str) -> type[TarkovCatalogRawMixin]:
    model = RAW_MODELS.get(resource)
    if model is None:
        raise TarkovUpstreamError(f"未知 raw 资源: {resource}")
    return model


def _decode_json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovUpstreamError(f"{label}解析失败") from exc
    if not isinstance(payload, dict):
        raise TarkovUpstreamError(f"{label}格式无效")
    return payload


def unwrap_json_blob(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def merge_locale(payload: dict[str, Any], locale: dict[str, Any]) -> dict[str, Any]:
    if not locale:
        return payload
    existing = payload.get("locale")
    if isinstance(existing, dict) and existing:
        return payload
    out = dict(payload)
    out["locale"] = locale
    return out


def download_json_object(
    url: str,
    *,
    timeout: int = 180,
    on_bytes: ByteProgress | None = None,
) -> tuple[dict[str, Any], str | None]:
    raw, upstream_at = download_bytes_with_meta(
        url, timeout=timeout, error_cls=TarkovUpstreamError, on_bytes=on_bytes
    )
    return _decode_json(raw, label=url), upstream_at


def download_json_resource(
    resource: str,
    *,
    lang: str | None = None,
    on_bytes: ByteProgress | None = None,
) -> tuple[dict[str, Any], str | None]:
    timeout = 60 if lang else 180
    return download_json_object(
        json_resource_url(resource, lang=lang),
        timeout=timeout,
        on_bytes=on_bytes,
    )


def load_raw_row(
    db: Session,
    resource: str,
    *,
    lang: str | None = None,
    mode_id: int | None = None,
) -> TarkovCatalogRawMixin | None:
    model = raw_model(resource)
    return (
        db.query(model)
        .filter(
            model.mode_id == (mode_id if mode_id is not None else raw_row_id()),
            model.lang == normalize_raw_lang(lang),
        )
        .one_or_none()
    )


def decode_raw_json(raw_json: str | None) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_json or "")
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def raw_row_header(
    row: TarkovCatalogRawMixin | None,
) -> tuple[str | None, str | None, str | None]:
    if row is None:
        return None, None, None
    synced = row.synced_at.isoformat() if row.synced_at else None
    return row.source, synced, row.note


def load_raw(
    db: Session,
    resource: str,
    *,
    lang: str | None = None,
    mode_id: int | None = None,
) -> dict[str, Any] | None:
    row = load_raw_row(db, resource, lang=lang, mode_id=mode_id)
    if row is None:
        return None
    return decode_raw_json(row.raw_json)


def load_main_payload(
    db: Session,
    resource: str,
    *,
    error_cls: type[Exception] = TarkovUpstreamError,
    missing: str = "无 raw",
    invalid: str = "raw_json 无效",
) -> tuple[str, dict[str, Any], str | None, str | None]:
    """当前模式主文件 + 同表 locale。各栏目读库走这里，不要再手拆 raw_json。"""
    row = load_raw_row(db, resource)
    if row is None:
        raise error_cls(missing)
    payload = decode_raw_json(row.raw_json)
    if payload is None:
        raise error_cls(invalid)
    payload = merge_locale(payload, load_locale_map(db, resource, payload=payload))
    source, synced, note = raw_row_header(row)
    return source or "", payload, synced, note


def load_locale_map(
    db: Session,
    resource: str,
    *,
    lang: str = "zh",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blob = load_raw(db, resource, lang=lang)
    if blob is None and payload is not None:
        nested = payload.get("locale")
        blob = nested if isinstance(nested, dict) else None
    if not isinstance(blob, dict):
        return {}
    data = unwrap_json_blob(blob)
    return data if isinstance(data, dict) else {}


def persist_raw(
    db: Session,
    resource: str,
    payload: dict[str, Any],
    *,
    lang: str | None = None,
    source: str,
    note: str,
    commit: bool = True,
    upstream_at: str | None = None,
) -> dict[str, Any]:
    now = now_naive()
    if upstream_at:
        note = f"{note} · 上游 {upstream_at}"
    raw_json = json.dumps(payload, ensure_ascii=False)
    mode_id = raw_row_id()
    lang_key = normalize_raw_lang(lang)
    model = raw_model(resource)
    row = load_raw_row(db, resource, lang=lang_key, mode_id=mode_id)
    if row is None:
        row = model(
            mode_id=mode_id,
            lang=lang_key,
            source=source,
            raw_json=raw_json,
            synced_at=now,
            note=note,
        )
        db.add(row)
    elif row.raw_json != raw_json:
        row.source = source
        row.raw_json = raw_json
        row.synced_at = now
        row.note = note
    else:
        # dump 字节没变：保留 synced_at，ETag / 浏览器哈希才不会被空同步打穿。
        row.source = source
        row.note = note
    if commit:
        db.commit()
    synced = row.synced_at.isoformat() if row.synced_at else now.isoformat()
    return {
        "id": resource_key(resource, lang=lang_key or None),
        "ok": True,
        "source": source,
        "synced_at": synced,
        "upstream_at": upstream_at,
        "error": None,
    }


def persist_locale_if_present(
    db: Session,
    resource: str,
    payload: dict[str, Any],
    *,
    source: str,
    note: str,
    lang: str = "zh",
) -> None:
    locale = payload.get("locale")
    if not isinstance(locale, dict) or not locale:
        return
    persist_raw(
        db,
        resource,
        locale if "data" in locale else {"data": locale},
        lang=lang,
        source=source,
        note=f"{note} locale",
        commit=False,
    )


def download_site_json(
    *, lang: str = "zh", on_progress: DumpProgress | None = None
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """拉 json.tarkov.dev 当前模式全部静态文件（含 locale）。单文件失败不中断。

    返回 (文件字典, 资源 → Last-Modified ISO)。
    """
    out: dict[str, dict[str, Any]] = {}
    upstream_times: dict[str, str] = {}
    prefix = json_api_prefix()
    errors: list[str] = []
    specs = site_dump_specs(lang=lang)
    total = len(specs)
    for index, (resource, res_lang, domain_id) in enumerate(specs, start=1):
        key = resource_key(resource, lang=res_lang)
        is_locale = res_lang is not None

        def emit(
            *,
            bytes_n: int = 0,
            total_bytes: int | None = None,
            done: bool = False,
            error: str | None = None,
            _key: str = key,
            _domain_id: str = domain_id,
            _index: int = index,
        ) -> None:
            if on_progress is None:
                return
            on_progress(
                {
                    "phase": "download",
                    "file": _key,
                    "domain_id": _domain_id,
                    "index": _index,
                    "total": total,
                    "bytes": bytes_n,
                    "total_bytes": total_bytes,
                    "done": done,
                    "error": error,
                }
            )

        def on_bytes(
            n: int,
            total_bytes: int | None,
            *,
            _emit: Callable[..., None] = emit,
        ) -> None:
            _emit(bytes_n=n, total_bytes=total_bytes)

        emit()
        try:
            payload, upstream_at = download_json_resource(
                resource, lang=res_lang, on_bytes=on_bytes
            )
            out[key] = payload
            if upstream_at:
                upstream_times[key] = upstream_at
            logger.debug("tarkov dump %s/%s ok", prefix, key)
            emit(done=True)
        except TarkovUpstreamError as exc:
            emit(done=True, error=str(exc))
            if is_locale:
                logger.warning("tarkov dump %s/%s locale failed: %s", prefix, key, exc)
                out[key] = {}
            else:
                errors.append(f"{resource}: {exc}")
                logger.warning("tarkov dump %s/%s failed: %s", prefix, resource, exc)
    if not any(isinstance(out.get(name), dict) and out[name] for name in JSON_RESOURCES):
        detail = "；".join(errors) if errors else "无文件"
        raise TarkovUpstreamError(f"json.tarkov.dev 全站为空：{detail}")
    return out, upstream_times


def persist_site_json(
    db: Session,
    dump: dict[str, dict[str, Any]],
    *,
    lang: str = "zh",
    upstream_times: dict[str, str] | None = None,
    on_progress: DumpProgress | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prefix = json_api_prefix()
    times = upstream_times or {}
    mode = parse_game_mode()
    specs = site_dump_specs(lang=lang)
    total = len(specs)
    for index, (resource, res_lang, domain_id) in enumerate(specs, start=1):
        key = resource_key(resource, lang=res_lang)
        if on_progress is not None:
            on_progress(
                {
                    "phase": "persist",
                    "file": key,
                    "domain_id": domain_id,
                    "index": index,
                    "total": total,
                }
            )
        payload = dump.get(key)
        if not isinstance(payload, dict) or not payload:
            rows.append(
                {
                    "id": domain_id,
                    "ok": False,
                    "status": "error",
                    "source": None,
                    "synced_at": None,
                    "upstream_at": None,
                    "mode": mode,
                    "error": "locale 不可用" if res_lang else "未下载到该资源",
                }
            )
            continue
        saved = persist_raw(
            db,
            resource,
            payload,
            lang=res_lang,
            source=SOURCE_JSON_API,
            note=f"json.tarkov.dev/{prefix}/{key}",
            commit=False,
            upstream_at=times.get(key),
        )
        saved["id"] = domain_id
        saved["mode"] = mode
        saved["status"] = "ok" if saved.get("ok") else "error"
        rows.append(saved)
    db.commit()
    return rows


def locale_data(dump: dict[str, dict[str, Any]], resource: str, *, lang: str = "zh") -> dict[str, Any]:
    blob = dump.get(resource_key(resource, lang=lang))
    if not isinstance(blob, dict):
        return {}
    data = unwrap_json_blob(blob)
    return data if isinstance(data, dict) else {}


def extras_from_site_dump(dump: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """从已下载的 json.tarkov.dev dump 抽出原 GraphQL extras 字段。"""
    out: dict[str, Any] = {}
    for resource, keys in EXTRAS_KEYS:
        blob = unwrap_json_blob(dump.get(resource) or {})
        if not isinstance(blob, dict):
            continue
        for key in keys:
            if key in blob:
                out[key] = blob[key]
    if not out:
        raise TarkovUpstreamError("json.tarkov.dev dump 未解析到 extras")
    return out
