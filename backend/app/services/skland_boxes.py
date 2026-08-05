"""森空岛干员 / 终末地盒子解析（从 skland_client 拆出）。"""

from __future__ import annotations

import urllib.parse
from typing import Any

from app.services.skland_client import (
    CHAR_AVATAR_CDN,
    ENDFIELD_CARD_DETAIL_URL,
    PLAYER_INFO_URL,
    PROFESSION_CN,
    ArknightsBox,
    ArknightsChar,
    ArknightsEquip,
    ArknightsSkill,
    EndfieldBox,
    EndfieldChar,
    EndfieldEquip,
    EndfieldSkill,
    EndfieldWeapon,
    SklandApiError,
    SklandRole,
    SklandSession,
    _http_json,
    _signed_headers,
)

def fetch_player_info(session: SklandSession, uid: str) -> dict[str, Any]:
    """拉取森空岛玩家完整数据（含干员盒子）。"""
    uid = str(uid or "").strip()
    if not uid:
        raise SklandApiError("缺少游戏 UID")
    url = f"{PLAYER_INFO_URL}?{urllib.parse.urlencode({'uid': uid})}"
    headers = _signed_headers(session, url, "get", None)
    resp = _http_json("GET", url, headers=headers)
    if resp.get("code") != 0:
        raise SklandApiError(
            resp.get("message") or "获取玩家数据失败",
            code=resp.get("code"),
        )
    data = resp.get("data")
    if not isinstance(data, dict):
        raise SklandApiError("玩家数据为空")
    return data


def _char_avatar_url(char_id: str) -> str:
    return f"{CHAR_AVATAR_CDN}/{char_id}.png"


_SPEC_CN = ("", "一", "二", "三")


def _skill_label(index: int, *, specialize: int, main_lvl: int) -> str:
    name = f"技能{index}"
    if specialize >= 1:
        sp = _SPEC_CN[min(3, specialize)]
        return f"{name} 专精{sp}"
    return f"{name} Lv.{max(1, min(7, main_lvl))}"


def _parse_skills(raw_skills: Any, *, main_skill_lvl: int) -> list[ArknightsSkill]:
    if not isinstance(raw_skills, list):
        return []
    out: list[ArknightsSkill] = []
    for i, row in enumerate(raw_skills, start=1):
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue
        try:
            specialize = int(row.get("specializeLevel") or 0)
        except (TypeError, ValueError):
            specialize = 0
        specialize = max(0, min(3, specialize))
        out.append(
            ArknightsSkill(
                skill_id=sid,
                specialize_level=specialize,
                label=_skill_label(i, specialize=specialize, main_lvl=main_skill_lvl),
            )
        )
    return out


def _parse_equips(raw_equips: Any, equip_info_map: dict[str, Any]) -> list[ArknightsEquip]:
    if not isinstance(raw_equips, list):
        return []
    out: list[ArknightsEquip] = []
    for row in raw_equips:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("id") or "").strip()
        if not eid:
            continue
        info = equip_info_map.get(eid) if isinstance(equip_info_map.get(eid), dict) else {}
        try:
            level = int(row.get("level") or 1)
        except (TypeError, ValueError):
            level = 1
        out.append(
            ArknightsEquip(
                equip_id=eid,
                name=str(info.get("name") or eid).strip() or eid,
                level=max(1, level),
                type_icon=str(info.get("typeIcon") or "").strip(),
                locked=bool(row.get("locked")),
            )
        )
    return out


