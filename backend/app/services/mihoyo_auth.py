"""米游社通行证登录：短信 / 密码 / 扫码。"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.services.mihoyo_client import (
    MihoyoApiError,
    MihoyoCredentials,
    MYS_VERSION,
    REQUEST_TIMEOUT,
    USER_AGENT,
    bind_with_cookie,
    ensure_session,
    parse_cookie_string,
)

logger = logging.getLogger(__name__)

ACCOUNT_API = "https://webapi.account.mihoyo.com"
# 扫码：对齐 MHY_Scanner / C++ GetLoginQrcodeUrl，用 mihoyo.com 而非 miyoushe web
PASSPORT_API = "https://passport-api.mihoyo.com"
PASSPORT_MIYOUSHE = "https://passport-api.miyoushe.com"

# web 登录页 app_id（短信/密码走 account API）
APP_ID = "bll8iq97cem8"
# App 扫码 app_id（C++ / MHY_Scanner：dw9y09jqjpxc；确认后 tokens[0] 即为 stoken）
QR_APP_ID = "dw9y09jqjpxc"
QR_CLIENT_TYPE = "2"

# 米哈游通行证官方 RSA 公钥（密码加密）
_RSA_PUBLIC_PEM = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDDvekdPMHN3AYhm/vktJT+YJr7
cI5DcsNKqdsx5DZX0gDuWFuIjzdwButrIYPNmRJ1G8ybDIF7oDW2eEpm5sMbL9zs
9ExXCdvqrn51qELbqj0XxtMTIpaCHFSI50PfPpTFV9Xt/hmyVwokoOXFlAEgCn+Q
CgGs52bFoYMtyi+xEQIDAQAB
-----END PUBLIC KEY-----"""


class MihoyoNeedGeetest(MihoyoApiError):
    """登录 / 发短信需要极验 4。"""

    def __init__(self, *, captcha_id: str, mmt_key: str):
        super().__init__(
            "请完成人机验证",
            code=1,
            data={"captcha_id": captcha_id, "mmt_key": mmt_key},
        )
        self.captcha_id = captcha_id
        self.mmt_key = mmt_key


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_sec() -> int:
    return int(time.time())


def rsa_encrypt(message: str) -> str:
    key = serialization.load_pem_public_key(_RSA_PUBLIC_PEM.encode("ascii"))
    encrypted = key.encrypt(message.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")


def _parse_geetest(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MihoyoApiError("人机验证数据无效") from exc
    if not isinstance(data, dict):
        raise MihoyoApiError("人机验证数据无效")
    return data


# 通行证风控：-3101 需极验，结果经 x-rpc-aigis 回传
AIGIS_NEED_CODE = -3101
SMS_ACTION_TYPE = "login_by_mobile_captcha"


def _account_headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": USER_AGENT,
        "Origin": "https://user.mihoyo.com",
        "Referer": "https://user.mihoyo.com/",
    }


def _passport_headers(*, device_id: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Origin": "https://user.mihoyo.com",
        "Referer": "https://user.mihoyo.com/",
        "x-rpc-app_id": APP_ID,
        "x-rpc-client_type": "4",
        "x-rpc-device_id": device_id,
        "x-rpc-device_fp": device_id[:13],
    }


def _login_passport_headers(*, device_id: str, aigis: str | None = None) -> dict[str, str]:
    """短信/密码登录：对齐 TeyvatGuide / Snap Hutao 的 app 通行证头。"""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Origin": "https://user.miyoushe.com",
        "Referer": "https://user.miyoushe.com/",
        "x-rpc-aigis": aigis or "",
        "x-rpc-app_id": APP_ID,
        "x-rpc-app_version": MYS_VERSION,
        "x-rpc-client_type": "2",
        "x-rpc-device_id": device_id,
        "x-rpc-device_fp": device_id[:13],
        "x-rpc-device_name": "Android",
        "x-rpc-device_model": "Unspecified",
        "x-rpc-game_biz": "bbs_cn",
        "x-rpc-sdk_version": "2.16.0",
    }


def _stable_device_id(seed: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"zhange-mihoyo:{seed.strip()}").hex


