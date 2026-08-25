"""库街区社区 / 游戏签到（从 kujiequ_client 拆出）。"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.core.timeutil import today
from app.services.checkin.common import (
    CheckinResult,
    award_item,
    format_upstream_request,
    format_upstream_response,
    is_placeholder_awards,
    prefer_richer_awards,
    prefer_richer_award_items,
)
from app.services.kujiequ.client import (
    API_BASE,
    GAME_PGR,
    GAME_WW,
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


def _goods_award_dict(row: dict[str, Any]) -> dict[str, Any] | None:
    name = _goods_name(row)
    if not name:
        return None
    num = row.get("goodsNum")
    if num is None:
        num = row.get("gainValue")
    if num is None:
        num = row.get("count")
    try:
        count = int(num) if num is not None else 1
    except (TypeError, ValueError):
        count = 1
    rid = (
        row.get("goodsId")
        or row.get("goodsID")
        or row.get("id")
        or row.get("type")
    )
    rtype = row.get("typeName") or row.get("goodsType") or row.get("type")
    icon = str(row.get("goodsUrl") or row.get("goods_url") or "").strip() or None
    return award_item(
        name=name,
        count=count,
        resource_id=rid,
        resource_type=rtype,
        icon_url=icon,
    )


def _format_goods_rows(
    rows: list[Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    for row in _iter_goods_dicts(rows):
        d = _goods_award_dict(row)
        if d:
            items.append(d)
    if not items:
        return None, []
    parts: list[str] = []
    for a in items:
        name = str(a["name"])
        count = int(a.get("count") or 1)
        if name == "库洛币":
            parts.append(f"库洛币+{count}")
        else:
            parts.append(f"{name}×{count}")
    return (" · ".join(parts) if parts else None), items


def get_task_process(creds: KujiequCredentials) -> dict[str, Any]:
    """取任务进度（每日任务 / 今日库洛币上限等）。"""
    if not creds.user_id:
        raise KujiequApiError("缺少 userId，无法读取任务进度")
    data = _post_form(
        "/encourage/level/getTaskProcess",
        {"gameId": 0, "userId": creds.user_id},
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)
    payload = data.get("data") or {}
    return payload if isinstance(payload, dict) else {}


def _task_progress(task: dict[str, Any]) -> tuple[int, int]:
    try:
        done = int(task.get("completeTimes") or 0)
    except (TypeError, ValueError):
        done = 0
    try:
        need = int(task.get("needActionTimes") or 1)
    except (TypeError, ValueError):
        need = 1
    return max(0, done), max(1, need)


def _find_daily_task(
    tasks: list[Any], *, keywords: tuple[str, ...]
) -> dict[str, Any] | None:
    for task in tasks:
        if not isinstance(task, dict):
            continue
        remark = str(task.get("remark") or "")
        if any(k in remark for k in keywords):
            return task
    return None


def _community_awards_from_tasks(
    creds: KujiequCredentials,
) -> tuple[str | None, list[dict[str, Any]]]:
    """从每日任务进度读取「用户签到」奖励（已签后 info 接口不含奖励）。"""
    if not creds.user_id:
        return None, []
    try:
        payload = get_task_process(creds)
    except KujiequApiError as exc:
        logger.warning("kujiequ task process failed: %s", exc.message)
        return None, []
    tasks = payload.get("dailyTask")
    if not isinstance(tasks, list):
        return None, []
    task = _find_daily_task(tasks, keywords=("签到",))
    if not task:
        return None, []
    done, need = _task_progress(task)
    if done < need:
        return None, []
    gold = task.get("gainGold")
    if gold is None:
        return None, []
    try:
        count = int(gold)
    except (TypeError, ValueError):
        return None, []
    item = award_item(name="库洛币", count=count, resource_type="gold")
    return f"库洛币+{count}", [item]


def _daily_task_counts(payload: dict[str, Any]) -> dict[str, Any]:
    tasks = payload.get("dailyTask")
    if not isinstance(tasks, list):
        tasks = []
    view = _find_daily_task(tasks, keywords=("浏览",))
    like = _find_daily_task(tasks, keywords=("点赞",))
    share = _find_daily_task(tasks, keywords=("分享",))
    sign = _find_daily_task(tasks, keywords=("签到",))

    def _pair(task: dict[str, Any] | None, default_need: int) -> tuple[int, int]:
        if not task:
            return 0, default_need
        return _task_progress(task)

    view_d, view_n = _pair(view, 3)
    like_d, like_n = _pair(like, 5)
    share_d, share_n = _pair(share, 1)
    gold = 0
    for task in (view, like, share, sign):
        if not task:
            continue
        done, need = _task_progress(task)
        if done < need:
            continue
        try:
            gold += int(task.get("gainGold") or 0)
        except (TypeError, ValueError):
            pass
    try:
        current = int(payload.get("currentDailyGold") or 0)
    except (TypeError, ValueError):
        current = 0
    try:
        daily_max = int(payload.get("maxDailyGold") or 80)
    except (TypeError, ValueError):
        daily_max = 80
    return {
        "view": view_d,
        "view_need": view_n,
        "like": like_d,
        "like_need": like_n,
        "share": share_d,
        "share_need": share_n,
        "gold": gold,
        "current_daily_gold": current,
        "max_daily_gold": daily_max,
        "all_done": view_d >= view_n and like_d >= like_n and share_d >= share_n,
    }


def _tasks_extra_text(
    *,
    view: int,
    view_need: int = 3,
    like: int,
    like_need: int = 5,
    share: int,
    share_need: int = 1,
    gold: int | None = None,
    current_daily_gold: int | None = None,
    max_daily_gold: int | None = None,
) -> str:
    parts = [
        f"浏览 {view}/{view_need}",
        f"点赞 {like}/{like_need}",
        f"分享 {share}/{share_need}",
    ]
    text = "每日任务：" + " · ".join(parts)
    if gold and gold > 0:
        text += f"（库洛币+{gold}）"
    if current_daily_gold is not None and max_daily_gold is not None:
        text += f"；今日 {current_daily_gold}/{max_daily_gold}"
    return text


def list_forum_posts(
    creds: KujiequCredentials,
    *,
    limit: int = 8,
    game_id: int = GAME_WW,
    forum_id: int = 9,
) -> list[dict[str, Any]]:
    """拉帖子列表（浏览/点赞用）。默认鸣潮推荐区。"""
    data = _post_form(
        "/forum/list",
        {
            "forumId": forum_id,
            "gameId": game_id,
            "pageIndex": 1,
            "pageSize": max(limit, 10),
            "searchType": 3,
            "timeType": 0,
            "topicId": 0,
        },
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)
    payload = data.get("data") or {}
    rows = payload.get("postList") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = str(row.get("postId") or "").strip()
        user_id = str(row.get("userId") or "").strip()
        if not post_id:
            continue
        try:
            is_like = int(row.get("isLike") or 0) == 1
        except (TypeError, ValueError):
            is_like = bool(row.get("isLike"))
        out.append(
            {
                "post_id": post_id,
                "user_id": user_id,
                "is_like": is_like,
                "forum_id": int(row.get("gameForumId") or forum_id),
                "game_id": int(row.get("gameId") or game_id),
            }
        )
        if len(out) >= max(1, limit):
            break
    return out


def view_post(creds: KujiequCredentials, post_id: str) -> None:
    data = _post_form(
        "/forum/getPostDetail",
        {
            "isOnlyPublisher": 0,
            "postId": post_id,
            "showOrderType": 2,
        },
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)


def like_post(
    creds: KujiequCredentials,
    *,
    post_id: str,
    to_user_id: str,
    forum_id: int,
    game_id: int,
) -> None:
    data = _post_form(
        "/forum/like",
        {
            "forumId": forum_id,
            "gameId": game_id,
            "likeType": 1,
            "operateType": 1,
            "postCommentId": 0,
            "postCommentReplyId": 0,
            "postId": post_id,
            "postType": 1,
            "toUserId": to_user_id or "0",
        },
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)


def share_task(creds: KujiequCredentials, *, game_id: int = GAME_WW) -> None:
    data = _post_form(
        "/encourage/level/shareTask",
        {"gameId": game_id},
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)


def complete_daily_tasks(creds: KujiequCredentials) -> dict[str, Any]:
    """完成每日任务：浏览×3、点赞×5、分享×1。"""
    before = _daily_task_counts(get_task_process(creds))
    if before["all_done"]:
        return {
            **before,
            "skipped": True,
            "text": _tasks_extra_text(
                view=before["view"],
                view_need=before["view_need"],
                like=before["like"],
                like_need=before["like_need"],
                share=before["share"],
                share_need=before["share_need"],
                gold=before["gold"] or None,
                current_daily_gold=before["current_daily_gold"],
                max_daily_gold=before["max_daily_gold"],
            ),
        }

    need_posts = max(
        before["view_need"] - before["view"],
        before["like_need"] - before["like"],
        1,
    )
    posts = list_forum_posts(creds, limit=max(8, need_posts + 2))
    if len(posts) < 3:
        raise KujiequApiError("帖子列表不足，无法完成每日任务")

    errors: list[str] = []
    view_n = before["view"]
    like_n = before["like"]
    share_n = before["share"]

    for item in posts:
        if view_n >= before["view_need"]:
            break
        try:
            view_post(creds, str(item["post_id"]))
            view_n += 1
        except KujiequApiError as exc:
            errors.append(f"浏览失败:{exc.message}")
        time.sleep(0.4)

    for item in posts:
        if like_n >= before["like_need"]:
            break
        if item.get("is_like"):
            continue
        try:
            like_post(
                creds,
                post_id=str(item["post_id"]),
                to_user_id=str(item.get("user_id") or ""),
                forum_id=int(item.get("forum_id") or 9),
                game_id=int(item.get("game_id") or GAME_WW),
            )
            like_n += 1
        except KujiequApiError as exc:
            errors.append(f"点赞失败:{exc.message}")
        time.sleep(0.4)

    if share_n < before["share_need"]:
        try:
            share_task(creds, game_id=GAME_WW)
            share_n = before["share_need"]
        except KujiequApiError as exc:
            errors.append(f"分享失败:{exc.message}")

    after = _daily_task_counts(get_task_process(creds))
    text = _tasks_extra_text(
        view=after["view"] or view_n,
        view_need=after["view_need"],
        like=after["like"] or like_n,
        like_need=after["like_need"],
        share=after["share"] or share_n,
        share_need=after["share_need"],
        gold=after["gold"] or None,
        current_daily_gold=after["current_daily_gold"],
        max_daily_gold=after["max_daily_gold"],
    )
    if errors:
        text += "（部分失败）"
    return {
        **after,
        "view": after["view"] or view_n,
        "like": after["like"] or like_n,
        "share": after["share"] or share_n,
        "skipped": False,
        "text": text,
        "errors": errors,
    }


def _attach_daily_tasks(
    creds: KujiequCredentials, result: CheckinResult
) -> CheckinResult:
    """在社区签到结果上附加每日任务执行情况（不展示连签天数）。"""
    if result.game_code != "kujiequ":
        return result
    if result.status == "error":
        return result
    try:
        tasks = complete_daily_tasks(creds)
        result.extra_text = str(tasks.get("text") or "") or None
    except KujiequApiError as exc:
        result.extra_text = f"每日任务失败：{exc.message}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("kujiequ daily tasks failed")
        result.extra_text = f"每日任务失败：{exc}"
    return result


def _game_awards_from_records(
    creds: KujiequCredentials,
    role: GameRole,
    *,
    retries: int = 0,
    retry_delay_sec: float = 1.2,
) -> tuple[str | None, list[dict[str, Any]]]:
    """从游戏签到领取记录（queryRecordV2）按北京自然日取今日奖励。"""
    last_text: str | None = None
    last_items: list[dict[str, Any]] = []
    attempts = max(1, retries + 1)
    for i in range(attempts):
        if i > 0:
            time.sleep(retry_delay_sec)
        last_text, last_items = _game_awards_from_records_once(creds, role)
        if last_text and not is_placeholder_awards(last_text):
            return last_text, last_items
    return last_text, last_items


def _game_awards_from_records_once(
    creds: KujiequCredentials, role: GameRole
) -> tuple[str | None, list[dict[str, Any]]]:
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
        return None, []
    rows = data.get("data") or []
    if not isinstance(rows, list):
        return None, []
    day = today().isoformat()
    todays = [
        r
        for r in rows
        if isinstance(r, dict) and str(r.get("sigInDate") or "").startswith(day)
    ]
    return _format_goods_rows(todays)


def fetch_game_attendance_bundle(
    creds: KujiequCredentials, role: GameRole
) -> dict[str, Any]:
    """拉取签到日历落库包：initSignInV2 + queryRecordV2。"""
    creds = _ensure_device(creds)
    form = {
        "gameId": role.game_id,
        "serverId": role.server_id,
        "roleId": role.role_id,
        "userId": role.user_id or creds.user_id,
    }
    init_data = _post_form(
        "/encourage/signIn/initSignInV2",
        form,
        token=creds.token,
        creds=creds,
    )
    _assert_ok(init_data)
    init_payload = init_data.get("data")
    if not isinstance(init_payload, dict):
        raise KujiequApiError("获取签到日历失败，请稍后重试")
    configs = init_payload.get("signInGoodsConfigs")
    if not isinstance(configs, list) or not configs:
        raise KujiequApiError("签到奖励日历为空，请稍后重试")

    records: list[Any] = []
    try:
        rec_data = _post_form(
            "/encourage/signIn/queryRecordV2",
            form,
            token=creds.token,
            creds=creds,
        )
        _assert_ok(rec_data)
        raw_rows = rec_data.get("data") or []
        if isinstance(raw_rows, list):
            records = raw_rows
    except KujiequApiError as exc:
        # 日历格子以 init 为准；领取记录失败不阻断
        logger.warning(
            "kujiequ attendance records gameId=%s role=%s failed: %s",
            role.game_id,
            role.role_id,
            exc.message,
        )
    return {"init": init_payload, "records": records}


def _awards_from_sign_payload(
    payload: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    """解析签到成功响应：社区 gainVoList / 游戏 todayList。"""
    gains = payload.get("gainVoList")
    if isinstance(gains, list) and gains:
        items: list[dict[str, Any]] = []
        parts: list[str] = []
        for g in gains:
            if not isinstance(g, dict):
                continue
            try:
                count = int(g.get("gainValue") or 0)
            except (TypeError, ValueError):
                count = 0
            items.append(
                award_item(name="库洛币", count=count or 1, resource_type="gold")
            )
            parts.append(f"库洛币+{g.get('gainValue') or '?'}")
        if items:
            return " · ".join(parts), items
    today_list = payload.get("todayList")
    if isinstance(today_list, dict):
        today_list = [today_list]
    if isinstance(today_list, list) and today_list:
        return _format_goods_rows(today_list)
    return None, []


def query_community_today(creds: KujiequCredentials) -> CheckinResult:
    """查社区签到状态。

    已签时行内无「签到」按钮，打开页 force 回源须一并补跑每日任务
    （浏览/点赞/分享）；未签仅展示进度，由行内签到触发执行。
    """
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

    awards_text: str | None = None
    awards_items: list[dict[str, Any]] = []
    task_line: str | None = None

    if has:
        # 已签：补跑每日任务后再取奖励/进度文案
        try:
            tasks = complete_daily_tasks(creds)
            task_line = str(tasks.get("text") or "") or None
        except KujiequApiError as exc:
            logger.warning("kujiequ daily tasks on status failed: %s", exc.message)
            task_line = f"每日任务失败：{exc.message}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("kujiequ daily tasks on status failed")
            task_line = f"每日任务失败：{exc}"
        awards_text, awards_items = _community_awards_from_tasks(creds)
    else:
        try:
            task_payload = get_task_process(creds)
            counts = _daily_task_counts(task_payload)
            if counts["all_done"]:
                task_line = _tasks_extra_text(
                    view=counts["view"],
                    view_need=counts["view_need"],
                    like=counts["like"],
                    like_need=counts["like_need"],
                    share=counts["share"],
                    share_need=counts["share_need"],
                    gold=counts["gold"] or None,
                    current_daily_gold=counts["current_daily_gold"],
                    max_daily_gold=counts["max_daily_gold"],
                )
            else:
                task_line = _tasks_extra_text(
                    view=counts["view"],
                    view_need=counts["view_need"],
                    like=counts["like"],
                    like_need=counts["like_need"],
                    share=counts["share"],
                    share_need=counts["share_need"],
                    current_daily_gold=counts["current_daily_gold"],
                    max_daily_gold=counts["max_daily_gold"],
                )
        except KujiequApiError as exc:
            logger.warning("kujiequ task process for display failed: %s", exc.message)
            task_line = "每日任务：进度暂不可用"

    return CheckinResult(
        game_code="kujiequ",
        game_name="库街区",
        role_uid=creds.user_id or "community",
        role_name=creds.user_name or "社区账号",
        channel_name="社区",
        status="already" if has else "pending",
        message="今日已签到" if has else "今日未签到",
        awards_text=awards_text,
        awards=awards_items or None,
        extra_text=task_line,
    )


def do_community_sign_in(creds: KujiequCredentials) -> CheckinResult:
    creds = _ensure_device(creds)
    form_body = {"gameId": GAME_PGR}
    data = _post_form(
        "/user/signIn",
        form_body,
        token=creds.token,
        creds=creds,
    )
    upstream_req = format_upstream_request(
        "POST", f"{API_BASE}/user/signIn", form_body
    )
    upstream_resp = format_upstream_response(data)
    code = data.get("code")
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    msg = str(data.get("msg") or "")
    if code_i == 1511 or "重复" in msg:
        awards_text, awards_items = _community_awards_from_tasks(creds)
        return CheckinResult(
            game_code="kujiequ",
            game_name="库街区",
            role_uid=creds.user_id or "community",
            role_name=creds.user_name or "社区账号",
            channel_name="社区",
            status="already",
            message=msg or "今日已签到",
            awards_text=awards_text,
            awards=awards_items or None,
            upstream_request=upstream_req,
            upstream_response=upstream_resp,
        )
    if code_i in (220, 401):
        raise KujiequApiError("登录已过期，请重新绑定", code=code_i)
    if code_i != 200 and not data.get("success"):
        raise KujiequApiError(msg or "社区签到失败", code=code_i)

    awards_text: str | None = None
    awards_items: list[dict[str, Any]] = []
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        awards_text, awards_items = _awards_from_sign_payload(payload)
    if not awards_text:
        awards_text, awards_items = _community_awards_from_tasks(creds)
    # 「请求成功」是通用话术，不用作签到结论
    if msg.strip() in ("请求成功", "success", "ok"):
        msg = "签到成功"
    return CheckinResult(
        game_code="kujiequ",
        game_name="库街区",
        role_uid=creds.user_id or "community",
        role_name=creds.user_name or "社区账号",
        channel_name="社区",
        status="ok",
        message=msg or "签到成功",
        awards_text=awards_text,
        awards=awards_items or None,
        upstream_request=upstream_req,
        upstream_response=upstream_resp,
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
    awards_text, awards_items = (
        _game_awards_from_records(creds, role) if signed else (None, [])
    )
    return CheckinResult(
        game_code=f"game_{role.game_id}",
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=role.server_name,
        status="already" if signed else "pending",
        message="今日已签到" if signed else "今日未签到",
        awards_text=awards_text,
        awards=awards_items or None,
    )


def do_game_sign_in(creds: KujiequCredentials, role: GameRole) -> CheckinResult:
    creds = _ensure_device(creds)
    # 与 today() 同一时区（北京），避免月末边界错月
    month = f"{today().month:02d}"
    form_body = {
        "gameId": role.game_id,
        "serverId": role.server_id,
        "roleId": role.role_id,
        "userId": role.user_id or creds.user_id,
        "reqMonth": month,
    }
    data = _post_form(
        "/encourage/signIn/v2",
        form_body,
        token=creds.token,
        creds=creds,
    )
    upstream_req = format_upstream_request(
        "POST", f"{API_BASE}/encourage/signIn/v2", form_body
    )
    upstream_resp = format_upstream_response(data)
    code = data.get("code")
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    msg = str(data.get("msg") or "").strip()
    if code_i == 1511 or "重复" in msg:
        awards_text, awards_items = _game_awards_from_records(
            creds, role, retries=1
        )
        return CheckinResult(
            game_code=f"game_{role.game_id}",
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=role.server_name,
            status="already",
            message="今日已签到",
            awards_text=awards_text,
            awards=awards_items or None,
            upstream_request=upstream_req,
            upstream_response=upstream_resp,
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
            upstream_request=upstream_req,
            upstream_response=upstream_resp,
        )
    awards_text: str | None = None
    awards_items: list[dict[str, Any]] = []
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        awards_text, awards_items = _awards_from_sign_payload(payload)
    # 签到响应常缺 goodsName / 仅返回「奖励」；补查领取记录（可短重试）
    recorded_text, recorded_items = _game_awards_from_records(
        creds, role, retries=2
    )
    if is_placeholder_awards(awards_text):
        awards_text, awards_items = recorded_text, recorded_items
    else:
        merged_text = prefer_richer_awards(awards_text, recorded_text)
        awards_items = (
            prefer_richer_award_items(
                awards_text, awards_items, recorded_text, recorded_items
            )
            or []
        )
        awards_text = merged_text

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
            upstream_request=upstream_req,
            upstream_response=upstream_resp,
        )
    prev_text, prev_items = awards_text, awards_items
    awards_text = prefer_richer_awards(prev_text, verified.awards_text)
    awards_items = (
        prefer_richer_award_items(
            prev_text,
            prev_items,
            verified.awards_text,
            verified.awards,
        )
        or []
    )
    return CheckinResult(
        game_code=f"game_{role.game_id}",
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=role.server_name,
        status="ok",
        message="签到成功",
        awards_text=awards_text,
        awards=awards_items or None,
        upstream_request=upstream_req,
        upstream_response=upstream_resp,
    )


def _kujiequ_game_sort_key(game_code: str) -> tuple[int, int]:
    """社区签到优先；游戏按鸣潮 → 战双，其余按 gameId。"""
    code = (game_code or "").strip()
    if code == "kujiequ":
        return (0, 0)
    if code.startswith("game_"):
        try:
            gid = int(code[5:])
        except ValueError:
            return (1, 99)
        order = {GAME_WW: 1, GAME_PGR: 2}.get(gid, 10 + gid)
        return (1, order)
    return (2, 99)


def sort_kujiequ_results(results: list[CheckinResult]) -> list[CheckinResult]:
    """稳定展示顺序：库街区社区 → 鸣潮 → 战双。logs 回读无序时也靠此纠正。"""
    return sorted(
        results,
        key=lambda r: (
            _kujiequ_game_sort_key(r.game_code),
            r.role_name or "",
            r.role_uid or "",
        ),
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
    return creds, sort_kujiequ_results(results)


def run_all_checkins(
    creds: KujiequCredentials,
    *,
    role_keys: set[tuple[str, str]] | None = None,
) -> tuple[KujiequCredentials, list[CheckinResult]]:
    from app.services.checkin.role_prefs import matches_role_filter

    creds = _ensure_device(creds)
    if not creds.user_id:
        mine = fetch_mine(creds)
        creds.user_id = mine["user_id"]
        creds.user_name = mine["user_name"] or creds.user_name

    results: list[CheckinResult] = []
    community_uid = creds.user_id or "community"
    if matches_role_filter("kujiequ", community_uid, role_keys):
        try:
            # 即使今日已签，仍补跑每日任务（浏览/点赞/分享）
            results.append(_attach_daily_tasks(creds, do_community_sign_in(creds)))
        except KujiequApiError as exc:
            if exc.code in (220, 401):
                raise
            results.append(
                CheckinResult(
                    game_code="kujiequ",
                    game_name="库街区",
                    role_uid=community_uid,
                    role_name=creds.user_name or "社区账号",
                    channel_name="社区",
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
    return creds, sort_kujiequ_results(results)


def friendly_error_message(message: str) -> str:
    text = (message or "").strip() or "库街区请求失败"
    if "过期" in text or "失效" in text:
        return "凭证可能已失效，请重新绑定库街区"
    return text
