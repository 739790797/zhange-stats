"""QQ 互联 OAuth2：授权跳转与 openid / 昵称解析。"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import timedelta

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.security import ALGORITHM
from app.core.timeutil import utc_now

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://graph.qq.com/oauth2.0/authorize"
TOKEN_URL = "https://graph.qq.com/oauth2.0/token"
OPENID_URL = "https://graph.qq.com/oauth2.0/me"
USER_INFO_URL = "https://graph.qq.com/user/get_user_info"
CALLBACK_JSONP_RE = re.compile(r"callback\s*\(\s*(\{.*\})\s*\)\s*;?", re.S)


class QqOAuthError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class QqProfile:
    openid: str
    unionid: str | None
    nickname: str | None
    avatar_url: str | None


def qq_redirect_uri(backend: str | None = None) -> str:
    base = (backend or "").rstrip("/")
    if not base:
        settings = get_settings()
        base = (settings.PUBLIC_BACKEND_URL or "").rstrip("/")
    if not base:
        raise QqOAuthError("无法确定回调地址（缺少访问 Host）")
    return f"{base}/api/auth/qq/callback"


def create_qq_oauth_state(
    *,
    user_id: int,
    member_id: int | None = None,
    frontend: str | None = None,
    backend: str | None = None,
    expires_minutes: int = 15,
) -> str:
    settings = get_settings()
    payload: dict = {
        "purpose": "qq_oauth_bind",
        "uid": user_id,
        "mid": member_id,
        "exp": utc_now() + timedelta(minutes=expires_minutes),
    }
    if frontend:
        payload["frontend"] = frontend.rstrip("/")
    if backend:
        payload["backend"] = backend.rstrip("/")
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_qq_oauth_state(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise QqOAuthError("QQ 登录状态已过期，请重试") from exc
    if payload.get("purpose") != "qq_oauth_bind":
        raise QqOAuthError("无效的 QQ 登录状态")
    if not payload.get("uid"):
        raise QqOAuthError("无效的 QQ 登录状态")
    return payload


def build_qq_authorize_url(*, state: str, backend: str | None = None) -> str:
    from app.services.integrations_config import get_qq_credentials

    app_id, app_key = get_qq_credentials()
    if not app_id:
        raise QqOAuthError("未配置 QQ_APP_ID")
    if not app_key:
        raise QqOAuthError("未配置 QQ_APP_KEY")
    params = {
        "response_type": "code",
        "client_id": app_id,
        "redirect_uri": qq_redirect_uri(backend),
        "state": state,
        "scope": "get_user_info",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _http_get_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "zhange-stats/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        raise QqOAuthError(f"QQ 接口 HTTP {exc.code}: {body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise QqOAuthError(f"无法连接 QQ 接口: {exc}") from exc


def _parse_token_body(text: str) -> dict[str, str]:
    text = (text or "").strip()
    if not text:
        raise QqOAuthError("QQ 换取 Token 返回为空")
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise QqOAuthError("QQ Token JSON 无效") from exc
        if data.get("error") or data.get("error_description"):
            raise QqOAuthError(
                str(data.get("error_description") or data.get("error") or "换取 Token 失败")
            )
        return {str(k): str(v) for k, v in data.items()}
    # access_token=...&expires_in=...
    parsed = urllib.parse.parse_qs(text, keep_blank_values=False)
    flat = {k: (v[0] if v else "") for k, v in parsed.items()}
    if flat.get("error") or flat.get("error_description"):
        raise QqOAuthError(
            flat.get("error_description") or flat.get("error") or "换取 Token 失败"
        )
    return flat


def _parse_jsonp_or_json(text: str) -> dict:
    text = (text or "").strip()
    m = CALLBACK_JSONP_RE.search(text)
    raw = m.group(1) if m else text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise QqOAuthError(f"QQ OpenID 响应无效: {text[:120]}") from exc
    if not isinstance(data, dict):
        raise QqOAuthError("QQ OpenID 响应格式错误")
    if data.get("error") or data.get("error_description"):
        raise QqOAuthError(
            str(data.get("error_description") or data.get("error") or "获取 OpenID 失败")
        )
    return data


def exchange_code_for_profile(code: str, *, backend: str | None = None) -> QqProfile:
    from app.services.integrations_config import get_qq_credentials

    app_id, app_key = get_qq_credentials()
    if not app_id or not app_key:
        raise QqOAuthError("未配置 QQ_APP_ID / QQ_APP_KEY")
    code = (code or "").strip()
    if not code:
        raise QqOAuthError("缺少授权 code")

    token_qs = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": app_key,
            "code": code,
            "redirect_uri": qq_redirect_uri(backend),
            "fmt": "json",
        }
    )
    token_data = _parse_token_body(_http_get_text(f"{TOKEN_URL}?{token_qs}"))
    access_token = token_data.get("access_token")
    if not access_token:
        raise QqOAuthError("QQ 未返回 access_token")

    me_qs = urllib.parse.urlencode(
        {"access_token": access_token, "fmt": "json", "unionid": "1"}
    )
    me = _parse_jsonp_or_json(_http_get_text(f"{OPENID_URL}?{me_qs}"))
    openid = str(me.get("openid") or "").strip()
    if not openid:
        raise QqOAuthError("QQ 未返回 openid")
    unionid = str(me.get("unionid") or "").strip() or None

    info_qs = urllib.parse.urlencode(
        {
            "access_token": access_token,
            "oauth_consumer_key": app_id,
            "openid": openid,
        }
    )
    nickname: str | None = None
    avatar_url: str | None = None
    try:
        info = json.loads(_http_get_text(f"{USER_INFO_URL}?{info_qs}"))
        if isinstance(info, dict) and int(info.get("ret") or 0) == 0:
            nickname = str(info.get("nickname") or "").strip() or None
            avatar_url = (
                str(
                    info.get("figureurl_qq_2")
                    or info.get("figureurl_qq_1")
                    or info.get("figureurl_2")
                    or info.get("figureurl_1")
                    or ""
                ).strip()
                or None
            )
        else:
            logger.warning("qq get_user_info failed: %s", info)
    except Exception:  # noqa: BLE001
        logger.exception("qq get_user_info error")

    return QqProfile(
        openid=openid,
        unionid=unionid,
        nickname=nickname,
        avatar_url=avatar_url,
    )
