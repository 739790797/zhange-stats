"""异环角色盒子：上游 fetch / parse / 读库编排。"""

from __future__ import annotations

import json
import logging
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.exastris import ExastrisBoxRaw
from app.models.member import Member
from app.services.taygedo_client import (
    GAME_NTE,
    GAME_NTE_NAME,
    H5_ORIGIN,
    TAYGEDO_BASE,
    TaygedoApiError,
    TaygedoCredentials,
    TaygedoRole,
    _http,
    list_nte_roles,
)

logger = logging.getLogger(__name__)

# 静态立绘 CDN（与开源 taygedo.py assets.nte 一致）
_CHAR_CDN = (
    "https://webstatic.tajiduo.com/bbs/yh-game-records-web-source/character"
)

# 品质排序：未知靠后
_QUALITY_RANK = {
    "S": 0,
    "s": 0,
    "A": 1,
    "a": 1,
    "B": 2,
    "b": 2,
}

# 上游 wire → 展示（橙=S / 紫=A；属性六系；定位=武器形态）
_QUALITY_LABEL = {
    "ITEM_QUALITY_ORANGE": "S",
    "ITEM_QUALITY_PURPLE": "A",
    "ITEM_QUALITY_BLUE": "B",
    "ORANGE": "S",
    "PURPLE": "A",
    "BLUE": "B",
    "S": "S",
    "A": "A",
    "B": "B",
}

_ELEMENT_LABEL = {
    "COSMOS": "相",
    "ANIMA": "灵",
    "INCANTATION": "咒",
    "CHAOS": "暗",
    "PSYCHE": "魂",
    "LAKSHANA": "光",
    "NATURE": "自然",
}

_GROUP_LABEL = {
    "ONE": "固态",
    "TWO": "气态",
    "THREE": "凝态",
    "FOUR": "合成",
    "FIVE": "液态",
    "SIX": "等离子",
    "ATTACK": "输出",
    "SUPPORT": "辅助",
    "DEFENSE": "防御",
    "ASSIST": "辅助",
}


def _wire_token(raw: str) -> str:
    """取 CHARACTER_ELEMENT_TYPE_COSMOS / ITEM_QUALITY_ORANGE 末段。"""
    text = str(raw or "").strip()
    if not text:
        return ""
    return text.rsplit("_", 1)[-1].upper()


def normalize_quality(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if upper in _QUALITY_LABEL:
        return _QUALITY_LABEL[upper]
    token = _wire_token(text)
    return _QUALITY_LABEL.get(token, token or text)


def normalize_element_label(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    token = _wire_token(text)
    return _ELEMENT_LABEL.get(token, token or text)


def normalize_group_label(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    token = _wire_token(text)
    return _GROUP_LABEL.get(token, token or text)


@dataclass
class ExastrisChar:
    char_id: str
    name: str
    quality: str = ""
    element_type: str = ""
    group_type: str = ""
    awaken_lev: int = 0
    portrait_url: str | None = None
    element_icon_url: str | None = None


@dataclass
class ExastrisBox:
    uid: str
    role_id: str
    role_name: str
    game_code: str
    game_name: str
    char_count: int
    chars: list[ExastrisChar] = field(default_factory=list)


def portrait_url_for(char_id: str) -> str:
    cid = str(char_id or "").strip()
    return f"{_CHAR_CDN}/tall/{cid}.PNG" if cid else ""


def element_icon_url_for(element_type: str) -> str | None:
    et = str(element_type or "").strip()
    if not et:
        return None
    return f"{_CHAR_CDN}/element/{et}.PNG"


def _h5_headers(creds: TaygedoCredentials) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": creds.access_token,
        "Origin": H5_ORIGIN,
        "Referer": f"{H5_ORIGIN}/",
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Tajiduo/1.2.2"
        ),
    }


def fetch_exastris_characters(
    creds: TaygedoCredentials, role_id: str
) -> dict[str, Any]:
    """GET /apihub/awapi/yh/characters?roleId= — 返回上游整包 JSON。"""
    rid = str(role_id or "").strip()
    if not rid:
        raise TaygedoApiError("异环角色缺少 roleId")
    query = urllib.parse.urlencode({"roleId": rid})
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/apihub/awapi/yh/characters?{query}",
        headers=_h5_headers(creds),
    )
    if status != 200 or data.get("code") != 0:
        msg = str(data.get("msg") or data.get("message") or "获取异环角色列表失败")
        code = data.get("code") if isinstance(data.get("code"), int) else None
        raise TaygedoApiError(msg, code=code or status)
    return data


