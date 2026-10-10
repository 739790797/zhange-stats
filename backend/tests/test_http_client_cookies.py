"""进程级 httpx.Client 不得把上游 Set-Cookie 存进共享 jar（跨用户串号）。"""

from __future__ import annotations

import httpx
import pytest

from app.core import http_client
from app.core.http_client import http_request
from app.services.mihoyo.auth import _cookies_from_response

PASSPORT = "https://passport-api.mihoyo.com/account/ma-cn-passport/app"


@pytest.fixture
def seen_cookies(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str | None]]:
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("cookie")))
        if request.url.path.endswith("/loginByMobileCaptcha"):
            return httpx.Response(
                200,
                headers=[
                    ("set-cookie", "ltoken_v2=user-a-ltoken; Path=/; Domain=.mihoyo.com"),
                    ("set-cookie", "account_mid_v2=user-a-mid; Path=/; Domain=.mihoyo.com"),
                    ("set-cookie", "acw_tc=gateway; Path=/"),
                ],
                json={"retcode": 0, "data": {}},
            )
        if request.url.path == "/redirect":
            return httpx.Response(
                302,
                headers=[
                    ("location", "https://passport-api.mihoyo.com/landing"),
                    ("set-cookie", "hop=1; Path=/"),
                ],
            )
        return httpx.Response(200, json={"retcode": 0, "data": {}})

    client = http_client._new_client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http_client, "_client", client)
    yield seen
    client.close()


def test_set_cookie_of_user_a_not_sent_on_user_b_request(seen_cookies) -> None:
    resp_a = http_request("POST", f"{PASSPORT}/loginByMobileCaptcha", json={})
    http_request("POST", f"{PASSPORT}/queryQRLoginStatus", json={"ticket": "user-b"})

    assert seen_cookies[1] == ("/account/ma-cn-passport/app/queryQRLoginStatus", None)
    assert len(http_client.get_http_client().cookies.jar) == 0
    assert resp_a.cookies.get("ltoken_v2") == "user-a-ltoken"


def test_cookies_from_response_still_reads_set_cookie(seen_cookies) -> None:
    resp = http_request("POST", f"{PASSPORT}/loginByMobileCaptcha", json={})

    assert _cookies_from_response(resp) == {
        "ltoken_v2": "user-a-ltoken",
        "account_mid_v2": "user-a-mid",
    }


def test_explicit_cookie_header_still_sent(seen_cookies) -> None:
    http_request("POST", f"{PASSPORT}/loginByMobileCaptcha", json={})
    http_request(
        "GET",
        "https://api.kurobbs.com/user/mineV2",
        headers={"Cookie": "user_token=bob"},
    )

    assert seen_cookies[-1] == ("/user/mineV2", "user_token=bob")


def test_redirect_hop_does_not_replay_set_cookie(seen_cookies) -> None:
    resp = http_request("GET", "https://passport-api.mihoyo.com/redirect")

    assert resp.status_code == 200
    assert seen_cookies[-1] == ("/landing", None)
    assert len(http_client.get_http_client().cookies.jar) == 0
