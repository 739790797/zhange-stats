"""Read the authenticated Stronghold history and optional official display resources."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Annotated
from urllib.parse import urlencode

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

from app.core.http_client import HttpRequestError, http_request
from app.schemas.stronghold import (
    StrongholdBattleData,
    StrongholdBondOut,
    StrongholdBossOut,
    StrongholdEquipmentOut,
    StrongholdMode,
    StrongholdOperatorOut,
    StrongholdScopeId,
    StrongholdTraitOut,
)
from app.services.skland.client import (
    SklandApiError,
    SklandRole,
    SklandSession,
    _signed_headers,
    background_request_gate,
)

_ORIGIN = "https://zonai.skland.com/api/ms/game/arknights/garrison"
_ACTIVITY_ID = "act3autochess"
_LABEL = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=96)]
_KEY = Annotated[str, Field(pattern=r"^[A-Za-z0-9_:.\-]{1,128}$")]
_KEY_RE = re.compile(r"[A-Za-z0-9_:.\-]{1,128}\Z", re.ASCII)
_ICON = re.compile(
    r"https://(?:web\.hycdn\.cn/arknights/game/assets|bbs\.hycdn\.cn/skland-fe-static/assets/arknights)/"
    r"(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:png|webp|jpe?g)\Z",
    re.ASCII,
)
_MODES: dict[str, StrongholdMode] = {"SINGLE": "single", "MULTI": "multi", "LOCAL": "local"}


class RoleBattle(BaseModel):
    upstream_view_id: _KEY
    season_id: StrongholdScopeId
    season_label: _LABEL
    difficulty_id: StrongholdScopeId
    difficulty_label: _LABEL
    ended_at: AwareDatetime
    mode_type: StrongholdMode | None = None
    completed: bool | None = None
    pass_round: Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)] | None = None
    strategy_id: _KEY | None = None
    strategy_name: _LABEL | None = None
    scene_id: _KEY | None = None
    version_id: _KEY | None = None
    battle: StrongholdBattleData = Field(default_factory=StrongholdBattleData)
    roster: list[StrongholdOperatorOut] | None = None
    bonds: list[StrongholdBondOut] | None = None


@dataclass(frozen=True)
class StrongholdBatch:
    records: Sequence[RoleBattle]
    resources_available: bool


def _request(session: SklandSession, endpoint: str, params: dict[str, str]) -> dict:
    url = f"{_ORIGIN}/{endpoint}?{urlencode(params)}"
    try:
        gate = background_request_gate.get()
        if gate is not None:
            gate()
        response = http_request(
            "GET",
            url,
            headers=_signed_headers(session, url, "get", None),
            timeout=12,
            deadline=16,
            max_bytes=16 * 1024 * 1024,
            follow_redirects=False,
        )
        if response.status_code != 200:
            raise SklandApiError(
                "森空岛卫戍协议请求失败", code=response.status_code, retry_after=response.headers.get("Retry-After")
            )
        body = response.json()
        if not isinstance(body, dict) or type(body.get("code")) is not int or body["code"] != 0:
            raise SklandApiError(
                "森空岛未返回卫戍协议数据",
                code=body.get("code") if isinstance(body, dict) and type(body.get("code")) is int else None,
                retry_after=response.headers.get("Retry-After"),
            )
        data = body.get("data")
        if response.headers.get("x-transformed", "").strip().lower() == "base64":
            content = data.get("content") if isinstance(data, dict) else None
            if not isinstance(content, str):
                raise ValueError("missing encoded content")
            data = json.loads(base64.b64decode(content, validate=True))
        if not isinstance(data, dict):
            raise ValueError("invalid response data")
        return data
    except (HttpRequestError, ValueError, TypeError):
        # Neither the official request URL nor the response body belongs in logs/errors.
        raise SklandApiError("森空岛卫戍协议响应不可用") from None


def _obj(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _key(value: object) -> str | None:
    return value if isinstance(value, str) and _KEY_RE.fullmatch(value) else None


def _scope(value: object) -> str | None:
    key = _key(value)
    return key.lower() if key and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", key) else None


def _label(value: object) -> str | None:
    value = value.strip() if isinstance(value, str) else ""
    return value[:96] or None


def _flag(value: object) -> bool | None:
    return bool(value) if type(value) in (int, bool) and value in (0, 1) else None


def _number(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= 2_147_483_647 else None


def _epoch(value: object) -> datetime | None:
    if (type(value) is int or isinstance(value, str)) and re.fullmatch(r"[1-9][0-9]{9}", str(value)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    return None


def _versions(resources: dict) -> dict[str, dict]:
    entries = resources.get("resources")
    if not isinstance(entries, list):
        raise SklandApiError("森空岛卫戍协议资源不可用")
    return {
        version: entry for entry in entries if (version := _key(_obj(_obj(entry).get("versionInfo")).get("versionId")))
    }


def _icon(value: object) -> str | None:
    return value if isinstance(value, str) and len(value) <= 512 and _ICON.fullmatch(value) else None


def _description(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = re.sub(r"<br\s*/?>", "\n", unescape(value).replace("\\n", "\n"), flags=re.IGNORECASE)
    # Strip formatting, not conditions such as <标准模拟> or <在场6名干员>.
    return (
        re.sub(
            r"<[@$][-\w.]+>|</>|</?(?:b|strong|em|i|span|font|p|div|u|color|size)\b[^<>]*>",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()[:4096]
        or None
    )


def _equipment(raw: object, catalog: dict) -> list[StrongholdEquipmentOut] | None:
    if not isinstance(raw, list):
        return None
    result = []
    for entry in raw[:16]:
        if equip_id := _key(_obj(entry).get("equipId")):
            info = _obj(catalog.get(equip_id))
            result.append(
                StrongholdEquipmentOut(
                    id=equip_id,
                    name=_label(info.get("name")),
                    tier=_number(info.get("itemLevel")),
                    description=_description(info.get("desc")),
                    icon_url=_icon(info.get("icon")),
                )
            )
    return result


def _traits(raw: object, catalog: dict) -> list[StrongholdTraitOut] | None:
    if not isinstance(raw, list):
        return None
    result = []
    for entry in raw[:16]:
        if trait_id := _key(entry):
            info = _obj(catalog.get(trait_id))
            result.append(
                StrongholdTraitOut(
                    id=trait_id,
                    name=_label(info.get("eventTypeDesc")),
                    description=_description(info.get("description")),
                    icon_url=_icon(info.get("icon"))
                    or _icon(info.get("eventTypeSmallIcon"))
                    or _icon(info.get("eventTypeIcon")),
                )
            )
    return result


def _operators(raw: object, resource: dict) -> list[StrongholdOperatorOut] | None:
    if not isinstance(raw, list):
        return None
    catalog = _obj(resource.get("chessInfo"))
    equipment = _obj(resource.get("equipInfo"))
    traits = _obj(resource.get("garrisonInfo"))
    operators = []
    for entry in raw[:32]:
        entry = _obj(entry)
        if not (chess_id := _key(entry.get("chessId"))):
            continue
        info = {**_obj(catalog.get(chess_id)), **_obj(entry.get("chessInfo"))}
        char_id = _key(info.get("charId")) or _key(entry.get("charId"))
        operators.append(
            StrongholdOperatorOut(
                id=chess_id,
                char_id=char_id if char_id and re.fullmatch(r"char_[0-9]+_[a-zA-Z0-9_]+", char_id) else None,
                name=_label(info.get("charName")),
                level=_number(info.get("charLevel")),
                phase=_number(info.get("evolvePhase")),
                tier=_number(info.get("chessLevel")),
                profession=_key(info.get("charProfession")),
                branch_id=_key(info.get("charSubProfession")),
                skill_id=_key(entry.get("skillId")),
                module_id=_key(entry.get("moduleId")),
                merge_level=_number(entry.get("mergeLevel")),
                equipment=_equipment(entry.get("equips"), equipment),
                traits=_traits(info.get("garrisonIds"), traits),
            )
        )
    return operators if operators or not raw else None


def _bosses(raw: object, resource: dict) -> list[StrongholdBossOut] | None:
    if not isinstance(raw, list):
        return None
    catalog = _obj(resource.get("bossInfo"))
    result = []
    for entry in raw[:32]:
        entry = _obj(entry)
        if boss_id := _key(entry.get("bossId")):
            info = _obj(catalog.get(boss_id))
            result.append(
                StrongholdBossOut(
                    id=boss_id,
                    enemy_id=_key(info.get("enemyId")),
                    hidden=_flag(entry.get("isHidden")),
                    killed=_flag(entry.get("isKilled")),
                )
            )
    return result


def _bonds(raw: object, resource: dict, mode: StrongholdMode | None) -> list[StrongholdBondOut] | None:
    if not isinstance(raw, list):
        return None
    catalog = _obj(resource.get("bondInfo"))
    bonds: dict[str, StrongholdBondOut] = {}
    conflicted: set[str] = set()
    for entry in raw[:256]:
        entry = _obj(entry)
        if not (bond_id := _key(entry.get("bondId"))) or bond_id in conflicted:
            continue
        info = _obj(catalog.get(bond_id))
        bond = StrongholdBondOut(
            bond_id=bond_id,
            name=_label(info.get("name")),
            description=_description(info.get("desc")),
            icon_url=_icon(info.get("icon")),
            active=_flag(entry.get("activate")),
            layer=_number(entry.get("layer")),
            layer_scope="role" if mode in ("single", "local") else "unknown",
        )
        if bond_id in bonds and bonds[bond_id] != bond:
            conflicted.add(bond_id)
            bond = StrongholdBondOut(bond_id=bond_id, name=bond.name, icon_url=bond.icon_url, layer_scope="unknown")
        bonds[bond_id] = bond
    return list(bonds.values()) if bonds or not raw else None


def parse_history(history: dict, role: SklandRole, versions: dict[str, dict]) -> list[RoleBattle]:
    items = _obj(history.get("history")).get("records")
    if not isinstance(items, list) or len(items) > 2000:
        raise SklandApiError("森空岛未返回有效的卫戍协议战绩列表")
    battles = []
    for item in items:
        item = _obj(item)
        record_id = _key(item.get("id"))
        ended_at = _epoch(item.get("gameEndTs"))
        season_id = _scope(item.get("activityId"))
        if not record_id or not record_id.startswith(f"{role.uid}-") or not ended_at or not season_id:
            raise SklandApiError("森空岛卫戍协议战绩缺少可验证的角色、活动或结束时间")
        mode = _MODES.get(_key(item.get("modeType")) or "")
        version_id = _key(item.get("versionId"))
        resource = versions.get(version_id or "", {})
        if _scope(_obj(resource.get("versionInfo")).get("activityId")) not in (None, season_id):
            resource = {}
        band_id = _key(item.get("bandId"))
        strategy = _obj(_obj(resource.get("bandInfo")).get(band_id))
        difficulty = _scope(item.get("modeDifficulty"))
        title_id = _key(item.get("title"))
        title = _label(_obj(_obj(resource.get("titleInfo")).get(title_id)).get("name"))
        started_at = _epoch(item.get("gameStartTs"))
        battles.append(
            RoleBattle(
                upstream_view_id=record_id,
                season_id=season_id,
                season_label=_label(_obj(resource.get("versionInfo")).get("seasonName")) or "卫戍协议",
                difficulty_id=difficulty or "unknown",
                difficulty_label=_label(item.get("mode")) or difficulty or "未知难度",
                ended_at=ended_at,
                mode_type=mode,
                completed=_flag(item.get("completeState")),
                pass_round=_number(item.get("passRound")),
                strategy_id=band_id,
                strategy_name=_label(strategy.get("name")),
                scene_id=_key(item.get("sceneId")),
                version_id=version_id,
                battle=StrongholdBattleData(
                    started_at=started_at if started_at and started_at <= ended_at else None,
                    team_completed=_flag(item.get("teamComplete")),
                    strategy_icon_url=_icon(strategy.get("icon")),
                    strategy_description=_description(strategy.get("desc")),
                    trophy_before=_number(item.get("trophyBefore")),
                    trophy_after=_number(item.get("trophyAfter")),
                    coin_cost=_number(item.get("coinCost")),
                    sync_count=_number(item.get("syncCnt")),
                    kill_count=_number(item.get("killCnt")),
                    title=title,
                    bosses=_bosses(item.get("acBossInfo"), resource),
                ),
                roster=_operators(item.get("chessSquad"), resource),
                bonds=_bonds(item.get("bondInfo"), resource, mode),
            )
        )
    return battles


def fetch_official_history(
    session: SklandSession, role: SklandRole, activity_id: str = _ACTIVITY_ID, versions: dict[str, dict] | None = None
) -> StrongholdBatch:
    history = _request(session, "info", {"uid": role.uid, "activityId": activity_id})
    return StrongholdBatch(parse_history(history, role, versions or {}), bool(versions))


def fetch_official_resources(session: SklandSession, activity_id: str) -> dict[str, dict]:
    return _versions(_request(session, "resource", {"activityId": activity_id}))


official_source = fetch_official_history
