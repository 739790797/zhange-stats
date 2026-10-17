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
    # Minecraft 页面已停用。
    # {
    #     "id": "minecraft_presence",
    #     "name": "Minecraft 在线时长轮询",
    #     "description": "轮询 Minecraft 在线名单，累计玩家在线/离线时长",
    #     "kind": "interval",
    #     "platform": "minecraft",
    # },
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
        "id": "game_schedule_arknights_sync",
        "name": "活动日历更新",
        "description": "从 game-schedule 同步明日方舟活动日历并落库",
        "kind": "cron",
        "platform": "arknights_schedule",
    },
    {
        "id": "game_schedule_endfield_sync",
        "name": "活动日历更新",
        "description": "从 game-schedule 同步终末地活动日历并落库",
        "kind": "cron",
        "platform": "endfield_schedule",
    },
    {
        "id": "tarkov_full_sync",
        "name": "攻略数据全量更新",
        "description": "回源 json.tarkov.dev 全文件与 tarkov-data-overlay，整站落本地库后再投影现有栏目",
        "kind": "cron",
        "platform": "tarkov_full",
    },
    {
        "id": "ror2_wiki_sync",
        "name": "图鉴数据更新",
        "description": "回源 riskofrain2.wiki.gg 的 Module 命名空间全部页面，以及每个幸存者词条。图鉴用的十份模块解析不过就不覆盖；其余模块只存原文",
        "kind": "cron",
        "platform": "ror2_wiki",
    },
    {
        "id": "ror2_weblate_sync",
        "name": "图鉴译文",
        "description": "把每份已落库的 Wiki 原文拆成字符串推到 Weblate。Lua 表按路径编号；有令牌的挂在令牌下。已审且原文未变的译文写回快照",
        "kind": "cron",
        "platform": "ror2_weblate",
    },
    {
        "id": "texteller_model_sync",
        "name": "公式识别模型",
        "description": "对照 hf-mirror 上的 OleehyO/TexTeller 更新本地公式识别权重（data/models/texteller）",
        "kind": "cron",
        "platform": "zhange",
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
        "id": "mihoyo_checkin",
        "name": "米游社每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "mihoyo",
    },
    {
        "id": "job_runs_prune",
        "name": "任务日志清理",
        "description": "删除超过保留期的 job_runs 与 *_checkin_logs（默认 90 天）；上卷 Minecraft 性能采样；删除超过 14 天的浏览器 RUM 样本",
        "kind": "cron",
        "platform": None,
    },
]

_CHECKIN_PLATFORMS = frozenset({"skland", "taygedo", "exilium", "kujiequ", "mihoyo"})
# 与侧栏平台菜单顺序一致（不含 Steam）
CHECKIN_PLATFORM_ORDER: tuple[str, ...] = (
    "skland",
    "taygedo",
    "kujiequ",
    "mihoyo",
    "exilium",
)
_KNOWN_JOB_IDS = {str(m["id"]) for m in JOB_CATALOG}
_PLATFORM_TO_JOB = {str(m["platform"]): str(m["id"]) for m in JOB_CATALOG if m.get("platform")}
