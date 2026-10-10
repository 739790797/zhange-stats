import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.public_url import resolve_backend_base
from app.core.security import MAX_ACCESS_TOKEN_MINUTES
from app.models.user import User
from app.services.auth_config import (
    enforce_single_admin_if_needed,
    load_auth_config,
    public_auth_config,
    save_auth_config,
)
from app.services.email import send_verification_email
from app.services.email_config import (
    MAX_CODE_EXPIRE_MINUTES,
    load_email_config,
    plaintext_auth_error,
    public_email_config,
    save_email_config,
)
from app.services.integrations_config import (
    get_minecraft_rcon_credentials,
    get_pelican_credentials,
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
from app.services.site_config import (
    ICP_BEIAN_HREF,
    load_site_config,
    public_site_config,
    save_site_config,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class EmailSettingsOut(BaseModel):
    """smtp_password 只写：响应恒为空串，是否已设置看 smtp_password_set。"""

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
    """smtp_password 空或缺省保留原口令；clear_smtp_password=true 才清空（优先于新值）。"""

    enabled: bool = False
    smtp_user: str = ""
    smtp_from: str = ""
    smtp_password: str | None = None
    clear_smtp_password: bool = False
    display_name: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(default=465, ge=1, le=65535)
    encryption: str = Field(default="SSL", pattern="^(SSL|STARTTLS|NONE)$")
    code_expire_minutes: int = Field(default=15, ge=1, le=MAX_CODE_EXPIRE_MINUTES)


class EmailTestRequest(BaseModel):
    to_email: EmailStr


class IntegrationsOut(BaseModel):
    """密钥字段只写：响应恒为空串，看 `*_set`；长 token 另给末 4 位 `*_hint`（不足 16 位为空）。"""

    steam_api_key: str = ""
    steam_api_key_set: bool
    steam_api_key_hint: str = ""
    qq_app_id: str
    qq_app_key: str = ""
    qq_app_key_set: bool
    qq_app_key_hint: str = ""
    qq_configured: bool
    steam_configured: bool
    qq_callback_url: str = ""
    github_token: str = ""
    github_token_set: bool = False
    github_token_hint: str = ""
    github_configured: bool = False
    pelican_base_url: str = ""
    pelican_client_token: str = ""
    pelican_client_token_set: bool = False
    pelican_client_token_hint: str = ""
    pelican_application_token: str = ""
    pelican_application_token_set: bool = False
    pelican_application_token_hint: str = ""
    pelican_server_uuid: str = ""
    pelican_configured: bool = False
    minecraft_rcon_host: str = ""
    minecraft_rcon_port: int = 25575
    minecraft_rcon_password: str = ""
    minecraft_rcon_password_set: bool = False
    minecraft_rcon_configured: bool = False
    minecraft_public_host: str = ""
    minecraft_public_port: int = 25565
    minecraft_public_configured: bool = False


class IntegrationsUpdate(BaseModel):
    """密钥字段空或缺省保留原值；`clear_<字段>`=true 才清空（优先于新值）。"""

    steam_api_key: str | None = None
    qq_app_id: str | None = None
    qq_app_key: str | None = None
    clear_steam_api_key: bool = False
    clear_qq_app_key: bool = False
    github_token: str | None = None
    clear_github_token: bool = False
    pelican_base_url: str | None = None
    pelican_client_token: str | None = None
    pelican_application_token: str | None = None
    pelican_server_uuid: str | None = None
    clear_pelican_client_token: bool = False
    clear_pelican_application_token: bool = False
    minecraft_rcon_host: str | None = None
    minecraft_rcon_port: int | None = Field(default=None, ge=0, le=65535)
    minecraft_rcon_password: str | None = None
    clear_minecraft_rcon_password: bool = False
    minecraft_public_host: str | None = None
    minecraft_public_port: int | None = Field(default=None, ge=0, le=65535)


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
        default=None, ge=5, le=MAX_ACCESS_TOKEN_MINUTES
    )
    min_password_length: int | None = Field(default=None, ge=6, le=72)
    reject_weak_admin_password: bool | None = None
    enforce_single_admin: bool | None = None


class SiteSettingsOut(BaseModel):
    icp_beian_no: str = ""
    icp_beian_href: str = ICP_BEIAN_HREF


class SiteSettingsUpdate(BaseModel):
    icp_beian_no: str = Field(default="", max_length=64)


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
        has_pwd = not body.clear_smtp_password and bool(
            (body.smtp_password and body.smtp_password.strip())
            or current.get("smtp_password")
        )
        if not has_pwd:
            raise HTTPException(status_code=400, detail="请填写密码")
        refused = plaintext_auth_error(body.smtp_host, body.encryption)
        if refused:
            raise HTTPException(status_code=400, detail=refused)

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
    refused = plaintext_auth_error(cfg["smtp_host"], cfg["encryption"])
    if refused:
        return {"ok": False, "message": refused}
    result = send_verification_email(str(body.to_email), "000000", db=db)
    if result["mode"] == "smtp" and result["sent"]:
        return {"ok": True, "message": "测试邮件已发送"}
    if result["mode"] == "log":
        return {
            "ok": False,
            "message": "发送失败或配置不完整，详情见服务端日志",
        }
    return {"ok": False, "message": "发送失败，请检查 SMTP 配置"}


class OcrEngineStatusOut(BaseModel):
    id: str
    label: str = ""
    installed: bool
    models_ready: bool


class OcrOptionOut(BaseModel):
    id: str
    label: str
    hint: str = ""


class OcrEngineMetaOut(BaseModel):
    id: str
    label: str
    hint: str = ""
    has_profiles: bool = False


class OcrUseCaseSettings(BaseModel):
    engines: list[str] = Field(default_factory=list)
    cross_check: bool = False


class OcrSettingsOut(BaseModel):
    paddle_profile: str
    engines: dict[str, bool]
    use_cases: dict[str, OcrUseCaseSettings]
    engine_status: list[OcrEngineStatusOut] = Field(default_factory=list)
    paddle_profiles: list[OcrOptionOut] = Field(default_factory=list)
    easyocr_profiles: list[OcrOptionOut] = Field(default_factory=list)
    engine_meta: list[OcrEngineMetaOut] = Field(default_factory=list)
    use_case_meta: list[OcrOptionOut] = Field(default_factory=list)
    engine_labels: dict[str, str] = Field(default_factory=dict)


class OcrSettingsUpdate(BaseModel):
    paddle_profile: str = "v5_server"
    engines: dict[str, bool] = Field(default_factory=dict)
    use_cases: dict[str, OcrUseCaseSettings] = Field(default_factory=dict)


def _ocr_settings_out(db: Session) -> dict[str, Any]:
    from app.services.ocr.config import load_ocr_config, public_ocr_config
    from app.services.ocr.runtime import engine_status

    cfg = load_ocr_config(db)
    return public_ocr_config(cfg, engine_status=engine_status(cfg.get("paddle_profile")))


@router.get("/ocr", response_model=OcrSettingsOut)
def get_ocr_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, Any]:
    return _ocr_settings_out(db)


