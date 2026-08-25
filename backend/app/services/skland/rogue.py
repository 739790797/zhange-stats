"""明日方舟集成战略（肉鸽）拉取与解析。"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from app.services.skland.client import (
    ARKNIGHTS_ROGUE_URL,
    SklandApiError,
    SklandSession,
    _http_json,
    _signed_headers,
    ensure_skland_user_id,
)

TOPIC_LABELS: dict[str, str] = {
    "rogue_1": "傀影",
    "rogue_2": "水月",
    "rogue_3": "萨米",
    "rogue_4": "萨卡兹",
    "rogue_5": "界园",
    "rogue_6": "黑流树海",
}

DEFAULT_TOPIC_ID = "rogue_5"


@dataclass
class RogueTopic:
    topic_id: str
    name: str
    selected: bool
    pic: str | None = None


@dataclass
class RogueCharBrief:
    char_id: str
    name: str
    rarity: int
    level: int
    evolve_phase: int
    profession: str = ""


@dataclass
class RogueRecord:
    record_id: str
    mode: str
    mode_grade: int
    success: bool
    score: int
    ending_text: str
    start_ts: str
    end_ts: str
    zone_count: int
    node_count: int
    relic_count: int
    band_name: str
    last_stage: str
    is_collect: bool
    squad: list[RogueCharBrief] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class RogueOverview:
    mode: str
    mode_grade: int
    score: int
    bp_level: int
    medal_current: int
    medal_count: int
    clear_difficulty: str
    clear_grade: int
    invest: int
    relic: int
    game_count: int


@dataclass
class RogueBox:
    topic_id: str
    topic_name: str
    topics: list[RogueTopic]
    overview: RogueOverview
    records: list[RogueRecord]
    favour_records: list[RogueRecord]


def normalize_topic_id(raw: str | None) -> str:
    s = str(raw or "").strip()
    if not s:
        return DEFAULT_TOPIC_ID
    # 允许中文主题名
    for tid, name in TOPIC_LABELS.items():
        if s == tid or s == name:
            return tid
    if s.startswith("rogue_"):
        return s
    return DEFAULT_TOPIC_ID


def fetch_arknights_rogue(
    session: SklandSession, *, uid: str, topic_id: str
) -> dict[str, Any]:
    uid = str(uid or "").strip()
    topic_id = normalize_topic_id(topic_id)
    if not uid:
        raise SklandApiError("缺少游戏 UID")
    user_id = ensure_skland_user_id(session)
    params = {
        "uid": uid,
        "targetUserId": user_id,
        "topicId": topic_id,
    }
    query = urllib.parse.urlencode(params)
    url = f"{ARKNIGHTS_ROGUE_URL}?{query}"
    headers = _signed_headers(session, url, "get", None)
    resp = _http_json("GET", url, headers=headers)
    if resp.get("code") != 0:
        raise SklandApiError(
            resp.get("message") or "获取肉鸽数据失败",
            code=resp.get("code"),
        )
    data = resp.get("data")
    if not isinstance(data, dict):
        raise SklandApiError("肉鸽数据为空")
    return resp


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _parse_char(row: Any) -> RogueCharBrief | None:
    if not isinstance(row, dict):
        return None
    cid = _str(row.get("id") or row.get("charId")).strip()
    if not cid:
        return None
    return RogueCharBrief(
        char_id=cid,
        name=_str(row.get("name") or cid),
        rarity=_int(row.get("rarity"), 0),
        level=_int(row.get("level"), 0),
        evolve_phase=_int(row.get("evolvePhase") or row.get("upgradePhase"), 0),
        profession=_str(row.get("profession")),
    )


def _parse_record(row: Any) -> RogueRecord | None:
    if not isinstance(row, dict):
        return None
    rid = _str(row.get("id")).strip()
    if not rid:
        return None
    band = _as_dict(row.get("band"))
    squad_src = (
        _as_list(row.get("lastChars"))
        or _as_list(row.get("troopChars"))
        or _as_list(row.get("initChars"))
    )
    squad: list[RogueCharBrief] = []
    for item in squad_src:
        ch = _parse_char(item)
        if ch:
            squad.append(ch)
    tags: list[str] = []
    for t in _as_list(row.get("tagList")):
        if isinstance(t, dict) and t.get("name"):
            tags.append(_str(t.get("name")))
        elif isinstance(t, str) and t.strip():
            tags.append(t.strip())
    success_raw = row.get("success")
    success = bool(success_raw) if not isinstance(success_raw, str) else success_raw in (
        "1",
        "true",
        "True",
    )
    return RogueRecord(
        record_id=rid,
        mode=_str(row.get("mode")),
        mode_grade=_int(row.get("modeGrade")),
        success=success,
        score=_int(row.get("score")),
        ending_text=_str(row.get("endingText")),
        start_ts=_str(row.get("startTs")),
        end_ts=_str(row.get("endTs")),
        zone_count=_int(row.get("cntCrossedZone")),
        node_count=_int(row.get("cntArrivedNode")),
        relic_count=_int(row.get("cntGainRelicItem")),
        band_name=_str(band.get("name")),
        last_stage=_str(row.get("lastStage")),
        is_collect=bool(row.get("isCollect")),
        squad=squad,
        tags=tags,
    )


def parse_arknights_rogue(
    raw: dict[str, Any], *, topic_id: str
) -> RogueBox:
    """从上游整包或 data 节点解析肉鸽概览。"""
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    if not isinstance(data, dict):
        raise SklandApiError("肉鸽数据格式异常")

    topic_id = normalize_topic_id(topic_id)
    topics: list[RogueTopic] = []
    for row in _as_list(data.get("topics")):
        if not isinstance(row, dict):
            continue
        tid = _str(row.get("id")).strip()
        if not tid:
            continue
        name = _str(row.get("name") or TOPIC_LABELS.get(tid, tid))
        topics.append(
            RogueTopic(
                topic_id=tid,
                name=name,
                selected=bool(row.get("isSelected")) or tid == topic_id,
                pic=_str(row.get("pic")) or None,
            )
        )
    if not topics:
        topics = [
            RogueTopic(
                topic_id=tid,
                name=name,
                selected=tid == topic_id,
            )
            for tid, name in TOPIC_LABELS.items()
        ]

    selected = next((t for t in topics if t.selected), None)
    if selected is None:
        selected = next((t for t in topics if t.topic_id == topic_id), topics[0])
        selected.selected = True

    history = _as_dict(data.get("history"))
    career = _as_dict(data.get("career"))
    clear = _as_dict(career.get("clearInfo"))
    medal = _as_dict(history.get("medal"))

    overview = RogueOverview(
        mode=_str(history.get("mode")),
        mode_grade=_int(history.get("modeGrade")),
        score=_int(history.get("score")),
        bp_level=_int(history.get("bpLevel")),
        medal_current=_int(medal.get("current")),
        medal_count=_int(medal.get("count")),
        clear_difficulty=_str(clear.get("difficulty")),
        clear_grade=_int(clear.get("grade")),
        invest=_int(career.get("invest")),
        relic=_int(career.get("relic")),
        game_count=_int(career.get("game")),
    )

    records: list[RogueRecord] = []
    for row in _as_list(history.get("records")):
        rec = _parse_record(row)
        if rec:
            records.append(rec)
    favour: list[RogueRecord] = []
    for row in _as_list(history.get("favourRecords")):
        rec = _parse_record(row)
        if rec:
            favour.append(rec)

    return RogueBox(
        topic_id=selected.topic_id,
        topic_name=selected.name,
        topics=topics,
        overview=overview,
        records=records,
        favour_records=favour,
    )
