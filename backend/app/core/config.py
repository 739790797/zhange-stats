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
