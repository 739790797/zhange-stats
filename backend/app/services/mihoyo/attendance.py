"""米游社讨论区签到、米游币任务与游戏福利签到。"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.services.checkin.common import (
    CheckinResult,
    award_item,
    format_upstream_request,
    format_upstream_response,
)
from app.services.checkin.role_prefs import RoleKey, matches_role_filter
from app.services.mihoyo.calendar import (
    award_from_mihoyo_row,
    select_today_awards,
)
from app.services.mihoyo.client import (
    BBS_FORUMS,
    GAME_BIZ_META,
    MihoyoApiError,
    MihoyoCredentials,
    _assert_ok,
    _bbs_headers,
    _game_headers_for_meta,
    _http_json,
    _mission_headers,
    call_with_cookie_refresh,
    compact_json_body,
    ensure_session,
    friendly_error_message,
    generate_ds_x6,
    is_auth_failure,
    list_bbs_business_ids,
    list_game_roles,
    mask_account,
)
from app.services.mihoyo_bbs import setting as bbs_setting

logger = logging.getLogger(__name__)

GAME_CODE = "mihoyo"
GAME_NAME = "米游社"

_RESULT_ORDER = {
    "mihoyo": 0,
    "genshin": 1,
    "bh3": 2,
    "starrail": 3,
    "zzz": 4,
    "bh2": 5,
}


def sort_mihoyo_results(results: list[CheckinResult]) -> list[CheckinResult]:
    return sorted(
        results,
        key=lambda r: (
            _RESULT_ORDER.get(str(r.game_code), 99),
            str(r.role_uid),
        ),
    )


def _role_label(creds: MihoyoCredentials) -> str:
    return creds.nickname or mask_account(creds.stuid or creds.ltuid) or "米游社账号"


def _reraise_auth(exc: MihoyoApiError) -> None:
    if is_auth_failure(code=exc.code, message=exc.message):
        raise exc


def _bbs_uid(creds: MihoyoCredentials) -> str:
    return creds.stuid or creds.ltuid or creds.account_id or "-"


def _welfare_info_url(meta: dict[str, str]) -> str:
    if meta.get("sign_kind") == "luna_zzz":
        return bbs_setting.zzz_game_is_signurl
    return bbs_setting.cn_game_is_signurl


def _welfare_home_url(meta: dict[str, str]) -> str:
    if meta.get("sign_kind") == "luna_zzz":
        return bbs_setting.zzz_game_checkin_rewards
    return bbs_setting.cn_game_checkin_rewards


def _welfare_sign_url(meta: dict[str, str]) -> str:
    if meta.get("sign_kind") == "luna_zzz":
        return bbs_setting.zzz_game_sign_url
    return bbs_setting.cn_game_sign_url


def _welfare_params(meta: dict[str, str], region: str = "", uid: str = "") -> dict[str, str]:
    params: dict[str, str] = {"act_id": meta["act_id"]}
    if region:
        params["region"] = region
    if uid:
        params["uid"] = uid
    return params


def _game_sign_body(meta: dict[str, str], region: str, uid: str) -> dict[str, Any]:
    # MihoyoBBSTools GameCheckin.check_in：仅 act_id / region / uid
    return {
        "act_id": meta["act_id"],
        "region": region,
        "uid": uid,
    }


def _parse_awards_from_info(data: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    awards = data.get("awards") if isinstance(data.get("awards"), list) else []
    try:
        total = int(data.get("total_sign_day") or 0)
    except (TypeError, ValueError):
        total = 0
    signed = bool(data.get("is_sign") or data.get("is_signed"))
    today_raw = data.get("today")
    today_index = None
    if isinstance(today_raw, int) and today_raw > 0:
        today_index = today_raw - 1
    elif isinstance(today_raw, str) and today_raw.strip().isdigit():
        today_index = int(today_raw.strip()) - 1
    items = select_today_awards(
        awards, signed=signed, total_sign_day=total, today_index=today_index
    )
    if not items:
        for row in awards:
            item = award_from_mihoyo_row(row)
            if item:
                items.append(item)
                if len(items) >= 3:
                    break
    parts = [f"{a['name']}×{a.get('count') or 1}" for a in items]
    text = " · ".join(parts) if parts else None
    return text, items


def _query_game_signed(
    creds: MihoyoCredentials, meta: dict[str, str], region: str, uid: str
) -> tuple[bool, str | None, list[dict[str, Any]]]:
    def _do(working: MihoyoCredentials) -> tuple[bool, str | None, list[dict[str, Any]]]:
        url = _welfare_info_url(meta)
        payload = _http_json(
            "GET",
            url,
            headers=_game_headers_for_meta(working, meta),
            params=_welfare_params(meta, region, uid),
        )
        data = _assert_ok(payload)
        signed = bool(data.get("is_sign") or data.get("is_signed"))
        awards_text, awards = _parse_awards_from_info(data)
        return signed, awards_text, awards

    return call_with_cookie_refresh(creds, _do)


def _sign_game_role(creds: MihoyoCredentials, role: Any) -> CheckinResult:
    meta = GAME_BIZ_META[role.game_biz]

    def _do(working: MihoyoCredentials) -> CheckinResult:
        signed, awards_text, awards = _query_game_signed(
            working, meta, role.region, role.role_uid
        )
        if signed:
            return CheckinResult(
                game_code=role.game_code,
                game_name=role.game_name,
                role_uid=role.role_uid,
                role_name=role.role_name,
                channel_name=role.channel_name,
                status="already",
                message="今日已签到" + (f"：{awards_text}" if awards_text else ""),
                awards_text=awards_text,
                awards=awards or None,
            )
        sign_url = _welfare_sign_url(meta)
        body = _game_sign_body(meta, role.region, role.role_uid)
        payload = _http_json(
            "POST",
            sign_url,
            headers=_game_headers_for_meta(working, meta),
            json_body=body,
        )
        message = str(payload.get("message") or "")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if payload.get("retcode") in (0, "0") and data.get("success") in (1, "1"):
            raise MihoyoApiError("签到触发人机验证，请稍后在米游社 App 内完成一次签到")
        if (
            payload.get("retcode") in (-5003, "-5003")
            or "已签到" in message
            or "签到过" in message
        ):
            signed, awards_text, awards = _query_game_signed(
                working, meta, role.region, role.role_uid
            )
            return CheckinResult(
                game_code=role.game_code,
                game_name=role.game_name,
                role_uid=role.role_uid,
                role_name=role.role_name,
                channel_name=role.channel_name,
                status="already",
                message="今日已签到" + (f"：{awards_text}" if awards_text else ""),
                awards_text=awards_text,
                awards=awards or None,
                upstream_request=format_upstream_request("POST", sign_url, body),
                upstream_response=format_upstream_response(payload),
            )
        _assert_ok(payload)
        signed, awards_text, awards = _query_game_signed(
            working, meta, role.region, role.role_uid
        )
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.role_uid,
            role_name=role.role_name,
            channel_name=role.channel_name,
            status="ok",
            message="签到成功" + (f"：{awards_text}" if awards_text else ""),
            awards_text=awards_text,
            awards=awards or None,
            upstream_request=format_upstream_request("POST", sign_url, body),
            upstream_response=format_upstream_response(payload),
        )

    return call_with_cookie_refresh(creds, _do)


def _bbs_forum_signed_today(creds: MihoyoCredentials, gid: str) -> bool:
    url = bbs_setting.bbs_sign_info_url
    query = f"gids={gid}"
    payload = _http_json(
        "GET",
        url,
        headers=_bbs_headers(creds, ds=generate_ds_x6(query=query)),
        params={"gids": gid},
    )
    data = _assert_ok(payload)
    return bool(data.get("is_sign"))


def _bbs_forum_sign(creds: MihoyoCredentials, forum: dict[str, str]) -> tuple[str, int | None]:
    gid = forum["gid"]
    url = bbs_setting.bbs_sign_url
    body = {"gids": gid}
    body_str = compact_json_body(body)
    payload = _http_json(
        "POST",
        url,
        headers=_bbs_headers(creds, ds=generate_ds_x6(body=body_str)),
        raw_body=body_str,
    )
    message = str(payload.get("message") or "")
    points = None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if data:
        try:
            points = int(data.get("points") or 0)
        except (TypeError, ValueError):
            points = None
    retcode = payload.get("retcode")
    if retcode not in (0, "0", None) and "已签到" not in message:
        code_i = None
        try:
            if retcode is not None and retcode != "":
                code_i = int(retcode)
        except (TypeError, ValueError):
            code_i = None
        raise MihoyoApiError(
            friendly_error_message(message or "讨论区签到失败"),
            code=code_i,
            data=payload,
        )
    return message, points


def _mission_states(creds: MihoyoCredentials) -> dict[str, int]:
    def _do(working: MihoyoCredentials) -> dict[str, int]:
        url = bbs_setting.bbs_tasks_list
        payload = _http_json(
            "GET",
            url,
            headers=_mission_headers(working),
            params={"point_sn": "myb"},
        )
        data = _assert_ok(payload)
        rows = data.get("states") if isinstance(data.get("states"), list) else []
        out: dict[str, int] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("mission_key") or "")
            try:
                out[key] = int(row.get("happened_times") or 0)
            except (TypeError, ValueError):
                out[key] = 0
        return out

    return call_with_cookie_refresh(creds, _do)


def _fetch_post_ids(creds: MihoyoCredentials, forum_id: str, *, limit: int = 12) -> list[str]:
    url = bbs_setting.bbs_post_list_url
    payload = _http_json(
        "GET",
        url,
        headers=_bbs_headers(creds),
        params={
            "forum_id": forum_id,
            "is_good": "false",
            "is_hot": "false",
            "page_size": str(limit),
            "sort_type": "1",
        },
    )
    data = _assert_ok(payload)
    rows = data.get("list") if isinstance(data.get("list"), list) else []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        post = row.get("post") if isinstance(row.get("post"), dict) else row
        pid = str(post.get("post_id") or "").strip()
        if pid:
            out.append(pid)
    return out


def _view_post(creds: MihoyoCredentials, post_id: str) -> None:
    url = bbs_setting.bbs_detail_url
    _http_json("GET", url, headers=_bbs_headers(creds), params={"post_id": post_id})


def _upvote_post(creds: MihoyoCredentials, post_id: str) -> None:
    url = bbs_setting.bbs_like_url
    _http_json(
        "POST",
        url,
        headers=_bbs_headers(creds),
        json_body={"post_id": post_id, "is_cancel": False},
    )


def _share_post(creds: MihoyoCredentials, post_id: str) -> None:
    url = bbs_setting.bbs_share_url
    _http_json(
        "GET",
        url,
        headers=_bbs_headers(creds),
        params={"entity_id": post_id, "entity_type": "1"},
    )


def complete_myb_missions(creds: MihoyoCredentials) -> str:
    """浏览 3 / 点赞 5 / 分享 1。"""
    states = _mission_states(creds)
    view_done = int(states.get("view_post_0") or 0)
    like_done = int(states.get("post_up_0") or 0)
    share_done = int(states.get("share_post_0") or 0)
    if view_done >= 3 and like_done >= 5 and share_done >= 1:
        return "米游币任务：已完成"

    posts = _fetch_post_ids(creds, "26")
    if len(posts) < 3:
        return "米游币任务：帖子不足，跳过"

    view_n = view_done
    for pid in posts[: max(0, 3 - view_done)]:
        try:
            _view_post(creds, pid)
            view_n += 1
        except MihoyoApiError:
            pass
        time.sleep(0.35)

    like_n = like_done
    for pid in posts[: max(0, 5 - like_done)]:
        try:
            _upvote_post(creds, pid)
            like_n += 1
        except MihoyoApiError:
            pass
        time.sleep(0.35)

    share_n = share_done
    if share_done < 1 and posts:
        try:
            _share_post(creds, posts[0])
            share_n = 1
        except MihoyoApiError:
            pass

    return (
        f"米游币任务：浏览 {min(view_n, 3)}/3 · 点赞 {min(like_n, 5)}/5 · "
        f"分享 {min(share_n, 1)}/1"
    )


def _bbs_sign_all(creds: MihoyoCredentials) -> tuple[int, list[str]]:
    try:
        businesses = set(list_bbs_business_ids(creds))
    except MihoyoApiError as exc:
        logger.warning("mihoyo list_bbs_business_ids skipped: %s", exc.message)
        businesses = set()
    signed_points = 0
    messages: list[str] = []
    for forum in BBS_FORUMS:
        gid = forum["gid"]
        if businesses and gid not in businesses:
            continue
        try:
            if _bbs_forum_signed_today(creds, gid):
                messages.append(f"{forum['name']}已签")
                continue
            msg, points = _bbs_forum_sign(creds, forum)
            if points:
                signed_points += points
            messages.append(f"{forum['name']}：{msg}")
        except MihoyoApiError as exc:
            _reraise_auth(exc)
            messages.append(f"{forum['name']}失败：{exc.message}")
        time.sleep(0.3)
    return signed_points, messages


def _community_signed_from_missions(creds: MihoyoCredentials) -> bool | None:
    """对齐 MihoyoBBSTools get_tasks_list：用 web Cookie 看讨论区签到任务。

    返回 True/False；解析不了时返回 None。
    """
    def _do(working: MihoyoCredentials) -> bool | None:
        payload = _http_json(
            "GET",
            bbs_setting.bbs_tasks_list,
            headers=_mission_headers(working),
            params={"point_sn": "myb"},
        )
        data = _assert_ok(payload)
        try:
            can_get = int(data.get("can_get_points") or 0)
        except (TypeError, ValueError):
            can_get = -1
        if can_get == 0:
            return True
        rows = data.get("states") if isinstance(data.get("states"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                mission_id = int(row.get("mission_id") or 0)
            except (TypeError, ValueError):
                mission_id = 0
            if mission_id == 58:
                return bool(row.get("is_get_award"))
        return False

    return call_with_cookie_refresh(creds, _do)


def _community_result(
    creds: MihoyoCredentials,
    *,
    do_sign: bool,
    attach_tasks: bool,
) -> CheckinResult:
    uid = _bbs_uid(creds)
    role_name = _role_label(creds)
    points_total = 0
    detail_parts: list[str] = []
    if do_sign:
        points_total, detail_parts = _bbs_sign_all(creds)
    else:
        try:
            signed = _community_signed_from_missions(creds)
        except MihoyoApiError as exc:
            _reraise_auth(exc)
            signed = None
        if signed is True:
            status = "already"
            message = "讨论区今日已签到"
        elif signed is False:
            status = "pending"
            message = "讨论区未签到"
        else:
            status = "pending"
            message = "讨论区签到状态未知"
    extra = None
    if attach_tasks:
        try:
            extra = complete_myb_missions(creds)
        except MihoyoApiError as exc:
            extra = f"米游币任务失败：{exc.message}"
    if do_sign:
        awards_text = f"米游币+{points_total}" if points_total else None
        awards = (
            [award_item(name="米游币", count=points_total, resource_type="points")]
            if points_total
            else None
        )
        return CheckinResult(
            game_code=GAME_CODE,
            game_name=GAME_NAME,
            role_uid=uid,
            role_name=role_name,
            channel_name="社区",
            status="ok",
            message="讨论区签到完成" + (f"（{'；'.join(detail_parts[:3])}）" if detail_parts else ""),
            awards_text=awards_text,
            awards=awards,
            extra_text=extra,
        )
    result = CheckinResult(
        game_code=GAME_CODE,
        game_name=GAME_NAME,
        role_uid=uid,
        role_name=role_name,
        channel_name="社区",
        status=status,
        message=message,
        extra_text=extra,
    )
    return result


def query_today_all(
    creds: MihoyoCredentials,
) -> tuple[MihoyoCredentials, list[CheckinResult]]:
    working = ensure_session(creds)
    results: list[CheckinResult] = []
    # 状态查询不跑米游币任务；社区失败（含鉴权）不把整次 status 打成 token 失效
    try:
        results.append(
            _community_result(working, do_sign=False, attach_tasks=False)
        )
    except MihoyoApiError as exc:
        # 社区鉴权失败记一行失败，不把整次 status 打成 token 失效
        # （角色列表 / 游戏福利仍可能可用；扫码重绑后尤甚）
        results.append(
            CheckinResult(
                game_code=GAME_CODE,
                game_name=GAME_NAME,
                role_uid=_bbs_uid(working),
                role_name=_role_label(working),
                channel_name="社区",
                status="error",
                message=friendly_error_message(exc.message),
            )
        )
    try:
        roles = list_game_roles(working)
    except MihoyoApiError as exc:
        # 游戏角色也拉不到且社区已失败 → 才视为整号 token 失效
        if not results or results[0].status == "error":
            raise
        logger.warning("mihoyo list_game_roles failed: %s", exc.message)
        roles = []
    for role in roles:
        try:
            meta = GAME_BIZ_META[role.game_biz]
            signed, awards_text, awards = _query_game_signed(
                working, meta, role.region, role.role_uid
            )
            if signed:
                results.append(
                    CheckinResult(
                        game_code=role.game_code,
                        game_name=role.game_name,
                        role_uid=role.role_uid,
                        role_name=role.role_name,
                        channel_name=role.channel_name,
                        status="already",
                        message="今日已签到" + (f"：{awards_text}" if awards_text else ""),
                        awards_text=awards_text,
                        awards=awards or None,
                    )
                )
            else:
                results.append(
                    CheckinResult(
                        game_code=role.game_code,
                        game_name=role.game_name,
                        role_uid=role.role_uid,
                        role_name=role.role_name,
                        channel_name=role.channel_name,
                        status="pending",
                        message="今日未签到",
                    )
                )
        except MihoyoApiError as exc:
            results.append(
                CheckinResult(
                    game_code=role.game_code,
                    game_name=role.game_name,
                    role_uid=role.role_uid,
                    role_name=role.role_name,
                    channel_name=role.channel_name,
                    status="error",
                    message=friendly_error_message(exc.message),
                )
            )
    return working, sort_mihoyo_results(results)


def run_all_checkins(
    creds: MihoyoCredentials,
    *,
    role_keys: set[RoleKey] | None = None,
) -> tuple[MihoyoCredentials, list[CheckinResult]]:
    working = ensure_session(creds)
    results: list[CheckinResult] = []

    community_key = (GAME_CODE, _bbs_uid(working))
    if matches_role_filter(GAME_CODE, community_key[1], role_keys):
        try:
            results.append(_community_result(working, do_sign=True, attach_tasks=True))
        except MihoyoApiError as exc:
            results.append(
                CheckinResult(
                    game_code=GAME_CODE,
                    game_name=GAME_NAME,
                    role_uid=community_key[1],
                    role_name=_role_label(working),
                    channel_name="社区",
                    status="error",
                    message=friendly_error_message(exc.message),
                )
            )

    for role in list_game_roles(working):
        if not matches_role_filter(role.game_code, role.role_uid, role_keys):
            continue
        try:
            results.append(_sign_game_role(working, role))
        except MihoyoApiError as exc:
            results.append(
                CheckinResult(
                    game_code=role.game_code,
                    game_name=role.game_name,
                    role_uid=role.role_uid,
                    role_name=role.role_name,
                    channel_name=role.channel_name,
                    status="error",
                    message=friendly_error_message(exc.message),
                )
            )
        time.sleep(0.25)

    return working, sort_mihoyo_results(results)


CALENDAR_GAME_CODES = frozenset(m["game_code"] for m in GAME_BIZ_META.values())


def fetch_game_attendance_bundle(creds: MihoyoCredentials, role: Any) -> dict[str, Any]:
    """福利签到 info + home，落库存原始 data。"""
    meta = GAME_BIZ_META[role.game_biz]

    def _do(working: MihoyoCredentials) -> dict[str, Any]:
        headers = _game_headers_for_meta(working, meta)
        info_url = _welfare_info_url(meta)
        home_url = _welfare_home_url(meta)
        info = _assert_ok(
            _http_json(
                "GET",
                info_url,
                headers=headers,
                params=_welfare_params(meta, role.region, role.role_uid),
            )
        )
        home = _assert_ok(
            _http_json(
                "GET",
                home_url,
                headers=headers,
                params=_welfare_params(meta, role.region, role.role_uid),
            )
        )
        return {
            "info": info,
            "home": home,
            "game_biz": role.game_biz,
            "game_code": role.game_code,
            "game_name": role.game_name,
            "sign_kind": meta["sign_kind"],
        }

    return call_with_cookie_refresh(creds, _do)
