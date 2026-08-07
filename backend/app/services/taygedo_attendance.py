"""塔吉多签到查询与执行（从 taygedo_client 拆出）。"""

from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

from app.services.checkin_common import (
    CheckinResult,
    award_item,
    awards_text_from_items,
    format_upstream_request,
    format_upstream_response,
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

# 社区任务（与官方任务中心 taskKey 对齐）
COMMUNITY_ID = 1
TASK_GID = 1
TK_SIGNIN = "signin_c"
TK_BROWSE = "browse_post_c"
TK_LIKE = "like_post_c"
TK_SHARE = "share"
SHARE_PLATFORM = "qq"
# 官方任务中心展示的塔塔币奖励（接口缺字段时回退）
_DEFAULT_TASK_GOLD: dict[str, int] = {
    TK_SIGNIN: 40,
    TK_BROWSE: 5,
    TK_LIKE: 5,
    TK_SHARE: 20,
}


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


def _pick_icon_url(*sources: Any) -> str | None:
    for src in sources:
        if not isinstance(src, dict):
            continue
        icon = src.get("icon") or src.get("iconUrl") or src.get("icon_url")
        if isinstance(icon, str) and icon.strip():
            return icon.strip()
    return None


def _item_award_dict(item: dict[str, Any]) -> dict[str, Any] | None:
    """从上游奖励对象解析结构化条目（含 icon_url，与签到日历同源）。"""
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
    return award_item(
        name=str(name),
        count=count,
        resource_id=rid,
        resource_type=rtype,
        icon_url=_pick_icon_url(source, item, nested if isinstance(nested, dict) else None),
    )


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
    """兼容旧调用：社区签到奖励改走任务中心塔塔币，不再读经验流水。"""
    _ = community_id
    return _app_signin_awards_from_tasks(creds)


def _task_gold_reward(
    row: dict[str, Any] | None, *, fallback: int | None = None
) -> int | None:
    """从任务中心单行解析塔塔币奖励。"""
    if not isinstance(row, dict):
        return fallback

    def _as_int(value: Any) -> int | None:
        try:
            n = int(value)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    for key in (
        "gold",
        "goldCoin",
        "gainGold",
        "rewardGold",
        "awardGold",
        "coin",
        "rewardNum",
        "awardNum",
    ):
        n = _as_int(row.get(key))
        if n is not None:
            return n
    for nest_key in ("reward", "award", "prize", "rewards"):
        nest = row.get(nest_key)
        if isinstance(nest, dict):
            n = _task_gold_reward(nest, fallback=None)
            if n is not None:
                return n
        elif isinstance(nest, list):
            total = 0
            hit = False
            for item in nest:
                if not isinstance(item, dict):
                    continue
                n = _task_gold_reward(item, fallback=None)
                if n is None:
                    n = _as_int(item.get("num") or item.get("count"))
                if n is not None:
                    total += n
                    hit = True
            if hit and total > 0:
                return total
    return fallback


def _app_signin_awards_from_tasks(
    creds: TaygedoCredentials,
) -> tuple[str | None, list[dict[str, Any]]]:
    """社区签到奖励：任务中心签到项的塔塔币（官方展示 +40）。"""
    try:
        tasks = get_user_tasks(creds)
    except TaygedoApiError:
        gold = _DEFAULT_TASK_GOLD[TK_SIGNIN]
        items = [award_item(name="塔塔币", count=gold, resource_type="gold")]
        return f"塔塔币+{gold}", items
    except Exception:  # noqa: BLE001
        gold = _DEFAULT_TASK_GOLD[TK_SIGNIN]
        items = [award_item(name="塔塔币", count=gold, resource_type="gold")]
        return f"塔塔币+{gold}", items

    row = tasks.get(TK_SIGNIN) or {}
    gold = _task_gold_reward(row, fallback=_DEFAULT_TASK_GOLD[TK_SIGNIN])
    if gold is None or gold <= 0:
        gold = _DEFAULT_TASK_GOLD[TK_SIGNIN]
    items = [award_item(name="塔塔币", count=int(gold), resource_type="gold")]
    return f"塔塔币+{gold}", items


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
    rewards = _list_game_rewards(creds, game_id, role_id=role_id)
    day_award: dict[str, Any] | None = None
    try:
        day_idx = int(state.get("days") or 0) - 1
    except (TypeError, ValueError):
        day_idx = -1
    if rewards and 0 <= day_idx < len(rewards):
        day_award = _item_award_dict(rewards[day_idx])

    if claimed_text:
        # 领取记录常无图标：用当日日历格补 icon_url
        if day_award and day_award.get("icon_url"):
            icon = str(day_award["icon_url"])
            enriched = []
            for a in claimed_items:
                if isinstance(a, dict) and not str(a.get("icon_url") or "").strip():
                    enriched.append({**a, "icon_url": icon})
                else:
                    enriched.append(a)
            return claimed_text, enriched
        return claimed_text, claimed_items

    if day_award:
        return _pack_awards([day_award])
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
    """已签到时补读签到奖励（社区走任务中心塔塔币；游戏走 sign 状态）。"""
    if game_code == GAME_APP:
        return _app_signin_awards_from_tasks(creds)
    return _fetch_rewards(creds, game_code, role_id=role_id)


def get_user_tasks(creds: TaygedoCredentials) -> dict[str, dict[str, Any]]:
    """GET /apihub/api/getUserTasks — task_list1 按 taskKey 索引。"""
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/apihub/api/getUserTasks?gid={TASK_GID}",
        headers=_app_headers(creds),
    )
    if status != 200 or data.get("code") != 0:
        _raise_if_auth_failure(status=status, data=data, fallback="查询任务列表失败")
        return {}
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for key in ("task_list1", "task_list2"):
        rows = payload.get(key) if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            task_key = str(row.get("taskKey") or row.get("code") or "").strip()
            if task_key:
                out[task_key] = row
    return out


