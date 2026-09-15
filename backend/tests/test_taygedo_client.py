"""塔吉多老虎通行证客户端：请求头合法性、换票兜底。"""

from unittest.mock import patch

import pytest

from app.services.taygedo.client import (
    LAOHU_SDK_VERSION,
    LAOHU_UA,
    TAYGEDO_APP_VER,
    TaygedoApiError,
    TaygedoCredentials,
    native_app_headers,
    recover_session_tokens,
    refresh_access_token,
    relogin_with_laohu,
)


def _creds(**overrides: str) -> TaygedoCredentials:
    data = {
        "uid": "u100",
        "device_id": "dev",
        "access_token": "atok",
        "refresh_token": "rtok",
    }
    data.update(overrides)
    return TaygedoCredentials(**data)


def test_laohu_ua_has_no_leading_or_trailing_whitespace() -> None:
    """httpx/h11 会把首尾空白的 User-Agent 判成 Illegal header value，发短信会失败。"""
    assert LAOHU_UA == LAOHU_UA.strip()
    assert LAOHU_UA.startswith(f"LaohuSDK/{LAOHU_SDK_VERSION} ")
    assert "\r" not in LAOHU_UA
    assert "\n" not in LAOHU_UA


def test_native_app_headers_match_official_protocol() -> None:
    headers = native_app_headers(_creds())
    assert headers["Authorization"] == "atok"
    assert headers["appversion"] == TAYGEDO_APP_VER
    assert headers["platform"] == "android"
    assert headers["uid"] == "u100"
    assert headers["deviceid"] == "dev"
    parts = headers["ds"].split(",")
    assert len(parts) == 3
    assert parts[0].isdigit()
    assert len(parts[1]) == 8
    assert len(parts[2]) == 32


def test_refresh_access_token_uses_usercenter_protocol() -> None:
    captured: dict[str, object] = {}

    def fake_http(method, url, *, headers=None, body=None, timeout=25):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["body"] = body
        return 200, {
            "code": 0,
            "data": {
                "uid": "u100",
                "accessToken": "new-a",
                "refreshToken": "new-r",
            },
        }

    with patch("app.services.taygedo.client._http", side_effect=fake_http):
        out = refresh_access_token(
            _creds(phone="13800000000", laohu_token="ltok", laohu_user_id="42")
        )
    assert captured["method"] == "POST"
    assert str(captured["url"]).endswith("/usercenter/api/refreshToken")
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "rtok"
    assert headers["appVersion"] == TAYGEDO_APP_VER
    assert headers["uid"] == "u100"
    assert headers["deviceId"] == "dev"
    assert headers["platform"] == "android"
    parts = str(headers["ds"]).split(",")
    assert len(parts) == 3
    assert out.access_token == "new-a"
    assert out.refresh_token == "new-r"
    assert out.phone == "13800000000"
    assert out.laohu_token == "ltok"
    assert out.laohu_user_id == "42"


def test_relogin_with_laohu_requires_tiger_token() -> None:
    assert relogin_with_laohu(_creds()) is None


def test_recover_session_tokens_falls_back_to_laohu() -> None:
    creds = _creds(phone="13800000000", laohu_token="ltok", laohu_user_id="42")
    fresh = TaygedoCredentials(
        uid="u100",
        device_id="dev",
        access_token="a2",
        refresh_token="r2",
    )
    with (
        patch(
            "app.services.taygedo.client.refresh_access_token",
            side_effect=TaygedoApiError("refreshToken 已失效", code=402),
        ),
        patch(
            "app.services.taygedo.client._user_center_login",
            return_value=fresh,
        ) as login,
    ):
        out = recover_session_tokens(creds)
    login.assert_called_once_with("ltok", "42", "dev")
    assert out.access_token == "a2"
    assert out.refresh_token == "r2"
    assert out.phone == "13800000000"
    assert out.laohu_token == "ltok"
    assert out.laohu_user_id == "42"


def test_recover_session_tokens_without_laohu_reraises() -> None:
    with patch(
        "app.services.taygedo.client.refresh_access_token",
        side_effect=TaygedoApiError("refreshToken 已失效", code=402),
    ):
        with pytest.raises(TaygedoApiError, match="refreshToken"):
            recover_session_tokens(_creds())