def parse_arknights_box(data: dict[str, Any], *, uid: str) -> ArknightsBox:
    status = data.get("status") if isinstance(data.get("status"), dict) else {}
    char_info_map = (
        data.get("charInfoMap") if isinstance(data.get("charInfoMap"), dict) else {}
    )
    equip_info_map = (
        data.get("equipmentInfoMap")
        if isinstance(data.get("equipmentInfoMap"), dict)
        else {}
    )
    raw_chars = data.get("chars") if isinstance(data.get("chars"), list) else []
    ap = status.get("ap") if isinstance(status.get("ap"), dict) else {}

    chars: list[ArknightsChar] = []
    for item in raw_chars:
        if not isinstance(item, dict):
            continue
        char_id = str(item.get("charId") or "").strip()
        if not char_id:
            continue
        info = char_info_map.get(char_id) if isinstance(char_info_map.get(char_id), dict) else {}
        profession = str(info.get("profession") or item.get("profession") or "")
        # charInfoMap.rarity 多为 0-5（对应 1-6 星）
        rarity_raw = info.get("rarity")
        try:
            rarity_idx = int(rarity_raw) if rarity_raw is not None else 0
        except (TypeError, ValueError):
            rarity_idx = 0
        rarity = rarity_idx + 1 if 0 <= rarity_idx <= 5 else max(1, min(6, rarity_idx))

        name = str(info.get("name") or char_id)
        try:
            level = int(item.get("level") or 0)
        except (TypeError, ValueError):
            level = 0
        try:
            evolve_phase = int(item.get("evolvePhase") or 0)
        except (TypeError, ValueError):
            evolve_phase = 0
        try:
            potential_rank = int(item.get("potentialRank") or 0)
        except (TypeError, ValueError):
            potential_rank = 0
        favor = item.get("favorPercent")
        try:
            favor_percent = int(favor) if favor is not None else None
        except (TypeError, ValueError):
            favor_percent = None
        gain = item.get("gainTime") or item.get("obtainTs")
        try:
            obtain_ts = int(gain) if gain is not None else None
        except (TypeError, ValueError):
            obtain_ts = None
        skin_id = item.get("skinId")
        try:
            main_skill_lvl = int(item.get("mainSkillLvl") or 1)
        except (TypeError, ValueError):
            main_skill_lvl = 1
        main_skill_lvl = max(1, min(7, main_skill_lvl))
        skills = _parse_skills(item.get("skills"), main_skill_lvl=main_skill_lvl)
        equips = _parse_equips(item.get("equip"), equip_info_map)
        chars.append(
            ArknightsChar(
                char_id=char_id,
                name=name,
                rarity=rarity,
                profession=profession,
                profession_label=PROFESSION_CN.get(profession, profession or "未知"),
                level=level,
                evolve_phase=evolve_phase,
                potential_rank=potential_rank,
                favor_percent=favor_percent,
                skin_id=str(skin_id) if skin_id else None,
                avatar_url=_char_avatar_url(char_id),
                obtain_ts=obtain_ts,
                main_skill_lvl=main_skill_lvl,
                skills=skills,
                equips=equips,
            )
        )

    chars.sort(
        key=lambda c: (-c.rarity, -c.evolve_phase, -c.level, -c.potential_rank, c.name)
    )

    try:
        player_level = int(status.get("level") or 0)
    except (TypeError, ValueError):
        player_level = 0
    try:
        register_ts = int(status.get("registerTs")) if status.get("registerTs") is not None else None
    except (TypeError, ValueError):
        register_ts = None
    try:
        ap_current = int(ap.get("current")) if ap.get("current") is not None else None
    except (TypeError, ValueError):
        ap_current = None
    try:
        ap_max = int(ap.get("max")) if ap.get("max") is not None else None
    except (TypeError, ValueError):
        ap_max = None

    return ArknightsBox(
        uid=str(status.get("uid") or uid),
        name=str(status.get("name") or uid),
        level=player_level,
        register_ts=register_ts,
        ap_current=ap_current,
        ap_max=ap_max,
        char_count=len(chars),
        chars=chars,
    )


def fetch_arknights_box(session: SklandSession, uid: str) -> ArknightsBox:
    return parse_arknights_box(fetch_player_info(session, uid), uid=uid)


_ENDFIELD_SKILL_ORDER = {
    "skill_type_normal_attack": 0,
    "normal_attack": 0,
    "normal_skill": 1,
    "skill_type_normal_skill": 1,
    "combo_skill": 2,
    "skill_type_combo_skill": 2,
    "ultimate_skill": 3,
    "skill_type_ultimate_skill": 3,
}

