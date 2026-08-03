"""塔吉多 / 异环 HTTP 客户端（bbs-api.tajiduo.com + 老虎通行证）。"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import random
import string
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from app.services.checkin_common import CheckinResult

logger = logging.getLogger(__name__)

TAYGEDO_BASE = "https://bbs-api.tajiduo.com"
H5_ORIGIN = "https://webstatic.tajiduo.com"
LAOHU_BASE = "https://user.laohu.com"

TAYGEDO_APP_VER = "1.2.5"
TAYGEDO_DS_SECRET = "pUds3dfMkl"
TAYGEDO_LOGIN_APP_ID = "10551"

LAOHU_SECRET = "89155cc4e8634ec5b1b6364013b23e3e"
LAOHU_APP_ID = "10550"
LAOHU_CHANNEL_ID = "1"
LAOHU_VERSION_CODE = "17"
LAOHU_SDK_VERSION = "4.327.0"
LAOHU_UA = "LaohuSDK/4.327.0 (android os 14;mobile  manufacturer Google; model Pixel 6) "

GAME_NTE = "1289"
GAME_NTE_NAME = "异环"
GAME_HT = "1256"
GAME_HT_NAME = "幻塔"
GAME_APP = "app"
GAME_APP_NAME = "塔吉多 APP"
# 游戏签到目标（不含社区）
GAME_SIGN_IDS: tuple[tuple[str, str], ...] = (
    (GAME_NTE, GAME_NTE_NAME),
    (GAME_HT, GAME_HT_NAME),
)

REQUEST_TIMEOUT = 25


class TaygedoApiError(Exception):
    def __init__(self, message: str, *, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class TaygedoCredentials:
    uid: str
    device_id: str
    access_token: str
    refresh_token: str
    phone: str | None = None
    laohu_token: str | None = None
    laohu_user_id: str | None = None

    def to_dict(self) -> dict[str, str]:
        data = {
            "uid": self.uid,
            "device_id": self.device_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }
        if self.phone:
            data["phone"] = self.phone
        if self.laohu_token:
            data["laohu_token"] = self.laohu_token
        if self.laohu_user_id:
            data["laohu_user_id"] = self.laohu_user_id
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TaygedoCredentials:
        uid = str(raw.get("uid") or "").strip()
        device_id = str(raw.get("device_id") or raw.get("deviceId") or "").strip()
        access = str(raw.get("access_token") or raw.get("accessToken") or "").strip()
        refresh = str(raw.get("refresh_token") or raw.get("refreshToken") or "").strip()
        if not uid or not device_id or not refresh:
            raise TaygedoApiError("凭证缺少 uid / device_id / refresh_token")
        return cls(
            uid=uid,
            device_id=device_id,
            access_token=access,
            refresh_token=refresh,
            phone=(str(raw["phone"]).strip() if raw.get("phone") else None),
            laohu_token=(
                str(raw.get("laohu_token") or raw.get("laohuToken") or "").strip() or None
            ),
            laohu_user_id=(
                str(raw.get("laohu_user_id") or raw.get("laohuUserId") or "").strip() or None
            ),
        )


@dataclass
class TaygedoRole:
    game_code: str
    game_name: str
    role_id: str
    role_name: str


def mask_phone(phone: str | None) -> str | None:
    text = (phone or "").strip()
    if len(text) < 7:
        return text or None
    return f"{text[:3]}****{text[-4:]}"


def _form_encode(data: dict[str, str], *, skip_empty: bool = False) -> str:
    items = []
    for key, value in data.items():
        if skip_empty and value == "":
            continue
        items.append(
            f"{urllib.parse.quote_plus(str(key))}={urllib.parse.quote_plus(str(value))}"
        )
    return "&".join(items)


def _http(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> tuple[int, dict[str, Any]]:
    req_headers = {"Accept": "application/json", "Connection": "keep-alive"}
    if headers:
        req_headers.update(headers)
    data = body.encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = str(exc)
    except urllib.error.URLError as exc:
        raise TaygedoApiError(f"网络错误：{exc.reason}") from exc

    if not raw.strip():
        if status in (401, 402, 403):
            raise TaygedoApiError(
                "登录态已失效，请重新绑定塔吉多",
                code=status,
            )
        raise TaygedoApiError(f"空响应（HTTP {status}）")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TaygedoApiError(f"无效 JSON（HTTP {status}）：{raw[:160]}") from exc
    if not isinstance(payload, dict):
        raise TaygedoApiError(f"响应格式异常（HTTP {status}）")
    return status, payload


def _aes_base64_encode(value: str, secret: str = LAOHU_SECRET) -> str:
    key = secret[-16:].encode("utf-8")
    padder = PKCS7(128).padder()
    padded = padder.update(value.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("ascii")


def _laohu_sign(data: dict[str, str], secret: str = LAOHU_SECRET) -> str:
    values = "".join(data[k] for k in sorted(data.keys()))
    return hashlib.md5(f"{values}{secret}".encode("utf-8")).hexdigest()


def _laohu_base_params(device_id: str, timestamp: str, *, version_field: str) -> dict[str, str]:
    base = {
        "adm": "",
        "appId": LAOHU_APP_ID,
        "bid": "com.pwrd.htassistant",
        "channelId": LAOHU_CHANNEL_ID,
        "deviceId": device_id,
        "deviceModel": "Pixel 6",
        "deviceName": "Pixel 6",
        "deviceSys": "14",
        "deviceType": "Pixel 6",
        "idfa": "",
        "sdkVersion": LAOHU_SDK_VERSION,
        "t": timestamp,
    }
    if version_field == "versionCode":
        return {**base, "imei": "", "versionCode": LAOHU_VERSION_CODE}
    return {**base, "mac": "", "version": LAOHU_VERSION_CODE}


def _signed_laohu_body(data: dict[str, str], *, include_empty: bool) -> str:
    payload = {**data, "sign": _laohu_sign(data)}
    return _form_encode(payload, skip_empty=not include_empty)


def _make_ds() -> str:
    timestamp = str(int(time.time()))
    alphabet = string.ascii_letters + string.digits
    nonce = "".join(random.choice(alphabet) for _ in range(8))
    signature = hashlib.md5(
        f"{timestamp}{nonce}{TAYGEDO_APP_VER}{TAYGEDO_DS_SECRET}".encode("utf-8")
    ).hexdigest()
    return f"{timestamp},{nonce},{signature}"


def login_with_password(phone: str, password: str) -> TaygedoCredentials:
    phone = (phone or "").strip()
    password = (password or "").strip()
    if not phone or not password:
        raise TaygedoApiError("请填写手机号和密码")

    device_id = uuid.uuid4().hex
    payload = {
        **_laohu_base_params(device_id, str(int(time.time() * 1000)), version_field="version"),
        "password": _aes_base64_encode(password),
        "username": _aes_base64_encode(phone),
    }
    status, data = _http(
        "POST",
        f"{LAOHU_BASE}/openApi/secureLogin",
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": LAOHU_UA,
            "robot-auth-type": "2",
        },
        body=_signed_laohu_body(payload, include_empty=True),
    )
    result = data.get("result") or {}
    laohu_token = result.get("token")
    laohu_user_id = result.get("userId")
    if status != 200 or data.get("code") != 0 or not laohu_token or laohu_user_id is None:
        raise TaygedoApiError(
            data.get("message") or data.get("msg") or "老虎通行证登录失败",
            code=data.get("code") if isinstance(data.get("code"), int) else None,
        )

    session = _user_center_login(str(laohu_token), str(laohu_user_id), device_id)
    session.phone = phone
    session.laohu_token = str(laohu_token)
    session.laohu_user_id = str(laohu_user_id)
    return session


def send_sms_captcha(phone: str, device_id: str | None = None) -> str:
    """调用老虎官方接口发送登录短信验证码，返回需复用的 device_id。"""
    phone = (phone or "").strip()
    if not phone:
        raise TaygedoApiError("请填写手机号")
    device_id = (device_id or "").strip() or uuid.uuid4().hex
    payload = {
        **_laohu_base_params(
            device_id, str(int(time.time())), version_field="versionCode"
        ),
        "areaCodeId": "1",
        "cellphone": phone,
        "type": "16",
    }
    status, data = _http(
        "POST",
        f"{LAOHU_BASE}/m/newApi/sendPhoneCaptchaWithOutLogin",
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": LAOHU_UA,
        },
        body=_signed_laohu_body(payload, include_empty=False),
    )
    msg = str(data.get("message") or data.get("msg") or "")
    sending = (
        status == 200
        and data.get("code") == 1
        and "短信正在发送" in msg
    )
    if status != 200 or (data.get("code") != 0 and not sending):
        raise TaygedoApiError(
            msg or "发送短信验证码失败",
            code=data.get("code") if isinstance(data.get("code"), int) else None,
        )
    return device_id


def _check_sms_captcha(phone: str, captcha: str, device_id: str) -> None:
    payload = {
        **_laohu_base_params(
            device_id, str(int(time.time())), version_field="versionCode"
        ),
        "captcha": captcha,
        "cellphone": phone,
    }
    status, data = _http(
        "POST",
        f"{LAOHU_BASE}/m/newApi/checkPhoneCaptchaWithOutLogin",
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": LAOHU_UA,
        },
        body=_signed_laohu_body(payload, include_empty=False),
    )
    if status != 200 or data.get("code") != 0:
        raise TaygedoApiError(
            data.get("message") or data.get("msg") or "短信验证码校验失败",
            code=data.get("code") if isinstance(data.get("code"), int) else None,
        )


def login_with_sms(phone: str, captcha: str, device_id: str) -> TaygedoCredentials:
    """短信验证码登录老虎通行证，再换取塔吉多用户中心凭证。"""
    phone = (phone or "").strip()
    captcha = (captcha or "").strip()
    device_id = (device_id or "").strip()
    if not phone or not captcha:
        raise TaygedoApiError("请填写手机号与验证码")
    if not device_id:
        raise TaygedoApiError("请先获取短信验证码")
    if not captcha.isdigit() or not (4 <= len(captcha) <= 8):
        raise TaygedoApiError("验证码格式不正确")

    _check_sms_captcha(phone, captcha, device_id)

    payload = {
        **_laohu_base_params(
            device_id, str(int(time.time() * 1000)), version_field="version"
        ),
        "areaCodeId": "1",
        "captcha": _aes_base64_encode(captcha),
        "cellphone": _aes_base64_encode(phone),
        "type": "16",
    }
    status, data = _http(
        "POST",
        f"{LAOHU_BASE}/openApi/sms/new/login",
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": LAOHU_UA,
        },
        body=_signed_laohu_body(payload, include_empty=True),
    )
    result = data.get("result") or {}
    laohu_token = result.get("token")
    laohu_user_id = result.get("userId")
    if status != 200 or data.get("code") != 0 or not laohu_token or laohu_user_id is None:
        raise TaygedoApiError(
            data.get("message") or data.get("msg") or "短信验证码登录失败",
            code=data.get("code") if isinstance(data.get("code"), int) else None,
        )

    session = _user_center_login(str(laohu_token), str(laohu_user_id), device_id)
    session.phone = phone
    session.laohu_token = str(laohu_token)
    session.laohu_user_id = str(laohu_user_id)
    return session


def _user_center_login(token: str, user_id: str, device_id: str) -> TaygedoCredentials:
    status, data = _http(
        "POST",
        f"{TAYGEDO_BASE}/usercenter/api/login",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Authorization": "",
            "appVersion": TAYGEDO_APP_VER,
            "platform": "android",
            "uid": "0",
            "debug-uid": "3",
            "deviceId": device_id,
            "ds": _make_ds(),
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.12.0",
        },
        body=_form_encode(
            {
                "token": token,
                "userIdentity": user_id,
                "appId": TAYGEDO_LOGIN_APP_ID,
            }
        ),
    )
    payload = data.get("data") or {}
    if (
        status != 200
        or data.get("code") != 0
        or not payload.get("accessToken")
        or not payload.get("refreshToken")
        or payload.get("uid") is None
    ):
        raise TaygedoApiError(
            data.get("msg") or data.get("message") or "塔吉多用户中心登录失败",
            code=data.get("code") if isinstance(data.get("code"), int) else None,
        )
    return TaygedoCredentials(
        uid=str(payload["uid"]),
        device_id=device_id,
        access_token=str(payload["accessToken"]),
        refresh_token=str(payload["refreshToken"]),
    )


def refresh_access_token(creds: TaygedoCredentials) -> TaygedoCredentials:
    status, data = _http(
        "POST",
        f"{TAYGEDO_BASE}/usercenter/api/refreshToken",
        headers={
            "authorization": creds.refresh_token,
            "deviceid": creds.device_id,
            "appversion": "1.1.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.12.0",
        },
        body="",
    )
    if status == 402:
        raise TaygedoApiError("refreshToken 已失效，请重新登录绑定", code=402)
    payload = data.get("data") or {}
    if (
        status != 200
        or data.get("code") != 0
        or not payload.get("accessToken")
        or not payload.get("refreshToken")
    ):
        raise TaygedoApiError(
            data.get("msg") or data.get("message") or "刷新登录态失败",
            code=data.get("code") if isinstance(data.get("code"), int) else None,
        )
    return TaygedoCredentials(
        uid=str(payload.get("uid") or creds.uid),
        device_id=creds.device_id,
        access_token=str(payload["accessToken"]),
        refresh_token=str(payload["refreshToken"]),
        phone=creds.phone,
        laohu_token=creds.laohu_token,
        laohu_user_id=creds.laohu_user_id,
    )


def ensure_access_token(creds: TaygedoCredentials) -> TaygedoCredentials:
    if creds.access_token:
        return creds
    return refresh_access_token(creds)


def list_game_roles(creds: TaygedoCredentials, game_id: str, game_name: str) -> list[TaygedoRole]:
    status, data = _http(
        "GET",
        f"{TAYGEDO_BASE}/usercenter/api/v2/getGameRoles?gameId={urllib.parse.quote(game_id)}",
        headers={
            "platform": "android",
            "authorization": creds.access_token,
            "uid": creds.uid,
            "deviceid": creds.device_id,
            "appversion": "1.1.0",
            "User-Agent": "okhttp/4.12.0",
        },
    )
    if status != 200 or data.get("code") != 0:
        msg = str(data.get("msg") or data.get("message") or f"获取{game_name}角色失败")
        code = data.get("code") if isinstance(data.get("code"), int) else None
        if is_auth_failure(status=status, code=code, message=msg):
            raise TaygedoApiError(friendly_error_message(msg), code=code or status)
        raise TaygedoApiError(msg, code=code)
    roles_raw = (data.get("data") or {}).get("roles") or []
    roles: list[TaygedoRole] = []
    for item in roles_raw:
        if not isinstance(item, dict) or item.get("roleId") is None:
            continue
        roles.append(
            TaygedoRole(
                game_code=game_id,
                game_name=game_name,
                role_id=str(item["roleId"]),
                role_name=str(item.get("roleName") or f"{game_name}角色"),
            )
        )
    return roles


def list_nte_roles(creds: TaygedoCredentials) -> list[TaygedoRole]:
    """兼容旧调用：仅异环角色。"""
    return list_game_roles(creds, GAME_NTE, GAME_NTE_NAME)


def list_all_game_roles(creds: TaygedoCredentials) -> list[TaygedoRole]:
    """异环 + 幻塔已绑定角色。"""
    out: list[TaygedoRole] = []
    last_auth: TaygedoApiError | None = None
    for game_id, game_name in GAME_SIGN_IDS:
        try:
            out.extend(list_game_roles(creds, game_id, game_name))
        except TaygedoApiError as exc:
            if is_auth_failure(code=exc.code, message=exc.message):
                last_auth = exc
                continue
            # 某游戏无角色 / 业务错误：跳过
            continue
    if not out and last_auth is not None:
        raise last_auth
    return out


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


def _item_award_text(item: dict[str, Any]) -> str | None:
    name = item.get("name") or item.get("rewardName") or item.get("awardName")
    if not name:
        nested = item.get("reward") or item.get("award") or item.get("item")
        if isinstance(nested, dict):
            name = nested.get("name")
            num = nested.get("num") or nested.get("count") or item.get("num") or item.get("count")
            if name:
                return f"{name} x{num or 1}"
        return None
    num = item.get("num") if item.get("num") is not None else item.get("count")
    return f"{name} x{num or 1}"


def _awards_from_sign_payload(data: dict[str, Any]) -> str | None:
    """从签到 POST 响应中提取当日奖励（优先于月历列表）。"""
    payload = data.get("data")
    if not isinstance(payload, dict):
        return None
    for key in ("rewards", "rewardList", "awards", "awardList", "items"):
        raw = payload.get(key)
        if isinstance(raw, list) and raw:
            parts = []
            for item in raw:
                if isinstance(item, dict):
                    text = _item_award_text(item)
                    if text:
                        parts.append(text)
            if parts:
                return "、".join(parts)
        if isinstance(raw, dict):
            text = _item_award_text(raw)
            if text:
                return text
    # 单条 name/num
    text = _item_award_text(payload)
    if text:
        return text
    name = payload.get("rewardName") or payload.get("awardName")
    if name:
        num = payload.get("num") or payload.get("count") or 1
        return f"{name} x{num}"
    return None


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
) -> str | None:
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
            return None
        raw = data.get("data")
        records = raw if isinstance(raw, list) else []
        parts: list[str] = []
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
            if num is not None:
                parts.append(f"{title}+{num}")
            else:
                parts.append(title)
        return "、".join(parts) if parts else None
    except Exception:  # noqa: BLE001
        return None


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


def _awards_from_claim_records(
    creds: TaygedoCredentials,
    game_id: str,
    *,
    role_id: str | None = None,
) -> str | None:
    """尝试官方领取记录接口（按真实领取时间筛今日）。失败则返回 None。"""
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
        parts: list[str] = []
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
            text = _item_award_text(rec)
            if not text and isinstance(rec.get("reward"), dict):
                text = _item_award_text(rec["reward"])
            if text:
                parts.append(text)
        if parts:
            return "、".join(parts)
    return None


def _awards_from_game_state(
    creds: TaygedoCredentials,
    game_id: str,
    state: dict[str, Any],
    *,
    role_id: str | None = None,
) -> str | None:
    """今日已签奖励：优先领取记录；否则用本月累计 days（第 N 次），禁止用日历日期。"""
    claimed = _awards_from_claim_records(creds, game_id, role_id=role_id)
    if claimed:
        return claimed

    rewards = _list_game_rewards(creds, game_id, role_id=role_id)
    if not rewards:
        return None
    # 与社区工具一致：todaySign 后 rewards[days-1] 为当日格（本月第 N 次）
    try:
        day_idx = int(state.get("days") or 0) - 1
    except (TypeError, ValueError):
        day_idx = -1
    if day_idx < 0:
        return None
    if 0 <= day_idx < len(rewards):
        return _item_award_text(rewards[day_idx])
    return None


def _fetch_rewards(
    creds: TaygedoCredentials, game_id: str, *, role_id: str | None = None
) -> str | None:
    state = _get_game_sign_state(creds, game_id)
    if not state or not state.get("todaySign"):
        return None
    return _awards_from_game_state(creds, game_id, state, role_id=role_id)


def fetch_today_awards(
    creds: TaygedoCredentials, *, game_code: str, role_id: str | None = None
) -> str | None:
    """已签到时补读今日游戏奖励（不含社区）。"""
    if game_code == GAME_APP:
        return None
    return _fetch_rewards(creds, game_code, role_id=role_id)


def query_game_today(creds: TaygedoCredentials, role: TaygedoRole) -> CheckinResult:
    """按官方 signin/state.todaySign 查询游戏今日签到与奖励。"""
    state = _get_game_sign_state(creds, role.game_code)
    channel = role.game_name
    if state and state.get("todaySign"):
        awards = _awards_from_game_state(
            creds, role.game_code, state, role_id=role.role_id
        )
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=channel,
            status="already",
            message=f"今日已签到，获得：{awards}" if awards else "今日已签到",
            awards_text=awards,
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
        awards = None
        if isinstance(exp, (int, float)) or isinstance(gold, (int, float)):
            awards = f"经验+{exp or 0}、金币+{gold or 0}"
        return CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid=creds.uid,
            role_name="社区账号",
            channel_name="塔吉多",
            status="ok",
            message=f"签到成功{('，获得：' + awards) if awards else ''}",
            awards_text=awards,
        )
    if _is_already(msg):
        awards = _app_awards_from_exp_records(creds)
        return CheckinResult(
            game_code=GAME_APP,
            game_name=GAME_APP_NAME,
            role_uid=creds.uid,
            role_name="社区账号",
            channel_name="塔吉多",
            status="already",
            message=f"今日已签到，获得：{awards}" if awards else "今日已签到",
            awards_text=awards,
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
        awards = _awards_from_sign_payload(data) or _fetch_rewards(
            creds, role.game_code, role_id=role.role_id
        )
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=channel,
            status="ok",
            message=f"签到成功{('，获得：' + awards) if awards else ''}",
            awards_text=awards,
        )
    if _is_already(msg):
        awards = _fetch_rewards(creds, role.game_code, role_id=role.role_id)
        return CheckinResult(
            game_code=role.game_code,
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=channel,
            status="already",
            message=f"今日已签到{('，获得：' + awards) if awards else ''}",
            awards_text=awards,
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
