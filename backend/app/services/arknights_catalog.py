"""明日方舟干员图鉴：从 ArknightsGameResource 同步 character_table。"""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.arknights import ArknightsCatalogMeta, ArknightsOperator
from app.services.skland_client import CHAR_AVATAR_CDN, PROFESSION_CN

logger = logging.getLogger(__name__)

CHARACTER_TABLE_URL = (
    "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/"
    "main/gamedata/excel/character_table.json"
)
VERSION_URL = (
    "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/version"
)

OPERATOR_PROFESSIONS = set(PROFESSION_CN.keys())
META_ROW_ID = 1
DOWNLOAD_TIMEOUT = 120


class ArknightsCatalogError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _http_get_bytes(url: str, *, timeout: int = DOWNLOAD_TIMEOUT) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "zhange-stats/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise ArknightsCatalogError(f"下载失败 HTTP {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise ArknightsCatalogError(f"无法连接资源站: {exc}") from exc


def _parse_rarity(raw: Any) -> int:
    try:
        rarity_idx = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        rarity_idx = 0
    if 0 <= rarity_idx <= 5:
        return rarity_idx + 1
    return max(1, min(6, rarity_idx))


def _is_playable_operator(char_id: str, data: dict[str, Any]) -> bool:
    if not char_id.startswith("char_"):
        return False
    profession = str(data.get("profession") or "")
    if profession not in OPERATOR_PROFESSIONS:
        return False
    if data.get("isNotObtainable") is True:
        return False
    # 过滤召唤物等：displayNumber 为空且无 appellation 的杂项少见；主要靠 profession
    return True


def parse_character_table(table: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for char_id, raw in table.items():
        if not isinstance(raw, dict):
            continue
        if not _is_playable_operator(str(char_id), raw):
            continue
        profession = str(raw.get("profession") or "")
        name = str(raw.get("name") or char_id).strip() or str(char_id)
        rarity = _parse_rarity(raw.get("rarity"))
        try:
            sort_id = int(raw.get("displayNumber") or 0)
        except (TypeError, ValueError):
            # displayNumber 可能是 "R001" 等，用 rarity*10000 兜底
            sort_id = rarity * 10000
        # displayNumber 非纯数字时用稳定排序键（跨进程一致）
        if not str(raw.get("displayNumber") or "").isdigit():
            digest = int(hashlib.md5(char_id.encode("utf-8")).hexdigest()[:6], 16)
            sort_id = rarity * 100000 + (digest % 100000)
        rows.append(
            {
                "char_id": str(char_id),
                "name": name[:64],
                "rarity": rarity,
                "profession": profession,
                "profession_label": PROFESSION_CN.get(profession, profession or "未知"),
                "sort_id": sort_id,
                "avatar_url": f"{CHAR_AVATAR_CDN}/{char_id}.png",
            }
        )
    rows.sort(key=lambda r: (-r["rarity"], r["sort_id"], r["char_id"]))
    return rows


def operator_count(db: Session) -> int:
    return db.query(ArknightsOperator).count()


def get_catalog_meta(db: Session) -> ArknightsCatalogMeta | None:
    return (
        db.query(ArknightsCatalogMeta)
        .filter(ArknightsCatalogMeta.id == META_ROW_ID)
        .one_or_none()
    )


def list_operators(db: Session) -> list[ArknightsOperator]:
    return (
        db.query(ArknightsOperator)
        .order_by(
            ArknightsOperator.rarity.desc(),
            ArknightsOperator.sort_id.asc(),
            ArknightsOperator.char_id.asc(),
        )
        .all()
    )


def ensure_catalog(db: Session) -> list[ArknightsOperator]:
    """图鉴为空时自动同步一次。"""
    if operator_count(db) == 0:
        sync_from_upstream(db)
    return list_operators(db)


def sync_from_upstream(db: Session) -> dict[str, Any]:
    """拉取 character_table 并全量替换图鉴。"""
    logger.info("syncing arknights character_table from upstream")
    raw = _http_get_bytes(CHARACTER_TABLE_URL)
    try:
        table = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArknightsCatalogError("character_table.json 解析失败") from exc
    if not isinstance(table, dict):
        raise ArknightsCatalogError("character_table.json 格式无效")

    version = ""
    try:
        version = _http_get_bytes(VERSION_URL, timeout=30).decode("utf-8").strip()
    except ArknightsCatalogError:
        logger.warning("failed to fetch ArknightsGameResource version file")

    rows = parse_character_table(table)
    if not rows:
        raise ArknightsCatalogError("未解析到可招募干员")

    db.query(ArknightsOperator).delete()
    now = now_naive()
    for row in rows:
        db.add(
            ArknightsOperator(
                char_id=row["char_id"],
                name=row["name"],
                rarity=row["rarity"],
                profession=row["profession"],
                profession_label=row["profession_label"],
                sort_id=row["sort_id"],
                avatar_url=row["avatar_url"],
                updated_at=now,
            )
        )

    meta = get_catalog_meta(db)
    if meta is None:
        meta = ArknightsCatalogMeta(id=META_ROW_ID)
        db.add(meta)
    meta.source_version = version or None
    meta.operator_count = len(rows)
    meta.synced_at = now
    meta.note = "yuanyan3060/ArknightsGameResource character_table"
    db.commit()

    logger.info("arknights catalog synced: %s operators, version=%s", len(rows), version)
    return {
        "operator_count": len(rows),
        "source_version": version or None,
        "synced_at": now.isoformat() if now else None,
    }
