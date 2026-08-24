"""米游社客户端单元测试（纯函数，无上游请求）。"""

from app.services.mihoyo_auth import (
    _passport_retcode,
    _stoken_from_qr_tokens,
    rsa_encrypt,
)
from app.services.mihoyo_client import (
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
    from app.services.mihoyo_client import generate_ds_web, generate_ds_x4

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
