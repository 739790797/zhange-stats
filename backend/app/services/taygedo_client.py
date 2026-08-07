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
# 异环 / 幻塔游戏签到目标（社区 APP 另计）
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



# 签到逻辑拆至 taygedo_attendance，此处再导出保持原 import 路径兼容
from app.services.taygedo_attendance import (  # noqa: E402
    ShopGoods,
    app_signin,
    checkin_all,
    checkin_target,
    ensure_session,
    exchange_shop_goods,
    fetch_today_awards,
    friendly_error_message,
    game_signin,
    get_shop_goods_detail,
    get_user_coin_state,
    is_auth_failure,
    list_checkin_targets,
    list_shop_goods,
    query_app_today,
    query_game_today,
    query_today_all,
    sort_taygedo_results,
)