def get_user_coin_state(creds: TaygedoCredentials) -> dict[str, Any]:
    """GET /apihub/api/getUserCoinTaskState — 塔塔币余额与今日进度。"""
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/apihub/api/getUserCoinTaskState",
        headers=_h5_headers(creds),
    )
    if status != 200 or data.get("code") != 0:
        _raise_if_auth_failure(status=status, data=data, fallback="查询塔塔币失败")
        return {}
    payload = data.get("data")
    return payload if isinstance(payload, dict) else {}


def _task_progress(tasks: dict[str, dict[str, Any]], task_key: str) -> tuple[int, int]:
    row = tasks.get(task_key) or {}
    try:
        done = int(row.get("completeTimes") or 0)
    except (TypeError, ValueError):
        done = 0
    try:
        need = int(row.get("limitTimes") or 0)
    except (TypeError, ValueError):
        need = 0
    return max(0, done), max(0, need)


def _tasks_extra_text(
    *,
    browse: int,
    browse_need: int,
    like: int,
    like_need: int,
    share: int,
    share_need: int,
    browse_gold: int | None = None,
    like_gold: int | None = None,
    share_gold: int | None = None,
    gold: int | None = None,
    today_get: int | None = None,
    today_total: int | None = None,
) -> str:
    def _prog(label: str, done: int, need: int, reward: int | None) -> str:
        base = f"{label} {done}/{need}" if need else f"{label} {done}"
        if reward is not None and reward > 0:
            return f"{base}(+{reward})"
        return base

    parts = [
        _prog("浏览", browse, browse_need, browse_gold),
        _prog("点赞", like, like_need, like_gold),
        _prog("分享", share, share_need, share_gold),
    ]
    if gold is not None and gold > 0:
        parts.append(f"塔塔币+{gold}")
    if today_get is not None and today_total is not None and today_total > 0:
        parts.append(f"今日 {today_get}/{today_total}")
    return "每日任务：" + " · ".join(parts)


