"""森空岛角色列表与签到 HTTP（从 skland_client 拆出）。"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

from app.services.checkin.common import (
    CheckinResult,
    STATUS_ERROR,
    STATUS_UNKNOWN,
    format_upstream_request,
    format_upstream_response,
)
from app.services.skland.awards import (
    arknights_awards_from_sign_resp,
    awards_from_claim_records,
    endfield_awards_from_sign_resp,
    has_claim_today,
)
from app.services.skland.client import (
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
    localize_arknights_channel_name,
    localize_endfield_server_name,
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
    channel = localize_endfield_server_name(
        default_role.get("serverName")
        or item.get("channelName")
        or item.get("serverName")
        or "未知渠道"
    )
    return (
        str(role_id) if role_id is not None else None,
        str(server_id) if server_id is not None else None,
        str(role_name),
        channel,
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
    # bilibili / 哔哩 / B服
    if (
        mid == "2"
        or "bilibili" in name.lower()
        or "哔哩" in name
        or "b服" in name.lower()
    ):
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
                        channel_name=localize_arknights_channel_name(
                            str(item.get("channelName") or "未知渠道")
                        ),
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


def _has_claim_today(resp: dict[str, Any], *, day) -> bool:
    return has_claim_today(resp, day=day)


def _awards_from_claim_records(
    resp: dict[str, Any], *, day, with_icons: bool = False
) -> tuple[str | None, list[dict[str, Any]]]:
    return awards_from_claim_records(resp, day=day, with_icons=with_icons)


def _arknights_awards(
    resp: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    return arknights_awards_from_sign_resp(resp)


def _endfield_awards(
    resp: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    return endfield_awards_from_sign_resp(resp)


# 兼容旧名
def _awards_from_calendar_get(
    resp: dict[str, Any], *, day, with_icons: bool = False
) -> tuple[str | None, list[dict[str, Any]]]:
    return _awards_from_claim_records(resp, day=day, with_icons=with_icons)


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


def _arknights_game_ids(role: SklandRole) -> list[str]:
    """方舟 attendance 只用角色自身 channelMasterId，禁止回退到官服 1。

    回退到 1 会把官服 records/奖励串到 B 服角色上。
    B 服缺 channelMasterId 时不得猜测 gameId。
    """
    mid = str(role.channel_master_id or "").strip()
    if mid:
        return [mid]
    if _is_arknights_bilibili(role):
        return []
    return ["1"]


def fetch_arknights_attendance(
    session: SklandSession, role: SklandRole
) -> dict[str, Any]:
    """GET 方舟签到（含 calendar + records）。"""
    last_resp: dict[str, Any] | None = None
    for game_id in _arknights_game_ids(role):
        resp = _attendance_get(
            session,
            ARKNIGHTS_ATTENDANCE_URL,
            {"uid": role.uid, "gameId": game_id},
        )
        last_resp = resp
        if resp.get("code") != 0:
            continue
        data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
        if not isinstance(data, dict):
            continue
        if data.get("calendar") is not None or data.get("records"):
            return resp
    if last_resp is None:
        raise SklandApiError("获取签到日历失败")
    return last_resp


def fetch_endfield_attendance(
    session: SklandSession, role: SklandRole
) -> dict[str, Any]:
    """GET 终末地签到日历（calendar + resourceInfoMap + hasToday）。"""
    import urllib.parse

    if not role.role_id or not role.server_id:
        raise SklandApiError("缺少终末地角色参数，无法获取签到日历")
    params = {
        "uid": role.uid,
        "gameId": "3",
        "roleId": str(role.role_id),
        "serverId": str(role.server_id),
    }
    query = urllib.parse.urlencode(params)
    url = f"{ENDFIELD_ATTENDANCE_URL}?{query}"
    headers = _signed_headers(session, url, "get", None)
    headers["sk-game-role"] = f"3_{role.role_id}_{role.server_id}"
    resp = _http_json("GET", url, headers=headers)
    if resp.get("code") != 0:
        raise SklandApiError(
            resp.get("message") or "获取终末地签到日历失败",
            code=resp.get("code"),
        )
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    if not data.get("calendar"):
        role_str = f"3_{role.role_id}_{role.server_id}"
        headers2 = _signed_headers(session, ENDFIELD_ATTENDANCE_URL, "get", None)
        headers2["sk-game-role"] = role_str
        resp2 = _http_json("GET", ENDFIELD_ATTENDANCE_URL, headers=headers2)
        if resp2.get("code") == 0:
            data2 = resp2.get("data") if isinstance(resp2.get("data"), dict) else {}
            if data2.get("calendar"):
                return resp2
    return resp


def fetch_today_awards(
    session: SklandSession, role: SklandRole
) -> tuple[str | None, list[dict[str, Any]]]:
    """按领取记录（真实时间戳）读取今日奖励，不依赖签到日历下标。"""
    from app.core.timeutil import today

    day = today()
    try:
        if role.game_code == GAME_ARKNIGHTS:
            # 方舟领取记录在 attendance GET 的 data.records
            last_resp: dict[str, Any] | None = None
            for game_id in _arknights_game_ids(role):
                resp = _attendance_get(
                    session,
                    ARKNIGHTS_ATTENDANCE_URL,
                    {"uid": role.uid, "gameId": game_id},
                )
                last_resp = resp
                text, items = _awards_from_claim_records(
                    resp, day=day, with_icons=True
                )
                if text:
                    return text, items
            if last_resp is not None:
                data = last_resp.get("data") if isinstance(last_resp.get("data"), dict) else {}
                logger.warning(
                    "arknights claim records empty uid=%s code=%s records=%s",
                    role.uid,
                    last_resp.get("code"),
                    len(data.get("records") or []) if isinstance(data, dict) else -1,
                )
            return None, []

        if role.game_code == GAME_ENDFIELD:
            if not role.role_id or not role.server_id:
                return None, []
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
            return _awards_from_claim_records(resp, day=day, with_icons=False)
    except SklandApiError as exc:
        logger.warning("fetch today awards failed: %s", exc.message)
        return None, []
    except Exception:  # noqa: BLE001
        logger.exception("fetch today awards unexpected error")
        return None, []
    return None, []


def _signed_today_from_resp(resp: dict[str, Any], *, day) -> bool:
    """是否今日已有领取记录（按 ts，不用 hasToday / calendar）。"""
    return _has_claim_today(resp, day=day)


def _is_arknights_bilibili(role: SklandRole) -> bool:
    mid = str(role.channel_master_id or "").strip()
    if mid == "2":
        return True
    name = (role.channel_name or "").strip().lower()
    return (
        "bilibili" in name
        or "哔哩" in (role.channel_name or "")
        or "b服" in name
    )


def query_role_today(session: SklandSession, role: SklandRole) -> CheckinResult:
    """只读查询今日签到状态与奖励（领取记录，不 POST）。"""
    from app.core.timeutil import today

    day = today()
    awards_text: str | None = None
    awards_items: list[dict[str, Any]] = []
    signed = False
    saw_empty_bili_records = False
    try:
        if role.game_code == GAME_ARKNIGHTS:
            for game_id in _arknights_game_ids(role):
                resp = _attendance_get(
                    session,
                    ARKNIGHTS_ATTENDANCE_URL,
                    {"uid": role.uid, "gameId": game_id},
                )
                if _has_claim_today(resp, day=day):
                    signed = True
                text, items = _awards_from_claim_records(
                    resp, day=day, with_icons=True
                )
                if text:
                    awards_text, awards_items = text, items
                    signed = True
                    break
                if signed:
                    break
                # B 服常见：code=0 但 records=[]，不能据此判「未签」
                if (
                    _is_arknights_bilibili(role)
                    and resp.get("code") == 0
                    and not _resp_has_award_signal(resp)
                ):
                    saw_empty_bili_records = True
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
                awards_text, awards_items = _awards_from_claim_records(
                    resp, day=day, with_icons=False
                )
                if awards_text:
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
            message=(
                f"今日已签到，获得：{awards_text}" if awards_text else "今日已签到"
            ),
            awards_text=awards_text,
            awards=awards_items or None,
        )
    if saw_empty_bili_records:
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.uid,
            role_name=role.role_name,
            channel_name=role.channel_name,
            status=STATUS_UNKNOWN,
            message="B服官方未返回领取记录，请点「立即签到」确认",
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


def query_today_all(session: SklandSession) -> tuple[SklandSession, list[CheckinResult]]:
    results = sort_skland_results(
        [query_role_today(session, role) for role in list_roles(session)]
    )
    return session, results


def checkin_arknights(session: SklandSession, role: SklandRole) -> CheckinResult:
    """方舟签到。成功态 message/awards_text 只保留 award，供执行记录使用。

    gameId 用绑定 channelMasterId（官服=1，B服=2）。
    B 服奖励只信本次 POST data.awards（GET records 常为空，不做回源补奖）。
    """
    game_id = str(role.channel_master_id or "").strip()
    if not game_id:
        if _is_arknights_bilibili(role):
            return CheckinResult(
                game_code=role.game_code,
                game_name=role.game_name,
                role_uid=role.uid,
                role_name=role.role_name,
                channel_name=role.channel_name,
                status=STATUS_ERROR,
                message="B服角色缺少 channelMasterId，请重新绑定森空岛",
            )
        game_id = "1"
    body = {"uid": role.uid, "gameId": game_id}
    headers = _signed_headers(session, ARKNIGHTS_ATTENDANCE_URL, "post", body)
    resp = _http_json("POST", ARKNIGHTS_ATTENDANCE_URL, headers=headers, body=body)
    upstream_req = format_upstream_request("POST", ARKNIGHTS_ATTENDANCE_URL, body)
    upstream_resp = format_upstream_response(resp)
    status, raw_message = _parse_status(resp)
    awards_text, awards_items = _arknights_awards(resp)
    # 官服「已签」响应常无 awards，可 GET records 补；B 服 GET 无用，跳过
    if (
        status == "already"
        and not awards_text
        and not _is_arknights_bilibili(role)
    ):
        awards_text, awards_items = fetch_today_awards(session, role)
    if status == "error":
        message = _friendly_error_message(raw_message)
    else:
        message = awards_text or ""
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        status=status,
        message=message,
        awards_text=awards_text,
        awards=awards_items or None,
        upstream_request=upstream_req,
        upstream_response=upstream_resp,
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
    upstream_req = format_upstream_request("POST", ENDFIELD_ATTENDANCE_URL, body)
    status, message = _parse_status(resp)

    if status == "error" and ("参数" in message or "sign" in message.lower()):
        role_str = f"3_{role.role_id}_{role.server_id}"
        headers2 = _signed_headers(session, ENDFIELD_ATTENDANCE_URL, "post", None)
        headers2["sk-game-role"] = role_str
        resp = _http_json("POST", ENDFIELD_ATTENDANCE_URL, headers=headers2, body=None)
        upstream_req = format_upstream_request(
            "POST",
            ENDFIELD_ATTENDANCE_URL,
            {"_note": "empty body", "sk-game-role": role_str},
        )
        status, message = _parse_status(resp)

    upstream_resp = format_upstream_response(resp)
    awards_text, awards_items = _endfield_awards(resp)
    if status == "ok" and awards_text:
        message = f"成功！获得：{awards_text}"
    elif status == "ok":
        message = "签到成功"
    elif status == "already":
        if not awards_text:
            awards_text, awards_items = fetch_today_awards(session, role)
        message = (
            f"今日已签到，获得：{awards_text}" if awards_text else "今日已签到"
        )
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
        awards_text=awards_text,
        awards=awards_items or None,
        upstream_request=upstream_req,
        upstream_response=upstream_resp,
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
            # B 服方舟：重复签到也不 GET 补奖（只信此前 POST 落库的 awards）
            if already and not (
                role.game_code == GAME_ARKNIGHTS and _is_arknights_bilibili(role)
            ):
                awards_text, awards_items = fetch_today_awards(session, role)
            else:
                awards_text, awards_items = None, []
            results.append(
                CheckinResult(
                    game_code=role.game_code,
                    game_name=role.game_name,
                    role_uid=role.uid,
                    role_name=role.role_name,
                    channel_name=role.channel_name,
                    status="already" if already else "error",
                    message=(
                        (awards_text or "")
                        if already and role.game_code == GAME_ARKNIGHTS
                        else (
                            (
                                f"今日已签到，获得：{awards_text}"
                                if awards_text
                                else "今日已签到"
                            )
                            if already
                            else _friendly_error_message(msg)
                        )
                    ),
                    awards_text=awards_text,
                    awards=awards_items or None,
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



