"""鸣潮 roleBox 资料卡：上游 fetch / parse / 读库编排。

开源对齐：TomyJan/Kuro-API-Collection + WavesUID 鉴权链
- POST /aki/roleBox/requestToken → accessToken（b-at）
- POST /aki/roleBox/akiBox/refreshData / baseData / calabashData
  （资料卡请求只带 did + b-at，不可再带用户 token，否则 10000/10900）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.kujiequ import KujiequWwBoxRaw
from app.models.member import Member
from app.services.kujiequ.client import (
    GAME_NAMES,
    GAME_WW,
    GameRole,
    KujiequApiError,
    KujiequCredentials,
    _assert_ok,
    _ensure_device,
    _post_form,
    list_roles_for_game,
)

logger = logging.getLogger(__name__)

# 开源文档：声骸接口固定渠道 19；国家默认隍陇=1
_CALABASH_CHANNEL_ID = 19
_CALABASH_COUNTRY_CODE = 1

# roleBox 链路探测：ios 头 + did/b-at（无用户 token）可通；混 token 会 10000「参数错误」
_ROLEBOX_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) KuroGameBox/3.1.3"
)
_ROLEBOX_VERSION = "3.1.3"


@dataclass
class WwBoxItem:
    name: str
    num: int = 0
    icon_url: str | None = None


@dataclass
class WwBox:
    uid: str
    role_id: str
    role_name: str
    server_id: str = ""
    server_name: str = ""
    game_code: str = str(GAME_WW)
    game_name: str = GAME_NAMES[GAME_WW]
    level: int = 0
    world_level: int = 0
    active_days: int = 0
    role_num: int = 0
    achievement_count: int = 0
    achievement_star: int = 0
    energy: int = 0
    max_energy: int = 0
    store_energy: int = 0
    store_energy_limit: int = 0
    store_energy_title: str = ""
    store_energy_icon_url: str | None = None
    liveness: int = 0
    liveness_max: int = 0
    small_count: int = 0
    big_count: int = 0
    sound_box: int = 0
    weekly_inst_count: int = 0
    weekly_inst_limit: int = 0
    weekly_inst_title: str = ""
    weekly_inst_icon_url: str | None = None
    rouge_score: int = 0
    rouge_score_limit: int = 0
    rouge_title: str = ""
    rouge_icon_url: str | None = None
    treasure_boxes: list[WwBoxItem] = field(default_factory=list)
    phantom_boxes: list[WwBoxItem] = field(default_factory=list)
    calabash_level: int = 0
    calabash_unlock: int = 0
    calabash_max: int = 0
    calabash_cost: int = 0


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def unwrap_aki_data(payload: Any) -> dict[str, Any]:
    """上游 data 常为字符串 JSON；统一解包为 dict。"""
    if isinstance(payload, dict):
        inner = payload.get("data", payload)
    else:
        inner = payload
    if isinstance(inner, str):
        text = inner.strip()
        if not text:
            return {}
        try:
            inner = json.loads(text)
        except json.JSONDecodeError as exc:
            raise KujiequApiError("鸣潮资料卡数据格式异常") from exc
    if not isinstance(inner, dict):
        return {}
    return inner


def _rolebox_headers(
    creds: KujiequCredentials,
    *,
    bat: str = "",
    with_user_token: bool = False,
) -> dict[str, str]:
    """roleBox 专用头。资料卡查询必须 with_user_token=False。"""
    creds = _ensure_device(creds)
    did = str(creds.dev_code or "").strip()
    headers = {
        "source": "ios",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": _ROLEBOX_UA,
        "devCode": f"127.0.0.1, {_ROLEBOX_UA}",
        "version": _ROLEBOX_VERSION,
        "did": did,
        "b-at": str(bat or ""),
    }
    if with_user_token:
        token = str(creds.token or "").strip()
        if not token:
            raise KujiequApiError("缺少 token，请重新绑定库街区")
        headers["token"] = token
        headers["Cookie"] = f"user_token={token}"
    return headers


def _role_form(role: GameRole) -> dict[str, Any]:
    if not role.role_id or not role.server_id:
        raise KujiequApiError("鸣潮角色缺少 roleId/serverId")
    return {
        "gameId": GAME_WW,
        "roleId": role.role_id,
        "serverId": role.server_id,
    }


def request_ww_bat_token(creds: KujiequCredentials, role: GameRole) -> str:
    """POST /aki/roleBox/requestToken — 需用户 token + did；返回 b-at。"""
    creds = _ensure_device(creds)
    data = _post_form(
        "/aki/roleBox/requestToken",
        {"roleId": role.role_id, "serverId": role.server_id},
        headers=_rolebox_headers(creds, bat="", with_user_token=True),
    )
    _assert_ok(data)
    payload = unwrap_aki_data(data)
    bat = str(payload.get("accessToken") or "").strip()
    if not bat:
        raise KujiequApiError("未获取到鸣潮数据令牌，请稍后重试")
    return bat


def refresh_ww_role_data(
    creds: KujiequCredentials, role: GameRole, *, bat: str
) -> None:
    """POST /aki/roleBox/akiBox/refreshData — 只带 did + b-at。"""
    data = _post_form(
        "/aki/roleBox/akiBox/refreshData",
        _role_form(role),
        headers=_rolebox_headers(creds, bat=bat, with_user_token=False),
    )
    _assert_ok(data)


def fetch_ww_base_data(
    creds: KujiequCredentials, role: GameRole, *, bat: str
) -> dict[str, Any]:
    """POST /aki/roleBox/akiBox/baseData — 只带 did + b-at。"""
    data = _post_form(
        "/aki/roleBox/akiBox/baseData",
        _role_form(role),
        headers=_rolebox_headers(creds, bat=bat, with_user_token=False),
    )
    _assert_ok(data)
    return unwrap_aki_data(data)


def fetch_ww_calabash_data(
    creds: KujiequCredentials,
    role: GameRole,
    *,
    bat: str,
    country_code: int = _CALABASH_COUNTRY_CODE,
) -> dict[str, Any]:
    """POST /aki/roleBox/akiBox/calabashData — 只带 did + b-at。"""
    form = {
        **_role_form(role),
        "channelId": _CALABASH_CHANNEL_ID,
        "countryCode": int(country_code),
    }
    data = _post_form(
        "/aki/roleBox/akiBox/calabashData",
        form,
        headers=_rolebox_headers(creds, bat=bat, with_user_token=False),
    )
    _assert_ok(data)
    return unwrap_aki_data(data)


def fetch_ww_box_bundle(creds: KujiequCredentials, role: GameRole) -> dict[str, Any]:
    """回源：换 bat → refresh → base；calabash 失败则记空对象。"""
    creds = _ensure_device(creds)
    bat = request_ww_bat_token(creds, role)
    try:
        refresh_ww_role_data(creds, role, bat=bat)
    except KujiequApiError as exc:
        if exc.code in (220, 401):
            raise
        # refresh 失败仍尝试读 base（部分账号 refresh 偶发失败）
        logger.warning(
            "ww refreshData failed role_id=%s: %s",
            role.role_id,
            exc.message,
        )
    base = fetch_ww_base_data(creds, role, bat=bat)
    calabash: dict[str, Any] = {}
    try:
        calabash = fetch_ww_calabash_data(creds, role, bat=bat)
    except KujiequApiError as exc:
        if exc.code in (220, 401):
            raise
        logger.warning(
            "ww calabash fetch failed role_id=%s: %s",
            role.role_id,
            exc.message,
        )
    return {"base": base, "calabash": calabash}


def _parse_named_items(rows: Any, *, name_keys: tuple[str, ...] = ("boxName", "name")) -> list[WwBoxItem]:
    if not isinstance(rows, list):
        return []
    out: list[WwBoxItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = ""
        for key in name_keys:
            name = str(row.get(key) or "").strip()
            if name:
                break
        if not name:
            continue
        icon = str(row.get("iconUrl") or row.get("icon") or "").strip() or None
        out.append(WwBoxItem(name=name, num=_to_int(row.get("num")), icon_url=icon))
    return out


def parse_ww_box(raw: dict[str, Any], *, role: GameRole) -> WwBox:
    """从组合 raw 二次加工为资料卡（纯函数）。"""
    base = raw.get("base") if isinstance(raw.get("base"), dict) else {}
    if not base and isinstance(raw, dict) and ("level" in raw or "name" in raw or "roleNum" in raw):
        # 兼容直接存 base 对象
        base = raw
    calabash = raw.get("calabash") if isinstance(raw.get("calabash"), dict) else {}

    treasure = _parse_named_items(base.get("treasureBoxList") or base.get("boxList"))
    phantoms = _parse_named_items(base.get("phantomBoxList"))

    role_name = str(base.get("name") or role.role_name or "").strip() or role.role_name
    uid = str(base.get("id") or role.role_id).strip() or role.role_id

    return WwBox(
        uid=uid,
        role_id=str(role.role_id),
        role_name=role_name,
        server_id=str(role.server_id or ""),
        server_name=str(role.server_name or ""),
        game_code=str(GAME_WW),
        game_name=GAME_NAMES[GAME_WW],
        level=_to_int(base.get("level")),
        world_level=_to_int(base.get("worldLevel")),
        active_days=_to_int(base.get("activeDays")),
        role_num=_to_int(base.get("roleNum")),
        achievement_count=_to_int(base.get("achievementCount")),
        achievement_star=_to_int(base.get("achievementStar")),
        energy=_to_int(base.get("energy")),
        max_energy=_to_int(base.get("maxEnergy")),
        store_energy=_to_int(base.get("storeEnergy")),
        store_energy_limit=_to_int(base.get("storeEnergyLimit")),
        store_energy_title=str(base.get("storeEnergyTitle") or "").strip(),
        store_energy_icon_url=str(base.get("storeEnergyIconUrl") or "").strip() or None,
        liveness=_to_int(base.get("liveness")),
        liveness_max=_to_int(base.get("livenessMaxCount")),
        small_count=_to_int(base.get("smallCount")),
        big_count=_to_int(base.get("bigCount")),
        sound_box=_to_int(base.get("soundBox")),
        weekly_inst_count=_to_int(base.get("weeklyInstCount")),
        weekly_inst_limit=_to_int(base.get("weeklyInstCountLimit")),
        weekly_inst_title=str(base.get("weeklyInstTitle") or "").strip(),
        weekly_inst_icon_url=str(base.get("weeklyInstIconUrl") or "").strip() or None,
        rouge_score=_to_int(base.get("rougeScore")),
        rouge_score_limit=_to_int(base.get("rougeScoreLimit")),
        rouge_title=str(base.get("rougeTitle") or "").strip(),
        rouge_icon_url=str(base.get("rougeIconUrl") or "").strip() or None,
        treasure_boxes=treasure,
        phantom_boxes=phantoms,
        calabash_level=_to_int(calabash.get("level")),
        calabash_unlock=_to_int(calabash.get("unlockCount")),
        calabash_max=_to_int(calabash.get("maxCount")),
        calabash_cost=_to_int(calabash.get("cost")),
    )


def get_ww_box_for_member(
    db: Session,
    member: Member,
    uid: str | None = None,
    *,
    force: bool = False,
):
    """读库二次加工鸣潮资料卡；无记录或 force 时回源落库。"""
    from app.services.kujiequ.checkin import _load_creds, _save_creds, get_bind_for_member

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")

    creds = _load_creds(bind)
    had_device = bool(creds.dev_code and creds.distinct_id)
    creds = _ensure_device(creds)
    if not had_device:
        # 稳定 did：首次生成后写回，避免每次换 did 导致 bat 失效
        _save_creds(bind, creds)
        db.commit()

    roles: list[GameRole] | None = None
    if not force:
        from app.services.box_role_cache import kujiequ_ww_roles_from_raws

        roles = kujiequ_ww_roles_from_raws(db, member.id)
    if roles is None:
        roles = list_roles_for_game(creds, GAME_WW)
    if not roles:
        raise KujiequApiError("未找到鸣潮绑定角色")

    target_uid = str(uid or "").strip()
    role: GameRole | None = None
    if target_uid:
        role = next((r for r in roles if r.role_id == target_uid), None)
    else:
        role = roles[0]
    if role is None:
        raise KujiequApiError("UID 不在当前鸣潮绑定列表中")
    if not role.role_id:
        raise KujiequApiError("鸣潮角色缺少 roleId，请重新绑定库街区")

    row = (
        db.query(KujiequWwBoxRaw)
        .filter(
            KujiequWwBoxRaw.member_id == member.id,
            KujiequWwBoxRaw.role_id == str(role.role_id),
        )
        .one_or_none()
    )
    if (force or row is None) and not role.server_id:
        roles = list_roles_for_game(creds, GAME_WW)
        if target_uid:
            role = next((r for r in roles if r.role_id == target_uid), None)
        else:
            role = roles[0] if roles else None
        if role is None or not role.role_id or not role.server_id:
            raise KujiequApiError("鸣潮角色缺少 roleId/serverId，请重新绑定库街区")
    stale = False
    if force or row is None:
        try:
            bundle = fetch_ww_box_bundle(creds, role)
            raw_json = json.dumps(bundle, ensure_ascii=False)
            from app.services.raw_payload_monitor import note_raw_payload

            note_raw_payload(
                "kujiequ_ww_box_raw",
                raw_json,
                member_id=member.id,
                role_id=role.role_id,
            )
            now = now_naive()
            if row is None:
                row = KujiequWwBoxRaw(
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
        except KujiequApiError:
            if row is None:
                raise
            stale = True
            logger.exception(
                "ww box refresh failed member_id=%s role_id=%s",
                member.id,
                role.role_id,
            )

    try:
        raw_obj = json.loads(row.raw_json)
    except json.JSONDecodeError as exc:
        raise KujiequApiError("鸣潮资料卡数据损坏，请刷新重试") from exc
    if not isinstance(raw_obj, dict):
        raise KujiequApiError("鸣潮资料卡数据格式异常，请刷新重试")

    box = parse_ww_box(raw_obj, role=role)
    return box, role, roles, row.synced_at, stale