def _daily_task_snapshot(creds: TaygedoCredentials) -> dict[str, Any]:
    tasks = get_user_tasks(creds)
    browse, browse_need = _task_progress(tasks, TK_BROWSE)
    like, like_need = _task_progress(tasks, TK_LIKE)
    share, share_need = _task_progress(tasks, TK_SHARE)
    if browse_need <= 0:
        browse_need = 5
    if like_need <= 0:
        like_need = 5
    if share_need <= 0:
        share_need = 1
    browse_gold = _task_gold_reward(
        tasks.get(TK_BROWSE), fallback=_DEFAULT_TASK_GOLD[TK_BROWSE]
    )
    like_gold = _task_gold_reward(
        tasks.get(TK_LIKE), fallback=_DEFAULT_TASK_GOLD[TK_LIKE]
    )
    share_gold = _task_gold_reward(
        tasks.get(TK_SHARE), fallback=_DEFAULT_TASK_GOLD[TK_SHARE]
    )
    coin_state = {}
    try:
        coin_state = get_user_coin_state(creds)
    except TaygedoApiError:
        pass
    try:
        today_get = int(coin_state.get("todayGet") or 0)
    except (TypeError, ValueError):
        today_get = 0
    try:
        today_total = int(coin_state.get("todayTotal") or 0)
    except (TypeError, ValueError):
        today_total = 0
    all_done = (
        browse >= browse_need and like >= like_need and share >= share_need
    )
    return {
        "browse": browse,
        "browse_need": browse_need,
        "like": like,
        "like_need": like_need,
        "share": share,
        "share_need": share_need,
        "browse_gold": browse_gold,
        "like_gold": like_gold,
        "share_gold": share_gold,
        "today_get": today_get,
        "today_total": today_total,
        "all_done": all_done,
    }


def list_recommend_posts(
    creds: TaygedoCredentials, *, count: int = 20, page: int = 1
) -> list[dict[str, Any]]:
    """GET /bbs/api/getRecommendPostList。"""
    query = urllib.parse.urlencode(
        {
            "communityId": COMMUNITY_ID,
            "count": max(1, min(50, int(count))),
            "page": max(1, int(page)),
        }
    )
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/bbs/api/getRecommendPostList?{query}",
        headers=_app_headers(creds),
    )
    if status != 200 or data.get("code") != 0:
        _raise_if_auth_failure(status=status, data=data, fallback="获取帖子列表失败")
        return []
    payload = data.get("data")
    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        nested = payload.get("posts") or payload.get("list") or []
        rows = nested if isinstance(nested, list) else []
    else:
        rows = []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = str(row.get("postId") or "").strip()
        if not post_id:
            continue
        self_op = row.get("selfOperation") if isinstance(row.get("selfOperation"), dict) else {}
        out.append(
            {
                "post_id": post_id,
                "liked": bool(self_op.get("liked")),
            }
        )
    return out


def view_post(creds: TaygedoCredentials, post_id: str) -> None:
    query = urllib.parse.urlencode({"postId": str(post_id)})
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/bbs/api/getPostFull?{query}",
        headers=_app_headers(creds),
    )
    if status == 200 and data.get("code") == 0:
        return
    _raise_if_auth_failure(status=status, data=data, fallback="浏览帖子失败")
    msg = str(data.get("msg") or data.get("message") or "浏览帖子失败")
    raise TaygedoApiError(friendly_error_message(msg), code=data.get("code"))


