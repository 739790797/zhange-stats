"""塔科夫上游整站 dump：json.tarkov.dev 全文件，一张文件一张 raw 表。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, SessionTransaction, undefer

from app.core.timeutil import now_naive
from app.services.guide_raw.codec import GZIP_PREFIX, RawTooLarge, pack_raw_text, unpack_raw_text
from app.models.tarkov import (
    TarkovBartersRaw,
    TarkovCatalogRawMixin,
    TarkovCraftsRaw,
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
from app.services.tarkov.http import (
    TARKOV_DUMP_MAX_BYTES,
    download_dump,
    download_response,
    http_last_modified_iso,
)

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

RAW_MODELS: dict[str, type[TarkovCatalogRawMixin]] = {
    "items": TarkovItemsRaw,
    "maps": TarkovMapsRaw,
    "tasks": TarkovTasksRaw,
    "traders": TarkovTradersRaw,
    "hideout": TarkovHideoutRaw,
    "barters": TarkovBartersRaw,
    "crafts": TarkovCraftsRaw,
    "overlay": TarkovOverlayRaw,
}


class TarkovUpstreamError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# 超过阈值的 raw 压成 gz1:（gzip 后再 base64），读的时候再展开。明文旧行仍按 JSON 读。
# 实现在 guide_raw.codec；这里的阈值仍可被测试替换，调用时再读。
_RAW_JSON_GZIP_PREFIX = GZIP_PREFIX
_RAW_JSON_GZIP_MIN_BYTES = 4 * 1024 * 1024
_RAW_JSON_PACKET_BUDGET = 12 * 1024 * 1024


def _pack_raw_json(text: str) -> str:
    """大 JSON 压到单包预算以内。小文档保持明文，方便直接看库。"""
    try:
        return pack_raw_text(
            text,
            min_bytes=_RAW_JSON_GZIP_MIN_BYTES,
            packet_budget=_RAW_JSON_PACKET_BUDGET,
        )
    except RawTooLarge as exc:
        raise TarkovUpstreamError(str(exc)) from exc


def _unpack_raw_json(stored: str) -> str:
    return unpack_raw_text(stored)


@dataclass(frozen=True)
class SiteDump:
    """整站 dump 一轮的结果。

    files：下载下来的文件（304 的不在里面）
    upstream_times：key → Last-Modified ISO
    unchanged：带上校验头后 304 的 key（跳过落库）
    changed：带了校验头、上游仍回 200 的 key（上游确认换过内容，落库时可跳过旧 blob 比对）
    """

    files: dict[str, dict[str, Any]]
    upstream_times: dict[str, str]
    unchanged: frozenset[str] = frozenset()
    changed: frozenset[str] = frozenset()


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


def download_resource_with_locale(
    resource: str,
    *,
    lang: str = "zh",
    timeout: float | int = 180,
    locale_timeout: float | int = 60,
    error_cls: type[Exception] = TarkovUpstreamError,
    label: str = "",
) -> dict[str, Any]:
    """主文件 + 同资源 locale：locale 挂在 payload["locale"]（lang 文件是 {data: {...}}）。

    locale 拉不到 / 解析不了只记 WARNING，不拖垮主文件。返回的 payload 可以直接 persist。
    """
    raw, _upstream_at = download_dump(
        json_resource_url(resource),
        timeout=timeout,
        error_cls=error_cls,
    )
    payload = _decode_json(raw, label=resource)
    if not payload:
        raise error_cls(f"json.tarkov.dev {resource} 为空")
    try:
        loc_raw, _loc_at = download_dump(
            json_resource_url(resource, lang=lang),
            timeout=locale_timeout,
            error_cls=error_cls,
        )
        loc_payload = _decode_json(loc_raw, label=f"{resource}_{lang}")
        loc_data = loc_payload.get("data")
        if isinstance(loc_data, dict) and loc_data:
            payload = dict(payload)
            payload["locale"] = loc_data
    except error_cls:
        logger.warning("json.tarkov.dev %s_%s locale unavailable", label or resource, lang)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("json.tarkov.dev %s_%s locale parse failed", label or resource, lang)
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
    raw, upstream_at = download_dump(
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
    with_json: bool = False,
) -> TarkovCatalogRawMixin | None:
    """默认只取表头（source / synced_at / note）；with_json 时同一条查询带上 raw_json。"""
    model = raw_model(resource)
    query = db.query(model)
    if with_json:
        query = query.options(undefer(model.raw_json))
    return query.filter(
        model.mode_id == (mode_id if mode_id is not None else raw_row_id()),
        model.lang == normalize_raw_lang(lang),
    ).one_or_none()


_SESSION_MEMO_KEY = "tarkov_raw_memo"


def session_memo(db: Session) -> dict[Any, Any] | None:
    """本事务内 raw 表头派生值（如 overlay token）的备忘；写 raw 或事务结束时清空。假 session 无 info 时为 None。"""
    info = getattr(db, "info", None)
    if not isinstance(info, dict):
        return None
    return info.setdefault(_SESSION_MEMO_KEY, {})


@event.listens_for(Session, "after_transaction_end")
def _drop_session_memo(session: Session, transaction: SessionTransaction) -> None:
    # 等锁后 db.commit() 再查时要看到别的线程刚写的 raw，备忘不能跨事务。
    if transaction.parent is None:
        session.info.pop(_SESSION_MEMO_KEY, None)


def decode_raw_json(raw_json: str | None) -> dict[str, Any] | None:
    try:
        payload = json.loads(_unpack_raw_json(raw_json or ""))
    except (TypeError, json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def locale_synced(db: Session, resource: str, *, lang: str = "zh") -> str:
    """同资源 locale 行的 synced_at。

    解析结果合了 locale（load_main_payload → load_locale_map），
    但主文件字节没变时 persist_raw 会保留 synced_at，
    所以只翻中文不改结构的上游更新只有 locale 这一行能反映出来。
    缓存键 / ETag 必须带上它，否则要重启才看得到新译文。
    """
    try:
        row = load_raw_row(db, resource, lang=lang)
    except Exception as exc:  # noqa: BLE001
        logger.warning("tarkov %s locale header unavailable: %s", resource, exc)
        return ""
    if row is None or row.synced_at is None:
        return ""
    return row.synced_at.isoformat()


def _raw_is_complete(resource: str, payload: dict[str, Any]) -> bool:
    """单文件落库前的形状校验：宁可整份丢，也不拿半截响应覆盖上一份好 raw。

    各资源复用自己的解析器（catalog / bosses / tasks …），避免两套判据漂移。
    """
    if not payload:
        return False
    data = unwrap_json_blob(payload)
    if resource == "items":
        from app.services.tarkov.items import items_container

        return bool(items_container(payload))

    if resource == "maps":
        from app.services.tarkov.bosses import _maps_blob, _mobs_blob

        return bool(_maps_blob(payload)) and bool(_mobs_blob(payload))

    if resource == "tasks":
        from app.services.tarkov.tasks import _tasks_map

        return bool(_tasks_map(payload))

    if resource == "traders":
        from app.services.tarkov.traders import _traders_map

        return bool(_traders_map(payload))

    if resource == "hideout":
        from app.services.tarkov.guides import parse_hideout_stations

        return bool(parse_hideout_stations({"hideout": data}))

    if resource in ("barters", "crafts"):
        # 空表是合法状态（{"data": []}），但 dict / 空数据不是。
        return isinstance(data, list)

    return bool(data)


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
    row = load_raw_row(db, resource, lang=lang, mode_id=mode_id, with_json=True)
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
    row = load_raw_row(db, resource, with_json=True)
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
    changed: bool | None = None,
) -> dict[str, Any]:
    """changed=True 表示上游确实换了字节（带校验头请求后仍 200）：跳过旧 blob 比对。

    超过 4MiB 的 JSON 先压成 gz1:，避免单条 UPDATE 冲过 16MiB 包上限。
    """
    now = now_naive()
    if upstream_at:
        note = f"{note} · 上游 {upstream_at}"
    raw_json = _pack_raw_json(json.dumps(payload, ensure_ascii=False))
    mode_id = raw_row_id()
    lang_key = normalize_raw_lang(lang)
    model = raw_model(resource)
    memo = session_memo(db)
    if memo is not None:
        memo.clear()
    row = load_raw_row(
        db,
        resource,
        lang=lang_key,
        mode_id=mode_id,
        with_json=changed is not True,
    )
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
    elif changed or row.raw_json != raw_json:
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


def notes_upstream_at(note: str | None) -> str | None:
    """从 note 尾部「· 上游 <iso>」取回上次的上游时间；取不到返回 None。"""
    text = (note or "").strip()
    marker = "上游 "
    idx = text.rfind(marker)
    if idx < 0:
        return None
    value = text[idx + len(marker):].strip()
    if not value:
        return None
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return None
    return value


def _to_http_date(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return format_datetime(parsed.astimezone(timezone.utc), usegmt=True)


def _not_modified(
    status_code: int,
    content: bytes,
    headers: Any,
) -> bool:
    return status_code == 304 and not content


def download_site_json(
    *,
    lang: str = "zh",
    on_progress: DumpProgress | None = None,
    validators: dict[str, str] | None = None,
) -> SiteDump:
    """拉 json.tarkov.dev 当前模式全部静态文件（含 locale）。单文件失败不中断。

    validators：key → 上次的上游时间；带上就发条件请求，304 的文件不必下载 / 落库
    （省掉 items ~17MB、maps ~8.6MB 的白下载）。
    """
    out: dict[str, dict[str, Any]] = {}
    unchanged: set[str] = set()
    changed: set[str] = set()
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

        url = json_resource_url(resource, lang=res_lang)
        expected = (validators or {}).get(key, "")
        headers: dict[str, str] = {}
        http_date = _to_http_date(expected)
        if http_date:
            headers["If-Modified-Since"] = http_date

        emit()
        try:
            if headers:
                resp = download_response(
                    url,
                    headers=headers,
                    timeout=60 if is_locale else 180,
                    error_cls=TarkovUpstreamError,
                    on_bytes=on_bytes,
                    max_bytes=TARKOV_DUMP_MAX_BYTES,
                )
                if _not_modified(resp.status_code, resp.content, resp.headers):
                    unchanged.add(key)
                    if expected:
                        upstream_times[key] = expected
                    logger.debug("tarkov dump %s/%s not modified", prefix, key)
                    emit(done=True)
                    continue
                payload = _decode_json(resp.content, label=key)
                upstream_at = http_last_modified_iso(getattr(resp, "headers", None))
                changed.add(key)
            else:
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
    downloaded = [
        name
        for name in JSON_RESOURCES
        if name in out and _raw_is_complete(name, out[name])
    ]
    if not downloaded and not unchanged:
        # 一份完整资源都没下到、也没有 304 短路 → 整站不可用；有 304 说明旧 raw 还在用。
        detail = "；".join(errors) if errors else "无文件"
        raise TarkovUpstreamError(f"json.tarkov.dev 全站为空：{detail}")
    return SiteDump(
        files=out,
        upstream_times=upstream_times,
        unchanged=frozenset(unchanged),
        changed=frozenset(changed),
    )


def persist_site_json(
    db: Session,
    dump: dict[str, dict[str, Any]],
    *,
    lang: str = "zh",
    upstream_times: dict[str, str] | None = None,
    on_progress: DumpProgress | None = None,
    unchanged: set[str] | None = None,
    changed: set[str] | None = None,
) -> list[dict[str, Any]]:
    """逐文件先验形状再落库：不完整的响应整份丢，上一份好 raw 原样留着。

    上游把某个文件换成 {"data":{}} / {"errors":[...]} 时，落库等于拿半截数据覆盖
    全量图鉴；这里按资源复用各自解析器（_raw_is_complete）判断，不通过就直接跳过。
    """
    rows: list[dict[str, Any]] = []
    prefix = json_api_prefix()
    times = upstream_times or {}
    skip = unchanged or set()
    modified = changed or set()
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
        if key in skip:
            rows.append(
                {
                    "id": domain_id,
                    "ok": True,
                    "status": "unchanged",
                    "source": None,
                    "synced_at": None,
                    "upstream_at": times.get(key),
                    "mode": mode,
                    "error": None,
                }
            )
            continue
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
        if res_lang:
            if not _locale_complete(payload):
                rows.append(
                    {
                        "id": domain_id,
                        "ok": False,
                        "status": "error",
                        "source": None,
                        "synced_at": None,
                        "upstream_at": None,
                        "mode": mode,
                        "error": "locale 内容为空",
                    }
                )
                continue
        elif not _raw_is_complete(resource, payload):
            logger.warning(
                "tarkov dump %s/%s 形状不完整，跳过落库保留旧 raw", prefix, key
            )
            rows.append(
                {
                    "id": domain_id,
                    "ok": False,
                    "status": "error",
                    "source": None,
                    "synced_at": None,
                    "upstream_at": None,
                    "mode": mode,
                    "error": "上游内容不完整，已保留上一份",
                }
            )
            continue
        try:
            saved = persist_raw(
                db,
                resource,
                payload,
                lang=res_lang,
                source=SOURCE_JSON_API,
                note=f"json.tarkov.dev/{prefix}/{key}",
                commit=False,
                upstream_at=times.get(key),
                changed=key in modified,
            )
        except TarkovUpstreamError as exc:
            logger.warning("tarkov dump %s/%s persist failed: %s", prefix, key, exc)
            rows.append(
                {
                    "id": domain_id,
                    "ok": False,
                    "status": "error",
                    "source": None,
                    "synced_at": None,
                    "upstream_at": None,
                    "mode": mode,
                    "error": str(exc),
                }
            )
            continue
        saved["id"] = domain_id
        saved["mode"] = mode
        saved["status"] = "ok" if saved.get("ok") else "error"
        rows.append(saved)
    try:
        db.commit()
    except OperationalError as exc:
        db.rollback()
        logger.exception("tarkov raw commit failed")
        raise TarkovUpstreamError(
            "图鉴 raw 写入时数据库连接被断开。请重试；仍失败的话把 max_allowed_packet 调到 64M"
        ) from exc
    return rows


def hydrate_unchanged_dump(
    db: Session,
    dump: dict[str, dict[str, Any]],
    unchanged: set[str] | frozenset[str],
    *,
    lang: str = "zh",
) -> None:
    """304 的文件不在本轮下载里。投影和补集仍要读上一份已落库的 raw。"""
    if not unchanged:
        return
    for resource, res_lang, _domain_id in site_dump_specs(lang=lang):
        key = resource_key(resource, lang=res_lang)
        if key not in unchanged or key in dump:
            continue
        try:
            payload = load_raw(db, resource, lang=res_lang)
        except Exception as exc:  # noqa: BLE001
            logger.warning("tarkov %s hydrate failed: %s", key, exc)
            continue
        if isinstance(payload, dict) and payload:
            dump[key] = payload


def stored_dump_validators(db: Session, *, lang: str = "zh") -> dict[str, str]:
    """从已落库 raw 的 note（「· 上游 <iso>」）取上次上游时间，条件请求用。

    不落校验头就没有新列：把 note 里已经记着的时间翻出来当 If-Modified-Since。
    """
    validators: dict[str, str] = {}
    for resource, res_lang, _domain_id in site_dump_specs(lang=lang):
        key = resource_key(resource, lang=res_lang)
        try:
            row = load_raw_row(db, resource, lang=res_lang)
        except Exception as exc:  # noqa: BLE001
            logger.warning("tarkov %s validator lookup failed: %s", key, exc)
            continue
        stamp = notes_upstream_at(row.note) if row is not None else None
        if stamp:
            validators[key] = stamp
    return validators


def _locale_complete(payload: dict[str, Any]) -> bool:
    data = unwrap_json_blob(payload)
    if isinstance(data, dict):
        return bool(data)
    if isinstance(data, list):
        return True
    return False


def locale_data(dump: dict[str, dict[str, Any]], resource: str, *, lang: str = "zh") -> dict[str, Any]:
    blob = dump.get(resource_key(resource, lang=lang))
    if not isinstance(blob, dict):
        return {}
    data = unwrap_json_blob(blob)
    return data if isinstance(data, dict) else {}

