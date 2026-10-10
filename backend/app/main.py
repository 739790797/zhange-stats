from contextlib import asynccontextmanager
import asyncio
import logging
import time
from mimetypes import guess_type
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.api import articles, auth, exilium, guides, jobs, kujiequ, members, mihoyo, profile, setup, skland, steam, taygedo
from app.api import app_update as app_update_api
from app.api import client_errors as client_errors_api
from app.api import rum as rum_api
from app.api import files as files_api
from app.api import runtime_health as runtime_health_api
from app.api import runtime_logs as runtime_logs_api
from app.api import settings as settings_api
from app.core.body_limit import MULTIPART_SLACK_BYTES, BodyLimitMiddleware
from app.core.http_headers import SecurityHeadersMiddleware
from app.core.config import get_settings
from app.core.cors import resolve_cors_origin_regex
from app.core.database import engine
from app.core.file_config import database_is_configured, ensure_config_dir
from app.core.http_client import close_http_client
from app.core.migrate import run_migrations
from app.core.paths import (
    cleanup_legacy_install_tree,
    hydrate_legacy_runtime,
    migrate_runtime_layout,
    resolve_install_dir,
    resolve_runtime_path,
)
from app.core.runtime_cache import pin_library_cache_env
from app.core.request_log_middleware import RequestLogMiddleware
from app.core.runtime_log_buffer import install_runtime_log_buffer
from app.core.setup_middleware import SetupRequiredMiddleware
from app.core.startup import run_post_database_startup, start_background_services
from app.services import avatar_store
from app.services import file_manager as file_manager_svc
from app.services.articles import store as article_store
from app.services.articles.texteller import MAX_RECOGNIZE_BYTES as MATH_RECOGNIZE_MAX_BYTES
from app.services.minecraft import files as minecraft_files_svc
from app.services.tarkov.key_ocr import MAX_RECOGNIZE_BYTES as TARKOV_OCR_MAX_BYTES
from app.models import arknights as _arknights  # noqa: F401
from app.models import arknights_rogue as _arknights_rogue  # noqa: F401
from app.models import exilium as _exilium  # noqa: F401
from app.models import kujiequ as _kujiequ  # noqa: F401
from app.models import mihoyo as _mihoyo  # noqa: F401
from app.models import job_run as _job_run  # noqa: F401
from app.models import member as _member  # noqa: F401
from app.models import play_session as _play_session  # noqa: F401
from app.models import presence_segment as _presence_segment  # noqa: F401
from app.models import register_challenge as _register_challenge  # noqa: F401
from app.models import skland as _skland  # noqa: F401
from app.models import steam_app as _steam_app  # noqa: F401
from app.models import system_config as _system_config  # noqa: F401
from app.models import tarkov as _tarkov  # noqa: F401
from app.models import minecraft as _minecraft  # noqa: F401
from app.models import taygedo as _taygedo  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.models import articles as _articles  # noqa: F401
from app.models import user_files as _user_files  # noqa: F401
from app.models import rum as _rum  # noqa: F401

logger = logging.getLogger("zhange.startup")
scheduler = BackgroundScheduler()
install_runtime_log_buffer()

_HEALTH_DB_TTL_SEC = 1.0
_health_db_ok: bool | None = None
_health_db_at = 0.0


class ImmutableStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


_ACTIVE_UPLOAD_TYPES = frozenset({"text/xml", "text/xsl", "application/xml"})
# 只在上传文件被当作顶层文档打开时生效（<img> 引用不受影响）；浏览器图片 / PDF / 纯文本查看器靠 img-src 与内联样式照常显示
UPLOAD_CSP = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"


def _is_active_media_type(media_type: str) -> bool:
    mt = media_type.lower()
    return (
        mt in _ACTIVE_UPLOAD_TYPES
        or mt.endswith("+xml")
        or "html" in mt
        or "javascript" in mt
        or "ecmascript" in mt
    )


class UploadStaticFiles(StaticFiles):
    """用户上传目录：目录由 lifespan 创建（import 不落盘）；HTML/SVG/XML/JS 一律 404，其余带沙箱 CSP，不从站点源跑脚本。"""

    def __init__(self, directory: Path, *, cache_control: str) -> None:
        super().__init__(directory=str(directory), check_dir=False)
        self._cache_control = cache_control

    async def check_config(self) -> None:
        # 目录缺失（未跑 lifespan）按 404 处理，不抛 500
        return None

    def file_response(self, full_path, stat_result, scope, status_code=200):  # type: ignore[override]
        media_type = guess_type(str(full_path))[0] or "application/octet-stream"
        if _is_active_media_type(media_type):
            raise HTTPException(status_code=404, detail="Not Found")
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = self._cache_control
        response.headers["Content-Security-Policy"] = UPLOAD_CSP
        return response


