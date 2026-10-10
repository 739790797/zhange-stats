"""Steam OpenID 断言校验：return_to、签名字段、claimed_id、nonce 时效与一次性、check_authentication 应答。"""

from __future__ import annotations

import secrets
import urllib.parse
from datetime import timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
from app.core.http_client import HttpRequestError
from app.core.security import ALGORITHM
from app.core.timeutil import utc_now
from app.services.qq_oauth import PURPOSE_BIND, create_qq_oauth_state
from app.services.steam import openid as steam_openid
from app.services.steam.openid import (
    OPENID_NS,
    REQUIRED_SIGNED_FIELDS,
    STEAM_OPENID_ENDPOINT,
    SteamOpenIdError,
    claim_openid_state,
    create_openid_state,
    decode_openid_state,
    new_openid_nonce,
    openid_nonce_matches,
    verify_steam_openid_assertion,
)

SID = "76561198000000000"
RETURN_TO = "https://site.example/api/profile/steam/openid/callback?state=abc.def.ghi"
VALID = "ns:http://specs.openid.net/auth/2.0\nis_valid:true\n"


@pytest.fixture(autouse=True)
def _clean_kv(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    reset_ephemeral_kv_for_tests()
    yield
    reset_ephemeral_kv_for_tests()


class _Resp:
    def __init__(self, status_code: int = 200, text: str = VALID) -> None:
        self.status_code = status_code
        self.text = text


@pytest.fixture
def steam(monkeypatch):
    """假的 Steam 校验端：记录每次请求，按 responses 依次应答。"""
    calls: list[dict] = []
    responses: list[object] = []

    def fake(method: str, url: str, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        reply = responses.pop(0) if responses else _Resp()
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(steam_openid, "http_request", fake)
    return calls, responses


def _nonce(offset_sec: int = 0) -> str:
    issued = utc_now() + timedelta(seconds=offset_sec)
    return issued.strftime("%Y-%m-%dT%H:%M:%SZ") + secrets.token_hex(4)


def _assertion(**overrides: str | None) -> dict[str, str]:
    query: dict[str, str | None] = {
        "openid.ns": OPENID_NS,
        "openid.mode": "id_res",
        "openid.op_endpoint": STEAM_OPENID_ENDPOINT,
        "openid.claimed_id": f"https://steamcommunity.com/openid/id/{SID}",
        "openid.identity": f"https://steamcommunity.com/openid/id/{SID}",
        "openid.return_to": RETURN_TO,
        "openid.response_nonce": _nonce(),
        "openid.assoc_handle": "1234567890",
        "openid.signed": "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle",
        "openid.sig": "c2lnbmF0dXJl",
    }
    query.update(overrides)
    return {k: v for k, v in query.items() if v is not None}


def _reason(query: dict[str, str], return_to: str = RETURN_TO) -> str:
    with pytest.raises(SteamOpenIdError) as exc:
        verify_steam_openid_assertion(query, return_to=return_to)
    return exc.value.reason


def test_valid_assertion_is_checked_with_steam(steam) -> None:
    calls, _ = steam
    query = _assertion()
    assert verify_steam_openid_assertion(query, return_to=RETURN_TO) == SID
    assert len(calls) == 1 and calls[0]["method"] == "POST"
    assert calls[0]["url"] == STEAM_OPENID_ENDPOINT
    sent = dict(urllib.parse.parse_qsl(calls[0]["content"].decode()))
    assert sent == {**query, "openid.mode": "check_authentication"}


def test_get_fallback_when_post_is_refused(steam) -> None:
    calls, responses = steam
    responses.extend([_Resp(405, "no"), _Resp()])
    assert verify_steam_openid_assertion(_assertion(), return_to=RETURN_TO) == SID
    assert [c["method"] for c in calls] == ["POST", "GET"]
    assert "openid.mode=check_authentication" in calls[1]["url"]


@pytest.mark.parametrize(
    "return_to",
    [
        "https://other-site.example/auth/steam?state=abc.def.ghi",
        "https://site.example/api/profile/steam/openid/callback?state=attacker",
        "https://site.example/api/profile/steam/openid/callback",
        None,
    ],
)
def test_assertion_for_another_return_to_is_rejected(steam, return_to) -> None:
    calls, _ = steam
    assert _reason(_assertion(**{"openid.return_to": return_to})) == "verify_failed"
    assert calls == []


def test_empty_expected_return_to_rejects_everything(steam) -> None:
    assert _reason(_assertion(**{"openid.return_to": ""}), return_to="") == "verify_failed"


@pytest.mark.parametrize("field", sorted(REQUIRED_SIGNED_FIELDS))
def test_required_fields_must_be_signed(steam, field) -> None:
    calls, _ = steam
    signed = ",".join(f for f in ["signed", *sorted(REQUIRED_SIGNED_FIELDS)] if f != field)
    assert _reason(_assertion(**{"openid.signed": signed})) == "verify_failed"
    assert calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"openid.identity": "https://steamcommunity.com/openid/id/76561198000000001"},
        {"openid.identity": None},
        {
            "openid.claimed_id": "https://evil.example/openid/id/76561198000000000",
            "openid.identity": "https://evil.example/openid/id/76561198000000000",
        },
        {"openid.op_endpoint": "https://evil.example/openid/login"},
        {"openid.ns": "http://openid.net/signon/1.1"},
        {"openid.mode": "checkid_setup"},
    ],
)
def test_malformed_assertions_are_rejected(steam, overrides) -> None:
    calls, _ = steam
    assert _reason(_assertion(**overrides)) == "verify_failed"
    assert calls == []


