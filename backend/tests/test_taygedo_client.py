"""塔吉多老虎通行证客户端：请求头合法性。"""

from app.services.taygedo.client import (
    LAOHU_SDK_VERSION,
    LAOHU_UA,
    TAYGEDO_APP_VER,
    TaygedoCredentials,
    native_app_headers,
)


def test_laohu_ua_has_no_leading_or_trailing_whitespace() -> None:
    """httpx/h11 会把首尾空白的 User-Agent 判成 Illegal header value，发短信会失败。"""
    assert LAOHU_UA == LAOHU_UA.strip()
    assert LAOHU_UA.startswith(f"LaohuSDK/{LAOHU_SDK_VERSION} ")
    assert "\r" not in LAOHU_UA
    assert "\n" not in LAOHU_UA


def test_native_app_headers_match_official_protocol() -> None:
    creds = TaygedoCredentials(
        uid="u100",
        device_id="dev",
        access_token="atok",
        refresh_token="rtok",
    )
    headers = native_app_headers(creds)
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
