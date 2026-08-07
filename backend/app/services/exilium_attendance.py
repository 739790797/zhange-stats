"""追放社区签到与每日任务（从 exilium_client 拆出）。"""

from __future__ import annotations

import logging
from typing import Any

from app.services.checkin_common import (
    CheckinResult,
    award_item,
    format_upstream_request,
    format_upstream_response,
)
from app.services.exilium_client import (
    API_BASE,
    GAME_CODE,
    GAME_NAME,
    ExiliumApiError,
    ExiliumCredentials,
    _http,
    _http_full,
    _to_int,
    enrich_user_info,
    friendly_error_message,
    list_score_logs,
    login_with_password,
    mask_account,
)

logger = logging.getLogger(__name__)

def ensure_session(creds: ExiliumCredentials) -> ExiliumCredentials:
    """探活；失败且有密码则重登。"""
    try:
        enrich_user_info(creds)
        return creds
    except ExiliumApiError as exc:
        if creds.account_name and creds.password:
            logger.info("exilium token invalid, re-login with password")
            return login_with_password(creds.account_name, creds.password)
        raise ExiliumApiError(
            friendly_error_message(exc.message) or "登录已失效，请重新绑定",
            code=exc.code,
        ) from exc


def get_sign_in_status(creds: ExiliumCredentials) -> bool:
    data = _http(
        "GET",
        "/community/task/get_current_sign_in_status",
        token=creds.token,
    )
    return bool(data.get("has_sign_in"))


def sign_in(creds: ExiliumCredentials) -> CheckinResult:
    body: dict[str, Any] = {}
    data, full = _http_full(
        "POST", "/community/task/sign_in", token=creds.token, body=body
    )
    upstream_req = format_upstream_request(
        "POST", f"{API_BASE}/community/task/sign_in", body
    )
    upstream_resp = format_upstream_response(full)
    item = str(data.get("get_item_name") or "").strip()
    count = data.get("get_item_count")
    exp = data.get("get_exp")
    score = data.get("get_score")
    awards_items: list[dict[str, Any]] = []
    parts: list[str] = []
    if item:
        try:
            qty = int(count) if count is not None else 1
        except (TypeError, ValueError):
            qty = 1
        awards_items.append(award_item(name=item, count=qty))
        parts.append(f"{item}*{count}" if count is not None else item)
    if exp is not None:
        try:
            exp_i = int(exp)
        except (TypeError, ValueError):
            exp_i = 0
        awards_items.append(
            award_item(name="经验", count=exp_i, resource_type="exp")
        )
        parts.append(f"经验+{exp}")
    if score is not None:
        try:
            score_i = int(score)
        except (TypeError, ValueError):
            score_i = 0
        awards_items.append(
            award_item(name="积分", count=score_i, resource_type="score")
        )
        parts.append(f"积分+{score}")
    awards = "，".join(parts) if parts else None
    role_name = creds.nickname or mask_account(creds.account_name) or "社区账号"
    return CheckinResult(
        game_code=GAME_CODE,
        game_name=GAME_NAME,
        role_uid=creds.user_id or creds.account_name or "-",
        role_name=role_name,
        channel_name="社区",
        status="ok",
        message="签到成功" + (f"：{awards}" if awards else ""),
        awards_text=awards,
        awards=awards_items or None,
        upstream_request=upstream_req,
        upstream_response=upstream_resp,
    )


def _awards_from_score_log(
    creds: ExiliumCredentials,
) -> tuple[str | None, list[dict[str, Any]]]:
    """已签到时官方不再返回奖励明细，从积分变动记录（points_Log）补全。"""
    from app.core.timeutil import today as beijing_today

    try:
        data = list_score_logs(creds, page=1, page_size=30)
    except ExiliumApiError:
        return None, []
    day = beijing_today().isoformat()
    for row in data.get("list") or []:
        if not isinstance(row, dict):
            continue
        reason = str(row.get("reason") or "").strip()
        log_time = str(row.get("log_time") or "").strip()
        if reason != "签到":
            continue
        if not log_time.startswith(day):
            continue
        score = _to_int(row.get("score"), 0)
        if score:
            item = award_item(name="积分", count=score, resource_type="score")
            return f"积分+{score}", [item]
        return "签到奖励已发放", []
    return None, []


def _today_task_score_summary(creds: ExiliumCredentials) -> tuple[int, int]:
    """今日「任务」积分条目数与总分（浏览/点赞/分享完成后各记一条）。"""
    from app.core.timeutil import today as beijing_today

    try:
        data = list_score_logs(creds, page=1, page_size=30)
    except ExiliumApiError:
        return 0, 0
    day = beijing_today().isoformat()
    count = 0
    total = 0
    for row in data.get("list") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("reason") or "").strip() != "任务":
            continue
        if not str(row.get("log_time") or "").startswith(day):
            continue
        count += 1
        total += _to_int(row.get("score"), 0)
    return count, total


def _tasks_extra_text(*, view: int, like: int, share: int, score: int | None = None) -> str:
    parts = [f"浏览 {view}/3", f"点赞 {like}/3", f"分享 {share}/1"]
    text = "每日任务：" + " · ".join(parts)
    if score and score > 0:
        text += f"（积分+{score}）"
    return text


