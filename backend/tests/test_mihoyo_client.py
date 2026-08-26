"""米游社客户端单元测试（纯函数，无上游请求）。"""

import base64
import json

import pytest

from app.services.mihoyo.auth import (
    MihoyoNeedGeetest,
    _aigis_from_geetest,
    _build_aigis_header,
    _extract_error_text,
    _humanize_passport_error,
    _parse_aigis_challenge,
    _passport_retcode,
    _raise_need_geetest_or_error,
    _stoken_from_qr_tokens,
    rsa_encrypt,
    send_login_sms,
)
from app.services.mihoyo.client import (
    MihoyoApiError,
    generate_ds_discuss,
    generate_ds_sign,
    parse_cookie_string,
)


def test_parse_cookie_string_basic():
    kv = parse_cookie_string("ltuid=123; login_ticket=abc; account_id_v2=456")
    assert kv["ltuid"] == "123"
    assert kv["login_ticket"] == "abc"
    assert kv["account_id_v2"] == "456"


def test_generate_ds_sign_format():
    ds = generate_ds_sign()
    parts = ds.split(",")
    assert len(parts) == 3
    assert parts[0].isdigit()
    assert len(parts[1]) == 6
    assert len(parts[2]) == 32


def test_generate_ds_discuss_format():
    ds = generate_ds_discuss("2")
    parts = ds.split(",")
    assert len(parts) == 3
    assert parts[0].isdigit()
    assert parts[1].isdigit()
    assert len(parts[2]) == 32


def test_generate_ds_web_and_x4_format():
    from app.services.mihoyo.client import generate_ds_web, generate_ds_x4

    web = generate_ds_web()
    parts = web.split(",")
    assert len(parts) == 3
    assert parts[0].isdigit()
    assert len(parts[1]) == 6
    assert len(parts[2]) == 32

    x4 = generate_ds_x4()
    parts = x4.split(",")
    assert len(parts) == 3
    assert parts[0].isdigit()
    assert len(parts[1]) == 6
    assert len(parts[2]) == 32


def test_rsa_encrypt_password():
    out = rsa_encrypt("test-password")
    assert isinstance(out, str)
    assert len(out) > 20


def test_passport_retcode_treats_zero_as_success():
    """上游成功时 retcode=0；不可用 `x or default` 把 0 当成缺失。"""
    assert _passport_retcode({"retcode": 0}) == 0
    assert _passport_retcode({"retcode": "0"}) == 0
    assert _passport_retcode({}) == -1
    assert _passport_retcode({"retcode": None}) == -1
    assert _passport_retcode({"retcode": -3501}) == -3501


def test_stoken_from_qr_tokens():
    assert (
        _stoken_from_qr_tokens(
            [{"token_type": 1, "token": "v2_abc"}, {"token_type": 4, "token": "ck"}]
        )
        == "v2_abc"
    )
    assert _stoken_from_qr_tokens([{"name": "stoken", "token": "s1"}]) == "s1"
    assert _stoken_from_qr_tokens([]) == ""
    # 对齐 MHY_Scanner：无 type 时取 tokens[0]
    assert _stoken_from_qr_tokens([{"token": "first"}]) == "first"


def test_region_label_maps_hoyoverse_codes():
    from app.services.mihoyo.client import region_label

    assert region_label("cn_gf01") == "官服"
    assert region_label("cn_qd01") == "B服"
    assert region_label("prod_gf_cn") == "官服"
    assert region_label("prod_qd_cn") == "B服"
    assert region_label("prod_official_asia") == "亚服"
    assert region_label("android01") == "官服"
    assert region_label("bb01") == "B服"
    assert region_label("mystery_xx", "星穹列车") == "星穹列车"
    assert region_label("mystery_xx") == "未知"
    assert region_label("") == "未知"