def like_post(creds: TaygedoCredentials, post_id: str) -> None:
    status, data = _http(
        "POST",
        f"{TAYGEDO_BASE}/bbs/api/post/like",
        headers={
            **_app_headers(creds),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=_form_encode({"postId": str(post_id)}),
    )
    if status == 200 and data.get("code") == 0:
        return
    _raise_if_auth_failure(status=status, data=data, fallback="点赞失败")
    msg = str(data.get("msg") or data.get("message") or "点赞失败")
    raise TaygedoApiError(friendly_error_message(msg), code=data.get("code"))


def share_post(
    creds: TaygedoCredentials, post_id: str, *, platform: str = SHARE_PLATFORM
) -> None:
    status, data = _http(
        "POST",
        f"{TAYGEDO_BASE}/bbs/api/post/share",
        headers={
            **_app_headers(creds),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=_form_encode({"platform": platform, "postId": str(post_id)}),
    )
    if status == 200 and data.get("code") == 0:
        return
    _raise_if_auth_failure(status=status, data=data, fallback="分享失败")
    msg = str(data.get("msg") or data.get("message") or "分享失败")
    raise TaygedoApiError(friendly_error_message(msg), code=data.get("code"))


def _tasks_extra_text_from_snap(
    snap: dict[str, Any], *, gold: int | None = None
) -> str:
    return _tasks_extra_text(
        browse=int(snap.get("browse") or 0),
        browse_need=int(snap.get("browse_need") or 0),
        like=int(snap.get("like") or 0),
        like_need=int(snap.get("like_need") or 0),
        share=int(snap.get("share") or 0),
        share_need=int(snap.get("share_need") or 0),
        browse_gold=snap.get("browse_gold"),
        like_gold=snap.get("like_gold"),
        share_gold=snap.get("share_gold"),
        gold=gold,
        today_get=snap.get("today_get"),
        today_total=snap.get("today_total"),
    )


def complete_daily_tasks(creds: TaygedoCredentials) -> dict[str, Any]:
    """完成任务中心每日任务：浏览 / 点赞 / 分享。"""
    before = _daily_task_snapshot(creds)
    if before["all_done"]:
        return {
            **before,
            "skipped": True,
            "gold": None,
            "text": _tasks_extra_text_from_snap(before),
        }

    need = max(
        before["browse_need"] - before["browse"],
        before["like_need"] - before["like"],
        1,
    )
    posts = list_recommend_posts(creds, count=max(12, need + 4))
    if len(posts) < 1:
        raise TaygedoApiError("帖子列表不足，无法完成每日任务")

    browse_n = before["browse"]
    like_n = before["like"]
    share_n = before["share"]
    errors: list[str] = []

    for item in posts:
        if browse_n >= before["browse_need"]:
            break
        try:
            view_post(creds, str(item["post_id"]))
            browse_n += 1
        except TaygedoApiError as exc:
            errors.append(f"浏览:{exc.message}")

    for item in posts:
        if like_n >= before["like_need"]:
            break
        if item.get("liked"):
            continue
        try:
            like_post(creds, str(item["post_id"]))
            like_n += 1
        except TaygedoApiError as exc:
            errors.append(f"点赞:{exc.message}")

    if share_n < before["share_need"]:
        try:
            share_post(creds, str(posts[0]["post_id"]))
            share_n += 1
        except TaygedoApiError as exc:
            errors.append(f"分享:{exc.message}")

    after = _daily_task_snapshot(creds)
    gold = None
    if after["today_get"] > before["today_get"]:
        gold = after["today_get"] - before["today_get"]
    text = _tasks_extra_text_from_snap(after, gold=gold)
    if errors and not after["all_done"]:
        text = f"{text}（部分失败：{'；'.join(errors[:2])}）"
    return {**after, "skipped": False, "gold": gold, "text": text, "errors": errors}


def _attach_daily_tasks(
    creds: TaygedoCredentials, result: CheckinResult
) -> CheckinResult:
    """在社区签到结果上附加每日任务执行情况。"""
    try:
        tasks = complete_daily_tasks(creds)
        task_line = str(tasks.get("text") or "") or None
    except TaygedoApiError as exc:
        logger.warning("taygedo daily tasks failed: %s", exc.message)
        task_line = f"每日任务失败：{exc.message}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("taygedo daily tasks failed")
        task_line = f"每日任务失败：{exc}"
    return CheckinResult(
        game_code=result.game_code,
        game_name=result.game_name,
        role_uid=result.role_uid,
        role_name=result.role_name,
        channel_name=result.channel_name,
        status=result.status,
        message=result.message,
        awards_text=result.awards_text,
        awards=result.awards,
        extra_text=task_line,
        upstream_request=result.upstream_request,
        upstream_response=result.upstream_response,
    )


def query_app_today(creds: TaygedoCredentials) -> CheckinResult:
    """查塔吉多 APP 社区签到状态（getSignState）。

    已签时打开页 force 回源会补跑每日任务（浏览/点赞/分享）；
    未签仅展示进度，由行内签到触发执行。
    """
    signed = _get_app_sign_state(creds)
    if signed:
        awards_text, awards_items = _app_signin_awards_from_tasks(creds)
        result = CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid=creds.uid,
            role_name="社区账号",
            channel_name="社区",
            status="already",
            message=(
                f"今日已签到，获得：{awards_text}" if awards_text else "今日已签到"
            ),
            awards_text=awards_text,
            awards=awards_items or None,
        )
        return _attach_daily_tasks(creds, result)
    if signed is None:
        return CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid=creds.uid,
            role_name="社区账号",
            channel_name="社区",
            status="error",
            message="查询社区签到状态失败",
        )
    task_line: str | None = None
    try:
        snap = _daily_task_snapshot(creds)
        task_line = _tasks_extra_text_from_snap(snap)
    except TaygedoApiError as exc:
        logger.warning("taygedo task progress for display failed: %s", exc.message)
        task_line = "每日任务：进度暂不可用"
    except Exception:  # noqa: BLE001
        logger.exception("taygedo task progress for display failed")
        task_line = "每日任务：进度暂不可用"
    return CheckinResult(
        game_code=GAME_APP,
        game_name=GAME_APP_NAME,
        role_uid=creds.uid,
        role_name="社区账号",
        channel_name="社区",
        status="pending",
        message="今日尚未签到",
        awards_text=None,
        extra_text=task_line,
    )


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


