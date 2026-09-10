"""管理员保存配置不再要求邮箱步进码。"""

from inspect import signature

from app.api.app_update import do_app_update
from app.api.profile.users_admin import delete_user, update_user
from app.api.settings import (
    update_auth_settings,
    update_email_settings,
    update_integrations,
    update_ocr_settings,
    update_platform_features,
)
from app.main import app
from app.schemas.auth import UserOut


def test_admin_writes_have_no_step_up_header() -> None:
    for fn in (
        update_auth_settings,
        update_email_settings,
        update_integrations,
        update_ocr_settings,
        update_platform_features,
        do_app_update,
        update_user,
        delete_user,
    ):
        assert "x_step_up_code" not in signature(fn).parameters


def test_step_up_removed_from_contract() -> None:
    assert "admin_step_up_required" not in UserOut.model_fields
    schema = app.openapi()
    paths = schema.get("paths") or {}
    assert not any("step-up" in path for path in paths)
    props = (
        ((schema.get("components") or {}).get("schemas") or {}).get("UserOut") or {}
    ).get("properties") or {}
    assert "admin_step_up_required" not in props