def test_extract_error_text_unwraps_nested_json():
    raw = json.dumps(
        {"retcode": -464, "msg": "请使用最新版本产品/链接以获得更佳体验"},
        ensure_ascii=False,
    )
    assert _extract_error_text(raw) == "请使用最新版本产品/链接以获得更佳体验"
    assert (
        _humanize_passport_error({"code": 400, "data": raw})
        == "请使用最新版本产品/链接以获得更佳体验"
    )


def test_parse_aigis_challenge_reads_gt():
    header = json.dumps(
        {
            "session_id": "sess-1",
            "mmt_type": 1,
            "data": json.dumps({"gt": "captcha-id-abc", "challenge": "x"}),
        }
    )
    session_id, captcha_id = _parse_aigis_challenge(header)
    assert session_id == "sess-1"
    assert captcha_id == "captcha-id-abc"
    assert _parse_aigis_challenge("") == ("", "")
    assert _parse_aigis_challenge("not-json") == ("", "")


def test_build_aigis_header_session_and_b64():
    geetest = {
        "captcha_id": "cid",
        "lot_number": "lot",
        "pass_token": "tok",
        "gen_time": "1",
        "captcha_output": "out",
    }
    header = _build_aigis_header("sess-1", geetest)
    session_id, encoded = header.split(";", 1)
    assert session_id == "sess-1"
    decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert decoded["lot_number"] == "lot"
    assert _aigis_from_geetest(geetest, "sess-1") == header
    assert _aigis_from_geetest(geetest, None) is None


def test_raise_need_geetest_from_aigis_header():
    class FakeResp:
        def __init__(self) -> None:
            self.headers = {
                "x-rpc-aigis": json.dumps(
                    {
                        "session_id": "sess-9",
                        "data": json.dumps({"gt": "gt-id"}),
                    }
                )
            }

    with pytest.raises(MihoyoNeedGeetest) as excinfo:
        _raise_need_geetest_or_error(
            FakeResp(),  # type: ignore[arg-type]
            {"retcode": -3101, "message": "风险验证失败"},
        )
    assert excinfo.value.captcha_id == "gt-id"
    assert excinfo.value.mmt_key == "sess-9"


def test_send_login_sms_uses_passport_api(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url, *, device_id, body, aigis=None):
        captured["url"] = url
        captured["device_id"] = device_id
        captured["body"] = body
        captured["aigis"] = aigis
        return {"action_type": "login_by_mobile_captcha"}, {}

    monkeypatch.setattr(
        "app.services.mihoyo.auth._passport_post",
        fake_post,
    )
    out = send_login_sms("13800138000")
    assert out["ok"] is True
    assert "createLoginCaptcha" in str(captured["url"])
    assert captured["aigis"] is None
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["area_code"]
    assert body["mobile"]


def test_is_auth_failure():
    from app.services.mihoyo.client import is_auth_failure

    assert is_auth_failure(code=-100)
    assert is_auth_failure(code="-100")
    assert is_auth_failure(code=10001)
    assert is_auth_failure(message="登录失效")
    assert is_auth_failure(message="登录已失效，请重新绑定")
    assert is_auth_failure(message="Cookie 无效，请重新绑定")
    assert not is_auth_failure(code=0, message="OK")
    assert not is_auth_failure(message="网络超时")
    assert not is_auth_failure(message="今日已签到")


def test_game_biz_meta_matches_mihoyobbstools():
    from app.services.mihoyo_bbs import setting as bbs_setting
    from app.services.mihoyo.client import GAME_BIZ_META

    assert GAME_BIZ_META["hk4e_cn"]["act_id"] == bbs_setting.genshin_act_id == "e202311201442471"
    assert GAME_BIZ_META["hk4e_cn"]["sign_kind"] == "luna"
    assert GAME_BIZ_META["hk4e_cn"]["signgame"] == "hk4e"
    assert GAME_BIZ_META["hkrpg_cn"]["act_id"] == bbs_setting.honkai_sr_act_id
    assert GAME_BIZ_META["nap_cn"]["act_id"] == bbs_setting.zzz_act_id
    assert GAME_BIZ_META["nap_cn"]["sign_kind"] == "luna_zzz"
    assert GAME_BIZ_META["bh3_cn"]["act_id"] == bbs_setting.honkai3rd_act_id
    assert "bbs_sign" not in {m["sign_kind"] for m in GAME_BIZ_META.values()}