def _body_limit_rules() -> list[tuple[str, int]]:
    def upload(max_file_bytes: int) -> int:
        return max_file_bytes + MULTIPART_SLACK_BYTES

    article_max = max(article_store.MAX_UPLOAD_BYTES, article_store.MAX_ATTACHMENT_BYTES)
    return [
        ("/api/settings/files/upload", upload(file_manager_svc.MAX_UPLOAD_BYTES)),
        ("/api/guides/minecraft/files/upload", upload(minecraft_files_svc.MAX_UPLOAD_BYTES)),
        ("/api/articles/assets", upload(article_max)),
        ("/api/articles/math/recognize", upload(MATH_RECOGNIZE_MAX_BYTES)),
        ("/api/profile/me/avatar", upload(avatar_store.MAX_UPLOAD_BYTES)),
        ("/api/members/{member_id}/avatar", upload(avatar_store.MAX_UPLOAD_BYTES)),
        ("/api/guides/tarkov/raid-prep/recognize", upload(TARKOV_OCR_MAX_BYTES)),
        ("/api/guides/tarkov/key-owns/recognize", upload(TARKOV_OCR_MAX_BYTES)),
        ("/api/csp-report", 64 * 1024),
        ("/api/client-errors", 64 * 1024),
        ("/api/client-rum", 256 * 1024),
    ]


BODY_LIMIT_RULES = _body_limit_rules()


def _ping_database() -> bool:
    """SELECT 1，1 秒内复用结果，避免探针打满连接池。"""
    global _health_db_ok, _health_db_at
    if not database_is_configured():
        return False
    now = time.monotonic()
    if _health_db_ok is not None and now - _health_db_at < _HEALTH_DB_TTL_SEC:
        return _health_db_ok
    from sqlalchemy import text

    ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    _health_db_ok = ok
    _health_db_at = now
    return ok


def _ensure_upload_root() -> Path:
    path = get_settings().upload_dir_path
    (path / "avatars").mkdir(parents=True, exist_ok=True)
    (path / "articles").mkdir(parents=True, exist_ok=True)
    return path


def _cleanup_legacy_after_hydrate(install: Path) -> None:
    leftover = cleanup_legacy_install_tree(install)
    if leftover:
        logger.info("startup leftover cleanup: %s", ",".join(leftover))


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_config_dir()
    from app.services.config_import import import_legacy_dotenv

    import_legacy_dotenv()
    migrate_runtime_layout(resolve_install_dir())
    pin_library_cache_env()
    from app.core.config_sync import sync_site_config

    sync_site_config()
    get_settings.cache_clear()
    cfg = get_settings()
    # 布局迁移之后再解析密钥；DATA_DIR 不可写时在这里启动失败，而不是拖到第一次登录
    _ = cfg.SECRET_KEY
    logger.info(
        "startup begin version=%s env=%s install_dir=%s",
        cfg.APP_VERSION,
        cfg.APP_ENV,
        (cfg.APP_INSTALL_DIR or "").strip() or "(unset)",
    )

    if not database_is_configured():
        logger.info("startup: database not configured; setup wizard required")
        logger.info("startup step 2/9: ensure upload root (%s)", cfg.UPLOAD_DIR)
        upload_path = _ensure_upload_root()
        hydrate_legacy_runtime(
            dest_data=cfg.data_dir_path,
            install=resolve_install_dir(configured=cfg.APP_INSTALL_DIR),
        )
        _cleanup_legacy_after_hydrate(resolve_install_dir(configured=cfg.APP_INSTALL_DIR))
        from app.services.setup import ensure_setup_token

        try:
            ensure_setup_token()
        except OSError:
            logger.warning("setup token could not be written", exc_info=True)
        from app.services.tarkov.goon_tracker_hub import hub as goon_hub

        # 向导完成后在工作线程里补跑启动步骤，三狗推送需要先绑定事件循环
        goon_hub.bind_loop(asyncio.get_running_loop())
        logger.info(
            "startup waiting for setup version=%s upload_root=%s",
            cfg.APP_VERSION,
            upload_path,
        )
        yield
        logger.info("shutdown begin")
        _shutdown_background()
        logger.info("shutdown complete")
        return

    logger.info("startup step 1/9: alembic migrate")
    try:
        run_migrations()
    except Exception:
        logger.exception(
            "startup migrate failed — process will exit; "
            "fix the migration, then git pull and run scripts/linux/install.sh + restart.sh"
        )
        raise

    logger.info("startup step 2/9: ensure upload root (%s)", cfg.UPLOAD_DIR)
    upload_path = _ensure_upload_root()
    hydrate_legacy_runtime(
        dest_data=cfg.data_dir_path,
        install=resolve_install_dir(configured=cfg.APP_INSTALL_DIR),
    )
    _cleanup_legacy_after_hydrate(resolve_install_dir(configured=cfg.APP_INSTALL_DIR))
    logger.info("startup step 2/9 done: upload_root=%s data_root=%s", upload_path, cfg.data_dir_path)

    run_post_database_startup(scheduler, run_steam_once=True, enforce_security_checks=True)

    logger.info(
        "startup complete version=%s scheduler_running=%s static_dir=%s",
        cfg.APP_VERSION,
        scheduler.running,
        (cfg.STATIC_DIR or "").strip() or "(unset)",
    )
    from app.services.tarkov.goon_tracker_hub import hub as goon_hub

    goon_hub.bind_loop(asyncio.get_running_loop())
    start_background_services()
    yield

    logger.info("shutdown begin")
    _shutdown_background()
    logger.info("shutdown complete")


