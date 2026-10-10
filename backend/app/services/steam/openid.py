"""Steam OpenID 2.0：跳转登录并校验，用于确认绑定账号归属。"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import urllib.parse
from datetime import datetime, timedelta

import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings
from app.core.http_client import HttpRequestError, http_request
from app.core.key_derivation import PURPOSE_OAUTH_STATE, derive_key
from app.core.security import ALGORITHM
from app.core.timeutil import UTC, utc_now

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
OPENID_NS = "http://specs.openid.net/auth/2.0"
CLAIMED_ID_RE = re.compile(
    r"^https?://steamcommunity\.com/openid/id/(\d{17})$"
)
STATE_PURPOSE = "steam_openid_bind"
STATE_TTL_MINUTES = 15
# 断言里的 response_nonce 只认前后这么多秒内签发的；每个 nonce 只收一次
NONCE_MAX_AGE_SEC = 5 * 60
# OpenID 2.0 §10.1：这些字段必须在签名范围内，否则断言可被改写后重放
REQUIRED_SIGNED_FIELDS = frozenset(
    {"op_endpoint", "claimed_id", "identity", "return_to", "response_nonce", "assoc_handle"}
)
_NONCE_TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z")


class SteamOpenIdError(ValueError):
    """校验失败。reason 是回跳前端用的固定码；消息只进服务端日志，不进 URL。"""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _state_key() -> bytes:
    return derive_key(get_settings().SECRET_KEY, PURPOSE_OAUTH_STATE)


def _nonce_hash(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()


def new_openid_nonce() -> str:
    """发起时写进浏览器 Cookie，state 里只存其哈希：回调必须回到发起绑定的那个浏览器。"""
    return secrets.token_urlsafe(24)


def openid_nonce_matches(state_data: dict, cookie_value: str | None) -> bool:
    expected = str(state_data.get("nh") or "")
    given = (cookie_value or "").strip()
    if not expected or not given:
        return False
    return hmac.compare_digest(expected, _nonce_hash(given))


def create_openid_state(
    *,
    user_id: int,
    nonce: str,
    member_id: int | None = None,
    frontend: str | None = None,
    backend: str | None = None,
    expires_minutes: int = STATE_TTL_MINUTES,
) -> str:
    if not nonce:
        raise ValueError("无效的 Steam 登录状态")
    payload: dict = {
        "purpose": STATE_PURPOSE,
        "uid": user_id,
        "mid": member_id,
        "nh": _nonce_hash(nonce),
        "jti": secrets.token_urlsafe(16),
        "exp": utc_now() + timedelta(minutes=expires_minutes),
    }
    if frontend:
        payload["frontend"] = frontend.rstrip("/")
    if backend:
        payload["backend"] = backend.rstrip("/")
    return jwt.encode(payload, _state_key(), algorithm=ALGORITHM)


def decode_openid_state(token: str) -> dict:
    try:
        payload = jwt.decode(token, _state_key(), algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("Steam 登录状态已过期，请重试") from exc
    if payload.get("purpose") != STATE_PURPOSE:
        raise ValueError("无效的 Steam 登录状态")
    if not payload.get("uid") or not payload.get("nh") or not payload.get("jti"):
        raise ValueError("无效的 Steam 登录状态")
    return payload


def claim_openid_state(state_data: dict) -> bool:
    """state 只能用一次：同一个回调 URL 被重放、或拿同一 state 配别的断言时返回 False。"""
    from app.core.ephemeral_kv import ephemeral_incr

    jti = str(state_data.get("jti") or "")
    if not jti:
        return False
    key = f"zhange:steam-openid-state:{_nonce_hash(jti)[:32]}"
    return ephemeral_incr(key, ttl_sec=(STATE_TTL_MINUTES + 1) * 60) == 1


def build_steam_login_url(*, return_to: str, realm: str) -> str:
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_ENDPOINT}?{urllib.parse.urlencode(params)}"


def extract_steam_id64(claimed_id: str) -> str:
    m = CLAIMED_ID_RE.match((claimed_id or "").strip())
    if not m:
        raise ValueError("无法从 Steam 响应解析 SteamID")
    return m.group(1)


def _nonce_is_fresh(nonce: str) -> bool:
    m = _NONCE_TIME_RE.match(nonce or "")
    if not m:
        return False
    try:
        issued = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return False
    return abs((utc_now() - issued).total_seconds()) <= NONCE_MAX_AGE_SEC


def _claim_response_nonce(nonce: str) -> bool:
    from app.core.ephemeral_kv import ephemeral_incr

    key = f"zhange:steam-openid-nonce:{_nonce_hash(nonce)[:32]}"
    return ephemeral_incr(key, ttl_sec=2 * NONCE_MAX_AGE_SEC + 60) == 1


def _is_valid_response(text: str) -> bool:
    """check_authentication 的应答是 key:value 行（OpenID 2.0 §4.1.1）。"""
    for line in (text or "").splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "is_valid":
            return value.strip().lower() == "true"
    return False


def verify_steam_openid_assertion(query: dict[str, str], *, return_to: str) -> str:
    """校验 Steam OpenID 回调，成功返回 SteamID64；失败抛 SteamOpenIdError。

    return_to 是本次回调应有的完整地址（含 state）：发给别的站点的断言、
    或配了别的 state 的断言都对不上。response_nonce 限时且只收一次。
    """
    mode = query.get("openid.mode")
    if mode == "cancel":
        raise SteamOpenIdError("cancelled", "用户取消了 Steam 授权")
    if mode != "id_res":
        raise SteamOpenIdError("verify_failed", "Steam 未完成登录授权")
    if query.get("openid.ns") != OPENID_NS:
        raise SteamOpenIdError("verify_failed", "openid.ns 无效")
    endpoint = query.get("openid.op_endpoint") or ""
    if endpoint.rstrip("/") != STEAM_OPENID_ENDPOINT:
        raise SteamOpenIdError("verify_failed", "Steam 授权端点无效")
    if not return_to or query.get("openid.return_to") != return_to:
        raise SteamOpenIdError("verify_failed", "openid.return_to 与本次回调地址不符")

    claimed = query.get("openid.claimed_id") or ""
    if claimed != (query.get("openid.identity") or ""):
        raise SteamOpenIdError("verify_failed", "openid.claimed_id 与 openid.identity 不一致")
    try:
        steam_id = extract_steam_id64(claimed)
    except ValueError as exc:
        raise SteamOpenIdError("verify_failed", str(exc)) from exc

    signed = {f.strip() for f in (query.get("openid.signed") or "").split(",")}
    missing = REQUIRED_SIGNED_FIELDS - signed
    if missing:
        raise SteamOpenIdError(
            "verify_failed", f"openid.signed 缺少 {','.join(sorted(missing))}"
        )

    nonce = query.get("openid.response_nonce") or ""
    if not _nonce_is_fresh(nonce):
        raise SteamOpenIdError("expired", "openid.response_nonce 过期或格式无效")
    # 先占用再去 Steam 校验：并发重放同一断言时只有一个能走到 check_authentication
    if not _claim_response_nonce(nonce):
        raise SteamOpenIdError("replayed", "openid.response_nonce 已使用过")

    # 原样带回参数，仅把 mode 改为 check_authentication
    check: dict[str, str] = {}
    for key, value in query.items():
        if key.startswith("openid."):
            check[key] = value
    check["openid.mode"] = "check_authentication"

    body = urllib.parse.urlencode(check).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "zhange-stats/1.0",
        "Origin": "https://steamcommunity.com",
        "Referer": "https://steamcommunity.com/",
    }
    try:
        resp = http_request(
            "POST",
            STEAM_OPENID_ENDPOINT,
            content=body,
            headers=headers,
            timeout=20,
        )
        if resp.status_code in {403, 405}:
            url = f"{STEAM_OPENID_ENDPOINT}?{urllib.parse.urlencode(check)}"
            resp = http_request(
                "GET",
                url,
                headers={
                    "User-Agent": "zhange-stats/1.0",
                    "Origin": "https://steamcommunity.com",
                    "Referer": "https://steamcommunity.com/",
                },
                timeout=20,
            )
        if resp.status_code >= 400:
            raise SteamOpenIdError(
                "upstream_error", f"Steam 校验失败 HTTP {resp.status_code}"
            )
        text = resp.text
    except HttpRequestError as exc:
        raise SteamOpenIdError(
            "upstream_error", f"无法连接 Steam 校验服务: {type(exc).__name__}"
        ) from exc

    if not _is_valid_response(text):
        raise SteamOpenIdError("verify_failed", "Steam 登录校验未通过")

    return steam_id