def _qr_passport_headers(*, device_id: str) -> dict[str, str]:
    # 对齐 MHY_Scanner：仅 Content-Type + app_id + device_id
    return {
        "Content-Type": "application/json",
        "x-rpc-app_id": QR_APP_ID,
        "x-rpc-device_id": device_id,
    }


def _cookies_from_response(resp: httpx.Response) -> dict[str, str]:
    """合并 Set-Cookie 头与 httpx cookie jar（扫码确认凭证主要在响应头）。"""
    out: dict[str, str] = {}
    for name, value in resp.headers.multi_items():
        if name.lower() != "set-cookie":
            continue
        part = value.split(";", 1)[0]
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        key, val = key.strip(), val.strip()
        if key and val:
            out[key] = val
    for key, val in resp.cookies.items():
        if key and val and key not in out:
            out[key] = str(val)
    # CDN / 网关垃圾 cookie
    for junk in ("aliyungf_tc", "acw_tc", "cdn_sec_tc"):
        out.pop(junk, None)
    return out


def _stoken_from_qr_tokens(tokens: list[Any]) -> str:
    """对齐 MHY_Scanner：优先 token_type=1 / name=stoken，否则取 tokens[0]。"""
    for row in tokens:
        if not isinstance(row, dict):
            continue
        token = str(row.get("token") or "").strip()
        if not token:
            continue
        token_type = row.get("token_type")
        name = str(row.get("name") or "").lower()
        if token_type in (1, "1") or name == "stoken":
            return token
    for row in tokens:
        if isinstance(row, dict):
            token = str(row.get("token") or "").strip()
            if token:
                return token
    return ""


def _passport_retcode(payload: dict[str, Any], *, default: int = -1) -> int:
    """解析通行证 retcode。注意成功时为 0，不可写 `payload.get(...) or default`。"""
    raw = payload.get("retcode")
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _extract_error_text(item: Any) -> str:
    """从通行证错误体抽出可读文案，避免把整段 JSON 甩到前端。"""
    if item is None:
        return ""
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return ""
        if text[:1] in "{[":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return text
            nested = _extract_error_text(parsed)
            return nested or text
        return text
    if isinstance(item, dict):
        for key in ("msg", "message", "info"):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        nested = item.get("data")
        if nested is not None and nested is not item:
            return _extract_error_text(nested)
    return ""


def _humanize_passport_error(payload: dict[str, Any]) -> str:
    for item in (payload.get("message"), payload.get("msg"), payload.get("data"), payload):
        text = _extract_error_text(item)
        if text:
            return text
    return "通行证请求失败"


def _parse_aigis_challenge(raw: str | None) -> tuple[str, str]:
    """解析响应头 x-rpc-aigis → (session_id, captcha_id)。"""
    text = (raw or "").strip()
    if not text:
        return "", ""
    try:
        info = json.loads(text)
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(info, dict):
        return "", ""
    session_id = str(info.get("session_id") or "").strip()
    data_raw = info.get("data")
    data: dict[str, Any] = {}
    if isinstance(data_raw, dict):
        data = data_raw
    elif isinstance(data_raw, str) and data_raw.strip():
        try:
            parsed = json.loads(data_raw)
            if isinstance(parsed, dict):
                data = parsed
        except json.JSONDecodeError:
            data = {}
    captcha_id = str(data.get("gt") or data.get("captcha_id") or "").strip()
    return session_id, captcha_id


def _build_aigis_header(session_id: str, geetest: dict[str, Any]) -> str:
    payload = json.dumps(geetest, ensure_ascii=False, separators=(",", ":"))
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{session_id};{encoded}"


def _aigis_from_geetest(
    geetest: str | dict[str, Any] | None,
    mmt_key: str | None,
) -> str | None:
    gt_data = _parse_geetest(geetest)
    session_id = (mmt_key or "").strip()
    if not gt_data or not session_id:
        return None
    return _build_aigis_header(session_id, gt_data)


