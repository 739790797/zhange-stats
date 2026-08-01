"""Steam OpenID 2.0：跳转登录并校验，用于确认绑定账号归属。"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.security import ALGORITHM
from app.core.timeutil import utc_now

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
CLAIMED_ID_RE = re.compile(
    r"^https?://steamcommunity\.com/openid/id/(\d{17})$"
)


def create_openid_state(
    *,
    user_id: int,
    member_id: int | None = None,
    expires_minutes: int = 15,
) -> str:
    settings = get_settings()
    payload = {
        "purpose": "steam_openid_bind",
        "uid": user_id,
        "mid": member_id,
        "exp": utc_now() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_openid_state(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Steam 登录状态已过期，请重试") from exc
    if payload.get("purpose") != "steam_openid_bind":
        raise ValueError("无效的 Steam 登录状态")
    if not payload.get("uid"):
        raise ValueError("无效的 Steam 登录状态")
    return payload


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


def verify_steam_openid_assertion(query: dict[str, str]) -> str:
    """校验 Steam OpenID 回调，成功返回 SteamID64。"""
    mode = query.get("openid.mode")
    if mode != "id_res":
        raise ValueError("Steam 未完成登录授权")

    claimed = query.get("openid.claimed_id") or query.get("openid.identity") or ""
    steam_id = extract_steam_id64(claimed)

    endpoint = query.get("openid.op_endpoint") or ""
    if endpoint.rstrip("/") != STEAM_OPENID_ENDPOINT:
        raise ValueError("Steam 授权端点无效")

    # 原样带回参数，仅把 mode 改为 check_authentication
    check: dict[str, str] = {}
    for key, value in query.items():
        if key.startswith("openid."):
            check[key] = value
    check["openid.mode"] = "check_authentication"

    body = urllib.parse.urlencode(check).encode("utf-8")
    req = urllib.request.Request(
        STEAM_OPENID_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "zhange-stats/1.0",
            "Origin": "https://steamcommunity.com",
            "Referer": "https://steamcommunity.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        # 部分环境 POST 403，改试 GET
        if exc.code in {403, 405}:
            url = f"{STEAM_OPENID_ENDPOINT}?{urllib.parse.urlencode(check)}"
            get_req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "zhange-stats/1.0",
                    "Origin": "https://steamcommunity.com",
                    "Referer": "https://steamcommunity.com/",
                },
            )
            with urllib.request.urlopen(get_req, timeout=20) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        else:
            raise ValueError(f"Steam 校验失败 HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"无法连接 Steam 校验服务: {exc}") from exc

    if "is_valid:true" not in text.replace(" ", "").lower():
        raise ValueError("Steam 登录校验未通过")

    return steam_id