def list_topic_ids(
    creds: ExiliumCredentials,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """拉取帖子列表（含 topic_id / is_like）。"""
    data = _http(
        "GET",
        "/community/topic/list?sort_type=2",
        token=creds.token,
    )
    raw = data.get("list") if isinstance(data.get("list"), list) else []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        tid = _to_int(row.get("topic_id"), 0)
        if tid <= 0:
            continue
        out.append(
            {
                "topic_id": tid,
                "is_like": bool(row.get("is_like")),
            }
        )
        if len(out) >= max(1, limit):
            break
    return out


def view_topic(creds: ExiliumCredentials, topic_id: int) -> None:
    tid = int(topic_id)
    _http("GET", f"/community/topic/{tid}?id={tid}", token=creds.token)


def like_topic(creds: ExiliumCredentials, topic_id: int) -> None:
    tid = int(topic_id)
    _http("GET", f"/community/topic/like/{tid}?id={tid}", token=creds.token)


def share_topic(creds: ExiliumCredentials, topic_id: int) -> None:
    tid = int(topic_id)
    _http("GET", f"/community/topic/share/{tid}?id={tid}", token=creds.token)


def complete_daily_tasks(creds: ExiliumCredentials) -> dict[str, Any]:
    """完成每日任务：浏览×3、点赞×3、分享×1。"""
    import time

    before_count, before_score = _today_task_score_summary(creds)
    if before_count >= 3:
        return {
            "view": 3,
            "like": 3,
            "share": 1,
            "score": before_score,
            "skipped": True,
            "text": _tasks_extra_text(view=3, like=3, share=1, score=before_score),
        }

    topics = list_topic_ids(creds, limit=5)
    if len(topics) < 3:
        raise ExiliumApiError("帖子列表不足，无法完成每日任务")

    view_n = 0
    like_n = 0
    share_n = 0
    errors: list[str] = []

    for item in topics[:3]:
        tid = int(item["topic_id"])
        try:
            view_topic(creds, tid)
            view_n += 1
        except ExiliumApiError as exc:
            errors.append(f"浏览失败:{exc.message}")
        time.sleep(0.35)

    for item in topics[:3]:
        tid = int(item["topic_id"])
        try:
            # 已点赞则跳过，避免 toggle 取消
            if not item.get("is_like"):
                like_topic(creds, tid)
            like_n += 1
        except ExiliumApiError as exc:
            errors.append(f"点赞失败:{exc.message}")
        time.sleep(0.35)

    try:
        share_topic(creds, int(topics[0]["topic_id"]))
        share_n = 1
    except ExiliumApiError as exc:
        errors.append(f"分享失败:{exc.message}")

    after_count, after_score = _today_task_score_summary(creds)
    gained = max(0, after_score - before_score)
    text = _tasks_extra_text(
        view=view_n,
        like=like_n,
        share=share_n,
        score=after_score if after_count else gained,
    )
    if errors:
        text += "（部分失败）"
    return {
        "view": view_n,
        "like": like_n,
        "share": share_n,
        "score": after_score,
        "gained": gained,
        "skipped": False,
        "text": text,
        "errors": errors,
    }


def _attach_daily_tasks(creds: ExiliumCredentials, result: CheckinResult) -> CheckinResult:
    """在签到结果上附加每日任务执行情况。"""
    if result.status == "error":
        return result
    try:
        tasks = complete_daily_tasks(creds)
        result.extra_text = str(tasks.get("text") or "") or None
    except ExiliumApiError as exc:
        result.extra_text = f"每日任务失败：{exc.message}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("exilium daily tasks failed")
        result.extra_text = f"每日任务失败：{exc}"
    return result


def _tasks_extra_from_score_log(creds: ExiliumCredentials) -> str | None:
    count, score = _today_task_score_summary(creds)
    if count <= 0:
        return "每日任务：未完成（点击立即签到可一并完成）"
    if count >= 3:
        return _tasks_extra_text(view=3, like=3, share=1, score=score)
    return f"每日任务：已领 {count}/3 项（积分+{score}）"


def _already_result(creds: ExiliumCredentials) -> CheckinResult:
    role_name = creds.nickname or mask_account(creds.account_name) or "社区账号"
    awards_text, awards_items = _awards_from_score_log(creds)
    return CheckinResult(
        game_code=GAME_CODE,
        game_name=GAME_NAME,
        role_uid=creds.user_id or creds.account_name or "-",
        role_name=role_name,
        channel_name="社区",
        status="already",
        message="今日已签到" + (f"：{awards_text}" if awards_text else ""),
        awards_text=awards_text,
        awards=awards_items or None,
    )


def query_today(creds: ExiliumCredentials) -> tuple[ExiliumCredentials, list[CheckinResult]]:
    working = ensure_session(creds)
    signed = get_sign_in_status(working)
    if signed:
        result = _already_result(working)
        result.extra_text = _tasks_extra_from_score_log(working)
        return working, [result]
    role_name = working.nickname or mask_account(working.account_name) or "社区账号"
    result = CheckinResult(
        game_code=GAME_CODE,
        game_name=GAME_NAME,
        role_uid=working.user_id or working.account_name or "-",
        role_name=role_name,
        channel_name="社区",
        status="pending",
        message="今日未签到",
        extra_text=_tasks_extra_from_score_log(working),
    )
    return working, [result]


def checkin(
    creds: ExiliumCredentials, *, force: bool = False
) -> tuple[ExiliumCredentials, list[CheckinResult]]:
    _ = force
    working = ensure_session(creds)
    signed = get_sign_in_status(working)
    if signed:
        result = _already_result(working)
    else:
        try:
            result = sign_in(working)
        except ExiliumApiError as exc:
            msg = exc.message or ""
            already = any(k in msg for k in ("已签到", "重复", "already", "签到过"))
            if already:
                result = _already_result(working)
            else:
                role_name = working.nickname or mask_account(working.account_name) or "社区账号"
                result = CheckinResult(
                    game_code=GAME_CODE,
                    game_name=GAME_NAME,
                    role_uid=working.user_id or working.account_name or "-",
                    role_name=role_name,
                    channel_name="社区",
                    status="error",
                    message=friendly_error_message(msg),
                )
                return working, [result]
    return working, [_attach_daily_tasks(working, result)]