def test_cancel_is_reported_as_cancelled(steam) -> None:
    assert _reason({"openid.mode": "cancel"}) == "cancelled"


@pytest.mark.parametrize(
    "make_nonce",
    [
        lambda: _nonce(-(steam_openid.NONCE_MAX_AGE_SEC + 30)),
        lambda: _nonce(steam_openid.NONCE_MAX_AGE_SEC + 30),
        lambda: "garbage",
        lambda: "",
    ],
    ids=["stale", "future", "garbage", "empty"],
)
def test_stale_future_or_malformed_nonce_is_rejected(steam, make_nonce) -> None:
    calls, _ = steam
    # 用例里现取时间：整套跑时收集到执行可能隔了好几分钟
    assert _reason(_assertion(**{"openid.response_nonce": make_nonce()})) == "expired"
    assert calls == []


def test_each_response_nonce_is_accepted_once(steam) -> None:
    calls, _ = steam
    query = _assertion()
    assert verify_steam_openid_assertion(query, return_to=RETURN_TO) == SID
    assert _reason(dict(query)) == "replayed"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "text",
    [
        "ns:http://specs.openid.net/auth/2.0\nis_valid:false\n",
        "",
        "<html>is_valid:true</html>",
        "ns:http://specs.openid.net/auth/2.0\nnot_is_valid:true\n",
        "is_valid:false\nis_valid:true\n",
    ],
)
def test_only_an_explicit_is_valid_true_passes(steam, text) -> None:
    _, responses = steam
    responses.append(_Resp(200, text))
    assert _reason(_assertion()) == "verify_failed"


def test_upstream_http_error_is_reported_without_details(steam) -> None:
    _, responses = steam
    responses.append(_Resp(502, "bad gateway"))
    assert _reason(_assertion()) == "upstream_error"


def test_upstream_network_error_keeps_only_the_error_class(steam) -> None:
    _, responses = steam
    responses.append(HttpRequestError("connect to https://steamcommunity.com?secret=1 failed"))
    with pytest.raises(SteamOpenIdError) as exc:
        verify_steam_openid_assertion(_assertion(), return_to=RETURN_TO)
    assert exc.value.reason == "upstream_error"
    assert "secret" not in str(exc.value)


def test_state_is_signed_with_the_derived_oauth_key() -> None:
    nonce = new_openid_nonce()
    state = create_openid_state(user_id=1, member_id=2, nonce=nonce, backend="https://site.example/")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(state, get_settings().SECRET_KEY, algorithms=[ALGORITHM])
    data = decode_openid_state(state)
    assert data["uid"] == 1 and data["mid"] == 2
    assert data["backend"] == "https://site.example"
    assert nonce not in state
    assert openid_nonce_matches(data, nonce)
    assert not openid_nonce_matches(data, new_openid_nonce())
    assert not openid_nonce_matches(data, None)


def test_tokens_from_other_purposes_are_not_steam_states() -> None:
    forged = jwt.encode(
        {"purpose": steam_openid.STATE_PURPOSE, "uid": 1, "nh": "x", "jti": "y",
         "exp": utc_now() + timedelta(minutes=5)},
        get_settings().SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(ValueError):
        decode_openid_state(forged)
    qq_state = create_qq_oauth_state(purpose=PURPOSE_BIND, nonce="n", user_id=1, member_id=2)
    with pytest.raises(ValueError):
        decode_openid_state(qq_state)


def test_state_requires_a_nonce() -> None:
    with pytest.raises(ValueError):
        create_openid_state(user_id=1, nonce="")


def test_state_can_be_claimed_once() -> None:
    data = decode_openid_state(create_openid_state(user_id=1, nonce=new_openid_nonce()))
    assert claim_openid_state(data) is True
    assert claim_openid_state(data) is False
    other = decode_openid_state(create_openid_state(user_id=1, nonce=new_openid_nonce()))
    assert claim_openid_state(other) is True