def _shutdown_background() -> None:
    from app.services.tarkov import goon_tracker as goon_tracker_svc

    goon_tracker_svc.stop_poller()
    try:
        from app.services.tarkov.workbench_image_pw import shutdown_patchright

        shutdown_patchright()
    except Exception:
        logger.warning("shutdown image-gen browser failed", exc_info=True)
    close_http_client()
    if scheduler.running:
        logger.info("shutdown: stopping scheduler")
        scheduler.shutdown(wait=False)


settings = get_settings()
_disable_docs = settings.is_production
app = FastAPI(
    title="战鸽数据",
    description="Zhange Stats · Steam 游玩统计与圈子成员管理",
    lifespan=lifespan,
    docs_url=None if _disable_docs else "/docs",
    redoc_url=None if _disable_docs else "/redoc",
    openapi_url=None if _disable_docs else "/openapi.json",
)

_cors_origins = settings.cors_origin_list
_cors_kwargs: dict = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if _cors_origins:
    _cors_kwargs["allow_origins"] = _cors_origins
else:
    # 本地 Vite（任意端口）+ Tauri 2 壳源；生产同域默认不放行 localhost 正则
    _cors_regex = resolve_cors_origin_regex(
        settings.CORS_ORIGIN_REGEX,
        production=settings.is_production,
    )
    if _cors_regex:
        _cors_kwargs["allow_origin_regex"] = _cors_regex

# 最后 add = 最外层。外→内：SecurityHeaders → RequestLog → GZip → CORS → SetupRequired → BodyLimit。
# RequestLog 在外才记得到 503 向导拦截与预检；CORS 在 SetupRequired 外，503 也带 CORS 头。
# GZip：无反代时也能压 JSON；nginx 见到 Content-Encoding 通常不再压。
app.add_middleware(BodyLimitMiddleware, rules=BODY_LIMIT_RULES)
app.add_middleware(SetupRequiredMiddleware)
app.add_middleware(CORSMiddleware, **_cors_kwargs)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(RequestLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

api = APIRouter(prefix="/api")
api.include_router(setup.router)
api.include_router(auth.router)
api.include_router(members.router)
api.include_router(profile.router)
api.include_router(settings_api.router)
api.include_router(files_api.router)
api.include_router(app_update_api.router)
api.include_router(runtime_logs_api.router)
api.include_router(runtime_health_api.router)
api.include_router(jobs.router)
api.include_router(steam.router)
api.include_router(skland.router)
api.include_router(taygedo.router)
api.include_router(exilium.router)
api.include_router(kujiequ.router)
api.include_router(mihoyo.router)
api.include_router(guides.router)
api.include_router(articles.router)
api.include_router(client_errors_api.router)
api.include_router(rum_api.router)
app.include_router(api)

# 只挂载头像/文章子目录，避免 DATA_DIR / 上传根目录下的私密文件被公开访问
_upload_root = settings.upload_dir_path
# 头像 URL 带 ?v= 版本；文章附件是 UUID 路径，可缓存更久
app.mount(
    "/uploads/avatars",
    UploadStaticFiles(_upload_root / "avatars", cache_control="public, max-age=86400"),
    name="uploads_avatars",
)
app.mount(
    "/uploads/articles",
    UploadStaticFiles(_upload_root / "articles", cache_control="public, max-age=604800"),
    name="uploads_articles",
)


@app.get("/robots.txt")
def robots_txt() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


@app.get("/health")
def health():
    """存活/就绪探测；数据库不通时 HTTP 503（编排器可摘流量）。未选库时 200 + setup。"""
    from fastapi.responses import JSONResponse

    if not database_is_configured():
        return JSONResponse(
            content={
                "status": "setup",
                "version": settings.APP_VERSION,
                "database": "unconfigured",
                "scheduler": "stopped",
            },
            status_code=200,
        )

    db_ok = _ping_database()
    sched_ok = bool(scheduler.running) if scheduler else False
    status = "ok" if db_ok else "degraded"
    body = {
        "status": status,
        "version": settings.APP_VERSION,
        "database": "ok" if db_ok else "error",
        "scheduler": "ok" if sched_ok else "stopped",
    }
    return JSONResponse(content=body, status_code=200 if db_ok else 503)


_static_dir = (
    resolve_runtime_path(settings.STATIC_DIR, configured_install=settings.APP_INSTALL_DIR)
    if settings.STATIC_DIR
    else None
)

if _static_dir and _static_dir.is_dir():
    assets_dir = _static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # API / uploads / health / docs 已由上方路由处理；其余走前端 SPA
        if full_path.startswith(
            ("api/", "uploads/", "health", "docs", "redoc", "openapi.json", "robots.txt")
        ):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (_static_dir / full_path).resolve()
        try:
            candidate.relative_to(_static_dir)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not Found") from exc
        if full_path and candidate.is_file():
            resp = FileResponse(candidate)
            if full_path.startswith("assets/"):
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        index = _static_dir / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Frontend not found")
        resp = FileResponse(index)
        resp.headers["Cache-Control"] = "no-cache"
        return resp