_ENDFIELD_EQUIP_SLOTS = (
    ("bodyEquip", "护甲"),
    ("armEquip", "护手"),
    ("firstAccessory", "配件·一"),
    ("secondAccessory", "配件·二"),
)

_ENDFIELD_SKILL_TYPE_LABEL = {
    "skill_type_normal_attack": "普攻",
    "normal_attack": "普攻",
    "normal_skill": "战技",
    "skill_type_normal_skill": "战技",
    "combo_skill": "连携技",
    "skill_type_combo_skill": "连携技",
    "ultimate_skill": "终结技",
    "skill_type_ultimate_skill": "终结技",
}


def fetch_endfield_card_detail(session: SklandSession, role: SklandRole) -> dict[str, Any]:
    """拉取终末地养成卡原始响应（整包 JSON，供落库）。"""
    if not role.role_id or not role.server_id:
        raise SklandApiError("缺少终末地角色参数，无法拉取养成卡")
    params = {
        "roleId": str(role.role_id),
        "serverId": str(role.server_id),
    }
    uid = str(role.uid or "").strip()
    if uid:
        params["uid"] = uid
    query = urllib.parse.urlencode(params)
    url = f"{ENDFIELD_CARD_DETAIL_URL}?{query}"
    headers = _signed_headers(session, url, "get", None)
    headers["sk-game-role"] = f"3_{role.role_id}_{role.server_id}"
    resp = _http_json("GET", url, headers=headers)
    if resp.get("code") != 0:
        raise SklandApiError(
            resp.get("message") or "获取终末地养成卡失败",
            code=resp.get("code"),
        )
    return resp


def _endfield_extract_detail(raw: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw.get("detail"), dict):
        return raw["detail"]
    data = raw.get("data")
    if isinstance(data, dict):
        if isinstance(data.get("detail"), dict):
            return data["detail"]
        if "base" in data or "chars" in data:
            return data
    if "base" in raw or "chars" in raw:
        return raw
    return {}


def _endfield_int(value: Any, default: int = 0) -> int:
    if isinstance(value, dict):
        for k in ("value", "level", "id"):
            if k in value:
                return _endfield_int(value.get(k), default)
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        if isinstance(value, str):
            s = value.strip()
            # equip_level_70
            if "_" in s:
                tail = s.rsplit("_", 1)[-1]
                if tail.isdigit():
                    return int(tail)
        return default


def _endfield_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, dict) and not value:
        return None
    n = _endfield_int(value, -10**9)
    if n == -10**9:
        return None
    return n


def _endfield_rarity(value: Any) -> int:
    if isinstance(value, dict):
        key = value.get("key")
        if isinstance(key, str) and "rarity" in key:
            tail = key.rsplit("_", 1)[-1]
            if tail.isdigit():
                return max(1, min(6, int(tail)))
        for k in ("value", "id", "rarity"):
            if k in value:
                return _endfield_rarity(value.get(k))
        return 1
    if isinstance(value, (int, float)):
        n = int(value)
        # 部分接口用 0-5 表示 1-6 星
        if 0 <= n <= 5:
            return n + 1
        return max(1, min(6, n))
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return _endfield_rarity(int(s))
        if "rarity" in s:
            tail = s.rsplit("_", 1)[-1]
            if tail.isdigit():
                return max(1, min(6, int(tail)))
    return 1


def _endfield_named(value: Any) -> tuple[str, str]:
    """返回 (id_or_key, display_name)。"""
    if isinstance(value, dict):
        vid = str(value.get("id") or value.get("key") or "").strip()
        name = str(value.get("value") or value.get("name") or vid).strip()
        return vid, name
    if value is None:
        return "", ""
    s = str(value).strip()
    return s, s