def _raise_need_geetest_or_error(resp: httpx.Response, payload: dict[str, Any]) -> None:
    retcode = _passport_retcode(payload, default=-1)
    if retcode == AIGIS_NEED_CODE:
        session_id, captcha_id = _parse_aigis_challenge(resp.headers.get("x-rpc-aigis"))
        if session_id and captcha_id:
            raise MihoyoNeedGeetest(captcha_id=captcha_id, mmt_key=session_id)
        raise MihoyoApiError(
            _humanize_passport_error(payload) or "需要人机验证，请稍后重试",
            code=retcode,
        )
    if retcode != 0:
        raise MihoyoApiError(_humanize_passport_error(payload), code=retcode)


def _passport_post(
    url: str,
    *,
    device_id: str,
    body: dict[str, Any],
    aigis: str | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    headers = _login_passport_headers(device_id=device_id, aigis=aigis)
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = client.post(url, headers=headers, json=body)
            try:
                payload = resp.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise MihoyoApiError("通行证返回异常") from exc
            set_cookies = _cookies_from_response(resp)
    except MihoyoApiError:
        raise
    except httpx.HTTPError as exc:
        raise MihoyoApiError("通行证请求失败，请稍后重试") from exc
    if not isinstance(payload, dict):
        raise MihoyoApiError("通行证返回异常")
    _raise_need_geetest_or_error(resp, payload)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    return data, set_cookies


def _creds_from_passport_login(
    *, data: dict[str, Any], set_cookies: dict[str, str]
) -> MihoyoCredentials:
    """短信/密码登录成功：token + user_info，结构接近扫码确认。"""
    cookies = dict(set_cookies)
    login_ticket = str(data.get("login_ticket") or cookies.get("login_ticket") or "").strip()
    if login_ticket:
        cookies.setdefault("login_ticket", login_ticket)

    extra_tokens: list[Any] = []
    tokens = data.get("tokens") if isinstance(data.get("tokens"), list) else []
    extra_tokens.extend(tokens)
    token_raw = data.get("token")
    if isinstance(token_raw, dict):
        extra_tokens.insert(0, token_raw)
    elif isinstance(token_raw, str) and token_raw.strip():
        extra_tokens.insert(
            0, {"token_type": 1, "name": "stoken", "token": token_raw.strip()}
        )

    synthetic = {
        "user_info": data.get("user_info") if isinstance(data.get("user_info"), dict) else {},
        "tokens": extra_tokens,
    }
    return _creds_from_qr_confirmed(data=synthetic, set_cookies=cookies)


def _assert_account_ok(payload: dict[str, Any]) -> dict[str, Any]:
    code = payload.get("code")
    if code is not None and int(code or 0) != 200:
        raise MihoyoApiError(
            _humanize_passport_error(payload),
            code=int(code) if str(code).lstrip("-").isdigit() else None,
        )
    data = payload.get("data")
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            parsed = None
        data = parsed if isinstance(parsed, dict) else data
    if not isinstance(data, dict):
        retcode = _passport_retcode(payload, default=0)
        if retcode != 0:
            raise MihoyoApiError(_humanize_passport_error(payload), code=retcode)
        raise MihoyoApiError("通行证返回异常")
    status = data.get("status")
    nested_retcode = data.get("retcode")
    if status not in (1, "1", None):
        msg = _extract_error_text(data) or "操作失败"
        code_val = status if str(status).lstrip("-").isdigit() else nested_retcode
        raise MihoyoApiError(
            msg,
            code=int(code_val) if str(code_val).lstrip("-").isdigit() else None,
        )
    if nested_retcode not in (0, "0", None, 1, "1"):
        msg = _extract_error_text(data) or "操作失败"
        raise MihoyoApiError(
            msg,
            code=int(nested_retcode) if str(nested_retcode).lstrip("-").isdigit() else None,
        )
    return data


def create_mmt(
    *,
    action_type: str,
    account: str | None = None,
) -> dict[str, Any]:
    """申请人机验证任务。返回 mmt_key / 可选 gt。"""
    reason = (
        "user.mihoyo.com%2523%252Flogin%252Fpassword"
        if action_type == "login_by_password"
        else "user.mihoyo.com%2523%252Flogin%252Fcaptcha"
    )
    params: dict[str, Any] = {
        "scene_type": 1,
        "now": _now_ms(),
        "reason": reason,
        "action_type": action_type,
        "t": _now_ms(),
    }
    if account:
        params["account"] = account.strip()
    url = f"{ACCOUNT_API}/Api/create_mmt?{urlencode(params)}"
    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url, headers=_account_headers())
        payload = resp.json()
    data = _assert_account_ok(payload)
    mmt = data.get("mmt_data") if isinstance(data.get("mmt_data"), dict) else {}
    mmt_key = str(mmt.get("mmt_key") or "").strip()
    if not mmt_key:
        raise MihoyoApiError("无法获取人机验证任务")
    gt = str(mmt.get("gt") or "").strip()
    need = bool(data.get("mmt_type") == 1 and gt)
    return {
        "mmt_key": mmt_key,
        "captcha_id": gt or None,
        "need_geetest": need,
        "mmt_type": int(data.get("mmt_type") or 0),
    }