def _taygedo_game_sort_key(game_code: str) -> tuple[int, int]:
    """社区 APP 优先；游戏按异环 → 幻塔。"""
    code = (game_code or "").strip()
    if code == GAME_APP:
        return (0, 0)
    order = {GAME_NTE: 1, GAME_HT: 2}.get(code)
    if order is not None:
        return (1, order)
    return (2, 99)


def sort_taygedo_results(results: list[CheckinResult]) -> list[CheckinResult]:
    """稳定展示顺序：社区 → 异环 → 幻塔。logs 回读无序时也靠此纠正。"""
    return sorted(
        results,
        key=lambda r: (
            _taygedo_game_sort_key(r.game_code),
            r.role_name or "",
            r.role_uid or "",
        ),
    )


def query_today_all(
    creds: TaygedoCredentials,
) -> tuple[TaygedoCredentials, list[CheckinResult]]:
    """社区签到优先，再查异环 / 幻塔游戏签到。"""
    working, targets = list_checkin_targets(creds)
    results: list[CheckinResult] = []
    for game_code, role in targets:
        if game_code == GAME_APP:
            results.append(query_app_today(working))
        elif role is not None:
            results.append(query_game_today(working, role))
    return working, sort_taygedo_results(results)


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
        body=_form_encode({"communityId": str(COMMUNITY_ID)}),
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
                    award_item(name="塔塔币", count=int(gold), resource_type="gold")
                )
            awards_text = "、".join(
                f"{a['name']}+{a['count']}" for a in awards_items
            )
        result = CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid=creds.uid,
            role_name="社区账号",
            channel_name="社区",
            status="ok",
            message=f"签到成功{('，获得：' + awards_text) if awards_text else ''}",
            awards_text=awards_text,
            awards=awards_items or None,
        )
        return _attach_daily_tasks(creds, result)
    if _is_already(msg):
        awards_text, awards_items = _app_signin_awards_from_tasks(creds)
        result = CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid=creds.uid,
            role_name="社区账号",
            channel_name="社区",
            status="already",
            message=(
                f"今日已签到，获得：{awards_text}" if awards_text else "今日已签到"
            ),
            awards_text=awards_text,
            awards=awards_items or None,
        )
        return _attach_daily_tasks(creds, result)
    return CheckinResult(
        game_code=GAME_APP,
        game_name=GAME_APP_NAME,
        role_uid=creds.uid,
        role_name="社区账号",
        channel_name="社区",
        status="error",
        message=friendly_error_message(msg or "社区签到失败"),
    )


