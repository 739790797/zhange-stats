from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.services.email import send_verification_email
from app.services.email_config import (
    load_email_config,
    public_email_config,
    save_email_config,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class EmailSettingsOut(BaseModel):
    enabled: bool
    smtp_user: str
    smtp_from: str
    smtp_password_set: bool
    display_name: str
    smtp_host: str
    smtp_port: int
    encryption: str
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


class EmailTestRequest(BaseModel):
    to_email: EmailStr


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
