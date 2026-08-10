from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.public_url import resolve_backend_base
from app.models.user import User
from app.services.auth_config import (
    enforce_single_admin_if_needed,
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
    get_napcat_credentials,
    get_qq_credentials,
    get_steam_api_key,
    load_integrations,
    public_integrations,
    save_integrations,
)
from app.services.platform_features import (
    JOB_FEATURE_IDS,
    build_feature_tree,
    effective_features,
    is_feature_enabled_from_flags,
    load_feature_flags,
    save_feature_flags,
)
from app.services.qq_oauth import qq_redirect_uri
from app.services.scheduler_config import save_scheduler_config
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
    napcat_base_url: str = ""
    napcat_token: str = ""
    napcat_token_set: bool = False
    napcat_configured: bool = False
    github_token: str = ""
    github_token_set: bool = False
    github_configured: bool = False


class IntegrationsUpdate(BaseModel):
    steam_api_key: str | None = None
    qq_app_id: str | None = None
    qq_app_key: str | None = None
    clear_steam_api_key: bool = False
    clear_qq_app_key: bool = False
    napcat_base_url: str | None = None
    napcat_token: str | None = None
    clear_napcat_token: bool = False
    github_token: str | None = None
    clear_github_token: bool = False


class AuthAdminBrief(BaseModel):
    id: int
    username: str
    display_name: str
    email: str | None = None
    weak_password: bool = False


class AuthSettingsOut(BaseModel):
    access_token_expire_minutes: int
    access_token_expire_days: float
    min_password_length: int = 8
    reject_weak_admin_password: bool | None = None
    reject_weak_admin_password_effective: bool = False
    enforce_single_admin: bool = False
    app_env: str = "development"
    is_production: bool = False
    admins: list[AuthAdminBrief] = Field(default_factory=list)
    weak_password_checked: bool = False


class AuthSettingsUpdate(BaseModel):
    access_token_expire_minutes: int | None = Field(
        default=None, ge=5, le=60 * 24 * 365
    )
    min_password_length: int | None = Field(default=None, ge=6, le=72)
    reject_weak_admin_password: bool | None = None
    enforce_single_admin: bool | None = None


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


class IntegrationsStatusOut(BaseModel):
    """登录用户可见：仅布尔就绪态，不含密钥。"""

    steam_configured: bool
    qq_configured: bool
    napcat_configured: bool


@router.get("/integrations/status", response_model=IntegrationsStatusOut)
def get_integrations_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> IntegrationsStatusOut:
    steam = bool(get_steam_api_key(db))
    qq_id, qq_key = get_qq_credentials(db)
    napcat_url, napcat_token = get_napcat_credentials(db)
    return IntegrationsStatusOut(
        steam_configured=steam,
        qq_configured=bool(qq_id and qq_key),
        napcat_configured=bool(napcat_url and napcat_token),
    )


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
    from app.services.app_updator import invalidate_check_cache

    save_integrations(db, body.model_dump())
    # Steam Key 变更可能影响轮询任务是否应注册
    register_scheduler_jobs(scheduler, db, run_steam_once=False)
    invalidate_check_cache()
    return _integrations_out(db, request)


@router.get("/auth", response_model=AuthSettingsOut)
def get_auth_settings(
    check_weak: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    # check_weak 会触发 bcrypt 字典探测；首屏默认跳过，由前端异步/手动开启
    return public_auth_config(
        load_auth_config(db),
        db=db,
        check_weak_passwords=check_weak,
    )


@router.put("/auth", response_model=AuthSettingsOut)
def update_auth_settings(
    body: AuthSettingsUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> dict:
    payload = body.model_dump(exclude_unset=True)
    saved = save_auth_config(db, payload)
    if saved.get("enforce_single_admin"):
        enforce_single_admin_if_needed(db, keep_user_id=current.id)
        db.commit()
    return public_auth_config(saved, db=db, check_weak_passwords=False)


class PlatformFeatureNodeOut(BaseModel):
    id: str
    name: str
    kind: str
    enabled: bool
    effective: bool
    parent_effective: bool = True
    reserved: bool = False
    job_id: str | None = None
    schedule: str | None = None
    interval_minutes: int | None = None
    hour: int | None = None
    minute: int | None = None
    children: list["PlatformFeatureNodeOut"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


PlatformFeatureNodeOut.model_rebuild()


class PlatformFeaturesOut(BaseModel):
    raw: dict[str, bool]
    effective: dict[str, bool]
    tree: list[PlatformFeatureNodeOut]


class PlatformFeatureJobUpdate(BaseModel):
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)


class PlatformFeaturesUpdate(BaseModel):
    features: dict[str, bool] = Field(default_factory=dict)
    jobs: dict[str, PlatformFeatureJobUpdate] = Field(default_factory=dict)


def _platform_features_payload(db: Session) -> dict[str, Any]:
    return {
        "raw": load_feature_flags(db),
        "effective": effective_features(db),
        "tree": build_feature_tree(db),
    }


@router.get("/platform-features", response_model=PlatformFeaturesOut)
def get_platform_features_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, Any]:
    """管理端：完整树 + raw / effective 开关。"""
    return _platform_features_payload(db)


@router.get("/platform-features/effective", response_model=dict[str, bool])
def get_platform_features_effective(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    """登录用户可见的生效功能开关（侧栏 / 页面用）。"""
    return effective_features(db)


@router.put("/platform-features", response_model=PlatformFeaturesOut)
def update_platform_features(
    body: PlatformFeaturesUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, Any]:
    from app.main import scheduler

    try:
        flags = (
            save_feature_flags(db, body.features, commit=False)
            if body.features
            else load_feature_flags(db)
        )

        job_payload: dict[str, Any] = {}
        for job_id, item in body.jobs.items():
            data = item.model_dump(exclude_none=True)
            # 系统级 enabled 只由功能开关决定，忽略客户端传入
            data.pop("enabled", None)
            if data:
                job_payload[job_id] = data

        for job_id, feature_id in JOB_FEATURE_IDS.items():
            entry = job_payload.setdefault(job_id, {})
            entry["enabled"] = is_feature_enabled_from_flags(flags, feature_id)

        if job_payload:
            save_scheduler_config(db, {"jobs": job_payload}, commit=False)

        db.commit()
    except Exception:
        db.rollback()
        raise

    register_scheduler_jobs(scheduler, db, run_steam_once=False)
    return _platform_features_payload(db)