def send_login_sms(
    phone: str,
    *,
    geetest: str | dict[str, Any] | None = None,
    mmt_key: str | None = None,
) -> dict[str, Any]:
    phone = phone.strip()
    if not phone:
        raise MihoyoApiError("手机号不能为空")

    aigis = _aigis_from_geetest(geetest, mmt_key)
    body = {
        "area_code": rsa_encrypt("+86"),
        "mobile": rsa_encrypt(phone),
    }
    _passport_post(
        f"{PASSPORT_API}/account/ma-cn-verifier/verifier/createLoginCaptcha",
        device_id=_stable_device_id(phone),
        body=body,
        aigis=aigis,
    )
    return {
        "ok": True,
        "message": "验证码已发送",
        "mmt_key": (mmt_key or "").strip() or None,
    }


def _creds_from_login_ticket(
    *,
    login_ticket: str,
    account_id: str,
    cookie_extra: dict[str, str] | None = None,
) -> MihoyoCredentials:
    parts = {
        "login_ticket": login_ticket,
        "account_id": account_id,
        "account_id_v2": account_id,
        "ltuid": account_id,
        "ltuid_v2": account_id,
    }
    if cookie_extra:
        parts.update(cookie_extra)
    cookie = "; ".join(f"{k}={v}" for k, v in parts.items() if v)
    creds = MihoyoCredentials(
        cookie=cookie,
        login_ticket=login_ticket,
        account_id=account_id,
        ltuid=account_id,
        stuid=account_id,
    )
    return ensure_session(creds)


def login_with_sms(phone: str, captcha: str) -> MihoyoCredentials:
    phone = phone.strip()
    code = captcha.strip()
    if not phone or not code:
        raise MihoyoApiError("手机号或验证码不能为空")
    body = {
        "area_code": rsa_encrypt("+86"),
        "mobile": rsa_encrypt(phone),
        "action_type": SMS_ACTION_TYPE,
        "captcha": code,
    }
    try:
        data, set_cookies = _passport_post(
            f"{PASSPORT_API}/account/ma-cn-passport/app/loginByMobileCaptcha",
            device_id=_stable_device_id(phone),
            body=body,
        )
    except MihoyoNeedGeetest as exc:
        raise MihoyoApiError(
            "登录需要人机验证，请重新获取验证码后再试",
            code=exc.code,
        ) from exc
    return _creds_from_passport_login(data=data, set_cookies=set_cookies)


def login_with_password(
    account: str,
    password: str,
    *,
    geetest: str | dict[str, Any] | None = None,
    mmt_key: str | None = None,
) -> MihoyoCredentials:
    account = account.strip()
    password = password.strip()
    if not account or not password:
        raise MihoyoApiError("账号或密码不能为空")

    aigis = _aigis_from_geetest(geetest, mmt_key)
    body = {
        "account": rsa_encrypt(account),
        "password": rsa_encrypt(password),
    }
    data, set_cookies = _passport_post(
        f"{PASSPORT_API}/account/ma-cn-passport/app/loginByPassword",
        device_id=_stable_device_id(account),
        body=body,
        aigis=aigis,
    )
    return _creds_from_passport_login(data=data, set_cookies=set_cookies)