def _endfield_icon(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    for key in ("iconUrl", "icon", "avatarSqUrl", "avatarRtUrl", "avatarUrl"):
        url = obj.get(key)
        if url:
            return str(url).strip() or None
    return None


def _parse_endfield_equip(slot: str, label: str, raw: Any) -> EndfieldEquip | None:
    if not isinstance(raw, dict) or not raw:
        return None
    data = raw.get("equipData") or raw.get("itemData") or raw.get("data") or raw
    if not isinstance(data, dict):
        data = raw
    item_id = str(
        data.get("id") or raw.get("equipId") or raw.get("id") or ""
    ).strip()
    name = str(data.get("name") or raw.get("name") or item_id or label).strip()
    if not item_id and not name:
        return None

    # 精锻：国服多为 equipData.level={key:equip_level_70,value:"70"}；也兼容 refine/forge 键
    refine = None
    for src in (raw, data):
        if not isinstance(src, dict):
            continue
        for key in (
            "refineLevel",
            "forgeLevel",
            "enhanceLevel",
            "breakthroughLevel",
            "精锻",
        ):
            if key in src and src.get(key) is not None:
                refine = _endfield_optional_int(src.get(key))
                if refine is not None:
                    break
        if refine is not None:
            break
    level = _endfield_optional_int(data.get("level"))
    if level is None:
        level = _endfield_optional_int(raw.get("level"))
    if refine is None and level is not None:
        # 无独立精锻字段时，装备等级即精锻等级
        refine = level

    return EndfieldEquip(
        slot=slot,
        item_id=item_id or name,
        name=name or label,
        icon_url=_endfield_icon(data) or _endfield_icon(raw),
        rarity=_endfield_rarity(data.get("rarity") if isinstance(data, dict) else None),
        level=level,
        refine_level=refine,
    )


def _parse_endfield_weapon(raw: Any) -> EndfieldWeapon | None:
    if not isinstance(raw, dict) or not raw:
        return None
    data = raw.get("weaponData") if isinstance(raw.get("weaponData"), dict) else raw
    weapon_id = str(data.get("id") or raw.get("id") or "").strip()
    name = str(data.get("name") or raw.get("name") or weapon_id).strip()
    if not weapon_id and not name:
        return None
    _, weapon_type = _endfield_named(data.get("type") or raw.get("type"))
    gem = raw.get("gem") if isinstance(raw.get("gem"), dict) else {}
    gem_data = gem.get("gemData") if isinstance(gem.get("gemData"), dict) else {}
    gem_icon = (
        str(gem_data.get("icon") or "").strip()
        or str(gem.get("icon") or "").strip()
        or None
    )
    return EndfieldWeapon(
        weapon_id=weapon_id or name,
        name=name or weapon_id,
        icon_url=_endfield_icon(data) or _endfield_icon(raw),
        rarity=_endfield_rarity(data.get("rarity")),
        level=_endfield_int(raw.get("level"), 1),
        refine_level=_endfield_int(raw.get("refineLevel"), 0),
        breakthrough_level=_endfield_int(raw.get("breakthroughLevel"), 0),
        weapon_type=weapon_type,
        gem_id=str(gem.get("id") or gem_data.get("termId") or "").strip(),
        gem_name=str(gem_data.get("name") or "").strip(),
        gem_icon_url=gem_icon or None,
    )


def _parse_endfield_skills(
    char_data: dict[str, Any], user_skills: Any
) -> list[EndfieldSkill]:
    catalog = char_data.get("skills") if isinstance(char_data.get("skills"), list) else []
    levels: dict[str, dict[str, Any]] = {}
    if isinstance(user_skills, dict):
        for sid, row in user_skills.items():
            if isinstance(row, dict):
                levels[str(sid)] = row
                nested_id = str(row.get("skillId") or "").strip()
                if nested_id:
                    levels[nested_id] = row

    skills: list[EndfieldSkill] = []
    for row in catalog:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue
        type_obj = row.get("type")
        type_key, type_value = _endfield_named(type_obj)
        if not type_key and isinstance(type_obj, str):
            type_key = type_obj
        type_label = (
            _ENDFIELD_SKILL_TYPE_LABEL.get(type_key)
            or type_value
            or type_key
            or "技能"
        )
        lvl_row = levels.get(sid) or {}
        skills.append(
            EndfieldSkill(
                skill_id=sid,
                name=str(row.get("name") or sid).strip(),
                skill_type=type_key,
                type_label=type_label,
                icon_url=_endfield_icon(row),
                level=_endfield_int(lvl_row.get("level"), 1),
                max_level=_endfield_int(lvl_row.get("maxLevel"), 0),
            )
        )
    skills.sort(
        key=lambda s: (_ENDFIELD_SKILL_ORDER.get(s.skill_type, 99), s.skill_id)
    )
    return skills


def _parse_endfield_char(item: dict[str, Any]) -> EndfieldChar | None:
    char_data = item.get("charData") if isinstance(item.get("charData"), dict) else {}
    char_id = str(
        item.get("id") or char_data.get("id") or item.get("charId") or ""
    ).strip()
    name = str(char_data.get("name") or item.get("name") or char_id).strip()
    if not char_id and not name:
        return None
    _, profession = _endfield_named(char_data.get("profession"))
    prop_obj = char_data.get("property")
    _, property_name = _endfield_named(prop_obj)
    prop_icon = None
    if isinstance(prop_obj, dict):
        prop_icon = _endfield_icon(prop_obj)
    _, weapon_type = _endfield_named(char_data.get("weaponType"))
    label_key, label_val = _endfield_named(char_data.get("labelType"))
    label_type = label_key or label_val
    gender = str(item.get("gender") or char_data.get("gender") or "").strip()
    own_ts = _endfield_optional_int(item.get("ownTs"))

    equips: list[EndfieldEquip] = []
    for field, label in _ENDFIELD_EQUIP_SLOTS:
        eq = _parse_endfield_equip(field, label, item.get(field))
        if eq:
            equips.append(eq)

    return EndfieldChar(
        char_id=char_id or name,
        name=name or char_id,
        rarity=_endfield_rarity(char_data.get("rarity")),
        level=_endfield_int(item.get("level"), 1),
        evolve_phase=_endfield_int(item.get("evolvePhase"), 0),
        potential_level=_endfield_int(item.get("potentialLevel"), 0),
        profession=profession,
        property_name=property_name,
        weapon_type=weapon_type,
        label_type=label_type,
        own_ts=own_ts,
        gender=gender,
        avatar_url=(
            str(char_data.get("avatarSqUrl") or "").strip()
            or str(char_data.get("avatarRtUrl") or "").strip()
            or None
        ),
        illustration_url=str(char_data.get("illustrationUrl") or "").strip() or None,
        property_icon_url=prop_icon,
        weapon=_parse_endfield_weapon(item.get("weapon")),
        skills=_parse_endfield_skills(char_data, item.get("userSkills")),
        equips=equips,
    )


def parse_endfield_box(
    raw: dict[str, Any],
    *,
    role: SklandRole | None = None,
) -> EndfieldBox:
    """从落库的原始响应二次加工为展示结构。"""
    detail = _endfield_extract_detail(raw)
    base = detail.get("base") if isinstance(detail.get("base"), dict) else {}
    raw_chars = detail.get("chars") if isinstance(detail.get("chars"), list) else []

    chars: list[EndfieldChar] = []
    for item in raw_chars:
        if not isinstance(item, dict):
            continue
        parsed = _parse_endfield_char(item)
        if parsed:
            chars.append(parsed)
    chars.sort(key=lambda c: (-c.rarity, -c.level, -c.potential_level, c.name))

    role_id = str(base.get("roleId") or (role.role_id if role else "") or "").strip()
    uid = str(
        base.get("uid")
        or base.get("roleId")
        or (role.uid if role else "")
        or role_id
    ).strip()
    server_id = str(
        base.get("serverId") or (role.server_id if role else "") or ""
    ).strip()
    char_num = _endfield_int(base.get("charNum"), len(chars))

    return EndfieldBox(
        uid=uid or role_id,
        role_id=role_id or uid,
        server_id=server_id,
        name=str(base.get("name") or (role.role_name if role else "") or uid).strip(),
        level=_endfield_int(base.get("level"), 0),
        server_name=str(
            base.get("serverName") or (role.channel_name if role else "") or ""
        ).strip(),
        avatar_url=str(base.get("avatarUrl") or "").strip() or None,
        char_count=char_num or len(chars),
        chars=chars,
    )
