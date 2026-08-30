"""塔科夫上游整站 dump：json.tarkov.dev 全文件 + api.tarkov.dev 静态补集。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import (
    TarkovBartersRaw,
    TarkovCatalogRawMixin,
    TarkovCraftsRaw,
    TarkovExtrasRaw,
    TarkovHideoutRaw,
    TarkovItemsRaw,
    TarkovMapsRaw,
    TarkovTasksRaw,
    TarkovTradersRaw,
)
from app.services.tarkov.ammo import SOURCE_JSON_API, TARKOV_GRAPHQL_URL
from app.services.tarkov.game_mode import (
    graphql_game_mode,
    json_api_prefix,
    json_resource_url,
    parse_game_mode,
    raw_row_id,
)
from app.services.tarkov.http import download_bytes, download_bytes_with_meta

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
}

_EXTRAS_QUERY = """
query CatalogExtras($lang: LanguageCode, $gameMode: GameMode) {
  achievements(lang: $lang) { id name hidden side }
  prestige(lang: $lang, gameMode: $gameMode) { id name prestigeLevel iconLink }
  skills(lang: $lang) { id name }
  playerLevels { level exp }
  fleaMarket(lang: $lang, gameMode: $gameMode) {
    name
    normalizedName
    minPlayerLevel
    enabled
    sellOfferFeeRate
    sellRequirementFeeRate
    foundInRaidRequired
  }
  lootContainers(lang: $lang) { id name normalizedName }
  questItems(lang: $lang) { id name shortName normalizedName }
  armorMaterials(lang: $lang) { id name destructibility }
  stationaryWeapons(lang: $lang) { id name shortName }
  handbookCategories(lang: $lang) { id name normalizedName }
  itemCategories(lang: $lang) { id name normalizedName }
}
""".strip()


class TarkovUpstreamError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


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
    url: str, *, timeout: int = 180
) -> tuple[dict[str, Any], str | None]:
    raw, upstream_at = download_bytes_with_meta(
        url, timeout=timeout, error_cls=TarkovUpstreamError
    )
    return _decode_json(raw, label=url), upstream_at


def download_json_resource(
    resource: str, *, lang: str | None = None
) -> tuple[dict[str, Any], str | None]:
    timeout = 60 if lang else 180
    return download_json_object(
        json_resource_url(resource, lang=lang),
        timeout=timeout,
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
        db.add(
            model(
                mode_id=mode_id,
                lang=lang_key,
                source=source,
                raw_json=raw_json,
                synced_at=now,
                note=note,
            )
        )
    else:
        row.source = source
        row.raw_json = raw_json
        row.synced_at = now
        row.note = note
    if commit:
        db.commit()
    return {
        "id": resource_key(resource, lang=lang_key or None),
        "ok": True,
        "source": source,
        "synced_at": now.isoformat(),
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
    *, lang: str = "zh"
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """拉 json.tarkov.dev 当前模式全部静态文件（含 locale）。单文件失败不中断。

    返回 (文件字典, 资源 → Last-Modified ISO)。
    """
    out: dict[str, dict[str, Any]] = {}
    upstream_times: dict[str, str] = {}
    prefix = json_api_prefix()
    errors: list[str] = []
    for resource in JSON_RESOURCES:
        try:
            payload, upstream_at = download_json_resource(resource)
            out[resource] = payload
            if upstream_at:
                upstream_times[resource] = upstream_at
            logger.info("tarkov dump %s/%s ok", prefix, resource)
        except TarkovUpstreamError as exc:
            errors.append(f"{resource}: {exc}")
            logger.warning("tarkov dump %s/%s failed: %s", prefix, resource, exc)
    for resource in JSON_LOCALES:
        key = resource_key(resource, lang=lang)
        try:
            payload, upstream_at = download_json_resource(resource, lang=lang)
            out[key] = payload
            if upstream_at:
                upstream_times[key] = upstream_at
        except TarkovUpstreamError as exc:
            logger.warning("tarkov dump %s/%s locale failed: %s", prefix, key, exc)
            out[key] = {}
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
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prefix = json_api_prefix()
    times = upstream_times or {}
    mode = parse_game_mode()
    for resource in JSON_RESOURCES:
        payload = dump.get(resource)
        if not isinstance(payload, dict) or not payload:
            rows.append(
                {
                    "id": f"dump:{resource}",
                    "ok": False,
                    "source": None,
                    "synced_at": None,
                    "upstream_at": None,
                    "mode": mode,
                    "error": "未下载到该资源",
                }
            )
            continue
        saved = persist_raw(
            db,
            resource,
            payload,
            source=SOURCE_JSON_API,
            note=f"json.tarkov.dev/{prefix}/{resource}",
            commit=False,
            upstream_at=times.get(resource),
        )
        saved["id"] = f"dump:{resource}"
        saved["mode"] = mode
        rows.append(saved)
    for resource in JSON_LOCALES:
        key = resource_key(resource, lang=lang)
        payload = dump.get(key)
        if not isinstance(payload, dict) or not payload:
            rows.append(
                {
                    "id": f"dump:{key}",
                    "ok": False,
                    "source": None,
                    "synced_at": None,
                    "upstream_at": None,
                    "mode": mode,
                    "error": "locale 不可用",
                }
            )
            continue
        saved = persist_raw(
            db,
            resource,
            payload,
            lang=lang,
            source=SOURCE_JSON_API,
            note=f"json.tarkov.dev/{prefix}/{key}",
            commit=False,
            upstream_at=times.get(key),
        )
        saved["id"] = f"dump:{key}"
        saved["mode"] = mode
        rows.append(saved)
    db.commit()
    return rows


def locale_data(dump: dict[str, dict[str, Any]], resource: str, *, lang: str = "zh") -> dict[str, Any]:
    blob = dump.get(resource_key(resource, lang=lang))
    if not isinstance(blob, dict):
        return {}
    data = unwrap_json_blob(blob)
    return data if isinstance(data, dict) else {}


def download_graphql_extras(*, lang: str = "zh") -> dict[str, Any]:
    body = json.dumps(
        {
            "query": _EXTRAS_QUERY,
            "variables": {"lang": lang, "gameMode": graphql_game_mode()},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    raw = download_bytes(
        TARKOV_GRAPHQL_URL,
        method="POST",
        body=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=45,
        error_cls=TarkovUpstreamError,
    )
    payload = _decode_json(raw, label="api.tarkov.dev extras")
    if payload.get("errors"):
        raise TarkovUpstreamError(f"api.tarkov.dev extras: {payload.get('errors')}")
    data = payload.get("data")
    if not isinstance(data, dict) or not data:
        raise TarkovUpstreamError("api.tarkov.dev extras 为空")
    return data
