"""口令哈希：直接用 bcrypt，存量 passlib `$2b$` 哈希照常校验；口令按原样存。"""

from __future__ import annotations

import pytest

from app.core.security import hash_password, verify_login_password, verify_password
from app.services.password_policy import PasswordPolicyError, validate_password

# passlib 1.7.4 `CryptContext(schemes=["bcrypt"])` 生成的存量哈希，换实现后不得失效
PASSLIB_HASHES = {
    "Str0ng-Enough!": "$2b$12$nyuFDwZZY1eYtuKXYBuJDezB.um.Og8vA/cs6W2zlEUd9dqpqS7py",
    "x" * 100: "$2b$12$ruSWfvJvxymxlh9NgYCbjeOu4/l.cg4aFRlm.IU5pqLKecEP4mcDW",
    "密码测试Passw0rd": "$2b$12$nIbbe6YwNNJnRW1rzi/k8uh8XB1uVBbHlFfAKvKTq8BKeoSTAPtl6",
    "  padded-Passw0rd  ": "$2b$12$./c1LaM4CIUC4GN5NnbMredcvGXG8XaXcAoNSfIjluWZRw.2x/D/C",
}


@pytest.mark.parametrize("plain", list(PASSLIB_HASHES))
def test_passlib_hashes_still_verify(plain: str) -> None:
    assert verify_password(plain, PASSLIB_HASHES[plain])


def test_passlib_hash_rejects_wrong_password() -> None:
    assert not verify_password("Str0ng-Enough?", PASSLIB_HASHES["Str0ng-Enough!"])


def test_passlib_long_password_truncates_at_72_bytes() -> None:
    stored = PASSLIB_HASHES["x" * 100]
    assert verify_password("x" * 72, stored)
    assert not verify_password("x" * 71, stored)


def test_new_hash_is_bcrypt_and_truncates_like_passlib() -> None:
    stored = hash_password("y" * 80)
    assert stored.startswith("$2b$")
    assert verify_password("y" * 72, stored)
    assert not verify_password("y" * 71, stored)


@pytest.mark.parametrize("stored", ["", "not-a-hash", "$2b$12$short", "$2b$99$" + "a" * 53])
def test_malformed_hash_is_false(stored: str) -> None:
    assert verify_password("anything", stored) is False


def test_login_falls_back_to_stripped_for_legacy_hashes() -> None:
    # 旧版改密 / 重置会先去掉首尾空白再存
    legacy = hash_password("padded-Passw0rd")
    assert not verify_password("  padded-Passw0rd  ", legacy)
    assert verify_login_password("  padded-Passw0rd  ", legacy)
    assert verify_login_password("padded-Passw0rd", legacy)


def test_login_keeps_padding_significant_for_new_hashes() -> None:
    stored = PASSLIB_HASHES["  padded-Passw0rd  "]
    assert verify_login_password("  padded-Passw0rd  ", stored)
    assert not verify_login_password("padded-Passw0rd", stored)
    assert not verify_login_password("   ", hash_password("x"))


def test_validate_password_keeps_input_as_typed() -> None:
    assert validate_password("  Abcdefg1!  ", min_length=8) == "  Abcdefg1!  "


@pytest.mark.parametrize("password", ["Abc1!" + "x" * 67, "密" * 24])
def test_validate_password_accepts_exactly_72_bytes(password: str) -> None:
    assert len(password.encode("utf-8")) == 72
    assert validate_password(password) == password


@pytest.mark.parametrize("password", ["Abc1!" + "x" * 68, "密" * 25, "Passw0rd-" + "密" * 22])
def test_validate_password_rejects_more_than_72_bytes(password: str) -> None:
    with pytest.raises(PasswordPolicyError, match="最多 72 字节"):
        validate_password(password)


@pytest.mark.parametrize(
    ("password", "kwargs", "message"),
    [
        ("        ", {}, "请设置密码"),
        ("Abcdefg1\x00!", {}, "空字符"),
        ("  password  ", {}, "过于简单"),
        ("  ADMIN123 ", {}, "过于简单"),
        (" alice2024 ", {"username": "alice2024"}, "用户名"),
        ("Ab1!xyz", {}, "至少 8 位"),
    ],
)
def test_validate_password_rejects(password: str, kwargs: dict, message: str) -> None:
    with pytest.raises(PasswordPolicyError) as exc:
        validate_password(password, min_length=8, **kwargs)
    assert message in str(exc.value)