def create_qr_login(*, device_id: str | None = None) -> dict[str, str]:
    did = (device_id or uuid.uuid4().hex).strip()
    url = f"{PASSPORT_API}/account/ma-cn-passport/app/createQRLogin"
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = client.post(url, headers=_qr_passport_headers(device_id=did), json={})
            payload = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        raise MihoyoApiError("生成二维码失败，请稍后重试") from exc
    if not isinstance(payload, dict):
        raise MihoyoApiError("生成二维码失败：上游返回异常")
    if _passport_retcode(payload) != 0:
        raise MihoyoApiError(str(payload.get("message") or "生成二维码失败"))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    scan_url = str(data.get("url") or "").strip()
    ticket = str(data.get("ticket") or "").strip()
    if not scan_url or not ticket:
        raise MihoyoApiError("生成二维码失败：缺少 url / ticket")
    return {"device_id": did, "scan_url": scan_url, "ticket": ticket}


def query_qr_login(*, device_id: str, ticket: str) -> dict[str, Any]:
    url = f"{PASSPORT_API}/account/ma-cn-passport/app/queryQRLoginStatus"
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = client.post(
                url,
                headers=_qr_passport_headers(device_id=device_id),
                json={"ticket": ticket},
            )
            try:
                payload = resp.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise MihoyoApiError("扫码状态查询失败：上游返回异常") from exc
            set_cookies = _cookies_from_response(resp)
    except MihoyoApiError:
        raise
    except httpx.HTTPError as exc:
        raise MihoyoApiError("扫码状态查询失败，请稍后重试") from exc

    if not isinstance(payload, dict):
        raise MihoyoApiError("扫码状态查询失败：上游返回异常")
    retcode = _passport_retcode(payload, default=0)
    message = str(payload.get("message") or "")
    if retcode == -3501:
        return {"status": "expired", "message": message or "二维码已过期"}
    if retcode == -3505:
        return {"status": "cancelled", "message": message or "已取消扫码"}
    if retcode != 0:
        return {"status": "error", "message": message or "扫码状态异常"}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    status = str(data.get("status") or "Created")
    if status == "Created":
        return {"status": "waiting", "message": "请使用米游社 App 扫码"}
    if status == "Scanned":
        return {"status": "scanned", "message": "已扫码，请在 App 内确认"}
    if status != "Confirmed":
        return {"status": "waiting", "message": message or status}

    try:
        creds = _creds_from_qr_confirmed(data=data, set_cookies=set_cookies)
    except MihoyoApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("mihoyo qr confirmed credential build failed")
        raise MihoyoApiError("扫码确认成功但凭证解析失败，请刷新二维码重试") from exc
    return {"status": "ok", "message": "扫码登录成功", "creds": creds}


