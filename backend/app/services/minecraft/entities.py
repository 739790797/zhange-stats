"""经 RCON 读取 NeoForge/Forge `entity list`，按类型与类别汇总。"""

from __future__ import annotations

import re
from typing import Any

from app.services.minecraft.rcon import MinecraftRconError, rcon_exec
from app.services.minecraft.status import strip_section_codes

_TYPE_RE = re.compile(
    r"(?m)^\s*(\d+)\s*:\s*([a-z0-9_.-]+:[a-z0-9_./-]+)\s*$",
    re.I,
)
_INLINE_RE = re.compile(
    r"(\d+)\s*:\s*([a-z0-9_.-]+:[a-z0-9_./-]+)",
    re.I,
)
_PREFIXES = ("neoforge", "forge")
_EXTRA_DIMS = ("minecraft:the_nether", "minecraft:the_end")
TYPE_CAP = 40

HOSTILE = frozenset(
    {
        "blaze",
        "bogged",
        "breeze",
        "cave_spider",
        "creaking",
        "creeper",
        "drowned",
        "elder_guardian",
        "ender_dragon",
        "enderman",
        "endermite",
        "evoker",
        "ghast",
        "giant",
        "guardian",
        "hoglin",
        "husk",
        "illusioner",
        "magma_cube",
        "phantom",
        "piglin",
        "piglin_brute",
        "pillager",
        "ravager",
        "shulker",
        "silverfish",
        "skeleton",
        "slime",
        "spider",
        "stray",
        "vex",
        "vindicator",
        "warden",
        "witch",
        "wither",
        "wither_skeleton",
        "zoglin",
        "zombie",
        "zombie_villager",
        "zombified_piglin",
    }
)
DROPS = frozenset({"item", "experience_orb"})
PROJECTILES = frozenset(
    {
        "arrow",
        "spectral_arrow",
        "trident",
        "snowball",
        "egg",
        "ender_pearl",
        "eye_of_ender",
        "potion",
        "experience_bottle",
        "firework_rocket",
        "fireball",
        "small_fireball",
        "dragon_fireball",
        "wither_skull",
        "shulker_bullet",
        "llama_spit",
        "fishing_bobber",
        "wind_charge",
        "breeze_wind_charge",
        "evoker_fangs",
    }
)
DISPLAYS = frozenset(
    {
        "armor_stand",
        "item_frame",
        "glow_item_frame",
        "painting",
        "leash_knot",
        "block_display",
        "item_display",
        "text_display",
        "interaction",
        "marker",
    }
)
CATEGORY_ORDER = (
    "player",
    "drop",
    "hostile",
    "passive",
    "projectile",
    "vehicle",
    "display",
    "mod",
    "other",
)


def parse_entity_list(raw: str) -> list[dict[str, Any]]:
    """从 `neoforge entity list` / `forge entity list` 文本抽出类型计数。"""
    text = strip_section_codes(raw or "").replace("\r", "\n")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _TYPE_RE.finditer(text):
        entity_id = match.group(2).lower()
        if entity_id in seen:
            continue
        seen.add(entity_id)
        rows.append({"id": entity_id, "count": int(match.group(1))})
    if rows:
        return rows
    for match in _INLINE_RE.finditer(text):
        entity_id = match.group(2).lower()
        if entity_id in seen:
            continue
        seen.add(entity_id)
        rows.append({"id": entity_id, "count": int(match.group(1))})
    return rows


def entity_category(entity_id: str) -> str:
    ns, sep, path = entity_id.lower().partition(":")
    if not sep:
        path = ns
        ns = "minecraft"
    if ns != "minecraft":
        return "mod"
    if path == "player":
        return "player"
    if path in DROPS:
        return "drop"
    if path in HOSTILE:
        return "hostile"
    if path in PROJECTILES or path.endswith("_fireball") or path.endswith("_bullet"):
        return "projectile"
    if "minecart" in path or path.endswith("_boat") or path.endswith("_raft"):
        return "vehicle"
    if path in DISPLAYS:
        return "display"
    if path:
        return "passive"
    return "other"


def _merge_counts(
    dest: dict[str, int], rows: list[dict[str, Any]]
) -> dict[str, int]:
    for row in rows:
        entity_id = str(row.get("id") or "").strip().lower()
        if not entity_id:
            continue
        dest[entity_id] = dest.get(entity_id, 0) + int(row.get("count") or 0)
    return dest


def summarize_entities(
    counts: dict[str, int],
    *,
    command: str = "",
    worlds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    types = [
        {
            "id": entity_id,
            "name": entity_id.split(":", 1)[-1],
            "count": count,
            "category": entity_category(entity_id),
        }
        for entity_id, count in counts.items()
        if count > 0
    ]
    types.sort(key=lambda row: (-int(row["count"]), str(row["id"])))
    buckets: dict[str, int] = {key: 0 for key in CATEGORY_ORDER}
    for row in types:
        key = str(row["category"])
        buckets[key] = buckets.get(key, 0) + int(row["count"])
    categories = [
        {"key": key, "count": buckets[key]}
        for key in CATEGORY_ORDER
        if buckets.get(key)
    ]
    total = sum(int(row["count"]) for row in types)
    return {
        "total": total,
        "command": command,
        "categories": categories,
        "types": types[:TYPE_CAP],
        "type_count": len(types),
        "worlds": worlds or [],
    }


def query_entities(
    host: str,
    port: int,
    password: str,
    *,
    timeout: float = 8.0,
) -> dict[str, Any]:
    last_error = "无法读取实体列表"
    for prefix in _PREFIXES:
        command = f"{prefix} entity list"
        try:
            text = rcon_exec(host, port, password, command, timeout=timeout)
        except MinecraftRconError as exc:
            last_error = exc.message
            if any(key in exc.message for key in ("密码", "连接", "超时", "地址", "端口")):
                raise
            continue
        except OSError as exc:
            raise MinecraftRconError(str(exc) or "无法连接 RCON") from exc
        rows = parse_entity_list(text)
        if not rows and "unknown" in (text or "").lower():
            last_error = "当前核心没有 entity list 命令（需要 NeoForge / Forge）"
            continue
        counts: dict[str, int] = {}
        worlds: list[dict[str, Any]] = []
        _merge_counts(counts, rows)
        default_total = sum(int(row["count"]) for row in rows)
        if default_total:
            worlds.append({"id": "minecraft:overworld", "total": default_total})
        for dim in _EXTRA_DIMS:
            extra_cmd = f"{prefix} entity list * {dim}"
            try:
                extra = rcon_exec(host, port, password, extra_cmd, timeout=timeout)
            except (MinecraftRconError, OSError):
                continue
            extra_rows = parse_entity_list(extra)
            if not extra_rows:
                continue
            _merge_counts(counts, extra_rows)
            worlds.append(
                {
                    "id": dim,
                    "total": sum(int(row["count"]) for row in extra_rows),
                }
            )
        if not counts:
            last_error = "当前维度没有实体"
            continue
        return summarize_entities(counts, command=command, worlds=worlds)
    raise MinecraftRconError(last_error)
