"""逃离塔科夫 BOSS：json.tarkov.dev maps + mobs，读时用物品 raw 填特殊战利品价格。"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovBossesMeta, TarkovBossesRaw
from app.services.tarkov_ammo import SOURCE_JSON_API
from app.services.tarkov_tasks import TRADER_BY_ID

logger = logging.getLogger(__name__)

META_ROW_ID = 1
RAW_ROW_ID = 1
BOSSES_JOB_KEY = "tarkov_bosses_sync"
DOWNLOAD_TIMEOUT = 180
LOOT_VALUE_CUTOFF = 80_000

TARKOV_JSON_MAPS_URL = "https://json.tarkov.dev/regular/maps"
TARKOV_JSON_MAPS_LOCALE_URL = "https://json.tarkov.dev/regular/maps_{lang}"

SLUG_ALIASES = {
    "goons": "knight",
    "the-goons": "knight",
    "cultists": "cultist-priest",
    "cultist": "cultist-priest",
    "bear": "vs-rf",
    "usec": "vs-rf-sniper",
}

# json dump 里 vsRF / vsRFSniper / Sentry 共用 normalizedName=af，中文还可能撞名。
MOB_DISPLAY_NAMES: dict[str, str] = {
    "vsRF": "BEAR",
    "vsRFSniper": "USEC",
}

NICKNAMES: dict[str, str] = {
    "reshala": "沙拉",
    "tagilla": "锤哥",
    "glukhar": "火车头",
    "knight": "骑士",
    "big-pipe": "大管",
    "birdeye": "鸟眼",
}

BEHAVIOR_ZH: dict[str, str] = {
    "Patrol": "巡逻",
    "Rush": "突击",
    "Stalker": "潜行",
    "Tank": "坦克",
    "Hostile and accurate": "敌对且精准",
    "Patrol and highly armored": "巡逻，重装甲",
    "Group patrol": "小队巡逻",
    "Frequent healing and stim injections": "频繁治疗与注射",
    "Sniper": "狙击",
    "Batshit insane": "完全疯了",
}

BODY_PART_ORDER = (
    "Chest",
    "Head",
    "LeftArm",
    "RightArm",
    "LeftLeg",
    "RightLeg",
    "Stomach",
)

BODY_PART_ZH: dict[str, str] = {
    "Chest": "胸腔",
    "Head": "头部",
    "LeftArm": "左臂",
    "RightArm": "右臂",
    "LeftLeg": "左腿",
    "RightLeg": "右腿",
    "Stomach": "胃部",
}

MAP_ZH: dict[str, str] = {
    "factory": "工厂",
    "night-factory": "夜间工厂",
    "customs": "海关",
    "woods": "森林",
    "shoreline": "海岸线",
    "interchange": "立交桥",
    "reserve": "储备站",
    "lighthouse": "灯塔",
    "the-lab": "实验室",
    "the-lab-dark": "暗室",
    "streets-of-tarkov": "塔科夫街区",
    "ground-zero": "中心区",
    "ground-zero-21": "中心区 21+",
    "the-labyrinth": "迷宫",
    "icebreaker": "破冰船",
    "terminal": "码头",
}

BOSS_STATIC: dict[str, dict[str, str]] = {
    "rogue": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/Rogues",
        "behavior": "Patrol",
    },
    "raider": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/raiders",
        "behavior": "Rush",
    },
    "kaban": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/kaban",
        "behavior": "Tank",
    },
    "cultist-priest": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/cultists",
        "behavior": "Stalker",
    },
    "knight": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/knight",
        "behavior": "Rush",
    },
    "glukhar": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/glukhar",
        "behavior": "Hostile and accurate",
    },
    "killa": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/killa",
        "behavior": "Patrol and highly armored",
    },
    "reshala": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/reshala",
        "behavior": "Group patrol",
    },
    "sanitar": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/sanitar",
        "behavior": "Frequent healing and stim injections",
    },
    "shturman": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/shturman",
        "behavior": "Sniper",
    },
    "tagilla": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/tagilla",
        "behavior": "Batshit insane",
    },
    "zryachiy": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/Zryachiy",
        "behavior": "Sniper",
    },
    "kollontay": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/Kollontay",
        "behavior": "",
    },
    "partisan": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/Partisan",
        "behavior": "",
    },
    "black-div": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/Black_Division",
        "behavior": "",
    },
    "shadow-of-tagilla": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/Shadow_of_Tagilla",
        "behavior": "Batshit insane",
    },
    "the-wedge": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/The_Wedge",
        "behavior": "",
    },
    "the-wedge-labs": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/The_Wedge",
        "behavior": "",
    },
    "Sentry": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/Scavs",
        "behavior": "Patrol",
    },
    "vsRF": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/BEAR",
        "behavior": "",
    },
    "vsRFSniper": {
        "wiki": "https://escapefromtarkov.fandom.com/wiki/USEC",
        "behavior": "Sniper",
    },
}

# tarkov.dev zh/bosses.json（行为长文 / 简介）
BOSS_I18N: dict[str, dict[str, str]] = {
    "cultist-priest": {
        "description": "潜行的家伙。邪教徒以 3-5 人一组潜伏在阴影中，等待玩家靠近。他们会悄无声息地接近敌人，用普通刀具或祭司专用的淬毒邪教匕首进行刺杀。若遭到射击，邪教徒会使用枪支和手榴弹还击。用刀攻击玩家后，他们可能会再次跑进树林，重新隐入阴影。",
    },
    "knight": {
        "description": "“The Goons”的首领。可在多张地图中刷新。",
    },
    "glukhar": {
        "bio": "关于他过往活动的可靠信息无从考证，因为所有文件要么遗失要么被列为机密，但据未经证实的消息，他曾拥有士官军衔。他参与过战斗行动，精通战术基础，并在争夺或保卫各类领土时积极运用这些知识。他的所有队员似乎也都曾是军人。尽管如今他的帮派实质上只是一个为塔科夫资源与影响力而战的土匪团体。他与有能力从诺文斯克地区运出货品的商人有联系，这些商人会定期为他派出最后仍在运营的货运列车。",
        "description": "Glukhar 及其众多守卫极具敌意。在开阔地带与他们交战极难成功。狭窄走廊和封闭房间是更理想的选择。Glukhar 及其守卫枪法极准。他们会始终聚集行动，守卫们会跟随 Glukhar 前往任何地点。",
    },
    "kaban": {
        "bio": "他曾在塔科夫经营合法小生意，但也不惮使用犯罪手段敛财。全面撤离后他留在城内，其帮派规模日益壮大。",
        "description": "魁梧体型使他能无需架枪就持续射击各种重机枪，但同时，Kaban 无法灵活移动，因此在战斗中，他要么固守阵地，要么在点位间缓慢移动。其人拥有大量武装护卫，其中不乏前军人，为他组织起了严密防御。该 Boss 驻扎在“塔科夫街区”的汽车修理厂区域。该区域防御森严，入口处配备固定机枪和 AGS 榴弹发射器，通道布有地雷，汽车服务中心屋顶部署有狙击手。Kaban 使用定制装具携带机枪弹药箱，外衣下穿着防弹装甲，在护卫中拥有绝对权威。附近的 Scav 会协助首领防御并为 Kaban 而战。",
    },
    "killa": {
        "description": "塔科夫的终极猛男。Killa 使用轻机枪或其他自动武器压制敌人，同时在掩体间潜行接近目标发动最终突击。进攻时他以之字形移动，运用烟雾弹和破片手榴弹，用自动火力无情压制敌人。他会超出巡逻范围长距离追击目标，若被他锁定只有远遁才能摆脱。",
    },
    "kollontay": {
        "bio": "他曾是内务部军官，在执法部门服役时就以品行恶劣著称，同事有时都畏惧其行径。任职期间他常使用最爱的审讯方式——橡胶警棍，以及其他非常规手段打压不合其意者。凭借强健体魄和大胆性情，在 TerraGroup 丑闻爆发后组建帮派，开始从事自己昔日本该打击的勾当——抢劫与匪帮活动。其实在冲突前他就常为当地“商人”提供保护，例如与 Kaban 的良好关系便广为人知。",
        "description": "Kollontay 护卫数量较少，偏好固守某处，偶尔巡逻领地。若自觉占据上风，可能会切换使用警棍。他活跃在 Klimov 购物中心，以及内务部塔科夫学院周边区域。",
    },
    "partisan": {
        "bio": "其过往可靠细节寥寥，但可知曾在阿富汗服役，其激进的作战方式于此扎根。人称“游击队员”，以布设陷阱与地雷的专长恶名昭彰。他歼灭敌人的声誉常源于利用对方大意攻其不备。游击战术知识使他成为危险对手，能将任何地点——无论森林或建筑——化为致命陷阱。幸存足够久并洞悉其手法者或能赢得他的青睐，但前提是能在为时已晚前识破陷阱。",
    },
    "raider": {
        "description": "Scav 掠夺者（简称“掠夺者”）是进阶版 Scav，比普通 Scav 更具战术性与战斗力。他们配备更危险的武器与高级弹药，同时拥有更精准的枪法，常仅用数发子弹就击倒重装玩家（或直接爆头秒杀）。Scav 掠夺者以小组形式巡逻，通常可通过独特装备、语音与攻击性进行辨识。初始对所有其他 Scav（包括玩家 Scav）友善，但若无视口头警告靠近则会转为敌对。若有 Scav 激怒他们，会对全体 Scav 敌对。",
    },
    "reshala": {
        "description": "他通常试图待在战斗后方避开玩家视线，且从不穿戴护甲。玩家 Scav 需注意：若 Scav 声望等级较低，Reshala 或其守卫会无端攻击你，或因你过于接近 Reshala 而开火。其守卫有时会对低声望玩家 Scav 发出警告后再转为敌对。",
    },
    "rogue": {
        "description": "游荡者守卫着灯塔地图的污水处理厂及周边区域。主要行为是巡逻，但常会在屋顶占据防御位置并使用固定武器。他们会攻击所有进入区域的玩家，但对 Scav 和 USEC 阵营的 PMC 稍显宽容。游荡者因高生命值、激光般精准的枪法及超远射程而极度危险。受伤时，他们会跑向掩体并使用医疗物品。",
    },
    "sanitar": {
        "bio": "前医生与科学家，曾为 TerraGroup 工作。他在实验室领导多个项目，包括开发新型精神活性物质。研究领域涵盖各种条件对人体影响至神经刺激素研发。除 TerraGroup 实验室外，他在蔚蓝海岸疗养院设有私人办公室，亦在此进行研究——尤其是在全面撤离前的最后数周。他常随医疗队前往热点地区出差，为企业工作后定期巡视非洲及其他办事处督导研发。在同事中享有毋庸置疑的权威与尊敬。",
        "description": "交战时他会与 Scav 同伴及护卫协同作战，但又常常会脱离战线治疗或注射药物。携带大量医疗物资，可能会导向持久战。",
    },
    "shturman": {
        "description": "Shturman 及其追随者会在伐木场远距离与玩家交战，偏好保持距离而不擅近距离战斗。",
    },
    "tagilla": {
        "description": "完全是个疯子，会试图用锤子砸碎你。但若你处于他无法路径找到的位置（如横梁），他会使用副武器（通常为霰弹枪）远程攻击。他在战局开始时便被会激活。此 Boss 会设置伏击、展开压制火力并在需要时实施突破。",
    },
    "zryachiy": {
        "bio": "塔科夫最神秘人物之一。其过往几乎无人知晓，仅知受过狙击训练，遥传曾多次出入中东与非洲热点地区。早在冲突爆发前，他就成为 Lightkeeper 的忠犬，积极参与建立 Lightkeeper 与所有合作者之间的联系。已知与游荡者团体及在各地绘制神秘符号的兜帽人交好。Zryachiy 沉默寡言，但共事者常能心领神会。关于其眼睛的传闻众多，有人说是先天特征，有人指认是某种增强暗视能力的眼药水导致眼球泛白的副作用。尽管外观如此，他似乎正是因卓越视力得名——这对前军用狙击手而言并不意外。",
        "description": "Lightkeeper 的邪教护卫。",
    },
}

_parsed_lock = threading.Lock()
_parsed_cache: tuple[str, list[dict[str, Any]]] | None = None


class TarkovBossesError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class BossesUpstreamBundle:
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
        raise TarkovBossesError(msg) from exc
    except urllib.error.URLError as exc:
        raise TarkovBossesError(f"无法连接资源站: {exc}") from exc


def _as_int(value: Any, default: int | None = 0) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _id_of(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("_id") or "").strip()
    if value is None:
        return ""
    return str(value).strip()


def resolve_boss_slug(slug: str) -> str:
    key = (slug or "").strip().lower()
    return SLUG_ALIASES.get(key, key)


def _maps_blob(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return {}
    blob = data.get("maps")
    return blob if isinstance(blob, dict) else {}


def _mobs_blob(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return {}
    blob = data.get("mobs")
    if isinstance(blob, dict):
        return blob
    return payload.get("mobs") if isinstance(payload.get("mobs"), dict) else {}


def _locale_lookup(locale: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if not key:
            continue
        val = locale.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _map_zh(raw: dict[str, Any], locale: dict[str, Any]) -> str:
    map_id = str(raw.get("id") or "").strip()
    slug = str(raw.get("normalizedName") or "").strip()
    loc = _locale_lookup(locale, f"{map_id} Name", map_id)
    if loc:
        return loc
    if slug in MAP_ZH:
        return MAP_ZH[slug]
    return str(raw.get("name") or slug or map_id)


def _mob_name(mob_id: str, raw: dict[str, Any], locale: dict[str, Any]) -> str:
    override = MOB_DISPLAY_NAMES.get(mob_id)
    if override:
        return override
    loc = _locale_lookup(locale, mob_id, f"{mob_id} Name")
    if loc and loc.lower() != mob_id.lower():
        return loc
    slug = str(raw.get("normalizedName") or "").strip()
    if slug:
        return slug.replace("-", " ").title()
    name = str(raw.get("name") or "").strip()
    return name or mob_id


def _behavior_zh(behavior: str) -> str:
    text = (behavior or "").strip()
    if not text:
        return ""
    return BEHAVIOR_ZH.get(text, text)


def _body_part_zh(part_id: str, locale_key: str, locale: dict[str, Any]) -> str:
    loc = _locale_lookup(locale, locale_key)
    if loc and not loc.startswith("QuestCondition"):
        return loc
    return BODY_PART_ZH.get(part_id, part_id)


def _slim_locations(raw: Any, locale: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for row in raw:
        if not isinstance(row, dict):
            continue
        key = str(row.get("spawnKey") or row.get("name") or "").strip()
        name = _locale_lookup(locale, key) or str(row.get("name") or key)
        chance = _as_float(row.get("chance"), 0) or 0
        if not name:
            continue
        out.append({"name": name, "chance": chance})
    return out


def _slim_escorts(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for row in raw:
        if not isinstance(row, dict):
            continue
        mob_id = str(row.get("mob") or "").strip()
        amounts: list[dict[str, Any]] = []
        for amt in row.get("amount") or []:
            if not isinstance(amt, dict):
                continue
            amounts.append(
                {
                    "chance": _as_float(amt.get("chance"), 0) or 0,
                    "count": _as_int(amt.get("count"), 0) or 0,
                }
            )
        if mob_id:
            out.append({"mob": mob_id, "amount": amounts})
    return out


def _slim_health(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for row in raw:
        if not isinstance(row, dict):
            continue
        part_id = str(row.get("id") or "").strip()
        if not part_id:
            continue
        out.append(
            {
                "id": part_id,
                "bodyPart": str(row.get("bodyPart") or ""),
                "max": _as_int(row.get("max"), 0) or 0,
            }
        )
    return out


def _slim_item_ids(raw: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    if not isinstance(raw, list):
        return out
    for row in raw:
        ident = ""
        if isinstance(row, dict):
            ident = _id_of(row.get("id") or row.get("item") or row)
        else:
            ident = str(row or "").strip()
        if ident and ident not in seen:
            seen.add(ident)
            out.append(ident)
    return out


def _slim_equipment(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for row in raw:
        if not isinstance(row, dict):
            continue
        item_id = _id_of(row.get("item"))
        if not item_id:
            continue
        contains: list[str] = []
        blob = row.get("contains") or row.get("containsItems")
        if isinstance(blob, list):
            for child in blob:
                cid = _id_of(child.get("item") if isinstance(child, dict) else child)
                if cid:
                    contains.append(cid)
        out.append({"item": item_id, "contains": contains})
    return out


def slim_maps_payload(
    payload: dict[str, Any],
    locale: dict[str, Any],
) -> dict[str, Any]:
    maps_out: dict[str, Any] = {}
    for key, raw in _maps_blob(payload).items():
        if not isinstance(raw, dict):
            continue
        bosses: list[dict[str, Any]] = []
        for spawn in raw.get("bosses") or []:
            if not isinstance(spawn, dict):
                continue
            mob_id = str(spawn.get("mob") or "").strip()
            if not mob_id:
                continue
            bosses.append(
                {
                    "mob": mob_id,
                    "spawnChance": _as_float(spawn.get("spawnChance"), 0) or 0,
                    "spawnLocations": _slim_locations(
                        spawn.get("spawnLocations"), locale
                    ),
                    "escorts": _slim_escorts(spawn.get("escorts")),
                }
            )
        extracts: list[dict[str, Any]] = []
        for extract in raw.get("extracts") or []:
            if not isinstance(extract, dict):
                continue
            extracts.append(
                {
                    "id": str(extract.get("id") or ""),
                    "name": str(extract.get("name") or ""),
                    "faction": str(extract.get("faction") or ""),
                }
            )
        maps_out[str(key)] = {
            "id": str(raw.get("id") or key),
            "name": str(raw.get("name") or ""),
            "normalizedName": str(raw.get("normalizedName") or ""),
            "description": str(raw.get("description") or ""),
            "wiki": str(raw.get("wiki") or ""),
            "raidDuration": _as_int(raw.get("raidDuration"), 0) or 0,
            "players": str(raw.get("players") or ""),
            "minPlayerLevel": _as_int(raw.get("minPlayerLevel"), 0) or 0,
            "maxPlayerLevel": _as_int(raw.get("maxPlayerLevel"), 0) or 0,
            "extracts": extracts,
            "bosses": bosses,
        }

    mobs_out: dict[str, Any] = {}
    for key, raw in _mobs_blob(payload).items():
        if not isinstance(raw, dict):
            continue
        mobs_out[str(key)] = {
            "id": str(raw.get("id") or key),
            "name": str(raw.get("name") or ""),
            "normalizedName": str(raw.get("normalizedName") or ""),
            "imagePortraitLink": str(raw.get("imagePortraitLink") or ""),
            "imagePosterLink": str(raw.get("imagePosterLink") or ""),
            "health": _slim_health(raw.get("health")),
            "items": _slim_item_ids(raw.get("items")),
            "equipment": _slim_equipment(raw.get("equipment")),
        }
    return {"maps": maps_out, "mobs": mobs_out, "locale": locale}


def download_json_api_maps(*, lang: str = "zh") -> BossesUpstreamBundle:
    raw = _http_request(TARKOV_JSON_MAPS_URL, timeout=180)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovBossesError("json.tarkov.dev maps 解析失败") from exc
    if not isinstance(payload, dict):
        raise TarkovBossesError("json.tarkov.dev maps 格式无效")
    if not _maps_blob(payload) or not _mobs_blob(payload):
        raise TarkovBossesError("json.tarkov.dev 未解析到地图 / BOSS")

    locale: dict[str, Any] = {}
    try:
        loc_raw = _http_request(
            TARKOV_JSON_MAPS_LOCALE_URL.format(lang=lang),
            timeout=60,
        )
        loc_payload = json.loads(loc_raw.decode("utf-8"))
        if isinstance(loc_payload, dict) and isinstance(loc_payload.get("data"), dict):
            locale = loc_payload["data"]
    except TarkovBossesError:
        logger.warning("json.tarkov.dev maps_%s locale unavailable", lang)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("json.tarkov.dev maps_%s locale parse failed", lang)

    slim = slim_maps_payload(payload, locale)
    if not slim["maps"] or not slim["mobs"]:
        raise TarkovBossesError("json.tarkov.dev maps 精简后为空")
    return BossesUpstreamBundle(
        source=SOURCE_JSON_API,
        payload=slim,
        note="json.tarkov.dev/regular/maps",
    )


def _health_parts(
    raw: list[dict[str, Any]],
    locale: dict[str, Any],
) -> tuple[int, list[dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in raw:
        part_id = str(row.get("id") or "").strip()
        if not part_id:
            continue
        by_id[part_id] = {
            "id": part_id,
            "name": _body_part_zh(part_id, str(row.get("bodyPart") or ""), locale),
            "max": int(row.get("max") or 0),
        }
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for part_id in BODY_PART_ORDER:
        if part_id in by_id:
            ordered.append(by_id[part_id])
            seen.add(part_id)
    for part_id, row in by_id.items():
        if part_id not in seen:
            ordered.append(row)
    total = sum(int(p.get("max") or 0) for p in ordered)
    return total, ordered


def _kebab_id(mob_id: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", mob_id)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", text)
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or mob_id.lower()


def assign_boss_slugs(mobs_by_id: dict[str, dict[str, Any]]) -> dict[str, str]:
    """同一 normalizedName 的多个 mob（如 af）各自保留独立 slug。"""
    bases: dict[str, str] = {}
    counts: dict[str, int] = {}
    for mob_id, raw in mobs_by_id.items():
        base = str(raw.get("normalizedName") or "").strip() or _kebab_id(mob_id)
        bases[mob_id] = base
        counts[base] = counts.get(base, 0) + 1
    out: dict[str, str] = {}
    used: set[str] = set()
    for mob_id, base in bases.items():
        slug = base if counts[base] == 1 else _kebab_id(mob_id)
        candidate = slug
        n = 2
        while candidate in used:
            candidate = f"{slug}-{n}"
            n += 1
        used.add(candidate)
        out[mob_id] = candidate
    return out


def _escorts_label(escorts: list[dict[str, Any]]) -> str:
    if not escorts:
        return "—"
    by_map: dict[str, list[dict[str, Any]]] = {}
    for row in escorts:
        key = str(row.get("map_slug") or row.get("map") or "")
        by_map.setdefault(key, []).append(row)
    totals: list[int] = []
    for group in by_map.values():
        sure = [
            int(e.get("count") or 0)
            for e in group
            if float(e.get("chance") or 0) >= 0.99
        ]
        if sure:
            totals.append(sum(sure))
        else:
            totals.append(sum(int(e.get("count") or 0) for e in group))
    totals = [n for n in totals if n > 0]
    if not totals:
        return "—"
    lo, hi = min(totals), max(totals)
    if lo == hi:
        return f"×{lo}"
    return f"×{lo}–{hi}"


def _finish_boss_row(row: dict[str, Any]) -> dict[str, Any]:
    spawn_bits: list[str] = []
    map_names: list[str] = []
    escorts: list[dict[str, Any]] = []
    locations: list[dict[str, Any]] = []
    map_chances: list[float] = []
    for m in row["maps"]:
        map_names.append(str(m.get("name") or m.get("slug") or ""))
        chances = [float(s.get("chance") or 0) for s in m.get("spawns") or []]
        map_chances.extend(chances)
        pct = _spawn_percent(chances)
        if pct:
            spawn_bits.append(f"{pct}（{m.get('name')}）")
        escorts.extend(m.get("escorts") or [])
        for spawn in m.get("spawns") or []:
            spawn_chance = float(spawn.get("chance") or 0)
            locs = spawn.get("locations") or []
            multi = len(locs) > 1
            for loc in locs:
                if not isinstance(loc, dict):
                    continue
                loc_chance = float(loc.get("chance") or 0)
                if loc_chance >= 0.999:
                    chance = spawn_chance
                elif multi and loc_chance == 1:
                    chance = spawn_chance
                else:
                    chance = loc_chance
                if chance == 0:
                    chance = spawn_chance
                locations.append(
                    {
                        "map": m.get("name"),
                        "map_slug": m.get("slug"),
                        "name": loc.get("name") or "",
                        "chance": chance,
                    }
                )
    row["maps_label"] = "、".join([n for n in map_names if n])
    row["spawn_label"] = "，".join(spawn_bits)
    row["spawn_short"] = _spawn_percent(map_chances)
    row["escorts"] = escorts
    row["escorts_label"] = _escorts_label(escorts)
    row["spawn_locations"] = locations
    return row


def _spawn_percent(chances: list[float]) -> str:
    if not chances:
        return ""
    lo = min(chances)
    hi = max(chances)
    lo_p = round(lo * 100)
    hi_p = round(hi * 100)
    if lo_p == hi_p or hi_p == 100:
        return f"{hi_p}%"
    return f"{lo_p}–{hi_p}%"


def _project_mob(
    mob_id: str,
    raw: dict[str, Any],
    locale: dict[str, Any],
    *,
    slug: str,
) -> dict[str, Any]:
    norm = str(raw.get("normalizedName") or "").strip()
    static = BOSS_STATIC.get(slug) or BOSS_STATIC.get(norm) or BOSS_STATIC.get(mob_id) or {}
    i18n = BOSS_I18N.get(slug) or BOSS_I18N.get(norm) or {}
    behavior = str(static.get("behavior") or "").strip()
    wiki = str(static.get("wiki") or "").strip()
    if not wiki and slug:
        wiki = f"https://escapefromtarkov.fandom.com/wiki/{slug}"
    total_hp, parts = _health_parts(
        raw.get("health") if isinstance(raw.get("health"), list) else [],
        locale,
    )
    nick_key = slug if slug in NICKNAMES else norm
    return {
        "id": str(raw.get("id") or mob_id),
        "slug": slug,
        "normalized_name": norm,
        "name": _mob_name(str(raw.get("id") or mob_id), raw, locale),
        "nickname": NICKNAMES.get(nick_key, ""),
        "behavior": behavior,
        "behavior_zh": _behavior_zh(behavior),
        "description": str(i18n.get("description") or "").strip(),
        "bio": str(i18n.get("bio") or "").strip(),
        "wiki_link": wiki,
        "portrait_link": str(raw.get("imagePortraitLink") or ""),
        "poster_link": str(raw.get("imagePosterLink") or ""),
        "health_total": total_hp,
        "health": parts,
        "maps": [],
        "item_ids": list(raw.get("items") or []),
        "equipment": list(raw.get("equipment") or []),
    }


def parse_boss_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    maps = payload.get("maps") if isinstance(payload.get("maps"), dict) else {}
    mobs = payload.get("mobs") if isinstance(payload.get("mobs"), dict) else {}
    locale = payload.get("locale") if isinstance(payload.get("locale"), dict) else {}

    spawn_ids: list[str] = []
    seen_ids: set[str] = set()
    for map_raw in maps.values():
        if not isinstance(map_raw, dict):
            continue
        for spawn in map_raw.get("bosses") or []:
            if not isinstance(spawn, dict):
                continue
            mob_id = str(spawn.get("mob") or "").strip()
            if not mob_id or mob_id in seen_ids:
                continue
            if not isinstance(mobs.get(mob_id), dict):
                continue
            seen_ids.add(mob_id)
            spawn_ids.append(mob_id)

    spawn_mobs = {mob_id: mobs[mob_id] for mob_id in spawn_ids}
    slugs = assign_boss_slugs(spawn_mobs)
    by_id: dict[str, dict[str, Any]] = {
        mob_id: _project_mob(mob_id, raw, locale, slug=slugs[mob_id])
        for mob_id, raw in spawn_mobs.items()
    }

    for map_raw in maps.values():
        if not isinstance(map_raw, dict):
            continue
        map_slug = str(map_raw.get("normalizedName") or "").strip()
        map_name = _map_zh(map_raw, locale)
        map_id = str(map_raw.get("id") or "").strip()
        for spawn in map_raw.get("bosses") or []:
            if not isinstance(spawn, dict):
                continue
            mob_id = str(spawn.get("mob") or "").strip()
            row = by_id.get(mob_id)
            if row is None:
                continue
            map_entry = next(
                (m for m in row["maps"] if m.get("id") == map_id or m.get("slug") == map_slug),
                None,
            )
            if map_entry is None:
                map_entry = {
                    "id": map_id,
                    "slug": map_slug,
                    "name": map_name,
                    "spawns": [],
                    "escorts": [],
                }
                row["maps"].append(map_entry)
            map_entry["spawns"].append(
                {
                    "chance": _as_float(spawn.get("spawnChance"), 0) or 0,
                    "locations": spawn.get("spawnLocations") or [],
                }
            )
            if not map_entry["escorts"]:
                escorts: list[dict[str, Any]] = []
                for esc in spawn.get("escorts") or []:
                    if not isinstance(esc, dict):
                        continue
                    esc_mob_id = str(esc.get("mob") or "").strip()
                    esc_mob = mobs.get(esc_mob_id) if isinstance(mobs.get(esc_mob_id), dict) else {}
                    esc_slug = str((esc_mob or {}).get("normalizedName") or "").strip()
                    esc_name = (
                        _mob_name(esc_mob_id, esc_mob, locale)
                        if esc_mob
                        else esc_mob_id
                    )
                    for amt in esc.get("amount") or [{"chance": 1, "count": 1}]:
                        if not isinstance(amt, dict):
                            continue
                        escorts.append(
                            {
                                "slug": esc_slug,
                                "name": esc_name,
                                "nickname": NICKNAMES.get(esc_slug, ""),
                                "count": int(amt.get("count") or 0),
                                "chance": float(amt.get("chance") or 0),
                                "map": map_name,
                                "map_slug": map_slug,
                            }
                        )
                map_entry["escorts"] = escorts

    rows: list[dict[str, Any]] = []
    for row in by_id.values():
        if not row["maps"]:
            continue
        rows.append(_finish_boss_row(row))
    rows.sort(key=lambda r: str(r.get("name") or "").lower())
    return rows


def _item_slot_value(item: dict[str, Any]) -> float:
    slots = max(int(item.get("width") or 1) * int(item.get("height") or 1), 1)
    best = 0
    for key in ("last_low_price", "avg24h_price"):
        val = item.get(key)
        if isinstance(val, int) and val > best:
            best = val
    for sell in item.get("sell_to_trader") or []:
        if not isinstance(sell, dict):
            continue
        price = int(sell.get("price_rub") or 0)
        if price > best:
            best = price
    return best / slots


def _best_trader_sell(item: dict[str, Any]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_price = -1
    for sell in item.get("sell_to_trader") or []:
        if not isinstance(sell, dict):
            continue
        price = int(sell.get("price_rub") or 0)
        if price > best_price:
            best_price = price
            best = sell
    return best


def _is_key_loot(item: dict[str, Any]) -> bool:
    types = {str(t).lower() for t in (item.get("types") or [])}
    if "keys" not in types:
        return False
    slug = str(item.get("normalized_name") or item.get("name") or "").lower()
    if "keycard" in slug or "marked" in slug:
        return False
    return True


def _loot_row(item: dict[str, Any]) -> dict[str, Any]:
    trader = _best_trader_sell(item)
    flea = item.get("last_low_price")
    if flea is None:
        flea = item.get("avg24h_price")
    types = [str(t) for t in (item.get("types") or [])]
    no_flea = "noflea" in {t.lower() for t in types}
    return {
        "item_id": item.get("id") or "",
        "name": item.get("name") or item.get("id") or "",
        "short_name": item.get("short_name") or "",
        "icon_link": item.get("icon_link") or "",
        "types": types,
        "flea_price": None if no_flea else flea,
        "trader_slug": str((trader or {}).get("slug") or ""),
        "trader_name": str((trader or {}).get("name") or ""),
        "trader_price": int((trader or {}).get("price_rub") or 0) or None,
        "trader_currency": str((trader or {}).get("currency") or "RUB"),
    }


def build_unique_loot(
    row: dict[str, Any],
    items: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    loot: list[dict[str, Any]] = []
    loot_keys: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(item: dict[str, Any], *, as_key: bool = False) -> None:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in seen:
            return
        seen.add(item_id)
        packed = {**item, "_slot": _item_slot_value(item)}
        if as_key:
            loot_keys.append(packed)
        else:
            loot.append(packed)

    for gear in row.get("equipment") or []:
        if not isinstance(gear, dict):
            continue
        parent = items.get(str(gear.get("item") or ""))
        if not parent:
            continue
        types = {str(t).lower() for t in (parent.get("types") or [])}
        if "noflea" in types or _item_slot_value(parent) > LOOT_VALUE_CUTOFF:
            add(parent)
            continue
        for cid in gear.get("contains") or []:
            child = items.get(str(cid))
            if not child:
                continue
            child_types = {str(t).lower() for t in (child.get("types") or [])}
            if "noflea" in child_types or _item_slot_value(child) > LOOT_VALUE_CUTOFF:
                add(parent)
                break

    for item_id in row.get("item_ids") or []:
        item = items.get(str(item_id))
        if not item:
            continue
        types = {str(t).lower() for t in (item.get("types") or [])}
        if "noflea" in types:
            add(item)
            continue
        if _item_slot_value(item) > LOOT_VALUE_CUTOFF:
            add(item, as_key=_is_key_loot(item))

    loot.sort(key=lambda it: float(it.get("_slot") or 0), reverse=True)
    loot_keys.sort(key=lambda it: float(it.get("_slot") or 0), reverse=True)
    out = [_loot_row(it) for it in loot]
    out.extend(_loot_row(it) for it in loot_keys[:5])
    return out


def _lookup_items(db: Session, item_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not item_ids:
        return {}
    try:
        from app.services import tarkov_catalog as catalog_svc
        from app.services import tarkov_items as items_svc

        source, payload, _synced, _note = catalog_svc._load_payload(db)
        if not catalog_svc.payload_has_full_items(source, payload):
            return {}
        locale = items_svc._locale_map(payload)
        out: dict[str, dict[str, Any]] = {}
        for ident, raw in catalog_svc.iter_raw_items(source, payload):
            if ident not in item_ids:
                continue
            row = catalog_svc._row_from_raw(ident, raw, locale)
            if not row:
                continue
            sells: list[dict[str, Any]] = []
            blob = raw.get("sellToTrader")
            if isinstance(blob, list):
                for sell in blob:
                    if not isinstance(sell, dict):
                        continue
                    trader_id = _id_of(sell.get("trader"))
                    slug, name = TRADER_BY_ID.get(trader_id, ("", ""))
                    if name and "（" in name:
                        name = name.split("（", 1)[0]
                    sells.append(
                        {
                            "trader_id": trader_id,
                            "slug": slug,
                            "name": name or slug,
                            "price": _as_int(sell.get("price"), 0) or 0,
                            "price_rub": _as_int(sell.get("priceRUB"), 0) or 0,
                            "currency": str(sell.get("currency") or "RUB"),
                        }
                    )
            out[ident] = {
                **row,
                "normalized_name": str(raw.get("normalizedName") or ""),
                "avg24h_price": _as_int(raw.get("avg24hPrice"), None),
                "last_low_price": _as_int(raw.get("lastLowPrice"), None),
                "width": _as_int(raw.get("width"), 1) or 1,
                "height": _as_int(raw.get("height"), 1) or 1,
                "sell_to_trader": sells,
            }
        return out
    except Exception:  # noqa: BLE001
        logger.warning("boss unique loot: items catalog unavailable", exc_info=True)
        return {}


def get_bosses_raw(db: Session) -> TarkovBossesRaw | None:
    return db.get(TarkovBossesRaw, RAW_ROW_ID)


def get_bosses_meta(db: Session) -> TarkovBossesMeta | None:
    return db.get(TarkovBossesMeta, META_ROW_ID)


def persist_bosses_bundle(db: Session, bundle: BossesUpstreamBundle) -> dict[str, Any]:
    global _parsed_cache
    rows = parse_boss_rows(bundle.payload)
    if not rows:
        raise TarkovBossesError("未解析到 BOSS 数据")
    now = now_naive()
    raw_json = json.dumps(bundle.payload, ensure_ascii=False)
    row = get_bosses_raw(db)
    if row is None:
        db.add(
            TarkovBossesRaw(
                id=RAW_ROW_ID,
                source=bundle.source,
                raw_json=raw_json,
                synced_at=now,
                note=bundle.note,
            )
        )
    else:
        row.source = bundle.source
        row.raw_json = raw_json
        row.synced_at = now
        row.note = bundle.note
    meta = get_bosses_meta(db)
    if meta is None:
        meta = TarkovBossesMeta(id=META_ROW_ID)
        db.add(meta)
    meta.source = bundle.source
    meta.boss_count = len(rows)
    meta.synced_at = now
    meta.note = bundle.note
    db.commit()
    with _parsed_lock:
        _parsed_cache = None
    return {
        "boss_count": len(rows),
        "source": bundle.source,
        "synced_at": now.isoformat() if now else None,
        "note": bundle.note,
    }


def sync_from_upstream(db: Session) -> dict[str, Any]:
    logger.info("syncing tarkov bosses from upstream")
    return persist_bosses_bundle(db, download_json_api_maps(lang="zh"))


def _load_payload(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    row = get_bosses_raw(db)
    if row is None:
        raise TarkovBossesError("无 BOSS raw")
    try:
        payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TarkovBossesError("BOSS raw_json 无效") from exc
    if not isinstance(payload, dict):
        raise TarkovBossesError("BOSS raw_json 格式无效")
    meta = get_bosses_meta(db)
    synced = meta.synced_at.isoformat() if meta and meta.synced_at else None
    note = (meta.note if meta else None) or row.note
    return row.source, payload, synced, note


def load_parsed_bosses(db: Session) -> tuple[str, list[dict[str, Any]], str | None, str | None]:
    global _parsed_cache
    meta = get_bosses_meta(db)
    synced = meta.synced_at.isoformat() if meta and meta.synced_at else None
    key = synced or ""
    with _parsed_lock:
        cached = _parsed_cache
        if cached is not None and cached[0] == key:
            source, _payload, synced_at, note = _load_payload(db)
            return source, cached[1], synced_at, note
    source, payload, synced_at, note = _load_payload(db)
    rows = parse_boss_rows(payload)
    with _parsed_lock:
        _parsed_cache = (key, rows)
    return source, rows, synced_at, note


def ensure_bosses(db: Session) -> None:
    if get_bosses_raw(db) is None:
        sync_from_upstream(db)


def _public_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id") or "",
        "slug": row.get("slug") or "",
        "name": row.get("name") or "",
        "nickname": row.get("nickname") or "",
        "behavior": row.get("behavior") or "",
        "behavior_zh": row.get("behavior_zh") or "",
        "maps_label": row.get("maps_label") or "",
        "spawn_label": row.get("spawn_label") or "",
        "spawn_short": row.get("spawn_short") or "",
        "escorts_label": row.get("escorts_label") or "",
        "health_total": int(row.get("health_total") or 0),
        "portrait_link": row.get("portrait_link") or "",
        "poster_link": row.get("poster_link") or "",
        "wiki_link": row.get("wiki_link") or "",
    }


def list_bosses(db: Session) -> dict[str, Any]:
    ensure_bosses(db)
    source, rows, synced_at, note = load_parsed_bosses(db)
    return {
        "items": [_public_summary(r) for r in rows],
        "boss_count": len(rows),
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def _find_boss_row(rows: list[dict[str, Any]], slug: str) -> dict[str, Any] | None:
    key = resolve_boss_slug(slug)
    if not key:
        return None
    for row in rows:
        if str(row.get("slug") or "") == key:
            return row
    lowered = key.lower()
    for row in rows:
        if str(row.get("id") or "").lower() == lowered:
            return row
    hits = [r for r in rows if str(r.get("normalized_name") or "") == key]
    if len(hits) == 1:
        return hits[0]
    return None


def get_boss_detail(db: Session, slug: str) -> dict[str, Any]:
    slug = resolve_boss_slug(slug)
    if not slug:
        raise TarkovBossesError("BOSS slug 无效")
    ensure_bosses(db)
    source, rows, synced_at, note = load_parsed_bosses(db)
    row = _find_boss_row(rows, slug)
    if row is None:
        raise TarkovBossesError(f"未找到 BOSS: {slug}")
    needed: set[str] = set(str(x) for x in (row.get("item_ids") or []))
    for gear in row.get("equipment") or []:
        if not isinstance(gear, dict):
            continue
        if gear.get("item"):
            needed.add(str(gear["item"]))
        for cid in gear.get("contains") or []:
            needed.add(str(cid))
    items = _lookup_items(db, needed)
    loot = build_unique_loot(row, items)
    return {
        **_public_summary(row),
        "description": row.get("description") or "",
        "bio": row.get("bio") or "",
        "health": row.get("health") or [],
        "maps": [
            {
                "id": m.get("id") or "",
                "slug": m.get("slug") or "",
                "name": m.get("name") or "",
                "spawn_chance": _spawn_percent(
                    [float(s.get("chance") or 0) for s in m.get("spawns") or []]
                ),
            }
            for m in row.get("maps") or []
        ],
        "spawn_locations": row.get("spawn_locations") or [],
        "escorts": row.get("escorts") or [],
        "unique_loot": loot,
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def bosses_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    job = JobRun(job_key=BOSSES_JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_from_upstream(db)
        job.status = "ok"
        job.message = json.dumps(
            {
                "boss_count": result.get("boss_count"),
                "source": result.get("source"),
            },
            ensure_ascii=False,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov bosses sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
