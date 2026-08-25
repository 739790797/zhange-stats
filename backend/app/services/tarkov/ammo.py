"""逃离塔科夫弹药：parse / 派生读模型。

共享回源见 tarkov_items（一次 items → 弹药+枪械派生）。
本模块保留 GraphQL/json 下载与解析，供 items 编排与单测使用。
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.tarkov import TarkovAmmo, TarkovAmmoMeta

logger = logging.getLogger(__name__)

TARKOV_GRAPHQL_URL = "https://api.tarkov.dev/graphql"
TARKOV_JSON_ITEMS_URL = "https://json.tarkov.dev/regular/items"
TARKOV_JSON_ITEMS_LOCALE_URL = "https://json.tarkov.dev/regular/items_{lang}"
TARKOVDATA_AMMO_URL = (
    "https://raw.githubusercontent.com/TarkovTracker/tarkovdata/"
    "master/ammunition.json"
)

SOURCE_GRAPHQL = "tarkov.dev"
SOURCE_JSON_API = "json.tarkov.dev"
SOURCE_TARKOVDATA = "tarkovdata"

META_ROW_ID = 1
DOWNLOAD_TIMEOUT = 120

_AMMO_QUERY = """
query AmmoSync($lang: LanguageCode) {
  ammo(lang: $lang) {
    caliber
    damage
    penetrationPower
    armorDamage
    ammoType
    initialSpeed
    accuracyModifier
    recoilModifier
    lightBleedModifier
    heavyBleedModifier
    item {
      id
      name
      shortName
      iconLink
      baseImageLink
    }
  }
}
""".strip()

_CALIBER_PREFIX_RE = re.compile(r"^Caliber", re.IGNORECASE)

# BSG 内部 caliber id → 展示名（仅收录可核对的解码，禁止启发式臆造）
# 来源：与 ammo/gun 共用同一张表，保证口径字符串一致。
_BSG_CALIBER_LABELS: dict[str, str] = {
    "Caliber1143x23ACP": ".45 ACP",
    "Caliber9x18PM": "9x18mm",
    "Caliber9x18PMM": "9x18mm PMM",
    "Caliber9x19PARA": "9x19mm",
    "Caliber9x21": "9x21mm",
    "Caliber9x33R": ".357 Magnum",
    "Caliber762x25TT": "7.62x25mm",
    "Caliber46x30": "4.6x30mm",
    "Caliber57x28": "5.7x28mm",
    "Caliber545x39": "5.45x39mm",
    "Caliber556x45NATO": "5.56x45mm",
    "Caliber58x42": "5.8x42mm",
    "Caliber68x51": "6.8x51mm",
    "Caliber762x35": ".300 Blackout",
    "Caliber762x39": "7.62x39mm",
    "Caliber762x51": "7.62x51mm",
    "Caliber762x54R": "7.62x54mm R",
    "Caliber784x49": ".308 Marlin Express",
    "Caliber9x39": "9x39mm",
    "Caliber93x64": "9.3x64mm",
    "Caliber366TKM": ".366 TKM",
    "Caliber127x33": ".50 AE",
    "Caliber127x55": "12.7x55mm",
    "Caliber127x99": ".50 BMG",
    "Caliber86x70": ".338 Lapua",
    "Caliber12g": "12/70",
    "Caliber20g": "20/70",
    "Caliber20x1mm": "20x1mm",
    "Caliber23x75": "23x75mm",
    "Caliber26x75": "26x75mm",
    "Caliber40x46": "40x46mm",
    "Caliber40mmRU": "40mm RU",
    "Caliber127x108": "12.7x108mm",
    "Caliber30x29": "30x29mm",
    "Caliber725": "72.5mm",
}


def normalize_caliber(raw: str | None) -> str:
    """口径规范化：只做白名单解码；未收录则去掉 Caliber 前缀原样保留，缺失为空。

    禁止用正则「猜」小数点位置（例如 127x55 会被错解成 1.27x55）。
    """
    text = (raw or "").strip()
    if not text:
        return ""
    mapped = _BSG_CALIBER_LABELS.get(text)
    if not mapped and not text.startswith("Caliber"):
        mapped = _BSG_CALIBER_LABELS.get(f"Caliber{text}")
    if mapped:
        return mapped
    # 上游已是展示名（GraphQL ammo 等）
    if text in _BSG_CALIBER_LABELS.values():
        return text
    aliases = {
        "5.56x45mm NATO": "5.56x45mm",
    }
    if text in aliases:
        return aliases[text]
    # 未收录的 BSG id：仅剥前缀，不补 mm、不插小数点
    if _CALIBER_PREFIX_RE.match(text):
        return _CALIBER_PREFIX_RE.sub("", text)
    return text


class TarkovAmmoError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class AmmoUpstreamBundle:
    """一次成功回源的原始包（落库前）。"""

    source: str
    payload: dict[str, Any]
    note: str


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


def _as_int(value: Any) -> int:
    """上游缺失时保持 0（列非空）；不把其它哨兵值写进去。"""
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


def _clean_item_names(
    item_id: str,
    *,
    name: str,
    short_name: str,
) -> tuple[str, str]:
    """去掉 json locale 占位；无名时用 id（真实主键，非臆造文案）。"""
    name = (name or "").strip()
    short_name = (short_name or "").strip()
    if name.endswith(" Name") and item_id in name:
        name = short_name
    if short_name.endswith(" ShortName") and item_id in short_name:
        short_name = ""
    if not name:
        name = short_name or item_id
    return name[:128], short_name[:64]


def _ammo_row(
    *,
    item_id: str,
    name: str,
    short_name: str,
    caliber_raw: Any,
    ammo_type_raw: Any,
    damage: Any,
    penetration: Any,
    armor_damage: Any,
    icon_link: Any = "",
    initial_speed: Any = 0,
    accuracy_modifier: Any = 0,
    recoil_modifier: Any = 0,
    light_bleed_modifier: Any = 0,
    heavy_bleed_modifier: Any = 0,
) -> dict[str, Any]:
    name, short_name = _clean_item_names(item_id, name=name, short_name=short_name)
    caliber_src = None if caliber_raw is None else str(caliber_raw or "")
    ammo_type = str(ammo_type_raw or "").strip()[:32]
    icon = str(icon_link or "").strip()[:512]
    return {
        "item_id": item_id[:64],
        "name": name,
        "short_name": short_name,
        "caliber": normalize_caliber(caliber_src)[:64],
        "ammo_type": ammo_type,
        "damage": _as_int(damage),
        "penetration": _as_int(penetration),
        "armor_damage": _as_int(armor_damage),
        "initial_speed": _as_float(initial_speed),
        "accuracy_modifier": _as_float(accuracy_modifier),
        "recoil_modifier": _as_float(recoil_modifier),
        "light_bleed_modifier": _as_float(light_bleed_modifier),
        "heavy_bleed_modifier": _as_float(heavy_bleed_modifier),
        "icon_link": icon,
    }


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
        rows.append(
            _ammo_row(
                item_id=item_id,
                name=str(item.get("name") or ""),
                short_name=str(item.get("shortName") or ""),
                caliber_raw=raw.get("caliber"),
                ammo_type_raw=raw.get("ammoType"),
                damage=raw.get("damage"),
                penetration=raw.get("penetrationPower"),
                armor_damage=raw.get("armorDamage"),
                icon_link=item.get("baseImageLink")
                or item.get("iconLink")
                or "",
                initial_speed=raw.get("initialSpeed"),
                accuracy_modifier=raw.get("accuracyModifier"),
                recoil_modifier=raw.get("recoilModifier"),
                light_bleed_modifier=raw.get("lightBleedModifier"),
                heavy_bleed_modifier=raw.get("heavyBleedModifier"),
            )
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
        # tarkovdata 无稳定 ammoType 字段时保持空，不猜测
        rows.append(
            _ammo_row(
                item_id=item_id,
                name=str(raw.get("name") or ""),
                short_name=str(raw.get("shortName") or ""),
                caliber_raw=raw.get("caliber"),
                ammo_type_raw=raw.get("ammoType") or ballistics.get("ammoType"),
                damage=ballistics.get("damage"),
                penetration=ballistics.get("penetrationPower"),
                armor_damage=ballistics.get("armorDamage"),
                initial_speed=ballistics.get("initialSpeed")
                or ballistics.get("velocity"),
                accuracy_modifier=ballistics.get("accuracyModifier")
                or ballistics.get("accuracy"),
                recoil_modifier=ballistics.get("recoilModifier")
                or ballistics.get("recoil"),
                light_bleed_modifier=ballistics.get("lightBleedModifier")
                or ballistics.get("lightBleedChance"),
                heavy_bleed_modifier=ballistics.get("heavyBleedModifier")
                or ballistics.get("heavyBleedChance"),
            )
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
        # 上游 categories 仅有 ammo/stackable-item/item，无手枪/步枪等细分；
        # 可用分类字段是 properties.ammoType。
        rows.append(
            _ammo_row(
                item_id=item_id,
                name=str(
                    locale.get(f"{item_id} Name")
                    or raw.get("name")
                    or locale.get(f"{item_id} ShortName")
                    or raw.get("shortName")
                    or ""
                ),
                short_name=str(
                    locale.get(f"{item_id} ShortName") or raw.get("shortName") or ""
                ),
                caliber_raw=props.get("caliber"),
                ammo_type_raw=props.get("ammoType") or raw.get("ammoType"),
                damage=props.get("damage"),
                penetration=props.get("penetrationPower"),
                armor_damage=props.get("armorDamage"),
                icon_link=raw.get("baseImageLink")
                or raw.get("iconLink")
                or "",
                initial_speed=props.get("initialSpeed"),
                accuracy_modifier=props.get("accuracyModifier"),
                recoil_modifier=props.get("recoilModifier"),
                light_bleed_modifier=props.get("lightBleedModifier"),
                heavy_bleed_modifier=props.get("heavyBleedModifier"),
            )
        )
    return rows


def parse_ammo_raw(source: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """按来源从 raw payload 解析派生行（纯函数，可单测 / 可重放）。"""
    src = (source or "").strip()
    if src == SOURCE_GRAPHQL:
        return parse_graphql_ammo(payload)
    if src == SOURCE_JSON_API:
        items_payload = payload.get("items")
        if not isinstance(items_payload, dict):
            raise TarkovAmmoError("json.tarkov.dev raw 缺少 items")
        locale = payload.get("locale")
        if locale is not None and not isinstance(locale, dict):
            locale = None
        return parse_json_api_ammo(items_payload, locale=locale)
    if src == SOURCE_TARKOVDATA:
        return parse_tarkovdata_ammo(payload)
    raise TarkovAmmoError(f"未知弹药 raw 来源: {src or '—'}")


def download_graphql_ammo(*, lang: str = "zh") -> AmmoUpstreamBundle:
    """拉取 GraphQL ammo 原始响应（不落库）。"""
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
        # 先校验可解析，再作为成功 raw（避免把 GraphQL errors 当成功落库）
        try:
            rows = parse_graphql_ammo(payload)
        except TarkovAmmoError as exc:
            last_error = exc
            continue
        if not rows:
            last_error = TarkovAmmoError("tarkov.dev ammo 为空")
            continue
        return AmmoUpstreamBundle(
            source=SOURCE_GRAPHQL,
            payload=payload,
            note="api.tarkov.dev GraphQL ammo",
        )
    if last_error:
        raise last_error
    raise TarkovAmmoError("tarkov.dev ammo 拉取失败")


def download_json_api_ammo(*, lang: str = "zh") -> AmmoUpstreamBundle:
    """json.tarkov.dev items + locale 信封（GraphQL 宕机回退）。"""
    raw = _http_request(TARKOV_JSON_ITEMS_URL, timeout=180)
    try:
        items_payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovAmmoError("json.tarkov.dev items 解析失败") from exc
    if not isinstance(items_payload, dict):
        raise TarkovAmmoError("json.tarkov.dev items 格式无效")

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
    rows = parse_ammo_raw(SOURCE_JSON_API, envelope)
    if not rows:
        raise TarkovAmmoError("json.tarkov.dev 未解析到弹药")
    return AmmoUpstreamBundle(
        source=SOURCE_JSON_API,
        payload=envelope,
        note="json.tarkov.dev/regular/items",
    )


def download_tarkovdata_ammo() -> AmmoUpstreamBundle:
    raw = _http_request(TARKOVDATA_AMMO_URL, timeout=90)
    try:
        table = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovAmmoError("tarkovdata ammunition.json 解析失败") from exc
    if not isinstance(table, dict):
        raise TarkovAmmoError("tarkovdata ammunition.json 格式无效")
    rows = parse_tarkovdata_ammo(table)
    if not rows:
        raise TarkovAmmoError("tarkovdata 未解析到弹药")
    return AmmoUpstreamBundle(
        source=SOURCE_TARKOVDATA,
        payload=table,
        note="TarkovTracker/tarkovdata ammunition.json",
    )


# 兼容旧测试 / 调用：下载并直接解析为行
def fetch_ammo_from_graphql(*, lang: str = "zh") -> list[dict[str, Any]]:
    return parse_ammo_raw(SOURCE_GRAPHQL, download_graphql_ammo(lang=lang).payload)


def fetch_ammo_from_json_api(*, lang: str = "zh") -> list[dict[str, Any]]:
    return parse_ammo_raw(SOURCE_JSON_API, download_json_api_ammo(lang=lang).payload)


def fetch_ammo_from_tarkovdata() -> list[dict[str, Any]]:
    return parse_ammo_raw(SOURCE_TARKOVDATA, download_tarkovdata_ammo().payload)


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


def replace_derived_ammo_rows(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    source: str,
    note: str,
    synced_at,
) -> None:
    if not rows:
        raise TarkovAmmoError("未解析到弹药数据")

    db.query(TarkovAmmo).delete()
    for row in rows:
        db.add(
            TarkovAmmo(
                item_id=row["item_id"],
                name=row["name"],
                short_name=row["short_name"],
                caliber=row["caliber"],
                ammo_type=row.get("ammo_type") or "",
                damage=row["damage"],
                penetration=row["penetration"],
                armor_damage=row["armor_damage"],
                initial_speed=float(row.get("initial_speed") or 0),
                accuracy_modifier=float(row.get("accuracy_modifier") or 0),
                recoil_modifier=float(row.get("recoil_modifier") or 0),
                light_bleed_modifier=float(row.get("light_bleed_modifier") or 0),
                heavy_bleed_modifier=float(row.get("heavy_bleed_modifier") or 0),
                icon_link=row.get("icon_link") or "",
                updated_at=synced_at,
            )
        )

    meta = get_ammo_meta(db)
    if meta is None:
        meta = TarkovAmmoMeta(id=META_ROW_ID)
        db.add(meta)
    meta.source = source
    meta.ammo_count = len(rows)
    meta.synced_at = synced_at
    meta.note = note


def ensure_ammo(db: Session) -> list[TarkovAmmo]:
    """确保弹药可读：委托共享 items 同步。"""
    from app.services.tarkov import items as items_svc

    try:
        items_svc.ensure_items(db)
    except items_svc.TarkovItemsError as exc:
        raise TarkovAmmoError(str(exc)) from exc
    return list_ammo(db)


def sync_from_upstream(db: Session) -> dict[str, Any]:
    """委托共享 items 回源（一次同步弹药+枪械）。"""
    from app.services.tarkov import items as items_svc

    try:
        return items_svc.sync_from_upstream(db)
    except items_svc.TarkovItemsError as exc:
        raise TarkovAmmoError(str(exc)) from exc
