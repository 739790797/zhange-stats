"""森空岛 / 鹰角通行证 HTTP 客户端（urllib，带请求签名）。"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

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


def localize_endfield_server_name(name: str | None) -> str:
    """终末地 serverName 展示中文化（China → 国服）。"""
    raw = (name or "").strip()
    if not raw:
        return "未知渠道"
    mapped = {
        "china": "国服",
        "cn": "国服",
    }.get(raw.lower())
    return mapped or raw


def localize_arknights_channel_name(name: str | None) -> str:
    """明日方舟渠道名展示：bilibili服 → B服。"""
    raw = (name or "").strip()
    if not raw:
        return "未知渠道"
    low = raw.lower().replace(" ", "")
    if (
        "bilibili" in low
        or "哔哩" in raw
        or low in ("b服", "bilibili服", "b站服")
    ):
        return "B服"
    return raw


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



# 签到 HTTP 拆至 skland_attendance，此处再导出保持原 import 路径兼容
from app.services.skland_attendance import (  # noqa: E402
    checkin_all_roles,
    checkin_arknights,
    checkin_endfield,
    checkin_role,
    fetch_binding_list,
    fetch_today_awards,
    friendly_error_message,
    list_roles,
    query_role_today,
    query_today_all,
    sort_skland_results,
    sort_skland_roles,
)
# 盒子解析拆至 skland_boxes，此处再导出保持原 import 路径兼容
from app.services.skland_boxes import (  # noqa: E402
    fetch_arknights_box,
    fetch_endfield_card_detail,
    fetch_player_info,
    parse_arknights_box,
    parse_endfield_box,
)