def test_compact_json_body_matches_ds2():
    from app.services.mihoyo.client import compact_json_body

    assert compact_json_body({"gids": "2"}) == '{"gids":"2"}'


def test_game_headers_include_signgame():
    from app.services.mihoyo.client import (
        GAME_BIZ_META,
        MihoyoCredentials,
        _game_headers_for_meta,
    )

    creds = MihoyoCredentials(
        cookie="ltuid=1; stoken=s; cookie_token=c", stuid="1", stoken="s"
    )
    genshin = _game_headers_for_meta(creds, GAME_BIZ_META["hk4e_cn"])
    assert genshin["x-rpc-signgame"] == "hk4e"
    assert genshin["Origin"] == "https://act.mihoyo.com"
    zzz = _game_headers_for_meta(creds, GAME_BIZ_META["nap_cn"])
    assert zzz["X-Rpc-Signgame"] == "zzz"


def test_bbs_headers_use_okhttp_and_stoken_cookie():
    from app.services.mihoyo.client import BBS_OKHTTP_UA, MihoyoCredentials, _bbs_headers

    creds = MihoyoCredentials(
        cookie="ltuid=1; stoken=v2_abc; mid=m1",
        stuid="1",
        stoken="v2_abc",
        mid="m1",
    )
    headers = _bbs_headers(creds)
    assert headers["User-Agent"] == BBS_OKHTTP_UA
    assert "stoken=v2_abc" in headers["Cookie"]
    assert "mid=m1" in headers["Cookie"]
    assert headers["x-rpc-verify_key"]


def test_call_with_cookie_refresh_retries_once(monkeypatch):
    from app.services.mihoyo.client import (
        MihoyoApiError,
        MihoyoCredentials,
        call_with_cookie_refresh,
    )

    creds = MihoyoCredentials(cookie="ltuid=1; stoken=s", stuid="1", stoken="s")
    calls = {"n": 0}

    def refresh(c, *, force=False):
        assert force is True
        c.cookie = "ltuid=1; stoken=s; cookie_token=new"
        return c

    monkeypatch.setattr("app.services.mihoyo.client.refresh_cookie_token", refresh)

    def fn(_c):
        calls["n"] += 1
        if calls["n"] == 1:
            raise MihoyoApiError("登录失效", code=-100)
        return "ok"

    assert call_with_cookie_refresh(creds, fn) == "ok"
    assert calls["n"] == 2
    assert "cookie_token=new" in creds.cookie


def test_welfare_urls_follow_mihoyobbstools():
    from app.services.mihoyo.attendance import _welfare_info_url, _welfare_sign_url
    from app.services.mihoyo_bbs import setting as bbs_setting
    from app.services.mihoyo.client import GAME_BIZ_META

    assert _welfare_info_url(GAME_BIZ_META["hk4e_cn"]) == bbs_setting.cn_game_is_signurl
    assert _welfare_sign_url(GAME_BIZ_META["hk4e_cn"]) == bbs_setting.cn_game_sign_url
    assert "luna" in _welfare_info_url(GAME_BIZ_META["hk4e_cn"])
    assert "bbs_sign_reward" not in _welfare_info_url(GAME_BIZ_META["hk4e_cn"])
    assert _welfare_info_url(GAME_BIZ_META["nap_cn"]) == bbs_setting.zzz_game_is_signurl
    assert "act-nap-api" in _welfare_sign_url(GAME_BIZ_META["nap_cn"])


def test_bbs_sign_url_has_no_signininfo():
    from app.services.mihoyo_bbs import setting as bbs_setting

    assert bbs_setting.bbs_sign_url.endswith("/apihub/app/api/signIn")
    assert not hasattr(bbs_setting, "bbs_sign_info_url")


