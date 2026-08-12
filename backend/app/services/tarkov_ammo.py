"""逃离塔科夫弹药：从 tarkov.dev GraphQL 同步（失败时回退社区静态 JSON）。"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovAmmo, TarkovAmmoMeta

logger = logging.getLogger(__name__)

TARKOV_GRAPHQL_URL = "https://api.tarkov.dev/graphql"
TARKOV_JSON_ITEMS_URL = "https://json.tarkov.dev/regular/items"
TARKOV_JSON_ITEMS_LOCALE_URL = "https://json.tarkov.dev/regular/items_{lang}"
TARKOVDATA_AMMO_URL = (
    "https://raw.githubusercontent.com/TarkovTracker/tarkovdata/"
    "master/ammunition.json"
)

META_ROW_ID = 1
DOWNLOAD_TIMEOUT = 120
AMMO_JOB_KEY = "tarkov_ammo_sync"

_AMMO_QUERY = """
query AmmoSync($lang: LanguageCode) {
  ammo(lang: $lang) {
    caliber
    damage
    penetrationPower
    armorDamage
    item {
      id
      name
      shortName
    }
  }
}
""".strip()

_CALIBER_PREFIX_RE = re.compile(r"^Caliber", re.IGNORECASE)
_CALIBER_MM_SUFFIX_RE = re.compile(r"mm$", re.IGNORECASE)

# BSG 内部 caliber id → 展示名（对齐 Wiki / 社区习惯）
_BSG_CALIBER_LABELS: dict[str, str] = {
    "Caliber1143x23ACP": ".45 ACP",
    "Caliber9x18PM": "9x18mm",
    "Caliber9x19PARA": "9x19mm",
    "Caliber9x21": "9x21mm",
    "Caliber9x33R": ".357 Magnum",
    "Caliber762x25TT": "7.62x25mm",
    "Caliber46x30": "4.6x30mm",
    "Caliber57x28": "5.7x28mm",
    "Caliber545x39": "5.45x39mm",
    "Caliber556x45NATO": "5.56x45mm",
    "Caliber762x35": ".300 Blackout",
    "Caliber762x39": "7.62x39mm",
    "Caliber762x51": "7.62x51mm",
    "Caliber762x54R": "7.62x54mm R",
    "Caliber9x39": "9x39mm",
    "Caliber366TKM": ".366 TKM",
    "Caliber127x55": "12.7x55mm",
    "Caliber86x70": ".338 Lapua",
    "Caliber12g": "12/70",
    "Caliber20g": "20/70",
    "Caliber23x75": "23x75mm",
    "Caliber40x46": "40x46mm",
    "Caliber40mmRU": "40mm RU",
    "Caliber127x108": "12.7x108mm",
    "Caliber30x29": "30x29mm",
}


class TarkovAmmoError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _http_request(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DOWNLOAD_TIMEOUT,
) -> bytes:
    req_headers = {"User-Agent": "zhange-stats/1.0", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:  # noqa: BLE001
            detail = ""
        msg = f"下载失败 HTTP {exc.code}: {url}"
        if detail:
            msg = f"{msg} ({detail})"
        raise TarkovAmmoError(msg) from exc
    except urllib.error.URLError as exc:
        raise TarkovAmmoError(f"无法连接资源站: {exc}") from exc


def normalize_caliber(raw: str | None) -> str:
    """统一口径展示：优先 BSG 映射表，再做通用清洗。"""
    text = (raw or "").strip()
    if not text:
        return "未知"
    mapped = _BSG_CALIBER_LABELS.get(text)
    if not mapped and not text.startswith("Caliber"):
        mapped = _BSG_CALIBER_LABELS.get(f"Caliber{text}")
    if mapped:
        return mapped
    # GraphQL 可能直接给 5.45x39mm
    if text.endswith("mm") and text[:-2] + "mm" in {
        "5.45x39mm", "5.56x45mm", "9x18mm", "9x19mm", "9x21mm", "9x39mm",
        "7.62x25mm", "7.62x39mm", "7.62x51mm", "4.6x30mm", "5.7x28mm",
        "12.7x55mm", "12.7x108mm", "23x75mm", "40x46mm", "30x29mm",
    }:
        return text
    aliases = {
        "5.45x39mm": "5.45x39mm",
        "5.56x45mm": "5.56x45mm",
        "5.56x45mm NATO": "5.56x45mm",
    }
    if text in aliases:
        return aliases[text]
    text2 = _CALIBER_PREFIX_RE.sub("", text)
    text2 = _CALIBER_MM_SUFFIX_RE.sub("", text2)
    m = re.fullmatch(r"(\d)(\d{2})x(\d+)", text2)
    if m:
        return f"{m.group(1)}.{m.group(2)}x{m.group(3)}"
    m = re.fullmatch(r"(\d)(\d{2})x(\d+)([A-Za-z].*)", text2)
    if m:
        return f"{m.group(1)}.{m.group(2)}x{m.group(3)}{m.group(4)}"
    return text

def parse_graphql_ammo(payload: dict[str, Any]) -> list[dict[str, Any]]:
    errors = payload.get("errors")
    if errors:
        raise TarkovAmmoError(f"tarkov.dev GraphQL 错误: {errors}")
    data = payload.get("data") or {}
    rows_raw = data.get("ammo")
    if not isinstance(rows_raw, list):
        raise TarkovAmmoError("tarkov.dev ammo 响应无效")
    rows: list[dict[str, Any]] = []
    for raw in rows_raw:
        if not isinstance(raw, dict):
            continue
        item = raw.get("item") if isinstance(raw.get("item"), dict) else {}
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            continue
        name = str(item.get("name") or item.get("shortName") or item_id).strip()
        short_name = str(item.get("shortName") or "").strip()
        rows.append(
            {
                "item_id": item_id[:64],
                "name": name[:128],
                "short_name": short_name[:64],
                "caliber": normalize_caliber(str(raw.get("caliber") or ""))[:64],
                "damage": int(raw.get("damage") or 0),
                "penetration": int(raw.get("penetrationPower") or 0),
                "armor_damage": int(raw.get("armorDamage") or 0),
            }
        )
    return rows


def parse_tarkovdata_ammo(table: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, raw in table.items():
        if not isinstance(raw, dict):
            continue
        ballistics = raw.get("ballistics") if isinstance(raw.get("ballistics"), dict) else {}
        item_id = str(raw.get("id") or key).strip()
        if not item_id:
            continue
        name = str(raw.get("name") or raw.get("shortName") or item_id).strip()
        short_name = str(raw.get("shortName") or "").strip()
        rows.append(
            {
                "item_id": item_id[:64],
                "name": name[:128],
                "short_name": short_name[:64],
                "caliber": normalize_caliber(str(raw.get("caliber") or ""))[:64],
                "damage": int(ballistics.get("damage") or 0),
                "penetration": int(ballistics.get("penetrationPower") or 0),
                "armor_damage": int(ballistics.get("armorDamage") or 0),
            }
        )
    return rows


def parse_json_api_ammo(
    payload: dict[str, Any],
    *,
    locale: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """从 json.tarkov.dev/regular/items 解析 ItemPropertiesAmmo。"""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        raise TarkovAmmoError("json.tarkov.dev items 响应无效")
    items_raw = data.get("items")
    if isinstance(items_raw, dict):
        items_iter = items_raw.values()
    elif isinstance(items_raw, list):
        items_iter = items_raw
    else:
        raise TarkovAmmoError("json.tarkov.dev items 缺少 items 字段")

    locale = locale or {}
    rows: list[dict[str, Any]] = []
    for raw in items_iter:
        if not isinstance(raw, dict):
            continue
        props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
        if props.get("propertiesType") != "ItemPropertiesAmmo":
            continue
        item_id = str(raw.get("id") or "").strip()
        if not item_id:
            continue
        name = str(
            locale.get(f"{item_id} Name")
            or raw.get("name")
            or locale.get(f"{item_id} ShortName")
            or raw.get("shortName")
            or item_id
        ).strip()
        short_name = str(
            locale.get(f"{item_id} ShortName") or raw.get("shortName") or ""
        ).strip()
        # 过滤未解析的 locale key 占位
        if name.endswith(" Name") and item_id in name:
            name = short_name or item_id
        if short_name.endswith(" ShortName") and item_id in short_name:
            short_name = ""
        rows.append(
            {
                "item_id": item_id[:64],
                "name": name[:128],
                "short_name": short_name[:64],
                "caliber": normalize_caliber(str(props.get("caliber") or ""))[:64],
                "damage": int(props.get("damage") or 0),
                "penetration": int(props.get("penetrationPower") or 0),
                "armor_damage": int(props.get("armorDamage") or 0),
            }
        )
    return rows


def fetch_ammo_from_json_api(*, lang: str = "zh") -> list[dict[str, Any]]:
    """json.tarkov.dev 扁平 JSON（GraphQL 宕机时官网同款备用）。"""
    raw = _http_request(TARKOV_JSON_ITEMS_URL, timeout=180)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovAmmoError("json.tarkov.dev items 解析失败") from exc
    if not isinstance(payload, dict):
        raise TarkovAmmoError("json.tarkov.dev items 格式无效")

    locale: dict[str, Any] = {}
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

    rows = parse_json_api_ammo(payload, locale=locale)
    if not rows:
        raise TarkovAmmoError("json.tarkov.dev 未解析到弹药")
    return rows


def fetch_ammo_from_graphql(*, lang: str = "zh") -> list[dict[str, Any]]:
    """拉取 ammo；先试指定语言，失败再试无 lang（英文默认）。"""
    attempts: list[dict[str, Any] | None] = [{"lang": lang}, None]
    last_error: TarkovAmmoError | None = None
    for variables in attempts:
        body_obj: dict[str, Any] = {"query": _AMMO_QUERY}
        if variables is not None:
            body_obj["variables"] = variables
        else:
            body_obj["query"] = _AMMO_QUERY.replace(
                "query AmmoSync($lang: LanguageCode) {\n  ammo(lang: $lang) {",
                "query AmmoSync {\n  ammo {",
            )
        body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
        try:
            raw = _http_request(
                TARKOV_GRAPHQL_URL,
                method="POST",
                body=body,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            payload = json.loads(raw.decode("utf-8"))
        except TarkovAmmoError as exc:
            last_error = exc
            continue
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = TarkovAmmoError("tarkov.dev 响应解析失败")
            last_error.__cause__ = exc
            continue
        if not isinstance(payload, dict):
            last_error = TarkovAmmoError("tarkov.dev 响应格式无效")
            continue
        try:
            return parse_graphql_ammo(payload)
        except TarkovAmmoError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise TarkovAmmoError("tarkov.dev ammo 拉取失败")


def fetch_ammo_from_tarkovdata() -> list[dict[str, Any]]:
    raw = _http_request(TARKOVDATA_AMMO_URL, timeout=90)
    try:
        table = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovAmmoError("tarkovdata ammunition.json 解析失败") from exc
    if not isinstance(table, dict):
        raise TarkovAmmoError("tarkovdata ammunition.json 格式无效")
    return parse_tarkovdata_ammo(table)


def ammo_count(db: Session) -> int:
    return db.query(TarkovAmmo).count()


def get_ammo_meta(db: Session) -> TarkovAmmoMeta | None:
    return (
        db.query(TarkovAmmoMeta)
        .filter(TarkovAmmoMeta.id == META_ROW_ID)
        .one_or_none()
    )


def list_ammo(db: Session) -> list[TarkovAmmo]:
    return (
        db.query(TarkovAmmo)
        .order_by(
            TarkovAmmo.caliber.asc(),
            TarkovAmmo.penetration.asc(),
            TarkovAmmo.name.asc(),
        )
        .all()
    )


def ensure_ammo(db: Session) -> list[TarkovAmmo]:
    """弹药表为空时自动同步一次。"""
    if ammo_count(db) == 0:
        sync_from_upstream(db)
    return list_ammo(db)


def _replace_ammo_rows(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    source: str,
    note: str,
) -> dict[str, Any]:
    if not rows:
        raise TarkovAmmoError("未解析到弹药数据")

    db.query(TarkovAmmo).delete()
    now = now_naive()
    for row in rows:
        db.add(
            TarkovAmmo(
                item_id=row["item_id"],
                name=row["name"],
                short_name=row["short_name"],
                caliber=row["caliber"],
                damage=row["damage"],
                penetration=row["penetration"],
                armor_damage=row["armor_damage"],
                updated_at=now,
            )
        )

    meta = get_ammo_meta(db)
    if meta is None:
        meta = TarkovAmmoMeta(id=META_ROW_ID)
        db.add(meta)
    meta.source = source
    meta.ammo_count = len(rows)
    meta.synced_at = now
    meta.note = note
    db.commit()

    logger.info("tarkov ammo synced: %s rows via %s", len(rows), source)
    return {
        "ammo_count": len(rows),
        "source": source,
        "synced_at": now.isoformat() if now else None,
    }


def sync_from_upstream(db: Session) -> dict[str, Any]:
    """优先 GraphQL；失败依次回退 json.tarkov.dev、tarkovdata。"""
    logger.info("syncing tarkov ammo from upstream")
    errors: list[str] = []

    try:
        rows = fetch_ammo_from_graphql(lang="zh")
        return _replace_ammo_rows(
            db,
            rows,
            source="tarkov.dev",
            note="api.tarkov.dev GraphQL ammo",
        )
    except TarkovAmmoError as exc:
        errors.append(f"graphql: {exc}")
        logger.warning("tarkov.dev GraphQL ammo sync failed: %s", exc)

    try:
        rows = fetch_ammo_from_json_api(lang="zh")
        note = "json.tarkov.dev/regular/items"
        if errors:
            note = f"{note} (fallback; {errors[0][:160]})"
        return _replace_ammo_rows(
            db,
            rows,
            source="json.tarkov.dev",
            note=note,
        )
    except TarkovAmmoError as exc:
        errors.append(f"json: {exc}")
        logger.warning("json.tarkov.dev ammo sync failed: %s", exc)

    try:
        rows = fetch_ammo_from_tarkovdata()
        note = "TarkovTracker/tarkovdata ammunition.json"
        if errors:
            note = f"{note} (fallback; {'; '.join(errors)[:200]})"
        return _replace_ammo_rows(
            db,
            rows,
            source="tarkovdata",
            note=note,
        )
    except TarkovAmmoError:
        detail = "；".join(errors) if errors else "未知错误"
        raise TarkovAmmoError(f"弹药同步失败：{detail}；tarkovdata 亦失败") from None


def ammo_sync_job_wrapper() -> None:
    """定时同步塔科夫弹药数据。"""
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    job = JobRun(job_key=AMMO_JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_from_upstream(db)
        job.status = "ok"
        job.message = json.dumps(
            {
                "ammo_count": result.get("ammo_count"),
                "source": result.get("source"),
            },
            ensure_ascii=False,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov ammo sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
