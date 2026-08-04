"""森空岛 / 鹰角通行证 HTTP 客户端（urllib，带请求签名）。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.services.checkin_common import CheckinResult

logger = logging.getLogger(__name__)

APP_CODE = "4ca99fa6b56cc2ba"
GRANT_URL = "https://as.hypergryph.com/user/oauth2/v2/grant"
CRED_URL = "https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code"
BINDING_URL = "https://zonai.skland.com/api/v1/game/player/binding"
PLAYER_INFO_URL = "https://zonai.skland.com/api/v1/game/player/info"
ARKNIGHTS_ATTENDANCE_URL = "https://zonai.skland.com/api/v1/game/attendance"
CHAR_AVATAR_CDN = (
    "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/avatar"
)
PROFESSION_CN = {
    "PIONEER": "先锋",
    "WARRIOR": "近卫",
    "TANK": "重装",
    "SNIPER": "狙击",
    "CASTER": "术师",
    "MEDIC": "医疗",
    "SUPPORT": "辅助",
    "SPECIAL": "特种",
}
ENDFIELD_ATTENDANCE_URL = "https://zonai.skland.com/api/v1/game/endfield/attendance"
# App「领取记录」：按真实领取时间戳查询，勿用 calendar 下标（calendar 是本月第 N 次）
ENDFIELD_ATTENDANCE_RECORD_URL = (
    "https://zonai.skland.com/api/v1/game/endfield/attendance/record"
)
ENDFIELD_CARD_DETAIL_URL = "https://zonai.skland.com/api/v1/game/endfield/card/detail"
SCAN_LOGIN_URL = "https://as.hypergryph.com/general/v1/gen_scan/login"
SCAN_STATUS_URL = "https://as.hypergryph.com/general/v1/scan_status"
TOKEN_BY_SCAN_URL = "https://as.hypergryph.com/user/auth/v1/token_by_scan_code"
SEND_PHONE_CODE_URL = "https://as.hypergryph.com/general/v1/send_phone_code"
TOKEN_BY_PHONE_CODE_URL = "https://as.hypergryph.com/user/auth/v2/token_by_phone_code"
TOKEN_BY_PHONE_PASSWORD_URL = (
    "https://as.hypergryph.com/user/auth/v1/token_by_phone_password"
)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1"
)
USER_AGENT_API = (
    "Skland/1.0.1 (com.hypergryph.skland; build:100001014; Android 31; ) Okhttp/4.11.0"
)
PLATFORM = "3"
VNAME = "1.0.0"
REQUEST_TIMEOUT = 20

GAME_ARKNIGHTS = "arknights"
GAME_ENDFIELD = "endfield"

GAME_META = {
    GAME_ARKNIGHTS: {
        "name": "明日方舟",
        "app_code": "arknights",
        "attendance_url": ARKNIGHTS_ATTENDANCE_URL,
    },
    GAME_ENDFIELD: {
        "name": "明日方舟：终末地",
        "app_code": "endfield",
        "attendance_url": ENDFIELD_ATTENDANCE_URL,
    },
}


class SklandApiError(Exception):
    def __init__(self, message: str, *, code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class SklandSession:
    cred: str
    sign_token: str


@dataclass
class SklandRole:
    game_code: str
    game_name: str
    uid: str
    role_name: str
    channel_name: str
    channel_master_id: str | None = None
    role_id: str | None = None
    server_id: str | None = None


@dataclass
class EndfieldEquip:
    slot: str
    item_id: str
    name: str
    icon_url: str | None
    rarity: int
    level: int | None = None
    refine_level: int | None = None  # 精锻；上游多为 equipData.level


@dataclass
class EndfieldSkill:
    skill_id: str
    name: str
    skill_type: str
    type_label: str
    icon_url: str | None
    level: int
    max_level: int


@dataclass
class EndfieldWeapon:
    weapon_id: str
    name: str
    icon_url: str | None
    rarity: int
    level: int
    refine_level: int = 0
    breakthrough_level: int = 0
    weapon_type: str = ""
    gem_id: str = ""
    gem_name: str = ""
    gem_icon_url: str | None = None


@dataclass
class EndfieldChar:
    char_id: str
    name: str
    rarity: int
    level: int
    evolve_phase: int
    potential_level: int
    profession: str
    property_name: str
    weapon_type: str
    label_type: str
    own_ts: int | None
    gender: str
    avatar_url: str | None
    illustration_url: str | None
    property_icon_url: str | None
    weapon: EndfieldWeapon | None
    skills: list[EndfieldSkill]
    equips: list[EndfieldEquip]


@dataclass
class EndfieldBox:
    uid: str
    role_id: str
    server_id: str
    name: str
    level: int
    server_name: str
    avatar_url: str | None
    char_count: int
    chars: list[EndfieldChar]


@dataclass
class ArknightsSkill:
    skill_id: str
    specialize_level: int  # 0-3
    label: str  # 展示用，如 技能1 Lv.7 / 技能2 专精三


@dataclass
class ArknightsEquip:
    equip_id: str
    name: str
    level: int
    type_icon: str
    locked: bool


@dataclass
class ArknightsChar:
    char_id: str
    name: str
    rarity: int  # 星级 1-6
    profession: str
    profession_label: str
    level: int
    evolve_phase: int
    potential_rank: int
    favor_percent: int | None = None
    skin_id: str | None = None
    avatar_url: str | None = None
    obtain_ts: int | None = None
    main_skill_lvl: int = 1
    skills: list[ArknightsSkill] | None = None
    equips: list[ArknightsEquip] | None = None


@dataclass
class ArknightsBox:
    uid: str
    name: str
    level: int
    register_ts: int | None
    ap_current: int | None
    ap_max: int | None
    char_count: int
    chars: list[ArknightsChar]


def normalize_hg_token(raw: str) -> str:
    """接受纯 token，或 web-api 返回的整段 JSON。"""
    text = (raw or "").strip()
    if not text:
        raise SklandApiError("请粘贴森空岛凭证 Token")
    if text.startswith("{"):
        try:
            payload = json.loads(text)
            content = (
                payload.get("data", {}).get("content")
                if isinstance(payload, dict)
                else None
            )
            if isinstance(content, str) and content.strip():
                return content.strip()
        except json.JSONDecodeError as exc:
            raise SklandApiError("Token JSON 格式无效") from exc
    return text


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> dict[str, Any]:
    data: bytes | None = None
    req_headers = {
        "User-Agent": USER_AGENT_API,
        "Accept": "*/*",
        "Connection": "keep-alive",
    }
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        # 森空岛部分接口用 HTTP 4xx 返回业务 JSON（如「请勿重复签到」）
        try:
            payload = json.loads(detail)
            if isinstance(payload, dict) and (
                "code" in payload or "message" in payload or "msg" in payload
            ):
                return payload
        except json.JSONDecodeError:
            pass
        raise SklandApiError(f"HTTP {exc.code}: {detail[:200]}") from exc
    except urllib.error.URLError as exc:
        raise SklandApiError(f"网络错误：{exc.reason}") from exc

    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SklandApiError("森空岛响应不是合法 JSON") from exc


def _scan_headers(device_id: str) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Connection": "close",
        "dId": device_id,
        "X-Requested-With": "com.hypergryph.skland",
        "Content-Type": "application/json",
    }


@dataclass
class SklandScanSession:
    scan_id: str
    scan_url: str


@dataclass
class SklandScanPoll:
    """status: waiting | scanned | ready | expired | error"""

    status: str
    message: str
    scan_code: str | None = None


def create_scan_login(device_id: str) -> SklandScanSession:
    resp = _http_json(
        "POST",
        SCAN_LOGIN_URL,
        headers=_scan_headers(device_id),
        body={},
    )
    status = resp.get("status", resp.get("code"))
    if status != 0:
        raise SklandApiError(
            resp.get("msg") or resp.get("message") or "创建扫码会话失败",
            code=status if isinstance(status, int) else None,
        )
    data = resp.get("data") or {}
    scan_id = data.get("scanId")
    scan_url = data.get("scanUrl")
    if not scan_id or not scan_url:
        raise SklandApiError("扫码会话缺少 scanId / scanUrl")
    return SklandScanSession(scan_id=str(scan_id), scan_url=str(scan_url))


def poll_scan_status(device_id: str, scan_id: str) -> SklandScanPoll:
    url = f"{SCAN_STATUS_URL}?{urllib.parse.urlencode({'scanId': scan_id})}"
    resp = _http_json("GET", url, headers=_scan_headers(device_id))
    status = resp.get("status", resp.get("code"))
    data = resp.get("data") or {}
    scan_code = data.get("scanCode")
    msg = str(resp.get("msg") or resp.get("message") or "")

    if status == 0 and scan_code:
        return SklandScanPoll(status="ready", message="扫码成功", scan_code=str(scan_code))
    if status == 100:
        return SklandScanPoll(status="waiting", message=msg or "等待扫码")
    if status == 101:
        return SklandScanPoll(status="scanned", message=msg or "已扫码，请在 App 内确认")
    if status == 102:
        return SklandScanPoll(status="expired", message=msg or "二维码已过期")
    return SklandScanPoll(
        status="error",
        message=msg or f"扫码状态异常（{status}）",
    )


def token_by_scan_code(device_id: str, scan_code: str) -> str:
    resp = _http_json(
        "POST",
        TOKEN_BY_SCAN_URL,
        headers=_scan_headers(device_id),
        body={"scanCode": scan_code},
    )
    status = resp.get("status", resp.get("code"))
    if status != 0:
        raise SklandApiError(
            resp.get("msg") or resp.get("message") or "扫码换取 Token 失败",
            code=status if isinstance(status, int) else None,
        )
    data = resp.get("data") or {}
    token = data.get("content") or data.get("token")
    if not token:
        raise SklandApiError("扫码登录未返回 Token")
    return str(token)


def _hg_login_headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://user.hypergryph.com",
        "Referer": "https://user.hypergryph.com/login",
    }


def _extract_hg_token(resp: dict[str, Any], *, action: str) -> str:
    status = resp.get("status", resp.get("code"))
    if status != 0:
        msg = str(resp.get("msg") or resp.get("message") or f"{action}失败")
        data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
        captcha = data.get("captcha") if isinstance(data, dict) else None
        if captcha or "人机" in msg or "验证" in msg and status == 1:
            raise SklandApiError(
                "需要人机验证，请改用扫码登录，或稍后重试短信/密码登录",
                code=status if isinstance(status, int) else None,
            )
        raise SklandApiError(msg, code=status if isinstance(status, int) else None)
    data = resp.get("data") or {}
    token = data.get("token") or data.get("content")
    if not token:
        raise SklandApiError(f"{action}未返回 Token")
    return str(token)


def send_phone_code(phone: str) -> None:
    """发送鹰角通行证登录短信验证码。"""
    phone = (phone or "").strip()
    if not phone:
        raise SklandApiError("请填写手机号")
    resp = _http_json(
        "POST",
        SEND_PHONE_CODE_URL,
        headers=_hg_login_headers(),
        body={"phone": phone, "type": 2},
    )
    status = resp.get("status", resp.get("code"))
    if status == 0:
        return
    msg = str(resp.get("msg") or resp.get("message") or "发送验证码失败")
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    if isinstance(data, dict) and data.get("captcha"):
        raise SklandApiError(
            "发送验证码触发人机验证，请改用扫码或密码登录，或稍后重试",
            code=status if isinstance(status, int) else None,
        )
    raise SklandApiError(msg, code=status if isinstance(status, int) else None)


def token_by_phone_code(phone: str, code: str) -> str:
    phone = (phone or "").strip()
    code = (code or "").strip()
    if not phone or not code:
        raise SklandApiError("请填写手机号与验证码")
    resp = _http_json(
        "POST",
        TOKEN_BY_PHONE_CODE_URL,
        headers=_hg_login_headers(),
        body={"phone": phone, "code": code},
    )
    return _extract_hg_token(resp, action="验证码登录")


def token_by_phone_password(phone: str, password: str) -> str:
    phone = (phone or "").strip()
    password = password or ""
    if not phone or not password:
        raise SklandApiError("请填写手机号与密码")
    resp = _http_json(
        "POST",
        TOKEN_BY_PHONE_PASSWORD_URL,
        headers=_hg_login_headers(),
        body={"phone": phone, "password": password},
    )
    return _extract_hg_token(resp, action="密码登录")


def generate_sign(sign_token: str, path: str, body: str) -> tuple[str, dict[str, str]]:
    timestamp = str(int(time.time()) - 2)
    sign_header = {
        "platform": PLATFORM,
        "timestamp": timestamp,
        "dId": "",
        "vName": VNAME,
    }
    header_str = json.dumps(sign_header, separators=(",", ":"))
    sign_str = f"{path}{body}{timestamp}{header_str}"
    hmac_hex = hmac.new(
        sign_token.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    md5_sign = hashlib.md5(hmac_hex.encode("utf-8")).hexdigest()
    return md5_sign, sign_header


def _signed_headers(
    session: SklandSession,
    url: str,
    method: str,
    body: dict[str, Any] | None,
) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    if method.lower() == "get":
        sign_body = parsed.query or ""
    else:
        sign_body = (
            json.dumps(body, ensure_ascii=False, separators=(",", ":")) if body is not None else ""
        )
    sign, sign_header = generate_sign(session.sign_token, parsed.path, sign_body)
    headers = {
        "cred": session.cred,
        "sign": sign,
        "platform": sign_header["platform"],
        "timestamp": sign_header["timestamp"],
        "dId": sign_header["dId"],
        "vName": sign_header["vName"],
        "Content-Type": "application/json",
    }
    return headers


def login_with_token(hg_token: str) -> SklandSession:
    token = normalize_hg_token(hg_token)
    grant = _http_json(
        "POST",
        GRANT_URL,
        body={"appCode": APP_CODE, "token": token, "type": 0},
    )
    if grant.get("status") != 0:
        raise SklandApiError(
            grant.get("msg") or grant.get("message") or "获取授权码失败",
            code=grant.get("status"),
        )
    code = grant.get("data", {}).get("code")
    if not code:
        raise SklandApiError("授权码为空")

    cred_resp = _http_json(
        "POST",
        CRED_URL,
        body={"code": code, "kind": 1},
    )
    if cred_resp.get("code") != 0:
        raise SklandApiError(
            cred_resp.get("message") or "获取 Cred 失败",
            code=cred_resp.get("code"),
        )
    data = cred_resp.get("data") or {}
    cred = data.get("cred")
    sign_token = data.get("token")
    if not cred or not sign_token:
        raise SklandApiError("Cred / 签名 Token 缺失")
    return SklandSession(cred=str(cred), sign_token=str(sign_token))


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


def fetch_player_info(session: SklandSession, uid: str) -> dict[str, Any]:
    """拉取森空岛玩家完整数据（含干员盒子）。"""
    uid = str(uid or "").strip()
    if not uid:
        raise SklandApiError("缺少游戏 UID")
    url = f"{PLAYER_INFO_URL}?{urllib.parse.urlencode({'uid': uid})}"
    headers = _signed_headers(session, url, "get", None)
    resp = _http_json("GET", url, headers=headers)
    if resp.get("code") != 0:
        raise SklandApiError(
            resp.get("message") or "获取玩家数据失败",
            code=resp.get("code"),
        )
    data = resp.get("data")
    if not isinstance(data, dict):
        raise SklandApiError("玩家数据为空")
    return data


def _char_avatar_url(char_id: str) -> str:
    return f"{CHAR_AVATAR_CDN}/{char_id}.png"


_SPEC_CN = ("", "一", "二", "三")


def _skill_label(index: int, *, specialize: int, main_lvl: int) -> str:
    name = f"技能{index}"
    if specialize >= 1:
        sp = _SPEC_CN[min(3, specialize)]
        return f"{name} 专精{sp}"
    return f"{name} Lv.{max(1, min(7, main_lvl))}"


def _parse_skills(raw_skills: Any, *, main_skill_lvl: int) -> list[ArknightsSkill]:
    if not isinstance(raw_skills, list):
        return []
    out: list[ArknightsSkill] = []
    for i, row in enumerate(raw_skills, start=1):
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue
        try:
            specialize = int(row.get("specializeLevel") or 0)
        except (TypeError, ValueError):
            specialize = 0
        specialize = max(0, min(3, specialize))
        out.append(
            ArknightsSkill(
                skill_id=sid,
                specialize_level=specialize,
                label=_skill_label(i, specialize=specialize, main_lvl=main_skill_lvl),
            )
        )
    return out


def _parse_equips(raw_equips: Any, equip_info_map: dict[str, Any]) -> list[ArknightsEquip]:
    if not isinstance(raw_equips, list):
        return []
    out: list[ArknightsEquip] = []
    for row in raw_equips:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("id") or "").strip()
        if not eid:
            continue
        info = equip_info_map.get(eid) if isinstance(equip_info_map.get(eid), dict) else {}
        try:
            level = int(row.get("level") or 1)
        except (TypeError, ValueError):
            level = 1
        out.append(
            ArknightsEquip(
                equip_id=eid,
                name=str(info.get("name") or eid).strip() or eid,
                level=max(1, level),
                type_icon=str(info.get("typeIcon") or "").strip(),
                locked=bool(row.get("locked")),
            )
        )
    return out


def parse_arknights_box(data: dict[str, Any], *, uid: str) -> ArknightsBox:
    status = data.get("status") if isinstance(data.get("status"), dict) else {}
    char_info_map = (
        data.get("charInfoMap") if isinstance(data.get("charInfoMap"), dict) else {}
    )
    equip_info_map = (
        data.get("equipmentInfoMap")
        if isinstance(data.get("equipmentInfoMap"), dict)
        else {}
    )
    raw_chars = data.get("chars") if isinstance(data.get("chars"), list) else []
    ap = status.get("ap") if isinstance(status.get("ap"), dict) else {}

    chars: list[ArknightsChar] = []
    for item in raw_chars:
        if not isinstance(item, dict):
            continue
        char_id = str(item.get("charId") or "").strip()
        if not char_id:
            continue
        info = char_info_map.get(char_id) if isinstance(char_info_map.get(char_id), dict) else {}
        profession = str(info.get("profession") or item.get("profession") or "")
        # charInfoMap.rarity 多为 0-5（对应 1-6 星）
        rarity_raw = info.get("rarity")
        try:
            rarity_idx = int(rarity_raw) if rarity_raw is not None else 0
        except (TypeError, ValueError):
            rarity_idx = 0
        rarity = rarity_idx + 1 if 0 <= rarity_idx <= 5 else max(1, min(6, rarity_idx))

        name = str(info.get("name") or char_id)
        try:
            level = int(item.get("level") or 0)
        except (TypeError, ValueError):
            level = 0
        try:
            evolve_phase = int(item.get("evolvePhase") or 0)
        except (TypeError, ValueError):
            evolve_phase = 0
        try:
            potential_rank = int(item.get("potentialRank") or 0)
        except (TypeError, ValueError):
            potential_rank = 0
        favor = item.get("favorPercent")
        try:
            favor_percent = int(favor) if favor is not None else None
        except (TypeError, ValueError):
            favor_percent = None
        gain = item.get("gainTime") or item.get("obtainTs")
        try:
            obtain_ts = int(gain) if gain is not None else None
        except (TypeError, ValueError):
            obtain_ts = None
        skin_id = item.get("skinId")
        try:
            main_skill_lvl = int(item.get("mainSkillLvl") or 1)
        except (TypeError, ValueError):
            main_skill_lvl = 1
        main_skill_lvl = max(1, min(7, main_skill_lvl))
        skills = _parse_skills(item.get("skills"), main_skill_lvl=main_skill_lvl)
        equips = _parse_equips(item.get("equip"), equip_info_map)
        chars.append(
            ArknightsChar(
                char_id=char_id,
                name=name,
                rarity=rarity,
                profession=profession,
                profession_label=PROFESSION_CN.get(profession, profession or "未知"),
                level=level,
                evolve_phase=evolve_phase,
                potential_rank=potential_rank,
                favor_percent=favor_percent,
                skin_id=str(skin_id) if skin_id else None,
                avatar_url=_char_avatar_url(char_id),
                obtain_ts=obtain_ts,
                main_skill_lvl=main_skill_lvl,
                skills=skills,
                equips=equips,
            )
        )

    chars.sort(
        key=lambda c: (-c.rarity, -c.evolve_phase, -c.level, -c.potential_rank, c.name)
    )

    try:
        player_level = int(status.get("level") or 0)
    except (TypeError, ValueError):
        player_level = 0
    try:
        register_ts = int(status.get("registerTs")) if status.get("registerTs") is not None else None
    except (TypeError, ValueError):
        register_ts = None
    try:
        ap_current = int(ap.get("current")) if ap.get("current") is not None else None
    except (TypeError, ValueError):
        ap_current = None
    try:
        ap_max = int(ap.get("max")) if ap.get("max") is not None else None
    except (TypeError, ValueError):
        ap_max = None

    return ArknightsBox(
        uid=str(status.get("uid") or uid),
        name=str(status.get("name") or uid),
        level=player_level,
        register_ts=register_ts,
        ap_current=ap_current,
        ap_max=ap_max,
        char_count=len(chars),
        chars=chars,
    )


def fetch_arknights_box(session: SklandSession, uid: str) -> ArknightsBox:
    return parse_arknights_box(fetch_player_info(session, uid), uid=uid)


_ENDFIELD_SKILL_ORDER = {
    "skill_type_normal_attack": 0,
    "normal_attack": 0,
    "normal_skill": 1,
    "skill_type_normal_skill": 1,
    "combo_skill": 2,
    "skill_type_combo_skill": 2,
    "ultimate_skill": 3,
    "skill_type_ultimate_skill": 3,
}

_ENDFIELD_EQUIP_SLOTS = (
    ("bodyEquip", "护甲"),
    ("armEquip", "护手"),
    ("firstAccessory", "配件·一"),
    ("secondAccessory", "配件·二"),
)

_ENDFIELD_SKILL_TYPE_LABEL = {
    "skill_type_normal_attack": "普攻",
    "normal_attack": "普攻",
    "normal_skill": "战技",
    "skill_type_normal_skill": "战技",
    "combo_skill": "连携技",
    "skill_type_combo_skill": "连携技",
    "ultimate_skill": "终结技",
    "skill_type_ultimate_skill": "终结技",
}


def fetch_endfield_card_detail(session: SklandSession, role: SklandRole) -> dict[str, Any]:
    """拉取终末地养成卡原始响应（整包 JSON，供落库）。"""
    if not role.role_id or not role.server_id:
        raise SklandApiError("缺少终末地角色参数，无法拉取养成卡")
    params = {
        "roleId": str(role.role_id),
        "serverId": str(role.server_id),
    }
    uid = str(role.uid or "").strip()
    if uid:
        params["uid"] = uid
    query = urllib.parse.urlencode(params)
    url = f"{ENDFIELD_CARD_DETAIL_URL}?{query}"
    headers = _signed_headers(session, url, "get", None)
    headers["sk-game-role"] = f"3_{role.role_id}_{role.server_id}"
    resp = _http_json("GET", url, headers=headers)
    if resp.get("code") != 0:
        raise SklandApiError(
            resp.get("message") or "获取终末地养成卡失败",
            code=resp.get("code"),
        )
    return resp


def _endfield_extract_detail(raw: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw.get("detail"), dict):
        return raw["detail"]
    data = raw.get("data")
    if isinstance(data, dict):
        if isinstance(data.get("detail"), dict):
            return data["detail"]
        if "base" in data or "chars" in data:
            return data
    if "base" in raw or "chars" in raw:
        return raw
    return {}


def _endfield_int(value: Any, default: int = 0) -> int:
    if isinstance(value, dict):
        for k in ("value", "level", "id"):
            if k in value:
                return _endfield_int(value.get(k), default)
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        if isinstance(value, str):
            s = value.strip()
            # equip_level_70
            if "_" in s:
                tail = s.rsplit("_", 1)[-1]
                if tail.isdigit():
                    return int(tail)
        return default


def _endfield_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, dict) and not value:
        return None
    n = _endfield_int(value, -10**9)
    if n == -10**9:
        return None
    return n


def _endfield_rarity(value: Any) -> int:
    if isinstance(value, dict):
        key = value.get("key")
        if isinstance(key, str) and "rarity" in key:
            tail = key.rsplit("_", 1)[-1]
            if tail.isdigit():
                return max(1, min(6, int(tail)))
        for k in ("value", "id", "rarity"):
            if k in value:
                return _endfield_rarity(value.get(k))
        return 1
    if isinstance(value, (int, float)):
        n = int(value)
        # 部分接口用 0-5 表示 1-6 星
        if 0 <= n <= 5:
            return n + 1
        return max(1, min(6, n))
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return _endfield_rarity(int(s))
        if "rarity" in s:
            tail = s.rsplit("_", 1)[-1]
            if tail.isdigit():
                return max(1, min(6, int(tail)))
    return 1


def _endfield_named(value: Any) -> tuple[str, str]:
    """返回 (id_or_key, display_name)。"""
    if isinstance(value, dict):
        vid = str(value.get("id") or value.get("key") or "").strip()
        name = str(value.get("value") or value.get("name") or vid).strip()
        return vid, name
    if value is None:
        return "", ""
    s = str(value).strip()
    return s, s


def _endfield_icon(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    for key in ("iconUrl", "icon", "avatarSqUrl", "avatarRtUrl", "avatarUrl"):
        url = obj.get(key)
        if url:
            return str(url).strip() or None
    return None


def _parse_endfield_equip(slot: str, label: str, raw: Any) -> EndfieldEquip | None:
    if not isinstance(raw, dict) or not raw:
        return None
    data = raw.get("equipData") or raw.get("itemData") or raw.get("data") or raw
    if not isinstance(data, dict):
        data = raw
    item_id = str(
        data.get("id") or raw.get("equipId") or raw.get("id") or ""
    ).strip()
    name = str(data.get("name") or raw.get("name") or item_id or label).strip()
    if not item_id and not name:
        return None

    # 精锻：国服多为 equipData.level={key:equip_level_70,value:"70"}；也兼容 refine/forge 键
    refine = None
    for src in (raw, data):
        if not isinstance(src, dict):
            continue
        for key in (
            "refineLevel",
            "forgeLevel",
            "enhanceLevel",
            "breakthroughLevel",
            "精锻",
        ):
            if key in src and src.get(key) is not None:
                refine = _endfield_optional_int(src.get(key))
                if refine is not None:
                    break
        if refine is not None:
            break
    level = _endfield_optional_int(data.get("level"))
    if level is None:
        level = _endfield_optional_int(raw.get("level"))
    if refine is None and level is not None:
        # 无独立精锻字段时，装备等级即精锻等级
        refine = level

    return EndfieldEquip(
        slot=slot,
        item_id=item_id or name,
        name=name or label,
        icon_url=_endfield_icon(data) or _endfield_icon(raw),
        rarity=_endfield_rarity(data.get("rarity") if isinstance(data, dict) else None),
        level=level,
        refine_level=refine,
    )


def _parse_endfield_weapon(raw: Any) -> EndfieldWeapon | None:
    if not isinstance(raw, dict) or not raw:
        return None
    data = raw.get("weaponData") if isinstance(raw.get("weaponData"), dict) else raw
    weapon_id = str(data.get("id") or raw.get("id") or "").strip()
    name = str(data.get("name") or raw.get("name") or weapon_id).strip()
    if not weapon_id and not name:
        return None
    _, weapon_type = _endfield_named(data.get("type") or raw.get("type"))
    gem = raw.get("gem") if isinstance(raw.get("gem"), dict) else {}
    gem_data = gem.get("gemData") if isinstance(gem.get("gemData"), dict) else {}
    gem_icon = (
        str(gem_data.get("icon") or "").strip()
        or str(gem.get("icon") or "").strip()
        or None
    )
    return EndfieldWeapon(
        weapon_id=weapon_id or name,
        name=name or weapon_id,
        icon_url=_endfield_icon(data) or _endfield_icon(raw),
        rarity=_endfield_rarity(data.get("rarity")),
        level=_endfield_int(raw.get("level"), 1),
        refine_level=_endfield_int(raw.get("refineLevel"), 0),
        breakthrough_level=_endfield_int(raw.get("breakthroughLevel"), 0),
        weapon_type=weapon_type,
        gem_id=str(gem.get("id") or gem_data.get("termId") or "").strip(),
        gem_name=str(gem_data.get("name") or "").strip(),
        gem_icon_url=gem_icon or None,
    )


def _parse_endfield_skills(
    char_data: dict[str, Any], user_skills: Any
) -> list[EndfieldSkill]:
    catalog = char_data.get("skills") if isinstance(char_data.get("skills"), list) else []
    levels: dict[str, dict[str, Any]] = {}
    if isinstance(user_skills, dict):
        for sid, row in user_skills.items():
            if isinstance(row, dict):
                levels[str(sid)] = row
                nested_id = str(row.get("skillId") or "").strip()
                if nested_id:
                    levels[nested_id] = row

    skills: list[EndfieldSkill] = []
    for row in catalog:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue
        type_obj = row.get("type")
        type_key, type_value = _endfield_named(type_obj)
        if not type_key and isinstance(type_obj, str):
            type_key = type_obj
        type_label = (
            _ENDFIELD_SKILL_TYPE_LABEL.get(type_key)
            or type_value
            or type_key
            or "技能"
        )
        lvl_row = levels.get(sid) or {}
        skills.append(
            EndfieldSkill(
                skill_id=sid,
                name=str(row.get("name") or sid).strip(),
                skill_type=type_key,
                type_label=type_label,
                icon_url=_endfield_icon(row),
                level=_endfield_int(lvl_row.get("level"), 1),
                max_level=_endfield_int(lvl_row.get("maxLevel"), 0),
            )
        )
    skills.sort(
        key=lambda s: (_ENDFIELD_SKILL_ORDER.get(s.skill_type, 99), s.skill_id)
    )
    return skills


def _parse_endfield_char(item: dict[str, Any]) -> EndfieldChar | None:
    char_data = item.get("charData") if isinstance(item.get("charData"), dict) else {}
    char_id = str(
        item.get("id") or char_data.get("id") or item.get("charId") or ""
    ).strip()
    name = str(char_data.get("name") or item.get("name") or char_id).strip()
    if not char_id and not name:
        return None
    _, profession = _endfield_named(char_data.get("profession"))
    prop_obj = char_data.get("property")
    _, property_name = _endfield_named(prop_obj)
    prop_icon = None
    if isinstance(prop_obj, dict):
        prop_icon = _endfield_icon(prop_obj)
    _, weapon_type = _endfield_named(char_data.get("weaponType"))
    label_key, label_val = _endfield_named(char_data.get("labelType"))
    label_type = label_key or label_val
    gender = str(item.get("gender") or char_data.get("gender") or "").strip()
    own_ts = _endfield_optional_int(item.get("ownTs"))

    equips: list[EndfieldEquip] = []
    for field, label in _ENDFIELD_EQUIP_SLOTS:
        eq = _parse_endfield_equip(field, label, item.get(field))
        if eq:
            equips.append(eq)

    return EndfieldChar(
        char_id=char_id or name,
        name=name or char_id,
        rarity=_endfield_rarity(char_data.get("rarity")),
        level=_endfield_int(item.get("level"), 1),
        evolve_phase=_endfield_int(item.get("evolvePhase"), 0),
        potential_level=_endfield_int(item.get("potentialLevel"), 0),
        profession=profession,
        property_name=property_name,
        weapon_type=weapon_type,
        label_type=label_type,
        own_ts=own_ts,
        gender=gender,
        avatar_url=(
            str(char_data.get("avatarSqUrl") or "").strip()
            or str(char_data.get("avatarRtUrl") or "").strip()
            or None
        ),
        illustration_url=str(char_data.get("illustrationUrl") or "").strip() or None,
        property_icon_url=prop_icon,
        weapon=_parse_endfield_weapon(item.get("weapon")),
        skills=_parse_endfield_skills(char_data, item.get("userSkills")),
        equips=equips,
    )


def parse_endfield_box(
    raw: dict[str, Any],
    *,
    role: SklandRole | None = None,
) -> EndfieldBox:
    """从落库的原始响应二次加工为展示结构。"""
    detail = _endfield_extract_detail(raw)
    base = detail.get("base") if isinstance(detail.get("base"), dict) else {}
    raw_chars = detail.get("chars") if isinstance(detail.get("chars"), list) else []

    chars: list[EndfieldChar] = []
    for item in raw_chars:
        if not isinstance(item, dict):
            continue
        parsed = _parse_endfield_char(item)
        if parsed:
            chars.append(parsed)
    chars.sort(key=lambda c: (-c.rarity, -c.level, -c.potential_level, c.name))

    role_id = str(base.get("roleId") or (role.role_id if role else "") or "").strip()
    uid = str(
        base.get("uid")
        or base.get("roleId")
        or (role.uid if role else "")
        or role_id
    ).strip()
    server_id = str(
        base.get("serverId") or (role.server_id if role else "") or ""
    ).strip()
    char_num = _endfield_int(base.get("charNum"), len(chars))

    return EndfieldBox(
        uid=uid or role_id,
        role_id=role_id or uid,
        server_id=server_id,
        name=str(base.get("name") or (role.role_name if role else "") or uid).strip(),
        level=_endfield_int(base.get("level"), 0),
        server_name=str(
            base.get("serverName") or (role.channel_name if role else "") or ""
        ).strip(),
        avatar_url=str(base.get("avatarUrl") or "").strip() or None,
        char_count=char_num or len(chars),
        chars=chars,
    )