def game_signin(creds: TaygedoCredentials, role: TaygedoRole) -> CheckinResult:
    form_body = {"roleId": role.role_id, "gameId": role.game_code}
    body = _form_encode(form_body)
    url = f"{TAYGEDO_BASE}/apihub/awapi/sign"
    status, data = _http(
        "POST",
        url,
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
    upstream_req = format_upstream_request("POST", url, form_body)
    upstream_resp = format_upstream_response(data)
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
            upstream_request=upstream_req,
            upstream_response=upstream_resp,
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
            upstream_request=upstream_req,
            upstream_response=upstream_resp,
        )
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=channel,
        status="error",
        message=friendly_error_message(msg or f"{role.game_name}签到失败"),
        upstream_request=upstream_req,
        upstream_response=upstream_resp,
    )


def checkin_target(
    creds: TaygedoCredentials,
    *,
    game_code: str,
    role: TaygedoRole | None = None,
) -> CheckinResult:
    if game_code == GAME_APP:
        return app_signin(creds)
    if role is None:
        raise TaygedoApiError("缺少游戏角色参数")
    return game_signin(creds, role)


def list_checkin_targets(
    creds: TaygedoCredentials,
) -> tuple[TaygedoCredentials, list[tuple[str, TaygedoRole | None]]]:
    """返回凭证 + 签到目标：社区 APP 优先，再异环 / 幻塔角色。"""
    working = ensure_session(creds)
    try:
        roles = list_all_game_roles(working)
    except TaygedoApiError as exc:
        if is_auth_failure(code=exc.code, message=exc.message):
            working = refresh_access_token(working)
            roles = list_all_game_roles(working)
        else:
            raise
    targets: list[tuple[str, TaygedoRole | None]] = [(GAME_APP, None)]
    targets.extend((role.game_code, role) for role in roles)
    return working, targets


def _app_meta(creds: TaygedoCredentials) -> dict[str, str]:
    return {
        "game_code": GAME_APP,
        "game_name": GAME_APP_NAME,
        "role_uid": creds.uid,
        "role_name": "社区账号",
        "channel_name": "社区",
    }


