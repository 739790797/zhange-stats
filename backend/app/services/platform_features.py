"""平台 / 游戏 / 任务功能开关（级联）。

存储于 system_configs.key = platform_features。
节点自身 enabled 与祖先共同决定 effective；关闭父级即整体不可用。
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig

PLATFORM_FEATURES_KEY = "platform_features"
_CACHE_TTL_SEC = 2.0

_flags_cache: dict[str, bool] | None = None
_flags_cache_at = 0.0
_cache_lock = threading.Lock()

# 树定义：为后续游戏 / 子任务预留层级。id 用点号表示祖先链。
# reserved=True：预留节点，UI 可展示但暂无独立门控，保存时忽略。
FEATURE_TREE: list[dict[str, Any]] = [
    {
        "id": "steam",
        "name": "Steam",
        "kind": "platform",
        "children": [
            {
                "id": "steam.presence",
                "name": "在线状态轮询",
                "kind": "job",
                "job_id": "steam_presence",
                "schedule": "interval",
            },
        ],
    },
    {
        "id": "skland",
        "name": "森空岛",
        "kind": "platform",
        "children": [
            {
                "id": "skland.checkin",
                "name": "每日签到",
                "kind": "job",
                "job_id": "skland_checkin",
            },
            {
                "id": "skland.arknights",
                "name": "明日方舟",
                "kind": "game",
                "children": [
                    {
                        "id": "skland.arknights.box_sync",
                        "name": "用户干员box",
                        "kind": "job",
                        "job_id": "arknights_box_sync",
                        "schedule": "cron",
                    },
                    {
                        "id": "skland.arknights.catalog_sync",
                        "name": "开源图鉴同步",
                        "kind": "job",
                        "job_id": "arknights_catalog_sync",
                        "schedule": "cron",
                    },
                ],
            },
            {
                "id": "skland.endfield",
                "name": "明日方舟：终末地",
                "kind": "game",
            },
        ],
    },
    {
        "id": "taygedo",
        "name": "塔吉多",
        "kind": "platform",
        "children": [
            {
                "id": "taygedo.checkin",
                "name": "每日签到",
                "kind": "job",
                "job_id": "taygedo_checkin",
            },
            {
                "id": "taygedo.exastris",
                "name": "异环",
                "kind": "game",
                "reserved": True,
            },
            {
                "id": "taygedo.tower",
                "name": "幻塔",
                "kind": "game",
                "reserved": True,
            },
        ],
    },
    {
        "id": "exilium",
        "name": "追放",
        "kind": "platform",
        "children": [
            {
                "id": "exilium.checkin",
                "name": "每日签到",
                "kind": "job",
                "job_id": "exilium_checkin",
            },
            {
                "id": "exilium.exchange",
                "name": "积分兑换",
                "kind": "feature",
            },
        ],
    },
    {
        "id": "kujiequ",
        "name": "库街区",
        "kind": "platform",
        "children": [
            {
                "id": "kujiequ.checkin",
                "name": "每日签到",
                "kind": "job",
                "job_id": "kujiequ_checkin",
            },
            {
                "id": "kujiequ.ww",
                "name": "鸣潮",
                "kind": "game",
                "reserved": True,
            },
            {
                "id": "kujiequ.pgr",
                "name": "战双帕弥什",
                "kind": "game",
                "reserved": True,
            },
        ],
    },
]

JOB_FEATURE_IDS: dict[str, str] = {
    "steam_presence": "steam.presence",
    "skland_checkin": "skland.checkin",
    "arknights_box_sync": "skland.arknights.box_sync",
    "arknights_catalog_sync": "skland.arknights.catalog_sync",
    "taygedo_checkin": "taygedo.checkin",
    "exilium_checkin": "exilium.checkin",
    "kujiequ_checkin": "kujiequ.checkin",
}

CHECKIN_PLATFORM_FEATURES: dict[str, str] = {
    "skland": "skland.checkin",
    "taygedo": "taygedo.checkin",
    "exilium": "exilium.checkin",
    "kujiequ": "kujiequ.checkin",
}

PLATFORM_SHORT_NAMES: dict[str, str] = {
    "steam": "Steam",
    "skland": "森空岛",
    "taygedo": "塔吉多",
    "exilium": "追放",
    "kujiequ": "库街区",
    "arknights_box": "用户干员box",
}


def _iter_nodes(
    nodes: list[dict[str, Any]] | None = None,
    *,
    ancestors: tuple[str, ...] = (),
):
    for node in nodes if nodes is not None else FEATURE_TREE:
        node_id = str(node["id"])
        yield node, ancestors
        children = node.get("children") or []
        if children:
            yield from _iter_nodes(children, ancestors=ancestors + (node_id,))


_ALL_FEATURE_IDS: list[str] = [str(n["id"]) for n, _ in _iter_nodes()]
_ALL_FEATURE_ID_SET: set[str] = set(_ALL_FEATURE_IDS)
_RESERVED_FEATURE_IDS: set[str] = {
    str(n["id"]) for n, _ in _iter_nodes() if n.get("reserved")
}


def all_feature_ids() -> list[str]:
    return list(_ALL_FEATURE_IDS)


def reserved_feature_ids() -> set[str]:
    return set(_RESERVED_FEATURE_IDS)


def default_features() -> dict[str, bool]:
    return {fid: True for fid in _ALL_FEATURE_IDS}


def invalidate_feature_cache() -> None:
    global _flags_cache, _flags_cache_at
    with _cache_lock:
        _flags_cache = None
        _flags_cache_at = 0.0


def load_feature_flags(db: Session) -> dict[str, bool]:
    global _flags_cache, _flags_cache_at
    now = time.monotonic()
    with _cache_lock:
        if _flags_cache is not None and now - _flags_cache_at < _CACHE_TTL_SEC:
            return dict(_flags_cache)

    base = default_features()
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == PLATFORM_FEATURES_KEY)
        .first()
    )
    if row:
        try:
            stored = json.loads(row.value or "{}")
        except json.JSONDecodeError:
            stored = {}
        if isinstance(stored, dict):
            flags = stored.get("features")
            if isinstance(flags, dict):
                for fid in base:
                    if fid in flags and flags[fid] is not None:
                        base[fid] = bool(flags[fid])
    # 预留节点始终视为开启（无独立门控）
    for fid in _RESERVED_FEATURE_IDS:
        base[fid] = True

    with _cache_lock:
        _flags_cache = dict(base)
        _flags_cache_at = time.monotonic()
    return base


def save_feature_flags(
    db: Session,
    features: dict[str, Any],
    *,
    commit: bool = True,
) -> dict[str, bool]:
    current = load_feature_flags(db)
    for key, value in features.items():
        if key in _RESERVED_FEATURE_IDS:
            continue
        if key in _ALL_FEATURE_ID_SET and value is not None:
            current[key] = bool(value)
    for fid in _RESERVED_FEATURE_IDS:
        current[fid] = True
    raw = json.dumps({"features": current}, ensure_ascii=False)
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == PLATFORM_FEATURES_KEY)
        .first()
    )
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=PLATFORM_FEATURES_KEY, value=raw))
    invalidate_feature_cache()
    if commit:
        db.commit()
    else:
        db.flush()
    global _flags_cache, _flags_cache_at
    with _cache_lock:
        _flags_cache = dict(current)
        _flags_cache_at = time.monotonic()
    return current


def is_feature_enabled_from_flags(
    flags: dict[str, bool], feature_id: str
) -> bool:
    """自身及全部祖先均为开启时才有效（基于已加载 flags）。"""
    parts = feature_id.split(".")
    for i in range(len(parts)):
        node_id = ".".join(parts[: i + 1])
        if node_id not in _ALL_FEATURE_ID_SET:
            return False
        if not flags.get(node_id, False):
            return False
    return True


def is_feature_enabled(db: Session, feature_id: str) -> bool:
    """自身及全部祖先均为开启时才有效。"""
    return is_feature_enabled_from_flags(load_feature_flags(db), feature_id)


def effective_features(db: Session) -> dict[str, bool]:
    flags = load_feature_flags(db)
    out: dict[str, bool] = {}
    for node, ancestors in _iter_nodes():
        fid = str(node["id"])
        enabled = bool(flags.get(fid, True))
        for anc in ancestors:
            if not flags.get(anc, True):
                enabled = False
                break
        out[fid] = enabled
    return out


def build_feature_tree(db: Session) -> list[dict[str, Any]]:
    """管理端树：含 enabled / effective / 调度配置。"""
    from app.services.scheduler_config import load_scheduler_config

    flags = load_feature_flags(db)
    sched = load_scheduler_config(db)

    def _walk(
        nodes: list[dict[str, Any]],
        ancestors: tuple[str, ...] = (),
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for node in nodes:
            fid = str(node["id"])
            parent_effective = all(flags.get(a, True) for a in ancestors)
            self_enabled = bool(flags.get(fid, True))
            item: dict[str, Any] = {
                "id": fid,
                "name": node["name"],
                "kind": node.get("kind") or "feature",
                "enabled": self_enabled,
                "effective": bool(parent_effective and self_enabled),
                "parent_effective": parent_effective,
                "reserved": bool(node.get("reserved")),
                "job_id": node.get("job_id"),
                "schedule": node.get("schedule"),
            }
            job_id = node.get("job_id")
            if job_id:
                job_cfg = sched.get(str(job_id)) or {}
                item["interval_minutes"] = job_cfg.get("interval_minutes")
                item["hour"] = job_cfg.get("hour")
                item["minute"] = job_cfg.get("minute")
            children = node.get("children") or []
            if children:
                item["children"] = _walk(children, ancestors + (fid,))
            result.append(item)
        return result

    return _walk(FEATURE_TREE)