@router.put("/ocr", response_model=OcrSettingsOut)
def update_ocr_settings(
    body: OcrSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, Any]:
    from app.services.ocr.config import OcrConfigError, public_ocr_config, save_ocr_config
    from app.services.ocr.runtime import engine_status

    try:
        saved = save_ocr_config(db, body.model_dump())
    except OcrConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return public_ocr_config(
        saved,
        engine_status=engine_status(saved.get("paddle_profile")),
    )


class IntegrationsStatusOut(BaseModel):
    """登录用户可见：仅布尔就绪态，不含密钥。"""

    steam_configured: bool
    qq_configured: bool
    pelican_configured: bool = False


@router.get("/integrations/status", response_model=IntegrationsStatusOut)
def get_integrations_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> IntegrationsStatusOut:
    steam = bool(get_steam_api_key(db))
    qq_id, qq_key = get_qq_credentials(db)
    pelican_url, pelican_token, pelican_uuid = get_pelican_credentials(db)
    return IntegrationsStatusOut(
        steam_configured=steam,
        qq_configured=bool(qq_id and qq_key),
        pelican_configured=bool(pelican_url and pelican_token and pelican_uuid),
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


class PelicanTestRequest(BaseModel):
    base_url: str = ""
    token: str | None = Field(default=None, max_length=512)
    server_uuid: str = ""


class PelicanTestResponse(BaseModel):
    ok: bool
    message: str
    server_name: str | None = None
    power_state: str | None = None


@router.post("/integrations/pelican-test", response_model=PelicanTestResponse)
def test_pelican_connection(
    body: PelicanTestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PelicanTestResponse:
    from app.services.minecraft.pelican import (
        PelicanError,
        get_resources,
        get_server,
        normalize_pelican_base_url,
        pelican_configured,
        power_state_from_resources,
    )

    saved_url, saved_token, saved_uuid = get_pelican_credentials(db)
    base = normalize_pelican_base_url(body.base_url) or saved_url
    token = (body.token or "").strip()
    # 已存 token 只发往已存面板：换地址必须重填，否则只写密钥能被测试接口带去任意主机
    if not token and base == saved_url:
        token = saved_token
    server_uuid = (body.server_uuid or "").strip() or saved_uuid
    if not pelican_configured(base, token, server_uuid):
        return PelicanTestResponse(ok=False, message="请填写 Panel 地址、Client Token 与 Server UUID")
    try:
        server = get_server(base, token, server_uuid)
        attrs = server.get("attributes") if isinstance(server.get("attributes"), dict) else {}
        name = str(attrs.get("name") or "") or None
        state = None
        try:
            res = get_resources(base, token, server_uuid)
            state = power_state_from_resources(res)
        except PelicanError:
            state = None
        return PelicanTestResponse(
            ok=True,
            message="已连接到 Pelican 上的这台服",
            server_name=name,
            power_state=state,
        )
    except PelicanError as exc:
        return PelicanTestResponse(ok=False, message=exc.message)


class MinecraftRconTestRequest(BaseModel):
    host: str = ""
    port: int = Field(default=0, ge=0, le=65535)
    password: str | None = Field(default=None, max_length=256)


class MinecraftRconTestResponse(BaseModel):
    ok: bool
    message: str


@router.post("/integrations/minecraft-rcon-test", response_model=MinecraftRconTestResponse)
def test_minecraft_rcon_connection(
    body: MinecraftRconTestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> MinecraftRconTestResponse:
    from app.services.minecraft.rcon import MinecraftRconError, query_list

    saved_host, saved_port, saved_password = get_minecraft_rcon_credentials(db)
    host = (body.host or "").strip() or saved_host
    port = int(body.port or 0)
    if port < 1 or port > 65535:
        port = saved_port
    if port < 1 or port > 65535:
        port = 25575
    password = (body.password or "").strip()
    if not password and host == saved_host:
        password = saved_password
    if not host or not password:
        return MinecraftRconTestResponse(ok=False, message="请填写 RCON 地址和密码")
    try:
        names = query_list(host, port, password)
    except MinecraftRconError as exc:
        return MinecraftRconTestResponse(ok=False, message=exc.message)
    except OSError as exc:
        return MinecraftRconTestResponse(ok=False, message=str(exc) or "无法连接 RCON")
    count = len(names)
    return MinecraftRconTestResponse(
        ok=True,
        message=f"已连通 RCON，当前 {count} 人在线" if count else "已连通 RCON",
    )


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


@router.get("/site/public", response_model=SiteSettingsOut)
def get_site_public(db: Session = Depends(get_db)) -> dict:
    """页脚备案号等公开站点信息（未登录可读）。"""
    return public_site_config(load_site_config(db))


@router.get("/site", response_model=SiteSettingsOut)
def get_site_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    return public_site_config(load_site_config(db))


@router.put("/site", response_model=SiteSettingsOut)
def update_site_settings(
    body: SiteSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    saved = save_site_config(db, body.model_dump())
    return public_site_config(saved)


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


class RuntimeEnvOut(BaseModel):
    """redis_url 只回 scheme://主机:端口/库号（不含账号、口令、查询串）；是否已配置看 *_set。"""

    app_env: str
    is_production: bool
    redis_url: str = ""
    redis_url_set: bool = False
    redis_password_set: bool = False
    cors_origins: str = ""
    cors_origin_regex: str = ""
    csp_enforce: bool = False
    trust_x_forwarded_for: bool = False
    rate_limit_enabled: bool = True
    db_engine: str = "sqlite"
    db_path: str = ""
    db_url: str = ""
    restart_required: bool = False
    # 由进程环境变量设定的字段名（如 app_env、db_url）：界面只读，PUT 改值返回 409
    env_locked: list[str] = Field(default_factory=list)


class RuntimeEnvUpdate(BaseModel):
    """redis_url 空或缺省保留原值；clear_redis_url=true 才清空（优先于新值）。

    回传的脱敏地址（不带账号口令）若与已存的主机、端口一致，沿用已存账号口令与查询串。
    """

    app_env: str | None = Field(default=None, max_length=32)
    redis_url: str | None = Field(default=None, max_length=512)
    clear_redis_url: bool = False
    cors_origins: str | None = Field(default=None, max_length=2000)
    cors_origin_regex: str | None = Field(default=None, max_length=2000)
    csp_enforce: bool | None = None
    trust_x_forwarded_for: bool | None = None
    rate_limit_enabled: bool | None = None
    db_engine: str | None = Field(default=None, max_length=16)
    db_path: str | None = Field(default=None, max_length=512)
    db_url: str | None = Field(default=None, max_length=2000)


_RUNTIME_ENV_FIELDS = {
    "app_env": "APP_ENV",
    "redis_url": "REDIS_URL",
    "cors_origins": "CORS_ORIGINS",
    "cors_origin_regex": "CORS_ORIGIN_REGEX",
    "csp_enforce": "CSP_ENFORCE",
    "trust_x_forwarded_for": "TRUST_X_FORWARDED_FOR",
    "rate_limit_enabled": "RATE_LIMIT_ENABLED",
}
_RUNTIME_DB_FIELDS = ("db_engine", "db_path", "db_url")
_REDIS_DEFAULT_PORT = 6379
_PRODUCTION_ENV_NAMES = ("production", "prod")


def _redis_target(url: str) -> tuple[urllib.parse.SplitResult, str, int] | None:
    """解析出 (parts, 主机, 端口)；没有主机（含 unix socket）或端口非法时返回 None。"""
    try:
        parts = urllib.parse.urlsplit((url or "").strip())
        port = parts.port or _REDIS_DEFAULT_PORT
    except ValueError:
        return None
    host = parts.hostname or ""
    if not host:
        return None
    return parts, host, port


def _redis_password_set(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit((url or "").strip())
    except ValueError:
        return False
    query = urllib.parse.parse_qs(parts.query)
    return bool(parts.password or query.get("password"))


def _mask_redis_url(url: str) -> str:
    """redis-py 也从查询串读 password=，所以查询串和账号口令一起去掉。"""
    target = _redis_target(url)
    if target is None:
        return ""
    parts, host, port = target
    netloc = f"[{host}]" if ":" in host else host
    return f"{parts.scheme}://{netloc}:{port}{parts.path}"


def _merge_redis_url(submitted: str, stored: str) -> str:
    """表单回传脱敏地址时补回已存账号口令与查询串；换了主机或端口则原样保存，已存口令不跟去别的服务器。"""
    text = (submitted or "").strip()
    new = _redis_target(text)
    old = _redis_target(stored)
    if new is None or old is None:
        return text
    new_parts, new_host, new_port = new
    old_parts, old_host, old_port = old
    if (new_host, new_port) != (old_host, old_port):
        return text
    if new_parts.username or new_parts.password or new_parts.query:
        return text
    userinfo = old_parts.netloc.rpartition("@")[0]
    netloc = f"{userinfo}@{new_parts.netloc}" if userinfo else new_parts.netloc
    return urllib.parse.urlunsplit(
        (new_parts.scheme, netloc, new_parts.path, old_parts.query, "")
    )


def _redis_canonical(url: str) -> str:
    target = _redis_target(url)
    if target is None:
        return (url or "").strip()
    parts, host, port = target
    db = parts.path.strip("/") or "0"
    return "|".join(
        (
            parts.scheme.lower(),
            parts.username or "",
            parts.password or "",
            host,
            str(port),
            db,
            parts.query,
        )
    )


def _runtime_env_locked() -> list[str]:
    """环境变量优先于 config/*.json（见 config._apply_app_json / resolve_database_url），写文件也不会生效。"""
    import os

    def _set(name: str) -> bool:
        return str(os.environ.get(name) or "").strip() != ""

    locked = [field for field, env in _RUNTIME_ENV_FIELDS.items() if _set(env)]
    if _set("DATABASE_URL"):
        locked.extend(_RUNTIME_DB_FIELDS)
    return locked


def _runtime_env_unchanged(field: str, value: Any, effective: dict[str, Any]) -> bool:
    current = effective.get(field)
    if isinstance(current, bool):
        return bool(value) == current
    a = str(value or "").strip()
    b = str(current or "").strip()
    if field == "app_env":
        return a.lower() == b.lower()
    if field == "redis_url":
        return _redis_canonical(a) == _redis_canonical(b)
    return a == b


def _runtime_env_out(*, restart_required: bool = False) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.core.file_config import load_database_settings

    s = get_settings()
    db = load_database_settings()
    redis_url = s.REDIS_URL or ""
    return {
        "app_env": s.APP_ENV,
        "is_production": s.is_production,
        "redis_url": _mask_redis_url(redis_url),
        "redis_url_set": bool(redis_url.strip()),
        "redis_password_set": _redis_password_set(redis_url),
        "cors_origins": s.CORS_ORIGINS or "",
        "cors_origin_regex": s.CORS_ORIGIN_REGEX or "",
        "csp_enforce": bool(s.CSP_ENFORCE),
        "trust_x_forwarded_for": bool(s.TRUST_X_FORWARDED_FOR),
        "rate_limit_enabled": bool(s.RATE_LIMIT_ENABLED),
        "db_engine": db["db_engine"],
        "db_path": db["db_path"],
        "db_url": db["db_url"],
        "restart_required": restart_required,
        "env_locked": _runtime_env_locked(),
    }


@router.get("/runtime-env", response_model=RuntimeEnvOut)
def get_runtime_env(_: User = Depends(require_admin)) -> dict[str, Any]:
    return _runtime_env_out()


@router.put("/runtime-env", response_model=RuntimeEnvOut)
def update_runtime_env(
    body: RuntimeEnvUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.core.file_config import (
        DatabaseSettingsError,
        load_database_settings,
        read_json,
        save_database_settings,
        write_json,
    )

    current = read_json("app") or {}
    payload = body.model_dump(exclude_unset=True)
    stored_redis = get_settings().REDIS_URL or ""
    if payload.pop("clear_redis_url", False):
        payload["redis_url"] = ""
    elif "redis_url" in payload:
        submitted = str(payload["redis_url"] or "").strip()
        if submitted:
            payload["redis_url"] = _merge_redis_url(submitted, stored_redis)
        else:
            payload.pop("redis_url")
    locked = set(_runtime_env_locked())
    if locked:
        effective = {**_runtime_env_out(), "redis_url": stored_redis}
        blocked = sorted(
            {
                _RUNTIME_ENV_FIELDS.get(field, "DATABASE_URL")
                for field, value in payload.items()
                if field in locked
                and not _runtime_env_unchanged(field, value, effective)
            }
        )
        if blocked:
            raise HTTPException(
                status_code=409,
                detail=f"{'、'.join(blocked)} 由服务器环境变量设定，请在服务器上修改后重启",
            )
        # 表单整页提交时锁定项原样带回，跳过即可
        payload = {k: v for k, v in payload.items() if k not in locked}
    if str(payload.get("app_env") or "").strip().lower() in _PRODUCTION_ENV_NAMES:
        from app.services.security_bootstrap import production_preflight_problems

        # 启动体检在 production 下会拒绝启动；先在这里拦住，免得重启后进不了管理端
        problems = production_preflight_problems(db)
        if problems:
            raise HTTPException(
                status_code=400,
                detail="生产环境启动体检未通过（保存后重启会拒绝启动）：" + " ".join(problems),
            )
    mapping = _RUNTIME_ENV_FIELDS
    restart = False
    for field, json_key in mapping.items():
        if field not in payload:
            continue
        current[json_key] = payload[field]
        restart = True
    if any(field in payload for field in mapping):
        env_name = str(current.get("APP_ENV") or "development").strip().lower()
        if env_name not in ("development", "production", "prod"):
            raise HTTPException(status_code=400, detail="APP_ENV 只能是 development 或 production")
        write_json("app", current)
    db_keys = ("db_engine", "db_path", "db_url")
    if any(key in payload for key in db_keys):
        before = load_database_settings()
        try:
            save_database_settings(
                engine=str(payload.get("db_engine") or before["db_engine"]),
                path=str(payload.get("db_path") if "db_path" in payload else before["db_path"]),
                url=str(payload.get("db_url") if "db_url" in payload else before["db_url"]),
            )
        except DatabaseSettingsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        restart = True
    get_settings.cache_clear()
    return _runtime_env_out(restart_required=restart)


class RuntimeConnTestOut(BaseModel):
    ok: bool
    message: str
    latency_ms: float | None = None


class RuntimeDatabaseTestIn(BaseModel):
    db_engine: str = Field(default="sqlite", max_length=16)
    db_path: str = Field(default="", max_length=512)
    db_url: str = Field(default="", max_length=2000)


class RuntimeRedisTestIn(BaseModel):
    redis_url: str = Field(default="", max_length=512)


@router.post("/runtime-env/database-test", response_model=RuntimeConnTestOut)
def test_runtime_database(
    body: RuntimeDatabaseTestIn,
    _: User = Depends(require_admin),
) -> RuntimeConnTestOut:
    from app.services.runtime_health import probe_database_settings

    result = probe_database_settings(
        engine=body.db_engine,
        path=body.db_path,
        url=body.db_url,
    )
    return RuntimeConnTestOut(
        ok=result.ok,
        message=result.message,
        latency_ms=result.latency_ms,
    )


@router.post("/runtime-env/redis-test", response_model=RuntimeConnTestOut)
def test_runtime_redis(
    body: RuntimeRedisTestIn,
    _: User = Depends(require_admin),
) -> RuntimeConnTestOut:
    from app.core.config import get_settings
    from app.services.runtime_health import probe_redis_url

    stored = get_settings().REDIS_URL or ""
    submitted = (body.redis_url or "").strip()
    result = probe_redis_url(_merge_redis_url(submitted, stored) if submitted else stored)
    return RuntimeConnTestOut(
        ok=result.ok,
        message=result.message,
        latency_ms=result.latency_ms,
    )

