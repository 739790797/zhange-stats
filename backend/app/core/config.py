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

    DATABASE_URL: str = "mysql+pymysql://root:password@127.0.0.1:3306/zhange_stats"
    # 留空或保持占位值时，首次启动会自动生成并写入 DATA_DIR/.secret_key
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    # 默认 24 小时；生产可按需再缩短
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    CORS_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_DISPLAY_NAME: str = "管理员"
    ADMIN_EMAIL: str = "admin@localhost"
    # 仅当显式开启时，启动才把种子管理员密码重置为 ADMIN_PASSWORD
    RESET_ADMIN_PASSWORD: bool = False
    # 仅当显式开启时，启动才把其它管理员降级为普通用户
    ENFORCE_SINGLE_ADMIN: bool = False

    STEAM_API_KEY: str = ""
    STEAM_POLL_INTERVAL_MINUTES: int = 3
    STEAM_POLL_ENABLED: bool = True
    # Steam OpenID 回调地址（必须是 Steam 能访问的公网/局域网 URL）
    PUBLIC_BACKEND_URL: str = "http://127.0.0.1:8000"
    PUBLIC_FRONTEND_URL: str = "http://127.0.0.1:5173"
    # 运行时数据目录（密钥等；勿挂到公开静态路径）
    DATA_DIR: str = "data"
    # 头像等本地上传目录（相对 backend 工作目录或绝对路径）
    UPLOAD_DIR: str = "uploads"

    # 邮件（不配置则验证码打印到服务端日志）
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_SSL: bool = True
    SMTP_STARTTLS: bool = False
    EMAIL_CODE_EXPIRE_MINUTES: int = 15

    # 部署 / 在线更新（可选；仅 Docker 且启用管理端更新时需要）
    APP_VERSION: str = _read_version_file()
    STATIC_DIR: str = ""
    UPDATE_ENABLED: bool = False
    UPDATE_REPO: str = "739790797/zhange-stats"
    UPDATE_IMAGE: str = "ghcr.io/739790797/zhange-stats"
    UPDATE_COMPOSE_FILE: str = "/deploy/compose.yml"
    UPDATE_COMPOSE_SERVICE: str = "app"
    UPDATE_COMPOSE_PROJECT: str = "zhange-stats"
    UPDATE_GITHUB_TOKEN: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.SECRET_KEY = ensure_secret_key(
        settings.SECRET_KEY,
        data_dir=settings.DATA_DIR,
        upload_dir=settings.UPLOAD_DIR,
    )
    return settings