def checkin_all(creds: TaygedoCredentials) -> tuple[TaygedoCredentials, list[CheckinResult]]:
    """返回可能刷新后的凭证 + 签到结果（社区 + 异环 / 幻塔）。"""
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
            if game_code == GAME_APP or role is None:
                meta = _app_meta(working)
                results.append(
                    CheckinResult(
                        game_code=meta["game_code"],
                        game_name=meta["game_name"],
                        role_uid=meta["role_uid"],
                        role_name=meta["role_name"],
                        channel_name=meta["channel_name"],
                        status="error",
                        message=friendly_error_message(exc.message),
                    )
                )
            else:
                results.append(
                    CheckinResult(
                        game_code=role.game_code,
                        game_name=role.game_name,
                        role_uid=role.role_id,
                        role_name=role.role_name,
                        channel_name=role.game_name,
                        status="error",
                        message=friendly_error_message(exc.message),
                    )
                )
    return working, sort_taygedo_results(results)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class ShopGoods:
    goods_id: str
    name: str
    cover: str = ""
    price: int = 0
    exchange_num: int = 0
    cycle_limit: int = 0
    cycle_type: int = 0
    stock: int = -1
    # 官方 listGoods.limit：1=有总库存跟踪；0=不限库存（此时 stock 常为 0 仍可兑）
    stock_limited: bool = False
    tab: str = ""
    state: int = 0
    game_id: str = ""

    @property
    def can_exchange(self) -> bool:
        if self.cycle_limit > 0 and self.exchange_num >= self.cycle_limit:
            return False
        # 仅库存跟踪商品：stock==0 才是售罄
        if self.stock_limited and self.stock == 0:
            return False
        # 常见：0/1 可兑；其它状态视为不可兑
        if self.state not in (0, 1):
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "goods_id": self.goods_id,
            "name": self.name,
            "cover": self.cover,
            "price": self.price,
            "exchange_num": self.exchange_num,
            "cycle_limit": self.cycle_limit,
            "cycle_type": self.cycle_type,
            "stock": self.stock,
            "stock_limited": self.stock_limited,
            "tab": self.tab,
            "state": self.state,
            "game_id": self.game_id,
            "can_exchange": self.can_exchange,
        }


# listGoods 常返回 gameId=0；真实归属在 getGoodsDetail，或可从 tab 推断
_SHOP_TAB_GAME_IDS: dict[str, str] = {
    "yh": GAME_NTE,  # 异环
    "ht": GAME_HT,  # 幻塔
}


def _shop_game_id_from_row(row: dict[str, Any]) -> str:
    """解析商品所属游戏。listGoods 的 gameId=0 视为空，回退到 tab。"""
    raw = row.get("gameId")
    if raw is None:
        raw = row.get("game_id")
    game_id = str(raw or "").strip()
    if game_id and game_id != "0":
        return game_id
    tab = str(row.get("tab") or "").strip().lower()
    return _SHOP_TAB_GAME_IDS.get(tab, "")


def _parse_shop_goods(row: dict[str, Any]) -> ShopGoods | None:
    goods_id = str(
        row.get("id")
        or row.get("goodsId")
        or row.get("goods_id")
        or ""
    ).strip()
    name = str(
        row.get("name")
        or row.get("goodsName")
        or row.get("goods_name")
        or ""
    ).strip()
    if not goods_id or not name:
        return None
    stock_limited = _to_int(row.get("limit"), 0) > 0
    stock_raw = _to_int(
        row.get("stock")
        if row.get("stock") is not None
        else (
            row.get("remainStock")
            if row.get("remainStock") is not None
            else row.get("surplusStock")
        ),
        -1,
    )
    # 不限库存时上游常给 stock=0，归一成 -1，避免前端当成「已兑完」
    stock = stock_raw if stock_limited else (-1 if stock_raw <= 0 else stock_raw)
    return ShopGoods(
        goods_id=goods_id,
        name=name,
        cover=str(
            row.get("cover")
            or row.get("icon")
            or row.get("pic")
            or row.get("picture")
            or row.get("img")
            or ""
        ).strip(),
        price=_to_int(row.get("price") or row.get("coin") or row.get("goldCoin"), 0),
        exchange_num=_to_int(
            row.get("exchangeNum")
            if row.get("exchangeNum") is not None
            else (
                row.get("exchange_num")
                if row.get("exchange_num") is not None
                else (
                    row.get("exchanged")
                    if row.get("exchanged") is not None
                    else row.get("userExchangeNum")
                )
            ),
            0,
        ),
        cycle_limit=_to_int(
            row.get("cycleLimit")
            if row.get("cycleLimit") is not None
            else (
                row.get("cycle_limit")
                if row.get("cycle_limit") is not None
                else 0
            ),
            0,
        ),
        cycle_type=_to_int(row.get("cycleType") or row.get("cycle_type"), 0),
        stock=stock,
        stock_limited=stock_limited,
        tab=str(row.get("tab") or "").strip(),
        state=_to_int(row.get("state") or row.get("status"), 0),
        game_id=_shop_game_id_from_row(row),
    )


