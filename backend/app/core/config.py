from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.secret import DEFAULT_SECRET_KEY, ensure_secret_key


def _read_version_file() -> str:
    for candidate in (
        Path("/app/VERSION"),
        Path(__file__).resolve().parents[3] / "VERSION",
        Path.cwd() / "VERSION",
        Path.cwd().parent / "VERSION",
    ):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "mysql+pymysql://root:password@127.0.0.1:3306/zhange_stats_dev"
    # 留空或保持占位值时，首次启动会自动生成并写入 DATA_DIR/.secret_key
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    # 默认 24 小时；管理端可在 system_configs 再调（最长 1 年）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    # 留空：本地 Vite 用 allow_origin_regex；生产同域一般无需 CORS
    CORS_ORIGINS: str = ""
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "123456"
    ADMIN_DISPLAY_NAME: str = "管理员"
    ADMIN_EMAIL: str = "admin@localhost"
    # 仅当显式开启时，启动才把种子管理员密码重置为 ADMIN_PASSWORD
    RESET_ADMIN_PASSWORD: bool = False
    # development | production（production 下弱口令默认拒绝启动）
    APP_ENV: str = "development"
    # 弱口令时拒绝启动；未显式设置时：production 默认拒绝，development 仅 WARNING
    REJECT_WEAK_ADMIN_PASSWORD: bool | None = None
    # 仅当显式开启时，启动才把其它管理员降级为普通用户
    ENFORCE_SINGLE_ADMIN: bool = False

    # 可选 Redis（限流跨实例）；留空则进程内滑动窗口
    REDIS_URL: str = ""

    STEAM_API_KEY: str = ""
    STEAM_POLL_INTERVAL_MINUTES: int = 3
    STEAM_POLL_ENABLED: bool = True
    # 可选手动覆盖 OAuth 回调基址；留空则从请求 Host / Origin / X-Forwarded-* 推断
    PUBLIC_BACKEND_URL: str = ""
    PUBLIC_FRONTEND_URL: str = ""

    # QQ 互联（个人中心绑定；审核中仅调试 QQ 号可用）
    QQ_APP_ID: str = ""
    QQ_APP_KEY: str = ""

    # NapCat OneBot HTTP（群列表 / 群成员；库配置优先）
    NAPCAT_BASE_URL: str = ""
    NAPCAT_TOKEN: str = ""

    # 森空岛每日签到（明日方舟 / 终末地）— 默认北京时间 00:01
    SKLAND_CHECKIN_ENABLED: bool = True
    SKLAND_CHECKIN_HOUR: int = 0
    SKLAND_CHECKIN_MINUTE: int = 1
    # 明日方舟盒子练度日更（默认 00:20，可与签到错开）
    ARKNIGHTS_BOX_SYNC_ENABLED: bool = True
    ARKNIGHTS_BOX_SYNC_HOUR: int = 0
    ARKNIGHTS_BOX_SYNC_MINUTE: int = 20
    # 明日方舟开源图鉴（ArknightsGameResource character_table，默认 04:00）
    ARKNIGHTS_CATALOG_SYNC_ENABLED: bool = True
    ARKNIGHTS_CATALOG_SYNC_HOUR: int = 4
    ARKNIGHTS_CATALOG_SYNC_MINUTE: int = 0
    # 塔吉多每日签到（异环）
    TAYGEDO_CHECKIN_ENABLED: bool = True
    TAYGEDO_CHECKIN_HOUR: int = 0
    TAYGEDO_CHECKIN_MINUTE: int = 1
    # 追放社区每日签到
    EXILIUM_CHECKIN_ENABLED: bool = True
    EXILIUM_CHECKIN_HOUR: int = 0
    EXILIUM_CHECKIN_MINUTE: int = 1
    # 库街区每日签到（社区 + 鸣潮/战双）
    KUJIEQU_CHECKIN_ENABLED: bool = True
    KUJIEQU_CHECKIN_HOUR: int = 0
    KUJIEQU_CHECKIN_MINUTE: int = 1
    # 运行时数据目录（密钥等；勿挂到公开静态路径）
    DATA_DIR: str = "data"
    # 头像等本地上传目录（相对 backend 工作目录或绝对路径）
    UPLOAD_DIR: str = "uploads"

    # 邮件（不配置则默认拒绝发码；本地可开 ALLOW_EMAIL_CODE_LOG 把验证码打到日志）
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_SSL: bool = True
    SMTP_STARTTLS: bool = False
    EMAIL_CODE_EXPIRE_MINUTES: int = 15
    # 仅本地调试：SMTP 未配时允许把完整验证码写入日志/stdout
    ALLOW_EMAIL_CODE_LOG: bool = False

    # 部署 / 在线更新（Docker 管理端手动更新始终可用）
    APP_VERSION: str = _read_version_file()
    STATIC_DIR: str = ""
    UPDATE_REPO: str = "739790797/zhange-stats"
    UPDATE_IMAGE: str = "ghcr.io/739790797/zhange-stats"
    UPDATE_COMPOSE_FILE: str = "/deploy/compose.yml"
    UPDATE_COMPOSE_SERVICE: str = "app"
    UPDATE_COMPOSE_PROJECT: str = "zhange-stats"
    UPDATE_GITHUB_TOKEN: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return (self.APP_ENV or "").strip().lower() in ("production", "prod")

    @property
    def reject_weak_admin_password(self) -> bool:
        """显式 REJECT_* 优先；否则 production 默认拒绝。"""
        if self.REJECT_WEAK_ADMIN_PASSWORD is not None:
            return bool(self.REJECT_WEAK_ADMIN_PASSWORD)
        return self.is_production


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.SECRET_KEY = ensure_secret_key(
        settings.SECRET_KEY,
        data_dir=settings.DATA_DIR,
        upload_dir=settings.UPLOAD_DIR,
    )
    return settings
