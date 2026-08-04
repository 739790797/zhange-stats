from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.public_url import resolve_backend_base
from app.models.user import User
from app.services.auth_config import (
    load_auth_config,
    public_auth_config,
    save_auth_config,
)
from app.services.email import send_verification_email
from app.services.email_config import (
    load_email_config,
    public_email_config,
    save_email_config,
)
from app.services.integrations_config import (
    load_integrations,
    public_integrations,
    save_integrations,
)
from app.services.qq_oauth import qq_redirect_uri
from app.services.scheduler_runtime import register_scheduler_jobs

router = APIRouter(prefix="/settings", tags=["settings"])


class EmailSettingsOut(BaseModel):
    enabled: bool
    smtp_user: str
    smtp_from: str
    smtp_password: str = ""
    smtp_password_set: bool
    display_name: str
    smtp_host: str
    smtp_port: int
    encryption: str
    code_expire_minutes: int
    configured: bool


class EmailSettingsUpdate(BaseModel):
    enabled: bool = False
    smtp_user: str = ""
    smtp_from: str = ""
    smtp_password: str | None = None
    display_name: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(default=465, ge=1, le=65535)
    encryption: str = Field(default="SSL", pattern="^(SSL|STARTTLS|NONE)$")
    code_expire_minutes: int = Field(default=15, ge=1, le=1440)


class EmailTestRequest(BaseModel):
    to_email: EmailStr


class IntegrationsOut(BaseModel):
    steam_api_key: str = ""
    steam_api_key_set: bool
    qq_app_id: str
    qq_app_key: str = ""
    qq_app_key_set: bool
    qq_configured: bool
    steam_configured: bool
    qq_callback_url: str = ""


class IntegrationsUpdate(BaseModel):
    steam_api_key: str | None = None
    qq_app_id: str | None = None
    qq_app_key: str | None = None
    clear_steam_api_key: bool = False
    clear_qq_app_key: bool = False


class AuthSettingsOut(BaseModel):
    access_token_expire_minutes: int
    access_token_expire_days: float


class AuthSettingsUpdate(BaseModel):
    access_token_expire_minutes: int = Field(default=60 * 24 * 30, ge=5, le=60 * 24 * 365)


def _integrations_out(db: Session, request: Request) -> dict:
    data = public_integrations(load_integrations(db))
    backend = resolve_backend_base(request)
    try:
        data["qq_callback_url"] = qq_redirect_uri(backend) if backend else ""
    except Exception:  # noqa: BLE001
        data["qq_callback_url"] = (
            f"{backend}/api/auth/qq/callback" if backend else ""
        )
    return data


@router.get("/email", response_model=EmailSettingsOut)
def get_email_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    return public_email_config(load_email_config(db))


@router.put("/email", response_model=EmailSettingsOut)
def update_email_settings(
    body: EmailSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    current = load_email_config(db)
    if body.enabled:
        if not body.smtp_user.strip():
            raise HTTPException(status_code=400, detail="请填写用户名")
        if not body.smtp_host.strip():
            raise HTTPException(status_code=400, detail="请填写 SMTP 服务器地址")
        if not body.smtp_port:
            raise HTTPException(status_code=400, detail="请填写端口号")
        has_pwd = bool(
            (body.smtp_password and body.smtp_password.strip())
            or current.get("smtp_password")
        )
        if not has_pwd:
            raise HTTPException(status_code=400, detail="请填写密码")

    saved = save_email_config(db, body.model_dump())
    return public_email_config(saved)


@router.post("/email/test")
def test_email_settings(
    body: EmailTestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    cfg = load_email_config(db)
    if not cfg.get("enabled"):
        return {"ok": False, "message": "请先启用邮件通知器并保存配置"}
    result = send_verification_email(str(body.to_email), "000000", db=db)
    if result["mode"] == "smtp" and result["sent"]:
        return {"ok": True, "message": "测试邮件已发送"}
    if result["mode"] == "log":
        return {
            "ok": False,
            "message": "发送失败或配置不完整，详情见服务端日志",
        }
    return {"ok": False, "message": "发送失败，请检查 SMTP 配置"}


@router.get("/integrations", response_model=IntegrationsOut)
def get_integrations(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    return _integrations_out(db, request)


@router.put("/integrations", response_model=IntegrationsOut)
def update_integrations(
    body: IntegrationsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    from app.main import scheduler

    save_integrations(db, body.model_dump())
    # Steam Key 变更可能影响轮询任务是否应注册
    register_scheduler_jobs(scheduler, db, run_steam_once=False)
    return _integrations_out(db, request)


@router.get("/auth", response_model=AuthSettingsOut)
def get_auth_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    return public_auth_config(load_auth_config(db))


@router.put("/auth", response_model=AuthSettingsOut)
def update_auth_settings(
    body: AuthSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    saved = save_auth_config(db, body.model_dump())
    return public_auth_config(saved)
