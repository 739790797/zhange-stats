"""塔吉多老虎通行证客户端：请求头合法性。"""

from app.services.taygedo.client import LAOHU_SDK_VERSION, LAOHU_UA


def test_laohu_ua_has_no_leading_or_trailing_whitespace() -> None:
    """httpx/h11 会把首尾空白的 User-Agent 判成 Illegal header value，发短信会失败。"""
    assert LAOHU_UA == LAOHU_UA.strip()
    assert LAOHU_UA.startswith(f"LaohuSDK/{LAOHU_SDK_VERSION} ")
    assert "\r" not in LAOHU_UA
    assert "\n" not in LAOHU_UA
