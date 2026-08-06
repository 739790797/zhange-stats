"""库街区社区 / 游戏签到（从 kujiequ_client 拆出）。"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.core.timeutil import today
from app.services.checkin_common import CheckinResult, is_placeholder_awards, prefer_richer_awards
from app.services.kujiequ_client import (
    GAME_PGR,
    GameRole,
    KujiequApiError,
    KujiequCredentials,
    _assert_ok,
    _ensure_device,
    _post_form,
    fetch_mine,
    list_all_game_roles,
)

logger = logging.getLogger(__name__)

# 接口偶发用「奖励」当物品名；与缺名同等处理
_GENERIC_GOODS_NAMES = frozenset({"奖励", "reward", "签到奖励", "未知", "unknown"})
_GENERIC_GOODS_NAMES_LOWER = frozenset(n.lower() for n in _GENERIC_GOODS_NAMES)


def _goods_name(row: dict[str, Any]) -> str:
    name = str(
        row.get("goodsName")
        or row.get("goods_name")
        or row.get("typeName")
        or row.get("name")
        or row.get("itemName")
        or row.get("title")
        or ""
    ).strip()
    if not name or name in _GENERIC_GOODS_NAMES or name.lower() in _GENERIC_GOODS_NAMES_LOWER:
        return ""
    return name


def _iter_goods_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    """摊平 todayList / 领取记录里可能嵌套的 goods 列表。"""
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        nested = (
            row.get("goodsList")
            or row.get("goods_list")
            or row.get("awardList")
            or row.get("awards")
            or row.get("todayList")
        )
        if isinstance(nested, dict):
            nested = [nested]
        if isinstance(nested, list) and nested:
            out.extend(_iter_goods_dicts(nested))
            # 外层若自身也有名称/数量，一并保留
            if _goods_name(row) or row.get("goodsNum") is not None:
                out.append(row)
        else:
            out.append(row)
    return out


def _format_goods_rows(rows: list[Any]) -> str | None:
    parts: list[str] = []
    for row in _iter_goods_dicts(rows):
        name = _goods_name(row)
        # 缺物品名时不要用「奖励」占位，交给调用方走领取记录补全
        if not name:
            continue
        num = row.get("goodsNum")
        if num is None:
            num = row.get("gainValue")
        if num is not None:
            parts.append(f"{name}×{num}" if name != "库洛币" else f"库洛币+{num}")
        else:
            parts.append(name)
    return " · ".join(parts) if parts else None


def _community_awards_from_tasks(creds: KujiequCredentials) -> str | None:
    """从每日任务进度读取「用户签到」奖励（已签后 info 接口不含奖励）。"""
    if not creds.user_id:
        return None
    try:
        data = _post_form(
            "/encourage/level/getTaskProcess",
            {"gameId": 0, "userId": creds.user_id},
            token=creds.token,
            creds=creds,
        )
        _assert_ok(data)
    except KujiequApiError as exc:
        logger.warning("kujiequ task process failed: %s", exc.message)
        return None
    payload = data.get("data") or {}
    tasks = payload.get("dailyTask") if isinstance(payload, dict) else None
    if not isinstance(tasks, list):
        return None
    for task in tasks:
        if not isinstance(task, dict):
            continue
        remark = str(task.get("remark") or "")
        if "签到" not in remark:
            continue
        try:
            done = int(task.get("completeTimes") or 0)
            need = int(task.get("needActionTimes") or 1)
        except (TypeError, ValueError):
            continue
        if done < need:
            return None
        gold = task.get("gainGold")
        if gold is None:
            return None
        return f"库洛币+{gold}"
    return None


def _game_awards_from_records(
    creds: KujiequCredentials,
    role: GameRole,
    *,
    retries: int = 0,
    retry_delay_sec: float = 1.2,
) -> str | None:
    """从游戏签到领取记录（queryRecordV2）按北京自然日取今日奖励。"""
    last: str | None = None
    attempts = max(1, retries + 1)
    for i in range(attempts):
        if i > 0:
            time.sleep(retry_delay_sec)
        last = _game_awards_from_records_once(creds, role)
        if last and not is_placeholder_awards(last):
            return last
    return last


def _game_awards_from_records_once(
    creds: KujiequCredentials, role: GameRole
) -> str | None:
    try:
        data = _post_form(
            "/encourage/signIn/queryRecordV2",
            {
                "gameId": role.game_id,
                "serverId": role.server_id,
                "roleId": role.role_id,
                "userId": role.user_id or creds.user_id,
            },
            token=creds.token,
            creds=creds,
        )
        _assert_ok(data)
    except KujiequApiError as exc:
        logger.warning(
            "kujiequ queryRecord gameId=%s role=%s failed: %s",
            role.game_id,
            role.role_id,
            exc.message,
        )
        return None
    rows = data.get("data") or []
    if not isinstance(rows, list):
        return None
    day = today().isoformat()
    todays = [
        r
        for r in rows
        if isinstance(r, dict) and str(r.get("sigInDate") or "").startswith(day)
    ]
    return _format_goods_rows(todays)


def _awards_from_sign_payload(payload: dict[str, Any]) -> str | None:
    """解析签到成功响应：社区 gainVoList / 游戏 todayList。"""
    gains = payload.get("gainVoList")
    if isinstance(gains, list) and gains:
        parts: list[str] = []
        for g in gains:
            if isinstance(g, dict):
                parts.append(f"库洛币+{g.get('gainValue') or '?'}")
        if parts:
            return " · ".join(parts)
    today_list = payload.get("todayList")
    if isinstance(today_list, dict):
        today_list = [today_list]
    if isinstance(today_list, list) and today_list:
        return _format_goods_rows(today_list)
    return None


def query_community_today(creds: KujiequCredentials) -> CheckinResult:
    creds = _ensure_device(creds)
    data = _post_form(
        "/user/signIn/info",
        {"gameId": GAME_PGR},
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)
    payload = data.get("data") or {}
    has = bool(payload.get("hasSignIn")) if isinstance(payload, dict) else False
    days = payload.get("continueDays") if isinstance(payload, dict) else None
    extra = f"连签 {days} 天" if days is not None else None
    awards = _community_awards_from_tasks(creds) if has else None
    return CheckinResult(
        game_code="kujiequ",
        game_name="库街区",
        role_uid=creds.user_id or "community",
        role_name=creds.user_name or "社区账号",
        channel_name="社区签到",
        status="already" if has else "pending",
        message="今日已签到" if has else "今日未签到",
        awards_text=awards,
        extra_text=extra,
    )


def do_community_sign_in(creds: KujiequCredentials) -> CheckinResult:
    creds = _ensure_device(creds)
    data = _post_form(
        "/user/signIn",
        {"gameId": GAME_PGR},
        token=creds.token,
        creds=creds,
    )
    code = data.get("code")
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    msg = str(data.get("msg") or "")
    if code_i == 1511 or "重复" in msg:
        info = query_community_today(creds)
        return CheckinResult(
            game_code="kujiequ",
            game_name="库街区",
            role_uid=creds.user_id or "community",
            role_name=creds.user_name or "社区账号",
            channel_name="社区签到",
            status="already",
            message=msg or "今日已签到",
            awards_text=info.awards_text,
            extra_text=info.extra_text,
        )
    if code_i in (220, 401):
        raise KujiequApiError("登录已过期，请重新绑定", code=code_i)
    if code_i != 200 and not data.get("success"):
        raise KujiequApiError(msg or "社区签到失败", code=code_i)

    awards = None
    extra = None
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        awards = _awards_from_sign_payload(payload)
        days = payload.get("continueDays")
        if days is not None:
            extra = f"连签 {days} 天"
    if not awards:
        awards = _community_awards_from_tasks(creds)
    # 「请求成功」是通用话术，不用作签到结论
    if msg.strip() in ("请求成功", "success", "ok"):
        msg = "签到成功"
    return CheckinResult(
        game_code="kujiequ",
        game_name="库街区",
        role_uid=creds.user_id or "community",
        role_name=creds.user_name or "社区账号",
        channel_name="社区签到",
        status="ok",
        message=msg or "签到成功",
        awards_text=awards,
        extra_text=extra,
    )


def query_game_today(creds: KujiequCredentials, role: GameRole) -> CheckinResult:
    creds = _ensure_device(creds)
    data = _post_form(
        "/encourage/signIn/initSignInV2",
        {
            "gameId": role.game_id,
            "serverId": role.server_id,
            "roleId": role.role_id,
            "userId": role.user_id or creds.user_id,
        },
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)
    payload = data.get("data") or {}
    signed = bool(payload.get("isSigIn")) if isinstance(payload, dict) else False
    days = payload.get("sigInNum") if isinstance(payload, dict) else None
    awards = _game_awards_from_records(creds, role) if signed else None
    return CheckinResult(
        game_code=f"game_{role.game_id}",
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=role.server_name,
        status="already" if signed else "pending",
        message="今日已签到" if signed else "今日未签到",
        awards_text=awards,
        extra_text=f"本月已签 {days} 天" if days is not None else None,
    )


def do_game_sign_in(creds: KujiequCredentials, role: GameRole) -> CheckinResult:
    creds = _ensure_device(creds)
    # 与 today() 同一时区（北京），避免月末边界错月
    month = f"{today().month:02d}"
    data = _post_form(
        "/encourage/signIn/v2",
        {
            "gameId": role.game_id,
            "serverId": role.server_id,
            "roleId": role.role_id,
            "userId": role.user_id or creds.user_id,
            "reqMonth": month,
        },
        token=creds.token,
        creds=creds,
    )
    code = data.get("code")
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    msg = str(data.get("msg") or "").strip()
    if code_i == 1511 or "重复" in msg:
        awards = _game_awards_from_records(creds, role, retries=1)
        return CheckinResult(
            game_code=f"game_{role.game_id}",
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=role.server_name,
            status="already",
            message="今日已签到",
            awards_text=awards,
        )
    if code_i in (220, 401):
        raise KujiequApiError("登录已过期，请重新绑定", code=code_i)
    if code_i != 200 and not data.get("success"):
        return CheckinResult(
            game_code=f"game_{role.game_id}",
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=role.server_name,
            status="error",
            message=msg or "游戏签到失败",
        )
    awards = None
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        awards = _awards_from_sign_payload(payload)
    # 签到响应常缺 goodsName / 仅返回「奖励」；补查领取记录（可短重试）
    recorded = _game_awards_from_records(creds, role, retries=2)
    if is_placeholder_awards(awards):
        awards = recorded
    else:
        awards = prefer_richer_awards(awards, recorded)

    # 库街区常返回 msg=「请求成功」但实际未签；以 initSignInV2.isSigIn 为准
    verified = query_game_today(creds, role)
    if verified.status != "already":
        return CheckinResult(
            game_code=f"game_{role.game_id}",
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=role.server_name,
            status="error",
            message="接口返回成功，但官方仍显示未签（请稍后重试或手动签到）",
            awards_text=None,
        )
    awards = prefer_richer_awards(awards, verified.awards_text)
    return CheckinResult(
        game_code=f"game_{role.game_id}",
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=role.server_name,
        status="ok",
        message="签到成功",
        awards_text=awards,
    )


def query_today_all(creds: KujiequCredentials) -> tuple[KujiequCredentials, list[CheckinResult]]:
    creds = _ensure_device(creds)
    if not creds.user_id:
        mine = fetch_mine(creds)
        creds.user_id = mine["user_id"]
        creds.user_name = mine["user_name"] or creds.user_name

    results: list[CheckinResult] = [query_community_today(creds)]
    for role in list_all_game_roles(creds):
        try:
            results.append(query_game_today(creds, role))
        except KujiequApiError as exc:
            if exc.code in (220, 401):
                raise
            results.append(
                CheckinResult(
                    game_code=f"game_{role.game_id}",
                    game_name=role.game_name,
                    role_uid=role.role_id,
                    role_name=role.role_name,
                    channel_name=role.server_name,
                    status="error",
                    message=exc.message,
                )
            )
    return creds, results


def run_all_checkins(
    creds: KujiequCredentials,
    *,
    role_keys: set[tuple[str, str]] | None = None,
) -> tuple[KujiequCredentials, list[CheckinResult]]:
    from app.services.checkin_role_prefs import matches_role_filter

    creds = _ensure_device(creds)
    if not creds.user_id:
        mine = fetch_mine(creds)
        creds.user_id = mine["user_id"]
        creds.user_name = mine["user_name"] or creds.user_name

    results: list[CheckinResult] = []
    community_uid = creds.user_id or "community"
    if matches_role_filter("kujiequ", community_uid, role_keys):
        try:
            results.append(do_community_sign_in(creds))
        except KujiequApiError as exc:
            if exc.code in (220, 401):
                raise
            results.append(
                CheckinResult(
                    game_code="kujiequ",
                    game_name="库街区",
                    role_uid=community_uid,
                    role_name=creds.user_name or "社区账号",
                    channel_name="社区签到",
                    status="error",
                    message=exc.message,
                )
            )

    for role in list_all_game_roles(creds):
        game_code = f"game_{role.game_id}"
        if not matches_role_filter(game_code, role.role_id, role_keys):
            continue
        try:
            results.append(do_game_sign_in(creds, role))
        except KujiequApiError as exc:
            if exc.code in (220, 401):
                raise
            results.append(
                CheckinResult(
                    game_code=game_code,
                    game_name=role.game_name,
                    role_uid=role.role_id,
                    role_name=role.role_name,
                    channel_name=role.server_name,
                    status="error",
                    message=exc.message,
                )
            )
    return creds, results


def friendly_error_message(message: str) -> str:
    text = (message or "").strip() or "库街区请求失败"
    if "过期" in text or "失效" in text:
        return "凭证可能已失效，请重新绑定库街区"
    return text