def test_mall_urls_follow_mystool():
    from app.services.mihoyo_bbs import setting as bbs_setting

    assert bbs_setting.url_good_list.startswith("https://api-takumi.mihoyo.com/")
    assert bbs_setting.url_myb_points.startswith("https://api-takumi.mihoyo.com/")
    assert "homutreasure" in bbs_setting.url_myb_points
    assert bbs_setting.url_exchange.startswith("https://api-takumi.miyoushe.com/")
    assert bbs_setting.mall_point_sn == "myb"


def test_list_exchange_goods_uses_point_sn_and_partitions(monkeypatch):
    from app.services.mihoyo.client import MihoyoCredentials, list_exchange_goods

    calls: list[tuple[str, str, dict]] = []

    def fake_http(method, url, *, headers, params=None, json_body=None, raw_body=None):
        del headers, json_body, raw_body
        params = dict(params or {})
        calls.append((method, url, params))
        assert "api-takumi.mihoyo.com" in url
        assert params.get("point_sn") == "myb"
        game = params.get("game")
        page = params.get("page")
        if game == "" and page == 1:
            return {
                "retcode": 0,
                "data": {
                    "list": [],
                    "games": [{"name": "原神", "key": "hk4e"}],
                },
            }
        if game == "hk4e" and page == 1:
            return {
                "retcode": 0,
                "data": {
                    "list": [
                        {
                            "goods_id": "1001",
                            "goods_name": "原石",
                            "icon": "https://example.com/gem.png",
                            "price": 160,
                            "num": 60,
                            "game_biz": "hk4e_cn",
                            "game": "hk4e",
                            "unlimit": True,
                            "type": 1,
                            "account_cycle_limit": 0,
                            "account_exchange_count": 0,
                        }
                    ]
                },
            }
        return {"retcode": 0, "data": {"list": []}}

    monkeypatch.setattr("app.services.mihoyo.client._http_json", fake_http)
    items = list_exchange_goods(MihoyoCredentials(cookie="ltuid=1; cookie_token=c"))
    assert len(items) == 1
    assert items[0].game_code == "genshin"
    assert items[0].goods_img.endswith("gem.png")
    assert items[0].price == 160
    assert any(c[2].get("game") == "hk4e" for c in calls)


def test_get_points_balance_uses_homutreasure(monkeypatch):
    from app.services.mihoyo.client import MihoyoCredentials, get_points_balance

    def fake_http(method, url, *, headers, params=None, json_body=None, raw_body=None):
        del method, headers, json_body, raw_body
        assert "homutreasure" in url
        assert (params or {}).get("point_sn") == "myb"
        return {"retcode": 0, "data": {"points": 1234}}

    monkeypatch.setattr("app.services.mihoyo.client._http_json", fake_http)
    assert get_points_balance(MihoyoCredentials(cookie="ltuid=1; cookie_token=c")) == 1234


def test_exchange_goods_uid_is_game_role(monkeypatch):
    from app.services.mihoyo.client import MihoyoCredentials, exchange_goods

    captured: dict = {}

    def fake_http(method, url, *, headers, params=None, json_body=None, raw_body=None):
        del params, raw_body
        captured["method"] = method
        captured["url"] = url
        captured["body"] = json_body
        captured["headers"] = headers
        return {"retcode": 0, "data": {}}

    monkeypatch.setattr("app.services.mihoyo.client._http_json", fake_http)
    exchange_goods(
        MihoyoCredentials(cookie="ltuid=1; cookie_token=c", stuid="bbs-uid"),
        goods_id="1001",
        game_biz="hk4e_cn",
        region="cn_gf01",
        role_uid="123456789",
    )
    assert captured["method"] == "POST"
    assert "api-takumi.miyoushe.com" in captured["url"]
    assert captured["body"]["uid"] == "123456789"
    assert captured["body"]["game_biz"] == "hk4e_cn"
    assert captured["body"]["region"] == "cn_gf01"
    assert "game_uid" not in captured["body"]
    assert captured["headers"]["Origin"] == "https://webstatic.miyoushe.com"
