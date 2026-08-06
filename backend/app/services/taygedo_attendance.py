"""塔吉多签到查询与执行（从 taygedo_client 拆出）。"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

from app.services.checkin_common import (
    CheckinResult,
    award_item,
    awards_text_from_items,
)
from app.services.taygedo_client import (
    GAME_APP,
    GAME_APP_NAME,
    GAME_HT,
    GAME_HT_NAME,
    GAME_NTE,
    GAME_NTE_NAME,
    GAME_SIGN_IDS,
    H5_ORIGIN,
    TAYGEDO_BASE,
    TaygedoApiError,
    TaygedoCredentials,
    TaygedoRole,
    _form_encode,
    _http,
    ensure_access_token,
    list_all_game_roles,
    refresh_access_token,
)

logger = logging.getLogger(__name__)

def friendly_error_message(msg: str) -> str:
    text = (msg or "").strip() or "未知错误"
    low = text.lower()
    if any(
        k in text
        for k in ("登录", "凭证", "token", "过期", "失效", "授权", "挤下线", "其他设备")
    ) or "unauthorized" in low or "http 401" in low or "http 402" in low or "http 403" in low:
        return f"凭证可能已失效，请重新绑定塔吉多（{text}）"
    if any(k in text for k in ("网络", "超时", "timeout", "连接")) or "timed out" in low:
        return f"网络异常，请稍后重试（{text}）"
    return text


def is_auth_failure(
    *,
    status: int | None = None,
    code: Any = None,
    message: str | None = None,
) -> bool:
    """判断是否为登录态失效（含单设备挤下线）。"""
    if status in (401, 403):
        return True
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    if code_i in (401, 402, 403, -1, 1001, 10001):
        return True
    text = (message or "").lower()
    keys = (
        "登录",
        "未登录",
        "凭证",
        "token",
        "过期",
        "失效",
        "授权",
        "unauthorized",
        "挤",
        "其他设备",
        "重新登录",
    )
    return any(k in text for k in keys)


def _raise_if_auth_failure(
    *,
    status: int,
    data: dict[str, Any],
    fallback: str,
) -> None:
    """仅在鉴权失败时抛错；其它业务错误由调用方自行处理。"""
    msg = str(data.get("msg") or data.get("message") or fallback)
    code = data.get("code")
    if is_auth_failure(status=status, code=code, message=msg):
        raise TaygedoApiError(
            friendly_error_message(msg),
            code=code if isinstance(code, int) else status,
        )


def _is_already(msg: str) -> bool:
    text = msg or ""
    return any(k in text for k in ("已签到", "重复签到", "签到过", "already"))


def _item_award_dict(item: dict[str, Any]) -> dict[str, Any] | None:
    name = item.get("name") or item.get("rewardName") or item.get("awardName")
    nested = item.get("reward") or item.get("award") or item.get("item")
    source = item
    if not name and isinstance(nested, dict):
        source = nested
        name = nested.get("name")
    if not name:
        return None
    num = source.get("num")
    if num is None:
        num = source.get("count")
    if num is None:
        num = item.get("num")
    if num is None:
        num = item.get("count")
    try:
        count = int(num) if num is not None else 1
    except (TypeError, ValueError):
        count = 1
    rid = (
        source.get("id")
        or source.get("itemId")
        or source.get("resourceId")
        or item.get("id")
        or item.get("itemId")
        or item.get("resourceId")
    )
    rtype = (
        source.get("type")
        or source.get("resourceType")
        or item.get("type")
        or item.get("resourceType")
    )
    return award_item(name=str(name), count=count, resource_id=rid, resource_type=rtype)


def _item_award_text(item: dict[str, Any]) -> str | None:
    d = _item_award_dict(item)
    if not d:
        return None
    return f"{d['name']} x{d['count']}"


def _pack_awards(items: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    if not items:
        return None, []
    text = awards_text_from_items(items)
    # 文案风格与旧逻辑兼容：空格 x
    if text:
        text = "、".join(
            f"{a['name']} x{a['count']}" for a in items if a.get("name")
        )
    return text, items


def _awards_from_sign_payload(
    data: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    """从签到 POST 响应中提取当日奖励（优先于月历列表）。"""
    payload = data.get("data")
    if not isinstance(payload, dict):
        return None, []
    items: list[dict[str, Any]] = []
    for key in ("rewards", "rewardList", "awards", "awardList", "items"):
        raw = payload.get(key)
        if isinstance(raw, list) and raw:
            for item in raw:
                if isinstance(item, dict):
                    d = _item_award_dict(item)
                    if d:
                        items.append(d)
            if items:
                return _pack_awards(items)
        if isinstance(raw, dict):
            d = _item_award_dict(raw)
            if d:
                return _pack_awards([d])
    d = _item_award_dict(payload)
    if d:
        return _pack_awards([d])
    name = payload.get("rewardName") or payload.get("awardName")
    if name:
        num = payload.get("num") or payload.get("count") or 1
        try:
            count = int(num)
        except (TypeError, ValueError):
            count = 1
        return _pack_awards([award_item(name=str(name), count=count)])
    return None, []


def _app_headers(creds: TaygedoCredentials) -> dict[str, str]:
    return {
        "authorization": creds.access_token,
        "uid": creds.uid,
        "deviceid": creds.device_id,
        "appversion": "1.1.0",
        "User-Agent": "okhttp/4.12.0",
    }


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


def _get_app_sign_state(creds: TaygedoCredentials, *, community_id: int = 1) -> bool | None:
    """GET /apihub/api/getSignState — data=true 表示今日已签。

    鉴权失败会抛 TaygedoApiError；其它业务失败返回 None。
    """
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/apihub/api/getSignState?communityId={community_id}",
        headers=_app_headers(creds),
    )
    if status == 200 and data.get("code") == 0:
        return bool(data.get("data"))
    _raise_if_auth_failure(status=status, data=data, fallback="查询社区签到状态失败")
    return None


def ensure_session(creds: TaygedoCredentials) -> TaygedoCredentials:
    """校验/刷新登录态；单设备挤下线后 refresh 失败则明确报凭证失效。"""
    working = ensure_access_token(creds)
    try:
        _get_app_sign_state(working)
        return working
    except TaygedoApiError as exc:
        if not is_auth_failure(code=exc.code, message=exc.message):
            raise
        working = refresh_access_token(working)
        _get_app_sign_state(working)  # 仍失败则抛出
        return working


def _app_awards_from_exp_records(
    creds: TaygedoCredentials, *, community_id: int = 1
) -> tuple[str | None, list[dict[str, Any]]]:
    """从经验领取记录里取今日签到奖励（type=3）。"""
    from app.core.timeutil import BEIJING, today

    day = today()
    try:
        status, data = _http(
            "GET",
            (
                f"{TAYGEDO_BASE}/usercenter/api/getUserExpRecords"
                f"?communityId={community_id}"
            ),
            headers=_app_headers(creds),
        )
        if status != 200 or data.get("code") != 0:
            return None, []
        raw = data.get("data")
        records = raw if isinstance(raw, list) else []
        items: list[dict[str, Any]] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            # 3 = 签到
            if rec.get("type") not in (3, "3"):
                continue
            ts = rec.get("createTime") or rec.get("create_time") or rec.get("updateTime")
            try:
                value = int(ts)
            except (TypeError, ValueError):
                continue
            if value > 10_000_000_000:
                value //= 1000
            from datetime import datetime

            if datetime.fromtimestamp(value, tz=BEIJING).date() != day:
                continue
            title = str(rec.get("title") or "签到奖励")
            num = rec.get("num")
            try:
                count = int(num) if num is not None else 1
            except (TypeError, ValueError):
                count = 1
            items.append(
                award_item(name=title, count=count, resource_type="exp")
            )
        if not items:
            return None, []
        text = "、".join(f"{a['name']}+{a['count']}" for a in items)
        return text, items
    except Exception:  # noqa: BLE001
        return None, []


def _get_game_sign_state(creds: TaygedoCredentials, game_id: str) -> dict[str, Any] | None:
    """GET /apihub/awapi/signin/state — 含 todaySign / day / days。"""
    try:
        status, data = _http(
            "GET",
            f"{TAYGEDO_BASE}/apihub/awapi/signin/state?gameId={urllib.parse.quote(game_id)}",
            headers=_h5_headers(creds),
        )
        if status != 200 or data.get("code") != 0:
            return None
        payload = data.get("data")
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _list_game_rewards(
    creds: TaygedoCredentials, game_id: str, *, role_id: str | None = None
) -> list[dict[str, Any]]:
    params = {"gameId": game_id}
    if role_id:
        params["roleId"] = role_id
    query = urllib.parse.urlencode(params)
    try:
        status, data = _http(
            "GET",
            f"{TAYGEDO_BASE}/apihub/awapi/sign/rewards?{query}",
            headers=_h5_headers(creds),
        )
        if status != 200 or data.get("code") != 0:
            return []
        raw = data.get("data")
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
        return []
    except Exception:  # noqa: BLE001
        return []


def fetch_game_attendance_bundle(
    creds: TaygedoCredentials, game_id: str, *, role_id: str
) -> dict[str, Any]:
    """拉取签到日历落库包：signin/state + sign/rewards。"""
    state = _get_game_sign_state(creds, game_id)
    if state is None:
        raise TaygedoApiError("获取签到状态失败，请稍后重试")
    rewards = _list_game_rewards(creds, game_id, role_id=role_id)
    if not rewards:
        raise TaygedoApiError("获取签到奖励日历失败，请稍后重试")
    return {"state": state, "rewards": rewards}


def _awards_from_claim_records(
    creds: TaygedoCredentials,
    game_id: str,
    *,
    role_id: str | None = None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """尝试官方领取记录接口（按真实领取时间筛今日）。失败则返回空。"""
    from app.core.timeutil import BEIJING, today

    day = today()
    params: dict[str, str] = {"gameId": game_id}
    if role_id:
        params["roleId"] = role_id
    query = urllib.parse.urlencode(params)
    candidates = (
        f"{TAYGEDO_BASE}/apihub/awapi/sign/records?{query}",
        f"{TAYGEDO_BASE}/apihub/awapi/signin/records?{query}",
        f"{TAYGEDO_BASE}/apihub/awapi/sign/record?{query}",
    )
    for url in candidates:
        try:
            status, data = _http("GET", url, headers=_h5_headers(creds))
        except TaygedoApiError:
            continue
        if status != 200 or data.get("code") != 0:
            continue
        raw = data.get("data")
        records: list[Any]
        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict):
            nested = raw.get("records") or raw.get("list") or raw.get("items")
            records = nested if isinstance(nested, list) else []
        else:
            continue
        items: list[dict[str, Any]] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            ts = (
                rec.get("ts")
                or rec.get("timestamp")
                or rec.get("createTime")
                or rec.get("signTime")
                or rec.get("time")
            )
            matched = False
            if ts is not None:
                try:
                    value = int(ts)
                    if value > 10_000_000_000:
                        value //= 1000
                    from datetime import datetime

                    matched = datetime.fromtimestamp(value, tz=BEIJING).date() == day
                except (TypeError, ValueError, OSError):
                    matched = False
            if not matched:
                for key in ("date", "signDate", "dayStr"):
                    text = str(rec.get(key) or "").strip()
                    if len(text) >= 10 and text[0:10] == day.isoformat():
                        matched = True
                        break
            if not matched:
                continue
            d = _item_award_dict(rec)
            if not d and isinstance(rec.get("reward"), dict):
                d = _item_award_dict(rec["reward"])
            if d:
                items.append(d)
        if items:
            return _pack_awards(items)
    return None, []


def _awards_from_game_state(
    creds: TaygedoCredentials,
    game_id: str,
    state: dict[str, Any],
    *,
    role_id: str | None = None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """今日已签奖励：优先领取记录；否则用本月累计 days（第 N 次），禁止用日历日期。"""
    claimed_text, claimed_items = _awards_from_claim_records(
        creds, game_id, role_id=role_id
    )
    if claimed_text:
        return claimed_text, claimed_items

    rewards = _list_game_rewards(creds, game_id, role_id=role_id)
    if not rewards:
        return None, []
    # 与社区工具一致：todaySign 后 rewards[days-1] 为当日格（本月第 N 次）
    try:
        day_idx = int(state.get("days") or 0) - 1
    except (TypeError, ValueError):
        day_idx = -1
    if day_idx < 0:
        return None, []
    if 0 <= day_idx < len(rewards):
        d = _item_award_dict(rewards[day_idx])
        if d:
            return _pack_awards([d])
    return None, []


def _fetch_rewards(
    creds: TaygedoCredentials, game_id: str, *, role_id: str | None = None
) -> tuple[str | None, list[dict[str, Any]]]:
    state = _get_game_sign_state(creds, game_id)
    if not state or not state.get("todaySign"):
        return None, []
    return _awards_from_game_state(creds, game_id, state, role_id=role_id)


def fetch_today_awards(
    creds: TaygedoCredentials, *, game_code: str, role_id: str | None = None
) -> tuple[str | None, list[dict[str, Any]]]:
    """已签到时补读今日游戏奖励（不含社区）。"""
    if game_code == GAME_APP:
        return None, []
    return _fetch_rewards(creds, game_code, role_id=role_id)


def query_game_today(creds: TaygedoCredentials, role: TaygedoRole) -> CheckinResult:
    """按官方 signin/state.todaySign 查询游戏今日签到与奖励。"""
    state = _get_game_sign_state(creds, role.game_code)
    channel = role.game_name
    if state and state.get("todaySign"):
        awards_text, awards_items = _awards_from_game_state(
            creds, role.game_code, state, role_id=role.role_id
        )
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=channel,
            status="already",
            message=(
                f"今日已签到，获得：{awards_text}" if awards_text else "今日已签到"
            ),
            awards_text=awards_text,
            awards=awards_items or None,
        )
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=channel,
        status="pending",
        message="今日尚未签到",
        awards_text=None,
    )


def query_today_all(
    creds: TaygedoCredentials,
) -> tuple[TaygedoCredentials, list[CheckinResult]]:
    """只查询异环 / 幻塔游戏签到，不含社区。"""
    working, targets = list_checkin_targets(creds)
    results: list[CheckinResult] = []
    for game_code, role in targets:
        if role is not None:
            results.append(query_game_today(working, role))
    return working, results


def app_signin(creds: TaygedoCredentials) -> CheckinResult:
    status, data = _http(
        "POST",
        f"{TAYGEDO_BASE}/apihub/api/signin",
        headers={
            "authorization": creds.access_token,
            "uid": creds.uid,
            "deviceid": creds.device_id,
            "appversion": "1.1.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.12.0",
        },
        body=_form_encode({"communityId": "1"}),
    )
    msg = str(data.get("msg") or data.get("message") or "")
    if status == 200 and data.get("code") == 0:
        payload = data.get("data") or {}
        exp = payload.get("exp")
        gold = payload.get("goldCoin")
        awards_text = None
        awards_items: list[dict[str, Any]] = []
        if isinstance(exp, (int, float)) or isinstance(gold, (int, float)):
            if isinstance(exp, (int, float)):
                awards_items.append(
                    award_item(name="经验", count=int(exp), resource_type="exp")
                )
            if isinstance(gold, (int, float)):
                awards_items.append(
                    award_item(name="金币", count=int(gold), resource_type="gold")
                )
            awards_text = "、".join(
                f"{a['name']}+{a['count']}" for a in awards_items
            )
        return CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid=creds.uid,
            role_name="社区账号",
            channel_name="塔吉多",
            status="ok",
            message=f"签到成功{('，获得：' + awards_text) if awards_text else ''}",
            awards_text=awards_text,
            awards=awards_items or None,
        )
    if _is_already(msg):
        awards_text, awards_items = _app_awards_from_exp_records(creds)
        return CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid=creds.uid,
            role_name="社区账号",
            channel_name="塔吉多",
            status="already",
            message=(
                f"今日已签到，获得：{awards_text}" if awards_text else "今日已签到"
            ),
            awards_text=awards_text,
            awards=awards_items or None,
        )
    return CheckinResult(
        game_code=GAME_APP,
        game_name=GAME_APP_NAME,
        role_uid=creds.uid,
        role_name="社区账号",
        channel_name="塔吉多",
        status="error",
        message=friendly_error_message(msg or "APP 签到失败"),
    )


def game_signin(creds: TaygedoCredentials, role: TaygedoRole) -> CheckinResult:
    body = _form_encode({"roleId": role.role_id, "gameId": role.game_code})
    status, data = _http(
        "POST",
        f"{TAYGEDO_BASE}/apihub/awapi/sign",
        headers={
            "Accept": "application/json",
            "Authorization": creds.access_token,
            "Origin": H5_ORIGIN,
            "Referer": f"{H5_ORIGIN}/",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Tajiduo/1.2.2"
            ),
        },
        body=body,
    )
    msg = str(data.get("msg") or data.get("message") or "")
    channel = role.game_name
    if status == 200 and data.get("code") == 0:
        # POST 成功后重读状态，用 days 对齐领取记录中的当日奖励
        awards_text, awards_items = _awards_from_sign_payload(data)
        if not awards_text:
            awards_text, awards_items = _fetch_rewards(
                creds, role.game_code, role_id=role.role_id
            )
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=channel,
            status="ok",
            message=(
                f"签到成功{('，获得：' + awards_text) if awards_text else ''}"
            ),
            awards_text=awards_text,
            awards=awards_items or None,
        )
    if _is_already(msg):
        awards_text, awards_items = _fetch_rewards(
            creds, role.game_code, role_id=role.role_id
        )
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=channel,
            status="already",
            message=(
                f"今日已签到{('，获得：' + awards_text) if awards_text else ''}"
            ),
            awards_text=awards_text,
            awards=awards_items or None,
        )
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=channel,
        status="error",
        message=friendly_error_message(msg or f"{role.game_name}签到失败"),
    )


def checkin_target(
    creds: TaygedoCredentials,
    *,
    game_code: str,
    role: TaygedoRole | None = None,
) -> CheckinResult:
    if role is None:
        raise TaygedoApiError("缺少游戏角色参数")
    return game_signin(creds, role)


def list_checkin_targets(
    creds: TaygedoCredentials,
) -> tuple[TaygedoCredentials, list[tuple[str, TaygedoRole | None]]]:
    """返回凭证 + 游戏签到目标（异环 / 幻塔），不含社区。"""
    working = ensure_session(creds)
    try:
        roles = list_all_game_roles(working)
    except TaygedoApiError as exc:
        if is_auth_failure(code=exc.code, message=exc.message):
            working = refresh_access_token(working)
            roles = list_all_game_roles(working)
        else:
            raise
    targets: list[tuple[str, TaygedoRole | None]] = [
        (role.game_code, role) for role in roles
    ]
    return working, targets


def checkin_all(creds: TaygedoCredentials) -> tuple[TaygedoCredentials, list[CheckinResult]]:
    """返回可能刷新后的凭证 + 游戏签到结果（异环 / 幻塔）。"""
    working, targets = list_checkin_targets(creds)
    results: list[CheckinResult] = []

    def _run(game_code: str, role: TaygedoRole | None) -> CheckinResult:
        nonlocal working
        try:
            return checkin_target(working, game_code=game_code, role=role)
        except TaygedoApiError as exc:
            if is_auth_failure(code=exc.code, message=exc.message):
                working = refresh_access_token(working)
                return checkin_target(working, game_code=game_code, role=role)
            raise

    for game_code, role in targets:
        try:
            results.append(_run(game_code, role))
        except TaygedoApiError as exc:
            results.append(
                CheckinResult(
                    game_code=role.game_code if role else game_code,
                    game_name=role.game_name if role else game_code,
                    role_uid=role.role_id if role else "-",
                    role_name=role.role_name if role else "-",
                    channel_name=role.game_name if role else "-",
                    status="error",
                    message=friendly_error_message(exc.message),
                )
            )
    return working, results
