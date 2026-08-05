"""QQ OAuth：未开通 UnionID 时不应阻断 openid 绑定。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.qq_oauth import QqOAuthError, exchange_code_for_profile


def test_exchange_falls_back_when_unionid_not_permitted() -> None:
    calls: list[str] = []

    def fake_get(url: str, timeout: int = 20) -> str:
        calls.append(url)
        if "oauth2.0/token" in url:
            return '{"access_token":"tok","expires_in":7776000}'
        if "oauth2.0/me" in url and "unionid=1" in url:
            raise QqOAuthError("CompanyID not set")
        if "oauth2.0/me" in url:
            return '{"client_id":"app","openid":"oid123"}'
        if "user/get_user_info" in url:
            return '{"ret":0,"nickname":"测试","figureurl_qq_1":"https://example.com/a.png"}'
        raise AssertionError(url)

    with (
        patch(
            "app.services.integrations_config.get_qq_credentials",
            return_value=("app", "key"),
        ),
        patch(
            "app.services.qq_oauth.qq_redirect_uri",
            return_value="https://x/api/auth/qq/callback",
        ),
        patch("app.services.qq_oauth._http_get_text", side_effect=fake_get),
    ):
        profile = exchange_code_for_profile("code1", backend="https://x")

    assert profile.openid == "oid123"
    assert profile.unionid is None
    assert profile.nickname == "测试"
    assert any("unionid=1" in u for u in calls)


def test_exchange_keeps_unionid_when_available() -> None:
    def fake_get(url: str, timeout: int = 20) -> str:
        if "oauth2.0/token" in url:
            return '{"access_token":"tok","expires_in":7776000}'
        if "oauth2.0/me" in url and "unionid=1" in url:
            return '{"client_id":"app","openid":"oid123","unionid":"uid999"}'
        if "oauth2.0/me" in url:
            return '{"client_id":"app","openid":"oid123"}'
        if "user/get_user_info" in url:
            return '{"ret":0,"nickname":"N"}'
        raise AssertionError(url)

    with (
        patch(
            "app.services.integrations_config.get_qq_credentials",
            return_value=("app", "key"),
        ),
        patch(
            "app.services.qq_oauth.qq_redirect_uri",
            return_value="https://x/api/auth/qq/callback",
        ),
        patch("app.services.qq_oauth._http_get_text", side_effect=fake_get),
    ):
        profile = exchange_code_for_profile("code1", backend="https://x")

    assert profile.openid == "oid123"
    assert profile.unionid == "uid999"