def _parse_char(item: dict[str, Any]) -> ExastrisChar | None:
    char_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    if not char_id and not name:
        return None
    if not char_id:
        char_id = name
    if not name:
        name = char_id
    quality_raw = str(item.get("quality") or "").strip()
    element_raw = str(
        item.get("elementType") or item.get("element_type") or ""
    ).strip()
    group_raw = str(item.get("groupType") or item.get("group_type") or "").strip()
    try:
        awaken_lev = int(item.get("awakenLev") or item.get("awaken_lev") or 0)
    except (TypeError, ValueError):
        awaken_lev = 0
    portrait = portrait_url_for(char_id) or None
    return ExastrisChar(
        char_id=char_id,
        name=name,
        quality=normalize_quality(quality_raw),
        element_type=normalize_element_label(element_raw),
        group_type=normalize_group_label(group_raw),
        awaken_lev=awaken_lev,
        portrait_url=portrait,
        # CDN 路径用上游原文（CHARACTER_ELEMENT_TYPE_*）
        element_icon_url=element_icon_url_for(element_raw) if element_raw else None,
    )


def _chars_list_from_raw(raw: dict[str, Any]) -> list[Any]:
    data = raw.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "characters", "chars", "items"):
            nested = data.get(key)
            if isinstance(nested, list):
                return nested
    if isinstance(raw.get("characters"), list):
        return raw["characters"]
    return []


def parse_exastris_box(
    raw: dict[str, Any],
    *,
    role: TaygedoRole,
) -> ExastrisBox:
    """从上游整包二次加工为盒子结构（纯函数）。"""
    chars: list[ExastrisChar] = []
    for item in _chars_list_from_raw(raw):
        if not isinstance(item, dict):
            continue
        parsed = _parse_char(item)
        if parsed is not None:
            chars.append(parsed)

    chars.sort(
        key=lambda c: (
            _QUALITY_RANK.get(c.quality, 99),
            -c.awaken_lev,
            c.name,
            c.char_id,
        )
    )
    return ExastrisBox(
        uid=str(role.role_id),
        role_id=str(role.role_id),
        role_name=str(role.role_name or GAME_NTE_NAME),
        game_code=GAME_NTE,
        game_name=GAME_NTE_NAME,
        char_count=len(chars),
        chars=chars,
    )


def get_exastris_box_for_member(
    db: Session,
    member: Member,
    uid: str | None = None,
    *,
    force: bool = False,
):
    """读库二次加工异环盒子；无记录或 force 时回源落库。"""
    from app.services.taygedo_attendance import ensure_session
    from app.services.taygedo_checkin import _load_creds, _save_creds, get_bind_for_member

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")

    creds = _load_creds(bind)
    roles: list[TaygedoRole] | None = None
    if not force:
        from app.services.box_role_cache import taygedo_nte_roles_from_raws

        roles = taygedo_nte_roles_from_raws(db, member.id)

    working = None
    if roles is None:
        working = ensure_session(creds)
        if working.access_token != creds.access_token or working.refresh_token != creds.refresh_token:
            _save_creds(bind, working)
            db.commit()
        roles = list_nte_roles(working)
    if not roles:
        raise TaygedoApiError("未找到异环绑定角色")

    target_uid = str(uid or "").strip()
    role: TaygedoRole | None = None
    if target_uid:
        role = next((r for r in roles if r.role_id == target_uid), None)
    else:
        role = roles[0]
    if role is None:
        raise TaygedoApiError("UID 不在当前异环绑定列表中")
    if not role.role_id:
        raise TaygedoApiError("异环角色缺少 roleId，请重新绑定塔吉多")

    row = (
        db.query(ExastrisBoxRaw)
        .filter(
            ExastrisBoxRaw.member_id == member.id,
            ExastrisBoxRaw.role_id == str(role.role_id),
        )
        .one_or_none()
    )
    stale = False
    if force or row is None:
        try:
            if working is None:
                working = ensure_session(creds)
                if (
                    working.access_token != creds.access_token
                    or working.refresh_token != creds.refresh_token
                ):
                    _save_creds(bind, working)
                    db.commit()
            raw = fetch_exastris_characters(working, role.role_id)
            raw_json = json.dumps(raw, ensure_ascii=False)
            from app.services.raw_payload_monitor import note_raw_payload

            note_raw_payload(
                "exastris_box_raw",
                raw_json,
                member_id=member.id,
                role_id=role.role_id,
            )
            now = now_naive()
            if row is None:
                row = ExastrisBoxRaw(
                    member_id=member.id,
                    role_id=str(role.role_id),
                    uid=str(role.role_id),
                    raw_json=raw_json,
                    synced_at=now,
                )
                db.add(row)
            else:
                row.uid = str(role.role_id)
                row.raw_json = raw_json
                row.synced_at = now
            db.commit()
            db.refresh(row)
        except TaygedoApiError:
            if row is None:
                raise
            stale = True
            logger.exception(
                "exastris box refresh failed member_id=%s role_id=%s",
                member.id,
                role.role_id,
            )

    try:
        raw_obj = json.loads(row.raw_json)
    except json.JSONDecodeError as exc:
        raise TaygedoApiError("异环养成数据损坏，请刷新重试") from exc
    if not isinstance(raw_obj, dict):
        raise TaygedoApiError("异环养成数据格式异常，请刷新重试")

    box = parse_exastris_box(raw_obj, role=role)
    return box, role, roles, row.synced_at, stale
