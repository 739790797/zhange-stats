"""森空岛角色列表与签到 HTTP（从 skland_client 拆出）。"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

from app.services.checkin_common import CheckinResult
from app.services.skland_client import (
    ARKNIGHTS_ATTENDANCE_URL,
    BINDING_URL,
    ENDFIELD_ATTENDANCE_RECORD_URL,
    ENDFIELD_ATTENDANCE_URL,
    GAME_ARKNIGHTS,
    GAME_ENDFIELD,
    GAME_META,
    SklandApiError,
    SklandRole,
    SklandSession,
    _http_json,
    _signed_headers,
)

logger = logging.getLogger(__name__)

def fetch_binding_list(session: SklandSession) -> list[dict[str, Any]]:
    headers = _signed_headers(session, BINDING_URL, "get", None)
    resp = _http_json("GET", BINDING_URL, headers=headers)
    if resp.get("code") != 0:
        raise SklandApiError(
            resp.get("message") or "获取绑定角色失败",
            code=resp.get("code"),
        )
    return list((resp.get("data") or {}).get("list") or [])


def _endfield_role_fields(item: dict[str, Any]) -> tuple[str | None, str | None, str, str]:
    """返回 role_id, server_id, role_name, channel_name。"""
    default_role = item.get("defaultRole") or {}
    if not default_role and item.get("roles"):
        roles = item.get("roles") or []
        if roles:
            default_role = roles[0]
    role_id = default_role.get("roleId") or item.get("roleId")
    server_id = default_role.get("serverId") or item.get("serverId")
    role_name = (
        default_role.get("nickname")
        or default_role.get("nickName")
        or item.get("nickName")
        or item.get("nickname")
        or "未知角色"
    )
    channel = (
        default_role.get("serverName")
        or item.get("channelName")
        or item.get("serverName")
        or "未知渠道"
    )
    return (
        str(role_id) if role_id is not None else None,
        str(server_id) if server_id is not None else None,
        str(role_name),
        str(channel),
    )


def _game_sort_key(game_code: str) -> int:
    order = {
        GAME_ARKNIGHTS: 0,
        GAME_ENDFIELD: 1,
    }
    return order.get(game_code, 99)


def _channel_sort_key(
    channel_name: str, channel_master_id: str | None = None
) -> int:
    """同游戏内：官服优先，bilibili 靠后。

    明日方舟 channelMasterId：1=官服，2=bilibili。
    """
    name = (channel_name or "").strip()
    mid = str(channel_master_id or "").strip()
    # 官服
    if mid == "1" or "官服" in name:
        return 0
    # bilibili / 哔哩
    if mid == "2" or "bilibili" in name.lower() or "哔哩" in name:
        return 2
    return 1


def sort_skland_roles(roles: list[SklandRole]) -> list[SklandRole]:
    return sorted(
        roles,
        key=lambda r: (
            _game_sort_key(r.game_code),
            _channel_sort_key(r.channel_name, r.channel_master_id),
            r.role_name or "",
            r.uid or "",
        ),
    )


def sort_skland_results(results: list[CheckinResult]) -> list[CheckinResult]:
    return sorted(
        results,
        key=lambda r: (
            _game_sort_key(r.game_code),
            _channel_sort_key(r.channel_name),
            r.role_name or "",
            r.role_uid or "",
        ),
    )


def list_roles(session: SklandSession) -> list[SklandRole]:
    apps = fetch_binding_list(session)
    roles: list[SklandRole] = []
    for app in apps:
        app_code = str(app.get("appCode") or "")
        if app_code == GAME_ARKNIGHTS:
            meta = GAME_META[GAME_ARKNIGHTS]
            for item in app.get("bindingList") or []:
                uid = str(item.get("uid") or "")
                if not uid:
                    continue
                roles.append(
                    SklandRole(
                        game_code=GAME_ARKNIGHTS,
                        game_name=meta["name"],
                        uid=uid,
                        role_name=str(item.get("nickName") or item.get("nickname") or "未知角色"),
                        channel_name=str(item.get("channelName") or "未知渠道"),
                        channel_master_id=str(item.get("channelMasterId") or "")
                        if item.get("channelMasterId") is not None
                        else None,
                    )
                )
        elif app_code == GAME_ENDFIELD:
            meta = GAME_META[GAME_ENDFIELD]
            for item in app.get("bindingList") or []:
                uid = str(item.get("uid") or item.get("defaultRole", {}).get("roleId") or "")
                role_id, server_id, role_name, channel = _endfield_role_fields(item)
                if not uid and role_id:
                    uid = role_id
                if not uid:
                    continue
                roles.append(
                    SklandRole(
                        game_code=GAME_ENDFIELD,
                        game_name=meta["name"],
                        uid=uid,
                        role_name=role_name,
                        channel_name=channel,
                        role_id=role_id,
                        server_id=server_id,
                    )
                )
    return sort_skland_roles(roles)


def _parse_status(resp: dict[str, Any]) -> tuple[str, str]:
    if resp.get("code") == 0:
        return "ok", "签到成功"
    msg = str(resp.get("message") or "签到失败")
    if "请勿重复签到" in msg or "already" in msg.lower() or "重复" in msg:
        return "already", "今日已签到"
    return "error", msg


def _format_award_items(awards: list[Any]) -> str | None:
    parts: list[str] = []
    for a in awards:
        if not isinstance(a, dict):
            continue
        res = a.get("resource") or {}
        if not isinstance(res, dict):
            res = {}
        name = res.get("name") or a.get("name") or "奖励"
        count = a.get("count") or res.get("count") or 1
        parts.append(f"{name}x{count}")
    return "、".join(parts) if parts else None


def _arknights_awards(resp: dict[str, Any]) -> str | None:
    awards = (resp.get("data") or {}).get("awards") or []
    if not isinstance(awards, list):
        return None
    return _format_award_items(awards)


def _endfield_awards(resp: dict[str, Any]) -> str | None:
    data = resp.get("data") or {}
    award_ids = data.get("awardIds") or []
    resource_map = data.get("resourceInfoMap") or {}
    if not award_ids:
        # 部分终末地响应也直接带 awards
        awards = data.get("awards") or []
        if isinstance(awards, list):
            return _format_award_items(awards)
        return None
    parts = []
    for award in award_ids:
        award_id = award.get("id") if isinstance(award, dict) else award
        if award_id is None:
            continue
        key = str(award_id)
        res = resource_map.get(key) or resource_map.get(award_id)
        if not isinstance(res, dict):
            continue
        parts.append(f'{res.get("name", "奖励")}x{res.get("count", 1)}')
    return "、".join(parts) if parts else None


def _ts_is_beijing_day(ts: Any, day) -> bool:
    try:
        value = int(ts)
    except (TypeError, ValueError):
        return False
    # 毫秒时间戳兜底
    if value > 10_000_000_000:
        value //= 1000
    from datetime import datetime

    from app.core.timeutil import BEIJING

    return datetime.fromtimestamp(value, tz=BEIJING).date() == day


def _award_text_from_resource(
    resource_map: dict[str, Any],
    resource_id: Any,
    count: Any = 1,
) -> str | None:
    if resource_id is None:
        return None
    res = resource_map.get(str(resource_id))
    if res is None and not isinstance(resource_id, str):
        res = resource_map.get(resource_id)
    if not isinstance(res, dict):
        return None
    name = res.get("name") or "奖励"
    # 终末地等：数量常在 resourceInfoMap 里
    raw_count = count if count is not None else res.get("count")
    try:
        qty = int(raw_count) if raw_count is not None else 1
    except (TypeError, ValueError):
        qty = 1
    return f"{name}x{qty}"


def _awards_from_status_items(
    items: list[Any],
    resource_map: dict[str, Any],
    *,
    require_done: bool = False,
) -> str | None:
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if require_done and not item.get("done"):
            continue
        rid = (
            item.get("resourceId")
            or item.get("awardId")
            or item.get("id")
        )
        text = _award_text_from_resource(
            resource_map, rid, item.get("count")
        )
        if text:
            parts.append(text)
    return "、".join(parts) if parts else None


def _awards_from_claim_records(resp: dict[str, Any], *, day) -> str | None:
    """从领取记录中按北京自然日提取奖励（App「领取记录」同源）。

    方舟 attendance GET：data.records[{ts, resourceId, type, count}]
    终末地 attendance/record GET：data.records[{ts, awardId}] + resourceInfoMap

    注意：calendar 下标是「本月第 N 次签到」，不是日历日期，禁止用来查今日奖励。
    """
    if resp.get("code") != 0:
        return None
    data = resp.get("data") or {}
    if not isinstance(data, dict):
        return None

    resource_map = data.get("resourceInfoMap") or {}
    if not isinstance(resource_map, dict):
        resource_map = {}

    records = data.get("records") or []
    if not isinstance(records, list):
        return None

    parts: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if not _ts_is_beijing_day(rec.get("ts"), day):
            continue
        if isinstance(rec.get("awards"), list):
            nested = _format_award_items(rec["awards"])
            if nested:
                parts.append(nested)
            continue
        rid = (
            rec.get("awardId")
            or rec.get("resourceId")
            or rec.get("id")
        )
        text = _award_text_from_resource(resource_map, rid, rec.get("count"))
        if text:
            parts.append(text)
    return "、".join(parts) if parts else None


def _has_claim_today(resp: dict[str, Any], *, day) -> bool:
    if resp.get("code") != 0:
        return False
    data = resp.get("data") or {}
    if not isinstance(data, dict):
        return False
    records = data.get("records") or []
    if not isinstance(records, list):
        return False
    return any(
        isinstance(rec, dict) and _ts_is_beijing_day(rec.get("ts"), day)
        for rec in records
    )


# 兼容旧名
def _awards_from_calendar_get(resp: dict[str, Any], *, day) -> str | None:
    return _awards_from_claim_records(resp, day=day)


def friendly_error_message(msg: str) -> str:
    text = (msg or "").strip() or "未知错误"
    low = text.lower()
    if any(
        k in text
        for k in ("未登录", "登录", "凭证", "cred", "token", "授权", "过期", "失效")
    ) or "unauthorized" in low:
        return f"凭证可能已失效，请重新绑定森空岛（{text}）"
    if any(k in text for k in ("网络", "超时", "timeout", "HTTP", "连接")) or "timed out" in low:
        return f"网络异常，请稍后重试（{text}）"
    return text


_friendly_error_message = friendly_error_message  # 兼容旧引用

def _attendance_get(
    session: SklandSession,
    url_base: str,
    params: dict[str, str],
) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{url_base}?{query}"
    headers = _signed_headers(session, url, "get", None)
    return _http_json("GET", url, headers=headers)


def _resp_has_award_signal(resp: dict[str, Any]) -> bool:
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    if not data:
        return False
    records = data.get("records") or []
    return isinstance(records, list) and bool(records)


def fetch_today_awards(session: SklandSession, role: SklandRole) -> str | None:
    """按领取记录（真实时间戳）读取今日奖励，不依赖签到日历下标。"""
    from app.core.timeutil import today

    day = today()
    try:
        if role.game_code == GAME_ARKNIGHTS:
            # 方舟领取记录在 attendance GET 的 data.records
            candidates: list[str] = []
            if role.channel_master_id:
                candidates.append(str(role.channel_master_id))
            if "1" not in candidates:
                candidates.append("1")
            last_resp: dict[str, Any] | None = None
            for game_id in candidates:
                resp = _attendance_get(
                    session,
                    ARKNIGHTS_ATTENDANCE_URL,
                    {"uid": role.uid, "gameId": game_id},
                )
                last_resp = resp
                text = _awards_from_claim_records(resp, day=day)
                if text:
                    return text
                if _resp_has_award_signal(resp) and game_id != candidates[-1]:
                    continue
            if last_resp is not None:
                data = last_resp.get("data") if isinstance(last_resp.get("data"), dict) else {}
                logger.warning(
                    "arknights claim records empty uid=%s code=%s records=%s",
                    role.uid,
                    last_resp.get("code"),
                    len(data.get("records") or []) if isinstance(data, dict) else -1,
                )
            return None

        if role.game_code == GAME_ENDFIELD:
            if not role.role_id or not role.server_id:
                return None
            resp = _attendance_get(
                session,
                ENDFIELD_ATTENDANCE_RECORD_URL,
                {
                    "uid": role.uid,
                    "gameId": "3",
                    "roleId": str(role.role_id),
                    "serverId": str(role.server_id),
                },
            )
            return _awards_from_claim_records(resp, day=day)
    except SklandApiError as exc:
        logger.warning("fetch today awards failed: %s", exc.message)
        return None
    except Exception:  # noqa: BLE001
        logger.exception("fetch today awards unexpected error")
        return None
    return None


def _signed_today_from_resp(resp: dict[str, Any], *, day) -> bool:
    """是否今日已有领取记录（按 ts，不用 hasToday / calendar）。"""
    return _has_claim_today(resp, day=day)


def query_role_today(session: SklandSession, role: SklandRole) -> CheckinResult:
    """只读查询今日签到状态与奖励（领取记录，不 POST）。"""
    from app.core.timeutil import today

    day = today()
    awards: str | None = None
    signed = False
    try:
        if role.game_code == GAME_ARKNIGHTS:
            candidates: list[str] = []
            if role.channel_master_id:
                candidates.append(str(role.channel_master_id))
            if "1" not in candidates:
                candidates.append("1")
            for game_id in candidates:
                resp = _attendance_get(
                    session,
                    ARKNIGHTS_ATTENDANCE_URL,
                    {"uid": role.uid, "gameId": game_id},
                )
                if _has_claim_today(resp, day=day):
                    signed = True
                text = _awards_from_claim_records(resp, day=day)
                if text:
                    awards = text
                    signed = True
                    break
                if signed:
                    break
        elif role.game_code == GAME_ENDFIELD:
            if role.role_id and role.server_id:
                resp = _attendance_get(
                    session,
                    ENDFIELD_ATTENDANCE_RECORD_URL,
                    {
                        "uid": role.uid,
                        "gameId": "3",
                        "roleId": str(role.role_id),
                        "serverId": str(role.server_id),
                    },
                )
                signed = _has_claim_today(resp, day=day)
                awards = _awards_from_claim_records(resp, day=day)
                if awards:
                    signed = True
    except SklandApiError as exc:
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.uid,
            role_name=role.role_name,
            channel_name=role.channel_name,
            status="error",
            message=friendly_error_message(exc.message),
        )

    if signed:
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.uid,
            role_name=role.role_name,
            channel_name=role.channel_name,
            status="already",
            message=f"今日已签到，获得：{awards}" if awards else "今日已签到",
            awards_text=awards,
        )
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        status="pending",
        message="今日尚未签到",
    )



def query_today_all(session: SklandSession) -> list[CheckinResult]:
    return sort_skland_results(
        [query_role_today(session, role) for role in list_roles(session)]
    )


def checkin_arknights(session: SklandSession, role: SklandRole) -> CheckinResult:
    body = {"uid": role.uid, "gameId": role.channel_master_id}
    headers = _signed_headers(session, ARKNIGHTS_ATTENDANCE_URL, "post", body)
    resp = _http_json("POST", ARKNIGHTS_ATTENDANCE_URL, headers=headers, body=body)
    status, message = _parse_status(resp)
    awards = _arknights_awards(resp)
    if status == "ok" and awards:
        message = f"成功！获得：{awards}"
    elif status == "ok":
        message = "签到成功"
    elif status == "already":
        if not awards:
            awards = fetch_today_awards(session, role)
        message = f"今日已签到，获得：{awards}" if awards else "今日已签到"
    elif status == "error":
        message = _friendly_error_message(message)
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        status=status,
        message=message,
        awards_text=awards,
    )


def checkin_endfield(session: SklandSession, role: SklandRole) -> CheckinResult:
    if not role.role_id or not role.server_id:
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.uid,
            role_name=role.role_name,
            channel_name=role.channel_name,
            status="error",
            message="缺少终末地角色参数，无法签到",
        )

    # 优先使用带 body 的国服接口；失败且提示参数问题时再试 sk-game-role 空 body
    body = {
        "uid": role.uid,
        "gameId": 3,
        "roleId": role.role_id,
        "serverId": role.server_id,
    }
    headers = _signed_headers(session, ENDFIELD_ATTENDANCE_URL, "post", body)
    resp = _http_json("POST", ENDFIELD_ATTENDANCE_URL, headers=headers, body=body)
    status, message = _parse_status(resp)

    if status == "error" and ("参数" in message or "sign" in message.lower()):
        role_str = f"3_{role.role_id}_{role.server_id}"
        headers2 = _signed_headers(session, ENDFIELD_ATTENDANCE_URL, "post", None)
        headers2["sk-game-role"] = role_str
        resp = _http_json("POST", ENDFIELD_ATTENDANCE_URL, headers=headers2, body=None)
        status, message = _parse_status(resp)

    awards = _endfield_awards(resp)
    if status == "ok" and awards:
        message = f"成功！获得：{awards}"
    elif status == "ok":
        message = "签到成功"
    elif status == "already":
        if not awards:
            awards = fetch_today_awards(session, role)
        message = f"今日已签到，获得：{awards}" if awards else "今日已签到"
    elif status == "error":
        message = _friendly_error_message(message)
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        status=status,
        message=message,
        awards_text=awards,
    )


def checkin_role(session: SklandSession, role: SklandRole) -> CheckinResult:
    if role.game_code == GAME_ARKNIGHTS:
        return checkin_arknights(session, role)
    if role.game_code == GAME_ENDFIELD:
        return checkin_endfield(session, role)
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        status="skipped",
        message="不支持的游戏",
    )


def checkin_all_roles(session: SklandSession) -> list[CheckinResult]:
    roles = list_roles(session)
    results: list[CheckinResult] = []
    for role in roles:
        try:
            results.append(checkin_role(session, role))
        except SklandApiError as exc:
            msg = exc.message or ""
            already = "请勿重复签到" in msg or "重复签到" in msg
            awards = fetch_today_awards(session, role) if already else None
            results.append(
                CheckinResult(
                    game_code=role.game_code,
                    game_name=role.game_name,
                    role_uid=role.uid,
                    role_name=role.role_name,
                    channel_name=role.channel_name,
                    status="already" if already else "error",
                    message=(
                        (f"今日已签到，获得：{awards}" if awards else "今日已签到")
                        if already
                        else _friendly_error_message(msg)
                    ),
                    awards_text=awards,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("skland checkin unexpected error")
            results.append(
                CheckinResult(
                    game_code=role.game_code,
                    game_name=role.game_name,
                    role_uid=role.uid,
                    role_name=role.role_name,
                    channel_name=role.channel_name,
                    status="error",
                    message=_friendly_error_message(str(exc)),
                )
            )
    return results