def _creds_from_qr_confirmed(
    *, data: dict[str, Any], set_cookies: dict[str, str]
) -> MihoyoCredentials:
    """App 扫码确认：优先取 tokens 中的 stoken + user_info.aid/mid。"""
    user = data.get("user_info") if isinstance(data.get("user_info"), dict) else {}
    aid = str(
        user.get("aid")
        or set_cookies.get("account_id_v2")
        or set_cookies.get("account_id")
        or set_cookies.get("ltuid_v2")
        or set_cookies.get("ltuid")
        or ""
    ).strip()
    mid = str(
        user.get("mid")
        or set_cookies.get("account_mid_v2")
        or set_cookies.get("ltmid_v2")
        or set_cookies.get("mid")
        or ""
    ).strip()
    tokens = data.get("tokens") if isinstance(data.get("tokens"), list) else []
    stoken = _stoken_from_qr_tokens(tokens)

    cookie_parts = {k: v for k, v in set_cookies.items() if v}
    if aid:
        cookie_parts.setdefault("account_id", aid)
        cookie_parts.setdefault("account_id_v2", aid)
        cookie_parts.setdefault("ltuid", aid)
        cookie_parts.setdefault("ltuid_v2", aid)
        cookie_parts.setdefault("stuid", aid)
    if mid:
        cookie_parts["mid"] = mid
        cookie_parts.setdefault("account_mid_v2", mid)
        cookie_parts.setdefault("ltmid_v2", mid)
    if stoken:
        cookie_parts["stoken"] = stoken

    login_ticket = str(cookie_parts.get("login_ticket") or "").strip()
    cookie_token = str(
        cookie_parts.get("cookie_token_v2")
        or cookie_parts.get("cookie_token")
        or ""
    ).strip()

    if stoken and aid:
        cookie = "; ".join(f"{k}={v}" for k, v in cookie_parts.items() if v)
        creds = MihoyoCredentials(
            cookie=cookie,
            account_id=aid,
            ltuid=aid,
            stuid=aid,
            stoken=stoken,
            mid=mid,
        )
        return _finalize_qr_creds(creds)

    if login_ticket and aid:
        return _creds_from_login_ticket(
            login_ticket=login_ticket,
            account_id=aid,
            cookie_extra=cookie_parts,
        )
    if cookie_token and aid:
        return _creds_from_cookie_token(
            aid=aid, cookie_token=cookie_token, extra=cookie_parts, mid=mid
        )
    if cookie_parts:
        cookie = "; ".join(f"{k}={v}" for k, v in cookie_parts.items())
        return bind_with_cookie(cookie)
    raise MihoyoApiError("扫码确认成功但未拿到登录凭证，请重试")


def _finalize_qr_creds(creds: MihoyoCredentials) -> MihoyoCredentials:
    """规范化凭证：补 mid/cookie_token，校验会话。"""
    working = _normalize_via_client(creds)
    if working.stoken.startswith("v2_") and not working.mid:
        raise MihoyoApiError("扫码未返回 mid，请刷新二维码重试")
    return ensure_session(working)


def _normalize_via_client(creds: MihoyoCredentials) -> MihoyoCredentials:
    from app.services.mihoyo_client import _normalize_creds

    return _normalize_creds(creds)


def _creds_from_cookie_token(
    *,
    aid: str,
    cookie_token: str,
    extra: dict[str, str],
    mid: str = "",
) -> MihoyoCredentials:
    """cookie_token → stoken（getMultiTokenByCookieToken）。"""
    cookie = "; ".join(
        f"{k}={v}"
        for k, v in {
            **extra,
            "account_id": aid,
            "account_id_v2": aid,
            "cookie_token": cookie_token,
            "cookie_token_v2": cookie_token,
            **({"mid": mid, "account_mid_v2": mid} if mid else {}),
        }.items()
        if v
    )
    url = (
        "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByCookieToken"
        f"?uid={aid}"
    )
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Cookie": cookie,
                },
            )
            payload = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        raise MihoyoApiError("无法用 cookie_token 换取 Stoken，请改用短信或密码登录") from exc
    if not isinstance(payload, dict) or _passport_retcode(payload) != 0:
        raise MihoyoApiError(
            str(payload.get("message") if isinstance(payload, dict) else "")
            or "无法用 cookie_token 换取 Stoken，请改用短信或密码登录"
        )
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = data.get("list") if isinstance(data.get("list"), list) else []
    stoken = ""
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").lower()
        if name == "stoken" or str(row.get("token_type") or "") in ("1", "3"):
            stoken = str(row.get("token") or "").strip()
            if name == "stoken" or str(row.get("token_type") or "") == "1":
                break
    if not stoken and rows and isinstance(rows[0], dict):
        stoken = str(rows[0].get("token") or "").strip()
    if not stoken:
        raise MihoyoApiError("无法获取 Stoken，请改用短信或密码登录")
    parts = parse_cookie_string(cookie)
    parts["stoken"] = stoken
    parts["stuid"] = aid
    if mid:
        parts["mid"] = mid
    cookie2 = "; ".join(f"{k}={v}" for k, v in parts.items())
    creds = MihoyoCredentials(
        cookie=cookie2,
        account_id=aid,
        ltuid=aid,
        stuid=aid,
        stoken=stoken,
        mid=mid,
    )
    return ensure_session(creds)
