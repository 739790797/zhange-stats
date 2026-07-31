from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "mysql+pymysql://root:password@127.0.0.1:3306/zhange_stats"
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    CORS_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_DISPLAY_NAME: str = "管理员"
    ADMIN_EMAIL: str = "admin@localhost"

    STEAM_API_KEY: str = ""
    STEAM_POLL_INTERVAL_MINUTES: int = 3
    STEAM_POLL_ENABLED: bool = True
    # Steam OpenID 回调地址（必须是 Steam 能访问的公网/局域网 URL）
    PUBLIC_BACKEND_URL: str = "http://127.0.0.1:8000"
    PUBLIC_FRONTEND_URL: str = "http://127.0.0.1:5173"
    # 头像等本地上传目录（相对 backend 工作目录或绝对路径）
    UPLOAD_DIR: str = "uploads"

    CS2_MATCH_POLL_ENABLED: bool = False
    CS2_MATCH_POLL_INTERVAL_MINUTES: int = 15
    CS2_MATCH_MAX_PER_MEMBER: int = 20
    CS2_GC_BOILER_PATH: str = ""
    CS2_GC_FETCH_SCRIPT: str = ""
    CS2_GC_TIMEOUT_SECONDS: int = 90
    CS2_GC_ENRICH_LIMIT: int = 10

    # 邮件（不配置则验证码打印到服务端日志）
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_SSL: bool = True
    SMTP_STARTTLS: bool = False
    EMAIL_CODE_EXPIRE_MINUTES: int = 15

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]



@lru_cache
def get_settings() -> Settings:
    return Settings()