def _parse_shop_tabs(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for row in raw:
        if isinstance(row, str):
            key = row.strip()
            if key:
                out.append({"tab": key, "name": key})
            continue
        if not isinstance(row, dict):
            continue
        key = str(row.get("tab") or row.get("key") or row.get("id") or "").strip()
        if not key:
            continue
        name = str(
            row.get("name") or row.get("title") or row.get("label") or key
        ).strip()
        out.append({"tab": key, "name": name or key})
    return out


def list_shop_goods(
    creds: TaygedoCredentials,
    *,
    tab: str = "all",
    count: int = 20,
    version: int = 0,
) -> tuple[list[ShopGoods], list[dict[str, str]]]:
    """GET /apihub/api/shop/listGoods — 塔塔币兑换商城。"""
    query = urllib.parse.urlencode(
        {
            "version": max(0, int(version)),
            "count": max(1, min(50, int(count))),
            "tab": str(tab or "all").strip() or "all",
        }
    )
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/apihub/api/shop/listGoods?{query}",
        headers=_h5_headers(creds),
    )
    if status != 200 or data.get("code") != 0:
        _raise_if_auth_failure(status=status, data=data, fallback="查询兑换商城失败")
        msg = str(data.get("msg") or data.get("message") or "查询兑换商城失败")
        raise TaygedoApiError(friendly_error_message(msg), code=data.get("code"))

    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    rows = payload.get("goods") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = payload.get("list") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = []

    items: list[ShopGoods] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = _parse_shop_goods(row)
        if item is None or item.goods_id in seen:
            continue
        seen.add(item.goods_id)
        items.append(item)

    tabs = _parse_shop_tabs(payload.get("tabs") if isinstance(payload, dict) else None)
    if not tabs:
        tabs = [{"tab": "all", "name": "全部"}]
    return items, tabs


def get_shop_goods_detail(
    creds: TaygedoCredentials, *, goods_id: str
) -> dict[str, Any]:
    """GET /apihub/api/shop/getGoodsDetail。"""
    query = urllib.parse.urlencode({"goodsId": str(goods_id)})
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/apihub/api/shop/getGoodsDetail?{query}",
        headers=_h5_headers(creds),
    )
    if status != 200 or data.get("code") != 0:
        _raise_if_auth_failure(status=status, data=data, fallback="查询商品详情失败")
        msg = str(data.get("msg") or data.get("message") or "查询商品详情失败")
        raise TaygedoApiError(friendly_error_message(msg), code=data.get("code"))
    payload = data.get("data")
    return payload if isinstance(payload, dict) else {}


def exchange_shop_goods(
    creds: TaygedoCredentials,
    *,
    goods_id: str,
    game_id: str,
    role_id: str,
    count: int = 1,
) -> dict[str, Any]:
    """POST /apihub/api/shop/exchange — App form: goodsId, gameId, roleId, count。

    注意：H5 头会返回 code=22 invalid request；必须走 App 头，且 count 必填。
    """
    status, data = _http(
        "POST",
        f"{TAYGEDO_BASE}/apihub/api/shop/exchange",
        headers={
            **_app_headers(creds),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=_form_encode(
            {
                "goodsId": str(goods_id),
                "gameId": str(game_id),
                "roleId": str(role_id),
                "count": str(max(1, int(count or 1))),
            }
        ),
    )
    if status == 200 and data.get("code") == 0:
        payload = data.get("data")
        return payload if isinstance(payload, dict) else {"ok": True}
    _raise_if_auth_failure(status=status, data=data, fallback="兑换失败")
    msg = str(data.get("msg") or data.get("message") or "兑换失败")
    raise TaygedoApiError(friendly_error_message(msg), code=data.get("code"))