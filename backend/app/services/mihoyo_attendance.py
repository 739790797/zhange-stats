"""米游社讨论区签到、米游币任务与游戏福利签到。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.services.checkin_common import (
    CheckinResult,
    award_item,
    format_upstream_request,
    format_upstream_response,
)
from app.services.checkin_role_prefs import RoleKey, matches_role_filter
from app.services.mihoyo_client import (
    BBS_API,
    BBS_FORUMS,
    GAME_BIZ_META,
    MihoyoApiError,
    MihoyoCredentials,
    TAKUMI_API,
    _assert_ok,
    _bbs_headers,
    _game_headers,
    _http_json,
    _normalize_creds,
    ensure_session,
    friendly_error_message,
    generate_ds_sign,
    generate_ds_x6,
    list_bbs_business_ids,
    list_game_roles,
    mask_account,
)

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


def _bbs_uid(creds: MihoyoCredentials) -> str:
    return creds.stuid or creds.ltuid or creds.account_id or "-"


def _welfare_info_url(meta: dict[str, str], region: str, uid: str) -> str:
    act_id = meta["act_id"]
    if meta["sign_kind"] == "bbs_sign":
        return (
            f"{TAKUMI_API}/event/bbs_sign_reward/info"
            f"?act_id={act_id}&region={region}&uid={uid}"
        )
    return (
        f"{TAKUMI_API}/event/luna/info?lang=zh-cn&act_id={act_id}&region={region}&uid={uid}"
    )


def _welfare_sign_url(meta: dict[str, str]) -> str:
    if meta["sign_kind"] == "bbs_sign":
        return f"{TAKUMI_API}/event/bbs_sign_reward/sign"
    return f"{TAKUMI_API}/event/luna/sign"


def _welfare_referer(meta: dict[str, str]) -> str:
    act_id = meta["act_id"]
    if meta["game_code"] == "genshin":
        return (
            "https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html"
            f"?bbs_auth_required=true&act_id={act_id}&utm_source=bbs&utm_medium=mys&utm_campaign=icon"
        )
    if meta["game_code"] == "bh3":
        return (
            "https://webstatic.mihoyo.com/bbs/event/signin/bh3/index.html"
            f"?bbs_auth_required=true&act_id={act_id}&bbs_presentation_style=fullscreen"
        )
    return "https://webstatic.mihoyo.com/"


def _game_sign_body(meta: dict[str, str], region: str, uid: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "act_id": meta["act_id"],
        "region": region,
        "uid": uid,
    }
    if meta["sign_kind"] == "bbs_sign":
        return body
    body["lang"] = "zh-cn"
    return body


def _parse_awards_from_info(data: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    awards = data.get("awards") if isinstance(data.get("awards"), list) else []
    items: list[dict[str, Any]] = []
    parts: list[str] = []
    for row in awards:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("cnt") or "").strip()
        if not name:
            continue
        try:
            count = int(row.get("count") or row.get("cnt") or 1)
        except (TypeError, ValueError):
            count = 1
        items.append(award_item(name=name, count=count))
        parts.append(f"{name}×{count}")
    text = " · ".join(parts) if parts else None
    return text, items


def _query_game_signed(
    creds: MihoyoCredentials, meta: dict[str, str], region: str, uid: str
) -> tuple[bool, str | None, list[dict[str, Any]]]:
    url = _welfare_info_url(meta, region, uid)
    payload = _http_json("GET", url, headers=_game_headers(creds, referer=_welfare_referer(meta)))
    data = _assert_ok(payload)
    signed = bool(data.get("is_sign") or data.get("is_signed"))
    awards_text, awards = _parse_awards_from_info(data)
    return signed, awards_text, awards


def _sign_game_role(creds: MihoyoCredentials, role: Any) -> CheckinResult:
    meta = GAME_BIZ_META[role.game_biz]
    signed, awards_text, awards = _query_game_signed(
        creds, meta, role.region, role.role_uid
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
        headers=_game_headers(creds, referer=_welfare_referer(meta)),
        json_body=body,
    )
    message = str(payload.get("message") or "")
    if "已签到" in message or "签到过" in message:
        signed, awards_text, awards = _query_game_signed(
            creds, meta, role.region, role.role_uid
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
        creds, meta, role.region, role.role_uid
    )
    status = "ok" if signed else "ok"
    return CheckinResult(
        game_code=role.game_code,
        game_name=role.game_name,
        role_uid=role.role_uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        status=status,
        message="签到成功" + (f"：{awards_text}" if awards_text else ""),
        awards_text=awards_text,
        awards=awards or None,
        upstream_request=format_upstream_request("POST", sign_url, body),
        upstream_response=format_upstream_response(payload),
    )


def _bbs_forum_signed_today(creds: MihoyoCredentials, gid: str) -> bool:
    url = f"{BBS_API}/apihub/app/api/signInInfo"
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
    url = f"{BBS_API}/apihub/app/api/signIn"
    body = {"gids": gid}
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    payload = _http_json(
        "POST",
        url,
        headers=_bbs_headers(creds, ds=generate_ds_x6(body=body_str)),
        json_body=body,
    )
    message = str(payload.get("message") or "")
    points = None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if data:
        try:
            points = int(data.get("points") or 0)
        except (TypeError, ValueError):
            points = None
    if payload.get("retcode") not in (0, "0", None) and "已签到" not in message:
        raise MihoyoApiError(message or "讨论区签到失败")
    return message, points


def _mission_states(creds: MihoyoCredentials) -> dict[str, int]:
    url = f"{BBS_API}/apihub/api/getUserMissionsState"
    payload = _http_json(
        "GET",
        url,
        headers=_game_headers(creds),
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


def _fetch_post_ids(creds: MihoyoCredentials, forum_id: str, *, limit: int = 12) -> list[str]:
    url = f"{BBS_API}/post/api/getForumPostList"
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
    url = f"{BBS_API}/post/api/getPostFull"
    _http_json("GET", url, headers=_bbs_headers(creds), params={"post_id": post_id})


def _upvote_post(creds: MihoyoCredentials, post_id: str) -> None:
    url = f"{BBS_API}/apihub/sapi/upvotePost"
    _http_json(
        "POST",
        url,
        headers=_bbs_headers(creds),
        json_body={"post_id": post_id, "is_cancel": False},
    )


def _share_post(creds: MihoyoCredentials, post_id: str) -> None:
    url = f"{BBS_API}/apihub/api/getShareConf"
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
    businesses = set(list_bbs_business_ids(creds))
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
            messages.append(f"{forum['name']}失败：{exc.message}")
        time.sleep(0.3)
    return signed_points, messages


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
            businesses = set(list_bbs_business_ids(creds))
        except MihoyoApiError:
            businesses = set()
        unsigned: list[str] = []
        for forum in BBS_FORUMS:
            gid = forum["gid"]
            if businesses and gid not in businesses:
                continue
            try:
                if not _bbs_forum_signed_today(creds, forum["gid"]):
                    unsigned.append(forum["name"])
            except MihoyoApiError:
                unsigned.append(forum["name"])
        if unsigned:
            status = "pending"
            message = f"讨论区未签：{'、'.join(unsigned[:4])}"
        else:
            status = "already"
            message = "讨论区今日已签到"
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
    # 状态查询不跑米游币任务；社区接口失败也不要把整次 status 打成 token 失效
    try:
        results.append(
            _community_result(working, do_sign=False, attach_tasks=False)
        )
    except MihoyoApiError as exc:
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
        # 游戏角色列表失败：保留社区结果，向上抛出让调用方感知 token 问题
        # 但若社区已成功，仅记录空角色即可
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
