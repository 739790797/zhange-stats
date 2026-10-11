"""设置接口上限：验证码有效期最多 30 分钟，登录有效期最多 30 天（与服务层封顶一致）。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.settings import AuthSettingsUpdate, EmailSettingsUpdate
from app.core.security import MAX_ACCESS_TOKEN_MINUTES
from app.services.auth_config import load_auth_config, save_auth_config
from app.services.email_config import MAX_CODE_EXPIRE_MINUTES


def test_email_code_expiry_accepts_up_to_30_minutes() -> None:
    assert EmailSettingsUpdate(code_expire_minutes=MAX_CODE_EXPIRE_MINUTES).code_expire_minutes == 30
    assert EmailSettingsUpdate(code_expire_minutes=1).code_expire_minutes == 1


@pytest.mark.parametrize("minutes", [0, 31, 1440])
def test_email_code_expiry_out_of_range_is_rejected(minutes: int) -> None:
    with pytest.raises(ValidationError):
        EmailSettingsUpdate(code_expire_minutes=minutes)


def test_access_token_lifetime_accepts_up_to_30_days() -> None:
    assert MAX_ACCESS_TOKEN_MINUTES == 60 * 24 * 30
    body = AuthSettingsUpdate(access_token_expire_minutes=MAX_ACCESS_TOKEN_MINUTES)
    assert body.access_token_expire_minutes == MAX_ACCESS_TOKEN_MINUTES


@pytest.mark.parametrize("minutes", [4, MAX_ACCESS_TOKEN_MINUTES + 1, 60 * 24 * 365])
def test_access_token_lifetime_out_of_range_is_rejected(minutes: int) -> None:
    with pytest.raises(ValidationError):
        AuthSettingsUpdate(access_token_expire_minutes=minutes)


def test_stored_token_lifetime_is_clamped_to_the_same_ceiling() -> None:
    save_auth_config(None, {"access_token_expire_minutes": 60 * 24 * 365})
    assert load_auth_config()["access_token_expire_minutes"] == MAX_ACCESS_TOKEN_MINUTES
