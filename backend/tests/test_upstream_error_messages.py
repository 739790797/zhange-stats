"""平台 client：上游 4xx/5xx / 坏 JSON 转固定文案 + 状态码，正文只截断进日志（同一故障只打一次 WARNING）。"""

from __future__ import annotations

import logging

import httpx
import pytest

from app.core.biz_logging import clear_log_until_change
from app.services.adapters import steam as steam_adapter
from app.services.kujiequ import client as kujiequ
from app.services.skland import client as skland
from app.services.steam import resolve as steam_resolve
from app.services.taygedo import client as taygedo

SECRET_BODY = "<html>upstream stack trace: secret-internal-host</html>"


@pytest.fixture(autouse=True)
def _fresh_repeat_state():
    clear_log_until_change()
    yield
    clear_log_until_change()


def _reply(module, monkeypatch, status: int, *, text: str = "", json_body=None) -> list[str]:
    urls: list[str] = []

    def fake(method, url, **_kwargs):
        urls.append(url)
        request = httpx.Request(method, url)
        if json_body is not None:
            return httpx.Response(status, json=json_body, request=request)
        return httpx.Response(status, text=text, request=request)

    monkeypatch.setattr(module, "http_request", fake)
    return urls


def _warnings(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_skland_http_error_hides_the_body_and_logs_it_once(monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    _reply(skland, monkeypatch, 502, text=SECRET_BODY)

    for _ in range(2):
        with pytest.raises(skland.SklandApiError) as exc_info:
            skland._http_json("GET", skland.BINDING_URL)
        assert exc_info.value.message == "森空岛请求失败（HTTP 502）"
        assert exc_info.value.code == 502

    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "secret-internal-host" in warnings[0].getMessage()
    assert warnings[0].exc_info is None


def test_skland_business_error_on_4xx_is_returned_to_the_caller(monkeypatch) -> None:
    _reply(skland, monkeypatch, 401, json_body={"code": 10001, "message": "用户未登录"})

    assert skland._http_json("GET", skland.BINDING_URL) == {
        "code": 10001,
        "message": "用户未登录",
    }


@pytest.mark.parametrize("body", ["[1, 2]", "null", "not json at all"])
def test_skland_non_object_responses_raise(monkeypatch, body) -> None:
    _reply(skland, monkeypatch, 200, text=body)

    with pytest.raises(skland.SklandApiError, match="森空岛响应格式无效"):
        skland._http_json("GET", skland.BINDING_URL)


def test_skland_login_with_token_tolerates_null_data(monkeypatch) -> None:
    _reply(skland, monkeypatch, 200, json_body={"status": 0, "data": None})

    with pytest.raises(skland.SklandApiError, match="授权码为空"):
        skland.login_with_token("hg-token")


def test_skland_cred_response_with_list_data_is_rejected_cleanly(monkeypatch) -> None:
    replies = iter(
        [
            {"status": 0, "data": {"code": "grant-code"}},
            {"code": 0, "data": ["unexpected"]},
        ]
    )

    def fake(method, url, **_kwargs):
        return httpx.Response(200, json=next(replies), request=httpx.Request(method, url))

    monkeypatch.setattr(skland, "http_request", fake)

    with pytest.raises(skland.SklandApiError, match="Cred / 签名 Token 缺失"):
        skland.login_with_token("hg-token")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"data": {"content": " tok "}}', "tok"),
        ('{"data": null}', '{"data": null}'),
        ('{"data": ["x"]}', '{"data": ["x"]}'),
        ("plain-token", "plain-token"),
    ],
)
def test_skland_normalize_hg_token_handles_odd_json(raw, expected) -> None:
    assert skland.normalize_hg_token(raw) == expected


def test_kujiequ_http_error_hides_the_body(monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    _reply(kujiequ, monkeypatch, 500, text=SECRET_BODY)

    for _ in range(2):
        with pytest.raises(kujiequ.KujiequApiError) as exc_info:
            kujiequ._post_form("/user/mineV2", {})
        assert exc_info.value.message == "库街区请求失败（HTTP 500）"

    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "secret-internal-host" in warnings[0].getMessage()


def test_kujiequ_non_json_hides_the_body(monkeypatch) -> None:
    _reply(kujiequ, monkeypatch, 200, text=SECRET_BODY)

    with pytest.raises(kujiequ.KujiequApiError) as exc_info:
        kujiequ._post_form("/user/mineV2", {})
    assert exc_info.value.message == "库街区响应无效"


def test_taygedo_non_json_hides_the_body(monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    _reply(taygedo, monkeypatch, 200, text=SECRET_BODY)

    with pytest.raises(taygedo.TaygedoApiError) as exc_info:
        taygedo._http("GET", f"{taygedo.TAYGEDO_BASE}/apihub/api/getGameBindRole?token=t0")
    assert exc_info.value.message == "无效 JSON（HTTP 200）"
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "token=t0" not in warnings[0].getMessage()


def test_steam_resolve_vanity_hides_body_and_api_key(monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    _reply(steam_resolve, monkeypatch, 403, text=SECRET_BODY)

    with pytest.raises(RuntimeError) as exc_info:
        steam_resolve.resolve_vanity("api-key-123", "gaben")

    assert str(exc_info.value) == "Steam 自定义主页名解析失败（HTTP 403）"
    assert "api-key-123" not in caplog.text
    assert "secret-internal-host" in caplog.text


def test_steam_resolve_vanity_rejects_non_object_json(monkeypatch) -> None:
    _reply(steam_resolve, monkeypatch, 200, json_body=["nope"])

    with pytest.raises(RuntimeError, match="返回格式无效"):
        steam_resolve.resolve_vanity("key", "gaben")


def test_steam_api_http_error_hides_body_and_api_key(monkeypatch, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    _reply(steam_adapter, monkeypatch, 500, text=SECRET_BODY)
    adapter = steam_adapter.SteamAdapter("api-key-123")

    with pytest.raises(RuntimeError) as exc_info:
        adapter.fetch_summaries(["76561198000000001"])

    assert str(exc_info.value) == "Steam API 请求失败（HTTP 500）"
    assert "api-key-123" not in caplog.text


def test_steam_owned_games_bad_json_is_a_runtime_error(monkeypatch) -> None:
    _reply(steam_adapter, monkeypatch, 200, text="<html>maintenance</html>")
    adapter = steam_adapter.SteamAdapter("key")

    with pytest.raises(RuntimeError, match="返回无法解析"):
        adapter.fetch_owned_game_icons("76561198000000001")


def test_steam_owned_games_skips_malformed_entries(monkeypatch) -> None:
    _reply(
        steam_adapter,
        monkeypatch,
        200,
        json_body={
            "response": {
                "games": ["junk", {"appid": 570, "img_icon_url": "abc"}, {"appid": 10}]
            }
        },
    )

    icons = steam_adapter.SteamAdapter("key").fetch_owned_game_icons("76561198000000001")

    assert list(icons) == ["570"]
