"""定时任务目录与平台映射。"""
from __future__ import annotations

from typing import Any

JOB_CATALOG: list[dict[str, Any]] = [
    {
        "id": "steam_presence",
        "name": "Steam 在线状态轮询",
        "description": "轮询圈子成员 Steam 在线状态与游玩记录",
        "kind": "interval",
        "platform": "steam",
    },
    {
        "id": "skland_checkin",
        "name": "森空岛每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "skland",
    },
    {
        "id": "arknights_box_sync",
        "name": "干员练度更新",
        "description": "按绑定用户同步森空岛干员练度快照（技能 / 模组等）",
        "kind": "cron",
        "platform": "arknights_box",
    },
    {
        "id": "arknights_catalog_sync",
        "name": "游戏资源更新",
        "description": "从 yuanyan3060/ArknightsGameResource 同步 character_table",
        "kind": "cron",
        "platform": "arknights_catalog",
    },
    {
        "id": "tarkov_ammo_sync",
        "name": "弹药数据更新",
        "description": "从 tarkov.dev GraphQL 同步弹药（失败回退 json.tarkov.dev / tarkovdata）",
        "kind": "cron",
        "platform": "tarkov_ammo",
    },
    {
        "id": "tarkov_gun_sync",
        "name": "枪械数据更新",
        "description": "从 tarkov.dev GraphQL 同步枪械（失败回退 json.tarkov.dev）",
        "kind": "cron",
        "platform": "tarkov_gun",
    },
    {
        "id": "taygedo_checkin",
        "name": "塔吉多每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "taygedo",
    },
    {
        "id": "exilium_checkin",
        "name": "追放社区每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "exilium",
    },
    {
        "id": "kujiequ_checkin",
        "name": "库街区每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "kujiequ",
    },
    {
        "id": "job_runs_prune",
        "name": "任务日志清理",
        "description": "删除超过保留期的 job_runs 与 *_checkin_logs（默认 90 天，可配 retention_days）",
        "kind": "cron",
        "platform": None,
    },
]

_CHECKIN_PLATFORMS = frozenset({"skland", "taygedo", "exilium", "kujiequ"})
# 与侧栏平台菜单顺序一致（不含 Steam）
CHECKIN_PLATFORM_ORDER: tuple[str, ...] = (
    "skland",
    "taygedo",
    "exilium",
    "kujiequ",
)
_KNOWN_JOB_IDS = {str(m["id"]) for m in JOB_CATALOG}
_PLATFORM_TO_JOB = {str(m["platform"]): str(m["id"]) for m in JOB_CATALOG if m.get("platform")}
